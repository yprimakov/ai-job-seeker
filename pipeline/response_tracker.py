"""
Response Tracker
================
Polls leoprime.dev@gmail.com for replies from applied companies and
automatically updates application_tracker.csv with the response type
and date received.

Matching strategy:
  1. Extract sender domain from the From header
  2. Normalize it (strip mail./careers./recruiting. subdomains, strip TLD)
  3. Fuzzy-match the normalized domain against company names in tracker
  4. Classify the response using Claude Haiku (Interview/Rejection/Phone Screen/etc.)

ATS notification domains are handled specially:
  - greenhouse.io, lever.co, jobvite.com, workday.com -> extract company from Subject
  - linkedin.com -> extract company from Subject

Usage:
    # Check for new responses (dry-run)
    python pipeline/response_tracker.py --dry-run

    # Apply updates to tracker
    python pipeline/response_tracker.py

    # One-time Gmail OAuth setup
    python pipeline/response_tracker.py --setup

    # Install as part of daily Task Scheduler job
    python pipeline/response_tracker.py --install
"""

import argparse
import csv
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

JOBS_DIR = Path(__file__).parent.parent / "jobs"
TRACKER_FILE = JOBS_DIR / "application_tracker.csv"
TOKEN_FILE = Path(__file__).parent / "gmail_token.json"
CREDENTIALS_FILE = Path(__file__).parent / "gmail_credentials.json"
TRACKER_SCRIPT = Path(__file__).parent / "tracker.py"

TRACKER_HEADERS = [
    "Date Applied", "Company", "Job Title", "LinkedIn URL", "Work Mode",
    "Salary Range", "Easy Apply", "Application Status", "Notes",
    "Tailored Resume File", "Follow Up Date",
    "Date Response Received", "Response Type",
]

# ATS notification domains: map to None (means extract company from Subject)
ATS_DOMAINS = {
    "greenhouse.io", "greenhouse-mail.io",
    "lever.co", "hire.lever.co",
    "jobvite.com",
    "workday.com", "myworkdayjobs.com",
    "smartrecruiters.com",
    "icims.com",
    "ashbyhq.com",
    "linkedin.com",
}

RESPONSE_TYPES = [
    "Phone Screen",
    "Interview",
    "Take-Home Assessment",
    "Offer",
    "Rejected",
    "Recruiter Outreach",
    "Other",
]


# ── Gmail API ──────────────────────────────────────────────────────────────────

def _get_gmail_service():
    try:
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from google.auth.transport.requests import Request
        from googleapiclient.discovery import build
    except ImportError:
        sys.exit(
            "Missing Gmail API libraries. Run:\n"
            "  pip install google-auth-oauthlib google-auth-httplib2 google-api-python-client"
        )

    SCOPES = ["https://www.googleapis.com/auth/gmail.readonly",
              "https://www.googleapis.com/auth/gmail.compose"]
    creds = None

    if TOKEN_FILE.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            from google.auth.transport.requests import Request
            creds.refresh(Request())
        else:
            if not CREDENTIALS_FILE.exists():
                sys.exit(
                    f"Gmail credentials not found at {CREDENTIALS_FILE}.\n"
                    "Download OAuth 2.0 credentials from Google Cloud Console and save there."
                )
            from google_auth_oauthlib.flow import InstalledAppFlow
            flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS_FILE), SCOPES)
            creds = flow.run_local_server(port=0)
        TOKEN_FILE.write_text(creds.to_json())

    from googleapiclient.discovery import build
    return build("gmail", "v1", credentials=creds)


def _fetch_recent_emails(service, days_back: int = 30) -> list[dict]:
    """Fetch emails received in the last N days from leoprime.dev@gmail.com."""
    after = (datetime.now() - timedelta(days=days_back)).strftime("%Y/%m/%d")
    query = f"after:{after} -from:me -category:promotions -category:social"

    messages = []
    page_token = None
    while True:
        kwargs = {"userId": "me", "q": query, "maxResults": 100}
        if page_token:
            kwargs["pageToken"] = page_token
        result = service.users().messages().list(**kwargs).execute()
        messages.extend(result.get("messages", []))
        page_token = result.get("nextPageToken")
        if not page_token:
            break

    emails = []
    for msg in messages:
        full = service.users().messages().get(
            userId="me", id=msg["id"], format="metadata",
            metadataHeaders=["From", "Subject", "Date"]
        ).execute()
        headers = {h["name"]: h["value"] for h in full["payload"]["headers"]}
        snippet = full.get("snippet", "")
        emails.append({
            "id": msg["id"],
            "from": headers.get("From", ""),
            "subject": headers.get("Subject", ""),
            "date": headers.get("Date", ""),
            "snippet": snippet,
        })
    return emails


# ── Company matching ───────────────────────────────────────────────────────────

def _normalize_domain(email_from: str) -> tuple[str, str]:
    """
    Extract and normalize sender domain from a From header.
    Returns (raw_domain, normalized_name).
    e.g. 'careers@anthropic.com' -> ('anthropic.com', 'anthropic')
    """
    m = re.search(r"@([\w.\-]+)", email_from)
    if not m:
        return "", ""
    domain = m.group(1).lower()
    # Strip known subdomains
    for prefix in ("mail.", "careers.", "recruiting.", "jobs.", "hr.", "talent.",
                   "noreply.", "no-reply.", "notifications.", "email."):
        if domain.startswith(prefix):
            domain = domain[len(prefix):]
    # Strip TLD (.com, .io, .co, .org, etc.)
    name = re.sub(r"\.(com|io|co|org|net|ai|dev|app|us|uk|ca|de|fr)$", "", domain)
    return domain, name


def _normalize_company(company: str) -> str:
    """Normalize company name for matching: lowercase, strip legal suffixes, collapse spaces."""
    name = company.lower()
    for suffix in (" inc", " llc", " ltd", " corp", " corporation", " co", " group",
                   " technologies", " technology", " solutions", " systems", " labs",
                   " lab", " ai", " hq"):
        name = name.replace(suffix, "")
    return re.sub(r"[^a-z0-9]", "", name).strip()


def _match_email_to_company(email: dict, tracker_companies: list[str]) -> str | None:
    """Return the matching company name from the tracker, or None."""
    raw_domain, domain_name = _normalize_domain(email["from"])

    # ATS notification: extract company from subject
    if raw_domain in ATS_DOMAINS or any(raw_domain.endswith("." + d) for d in ATS_DOMAINS):
        subject = email["subject"].lower()
        for company in tracker_companies:
            slug = _normalize_company(company)
            if slug and slug in re.sub(r"[^a-z0-9]", "", subject):
                return company
        return None

    # Direct company email: match domain name against company names
    if not domain_name:
        return None

    norm_domain = _normalize_company(domain_name)
    best_company, best_len = None, 0
    for company in tracker_companies:
        norm_co = _normalize_company(company)
        if not norm_co:
            continue
        # Check if either contains the other (handles "D24 Search" vs "d24search")
        if norm_co in norm_domain or norm_domain in norm_co:
            if len(norm_co) > best_len:
                best_len = len(norm_co)
                best_company = company
    return best_company


# ── Response classification ────────────────────────────────────────────────────

def _classify_responses(emails_with_companies: list[tuple[dict, str]]) -> list[dict]:
    """
    Use Claude Haiku to classify email snippets as a known response type.
    Batches all emails in one API call.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key or not emails_with_companies:
        return []

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)

        items = "\n".join(
            f'[{i}] Company: {company} | Subject: {e["subject"]} | Snippet: {e["snippet"][:200]}'
            for i, (e, company) in enumerate(emails_with_companies)
        )

        prompt = f"""Classify each job application email response into exactly one category:
Phone Screen, Interview, Take-Home Assessment, Offer, Rejected, Recruiter Outreach, Other

Items:
{items}

Return a JSON array of objects with keys "index" and "type". Example:
[{{"index": 0, "type": "Rejected"}}, {{"index": 1, "type": "Phone Screen"}}]

Return only valid JSON, no explanation."""

        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=400,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = response.content[0].text.strip()
        raw = re.sub(r"^```json\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
        results = json.loads(raw)

        classified = []
        for item in results:
            idx = item.get("index", -1)
            if 0 <= idx < len(emails_with_companies):
                email, company = emails_with_companies[idx]
                classified.append({
                    "email": email,
                    "company": company,
                    "response_type": item.get("type", "Other"),
                })
        return classified

    except Exception as e:
        print(f"[warn] Classification failed: {e}")
        return [
            {"email": e, "company": c, "response_type": "Other"}
            for e, c in emails_with_companies
        ]


# ── Tracker update ─────────────────────────────────────────────────────────────

def _parse_email_date(date_str: str) -> str:
    """Parse RFC 2822 email date to YYYY-MM-DD, or return today."""
    for fmt in (
        "%a, %d %b %Y %H:%M:%S %z",
        "%d %b %Y %H:%M:%S %z",
        "%a, %d %b %Y %H:%M:%S %Z",
    ):
        try:
            return datetime.strptime(date_str[:31].strip(), fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return datetime.now().strftime("%Y-%m-%d")


def _load_tracker() -> list[dict]:
    if not TRACKER_FILE.exists():
        return []
    with open(TRACKER_FILE, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _save_tracker(rows: list[dict]) -> None:
    with open(TRACKER_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=TRACKER_HEADERS, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            # Fill in missing keys with empty string
            writer.writerow({h: row.get(h, "") for h in TRACKER_HEADERS})


# ── Main poll loop ─────────────────────────────────────────────────────────────

def poll_responses(dry_run: bool = False, days_back: int = 30) -> None:
    rows = _load_tracker()
    if not rows:
        print("No applications in tracker.")
        return

    # Only look at applications without a response yet
    pending_companies = [
        r.get("Company", "") for r in rows
        if not r.get("Date Response Received", "").strip()
        and r.get("Company", "").strip()
    ]
    if not pending_companies:
        print("All applications already have a recorded response.")
        return

    print(f"Polling Gmail for responses to {len(pending_companies)} pending applications...")

    service = _get_gmail_service()
    emails = _fetch_recent_emails(service, days_back=days_back)
    print(f"  Fetched {len(emails)} emails from last {days_back} days.")

    # Match emails to companies
    matched = []
    seen_companies: set[str] = set()
    for email in emails:
        company = _match_email_to_company(email, pending_companies)
        if company and company not in seen_companies:
            matched.append((email, company))
            seen_companies.add(company)

    if not matched:
        print("  No matches found against pending applications.")
        return

    print(f"  Matched {len(matched)} email(s) to pending applications.")
    classified = _classify_responses(matched)

    for item in classified:
        company = item["company"]
        response_type = item["response_type"]
        date_received = _parse_email_date(item["email"]["date"])
        subject = item["email"]["subject"]

        print(f"\n  [{response_type}] {company}")
        print(f"    Subject: {subject}")
        print(f"    Date: {date_received}")

        if dry_run:
            continue

        # Find matching tracker row(s) and update
        for row in rows:
            if (row.get("Company", "").lower() == company.lower()
                    and not row.get("Date Response Received", "").strip()):
                row["Date Response Received"] = date_received
                row["Response Type"] = response_type
                row["Application Status"] = response_type
                break

    if not dry_run:
        _save_tracker(rows)
        print(f"\n[ok] Updated tracker with {len(classified)} response(s).")
    else:
        print(f"\n[dry-run] {len(classified)} update(s) would be applied.")


# ── CLI ────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Poll Gmail for job application responses")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show matches without updating tracker")
    parser.add_argument("--days-back", type=int, default=30,
                        help="How many days of email to scan (default: 30)")
    parser.add_argument("--setup", action="store_true",
                        help="Run one-time Gmail OAuth setup")
    parser.add_argument("--install", action="store_true",
                        help="Add response polling to the daily Task Scheduler job")
    args = parser.parse_args()

    if args.setup:
        print("Starting Gmail OAuth setup...")
        _get_gmail_service()
        print(f"[ok] Token saved to {TOKEN_FILE}")
        return

    if args.install:
        python = sys.executable
        script = Path(__file__).resolve()
        task_name = "JobSeekerResponsePoll"
        cmd = [
            "schtasks.exe", "/Create", "/F",
            "/TN", task_name,
            "/TR", f'"{python}" "{script}"',
            "/SC", "DAILY",
            "/ST", "09:05",
            "/RL", "HIGHEST",
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            print(f"[ok] Task '{task_name}' scheduled daily at 09:05.")
        else:
            print(f"[error] {result.stderr}")
        return

    poll_responses(dry_run=args.dry_run, days_back=args.days_back)


if __name__ == "__main__":
    main()
