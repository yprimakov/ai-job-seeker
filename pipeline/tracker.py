"""
Job Application Tracker & Q&A Knowledge Base
=============================================
Manages two CSV files:
  - application_tracker.csv  — logs every job application
  - application_qa.csv       — stores questions encountered during applications + answers

Usage:
    # Log a new application
    python tracker.py log --company "People In AI" --title "Principal AI Engineer" \\
        --url "https://linkedin.com/jobs/view/..." --mode Remote --salary "$275K-$325K" \\
        --easy-apply --resume-file "output/PeopleInAI_Principal_20260315.md"

    # Record an unknown question encountered during an application
    python tracker.py question --q "What is your expected salary?" --context "People In AI Easy Apply"

    # Answer a recorded question
    python tracker.py answer --id Q001 --answer "My target is $200K-$250K base"

    # Show all pending (unanswered) questions
    python tracker.py pending

    # Show all applications
    python tracker.py list

    # Look up if a question has been answered before (fuzzy search)
    python tracker.py lookup --q "salary expectations"
"""

import argparse
import csv
import os
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path

import anthropic
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

JOBS_DIR = Path(__file__).parent.parent / "jobs"
JOBS_DIR.mkdir(parents=True, exist_ok=True)
TRACKER_FILE = JOBS_DIR / "application_tracker.csv"
QA_FILE = JOBS_DIR / "application_qa.csv"
APPS_DIR = Path(__file__).parent.parent / "applications"

TRACKER_HEADERS = [
    "Date Applied", "Company", "Job Title", "LinkedIn URL", "Work Mode",
    "Salary Range", "Easy Apply", "Application Status", "Notes",
    "Tailored Resume File", "Follow Up Date",
    "Date Response Received", "Response Type",
]
QA_HEADERS = [
    "Question ID", "Question", "Context (where it appeared)",
    "Answer", "Date Answered", "Notes",
]


# ── Application folder resolver ────────────────────────────────────────────────
def find_resume_for_application(company: str, title: str) -> str:
    """
    Search applications/ for a folder matching company+title and return the
    relative path to resume.pdf, or empty string if not found.
    Folder naming convention: YYYYMMDD_Company_Title (underscores, truncated).
    """
    if not APPS_DIR.exists():
        return ""
    company_slug = re.sub(r"[^a-z0-9]+", "_", company.lower()).strip("_")
    title_slug   = re.sub(r"[^a-z0-9]+", "_", title.lower()).strip("_")
    # Score each folder by how many slug tokens appear in its name
    best_path, best_score = "", 0
    for folder in sorted(APPS_DIR.iterdir(), reverse=True):
        if not folder.is_dir():
            continue
        name = folder.name.lower()
        company_hits = sum(1 for tok in company_slug.split("_") if tok and tok in name)
        title_hits   = sum(1 for tok in title_slug.split("_")   if tok and tok in name)
        score = company_hits + title_hits
        if score > best_score:
            pdf = folder / "resume.pdf"
            if pdf.exists():
                best_score = score
                best_path = str(pdf.relative_to(APPS_DIR.parent))
    return best_path if best_score >= 2 else ""


# ── Salary normalizer ──────────────────────────────────────────────────────────
def normalize_salary(raw: str) -> str:
    """Normalize salary to '$NNNk-$MMMk' or '$NNNk' format. Returns raw if unparseable."""
    if not raw:
        return raw
    # Extract all dollar amounts (handles $180K, $180,000, 180000, etc.)
    amounts = re.findall(r"\$?\s*([\d,]+)\s*[kK]?", raw.replace(",", ""))
    values = []
    for tok, m in zip(re.findall(r"\$?\s*[\d,]+\s*[kK]?", raw), amounts):
        n = int(m.replace(",", ""))
        if "k" in tok.lower() or n < 10000:
            values.append(n * 1000 if n < 1000 else n)
        else:
            values.append(n)
    if not values:
        return raw
    values = sorted(set(values))
    def fmt(v):
        return f"${v // 1000}k"
    if len(values) == 1:
        return fmt(values[0])
    return f"{fmt(values[0])}-{fmt(values[-1])}"


# ── CSV helpers ────────────────────────────────────────────────────────────────
def read_csv(path: Path, headers: list[str]) -> list[dict]:
    if not path.exists():
        return []
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return list(reader)


def write_csv(path: Path, headers: list[str], rows: list[dict]) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        writer.writerows(rows)


def append_csv(path: Path, headers: list[str], row: dict) -> None:
    file_exists = path.exists() and path.stat().st_size > 0
    with open(path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        if not file_exists:
            writer.writeheader()
        writer.writerow(row)


# ── Next Q ID ──────────────────────────────────────────────────────────────────
def next_question_id(rows: list[dict]) -> str:
    if not rows:
        return "Q001"
    ids = [r.get("Question ID", "") for r in rows if r.get("Question ID", "").startswith("Q")]
    nums = [int(i[1:]) for i in ids if i[1:].isdigit()]
    return f"Q{(max(nums) + 1):03d}" if nums else "Q001"


# ── Semantic lookup with Claude ────────────────────────────────────────────────
def semantic_lookup(query: str, qa_rows: list[dict]) -> list[dict]:
    """Use Claude to find previously answered questions similar to the query."""
    answered = [r for r in qa_rows if r.get("Answer", "").strip()]
    if not answered:
        return []

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        # Fallback: simple substring match
        q_lower = query.lower()
        return [r for r in answered if q_lower in r.get("Question", "").lower()]

    client = anthropic.Anthropic(api_key=api_key)
    qa_text = "\n".join(
        f"[{r['Question ID']}] Q: {r['Question']} | A: {r['Answer']}"
        for r in answered
    )
    prompt = f"""Given this query: "{query}"

Find the most relevant previously answered questions from this list (return their IDs, comma-separated, or "none"):
{qa_text}

Return only the matching Question IDs (e.g., "Q001, Q003") or "none". No explanation."""

    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=100,
        messages=[{"role": "user", "content": prompt}],
    )
    result = response.content[0].text.strip()
    if result.lower() == "none":
        return []
    ids = [i.strip() for i in result.split(",")]
    return [r for r in answered if r.get("Question ID") in ids]


# ── Commands ───────────────────────────────────────────────────────────────────
def cmd_log(args):
    rows = read_csv(TRACKER_FILE, TRACKER_HEADERS)
    # Dedup check
    for existing in rows:
        if (existing.get("Company", "").lower() == args.company.lower() and
                existing.get("Job Title", "").lower() == args.title.lower()):
            print(f"[skip] Already logged: {args.title} @ {args.company}")
            return

    follow_up = args.follow_up or (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")
    row = {
        "Date Applied": datetime.now().strftime("%Y-%m-%d"),
        "Company": args.company,
        "Job Title": args.title,
        "LinkedIn URL": args.url or "",
        "Work Mode": args.mode or "",
        "Salary Range": normalize_salary(args.salary or ""),
        "Easy Apply": "Yes" if args.easy_apply else "No",
        "Application Status": "Applied",
        "Notes": args.notes or "",
        "Tailored Resume File": args.resume_file or find_resume_for_application(args.company, args.title),
        "Follow Up Date": follow_up,
    }
    append_csv(TRACKER_FILE, TRACKER_HEADERS, row)
    resume_note = f" | resume: {row['Tailored Resume File']}" if row["Tailored Resume File"] else ""
    print(f"[ok] Logged application: {args.title} @ {args.company} (follow-up: {follow_up}{resume_note})")


def cmd_question(args):
    rows = read_csv(QA_FILE, QA_HEADERS)

    # Check for similar existing answers first
    similar = semantic_lookup(args.q, rows)
    if similar:
        print("\n[!] Similar questions already answered:")
        for r in similar:
            print(f"  [{r['Question ID']}] {r['Question']}")
            print(f"  -> {r['Answer']}\n")
        cont = input("Still log as new question? (y/N): ").strip().lower()
        if cont != "y":
            return

    qid = next_question_id(rows)
    row = {
        "Question ID": qid,
        "Question": args.q,
        "Context (where it appeared)": args.context or "",
        "Answer": "",
        "Date Answered": "",
        "Notes": "",
    }
    append_csv(QA_FILE, QA_HEADERS, row)
    print(f"[ok] Recorded question {qid}: {args.q}")
    print(f"  Run: python tracker.py answer --id {qid} --answer \"your answer\"")


def cmd_answer(args):
    rows = read_csv(QA_FILE, QA_HEADERS)
    updated = False
    for row in rows:
        if row.get("Question ID") == args.id:
            row["Answer"] = args.answer
            row["Date Answered"] = datetime.now().strftime("%Y-%m-%d")
            row["Notes"] = args.notes or row.get("Notes", "")
            updated = True
            break
    if not updated:
        sys.exit(f"Error: Question ID {args.id} not found.")
    write_csv(QA_FILE, QA_HEADERS, rows)
    print(f"[ok] Answer saved for {args.id}")


def cmd_pending(args):
    rows = read_csv(QA_FILE, QA_HEADERS)
    pending = [r for r in rows if not r.get("Answer", "").strip()]
    if not pending:
        print("No pending questions.")
        return
    print(f"\n{len(pending)} unanswered question(s):\n")
    for r in pending:
        print(f"  [{r['Question ID']}] {r['Question']}")
        print(f"  Context: {r.get('Context (where it appeared)', '')}\n")


def cmd_list(args):
    rows = read_csv(TRACKER_FILE, TRACKER_HEADERS)
    if not rows:
        print("No applications logged yet.")
        return
    print(f"\n{len(rows)} application(s):\n")
    for r in rows:
        status = r.get("Application Status", "")
        ea = "[EA]" if r.get("Easy Apply") == "Yes" else "    "
        print(f"  {ea} [{r.get('Date Applied')}] {r.get('Job Title')} @ {r.get('Company')} — {status}")
        if r.get("Salary Range"):
            print(f"      $ {r.get('Salary Range')} | {r.get('Work Mode')}")


def cmd_lookup(args):
    rows = read_csv(QA_FILE, QA_HEADERS)
    matches = semantic_lookup(args.q, rows)
    if not matches:
        print("No similar answered questions found.")
        return
    print(f"\nFound {len(matches)} match(es):\n")
    for r in matches:
        print(f"  [{r['Question ID']}] Q: {r['Question']}")
        print(f"  Context: {r.get('Context (where it appeared)', '')}")
        print(f"  A: {r['Answer']}\n")


def cmd_update_status(args):
    rows = read_csv(TRACKER_FILE, TRACKER_HEADERS)
    updated = False
    for row in rows:
        if (row.get("Company", "").lower() == args.company.lower() and
                row.get("Job Title", "").lower() == args.title.lower()):
            row["Application Status"] = args.status
            row["Notes"] = args.notes or row.get("Notes", "")
            updated = True
            break
    if not updated:
        sys.exit(f"Error: No matching application found for {args.title} @ {args.company}")
    write_csv(TRACKER_FILE, TRACKER_HEADERS, rows)
    print(f"[ok] Status updated to '{args.status}' for {args.title} @ {args.company}")


def cmd_log_response(args):
    """Record a recruiter/company response against an existing application row."""
    rows = read_csv(TRACKER_FILE, TRACKER_HEADERS)
    updated = False
    for row in rows:
        if (row.get("Company", "").lower() == args.company.lower() and
                row.get("Job Title", "").lower() == args.title.lower()):
            row["Date Response Received"] = args.date or datetime.now().strftime("%Y-%m-%d")
            row["Response Type"] = args.response_type
            row["Application Status"] = args.response_type  # keep status in sync
            row["Notes"] = args.notes or row.get("Notes", "")
            updated = True
            break
    if not updated:
        sys.exit(f"Error: No matching application found for {args.title} @ {args.company}")
    write_csv(TRACKER_FILE, TRACKER_HEADERS, rows)
    print(f"[ok] Response recorded: {args.response_type} from {args.company} on {row['Date Response Received']}")


def cmd_stats(args):
    """Print response rate analytics across all logged applications."""
    rows = read_csv(TRACKER_FILE, TRACKER_HEADERS)
    if not rows:
        print("No applications logged yet.")
        return

    total = len(rows)
    responded = [r for r in rows if r.get("Date Response Received", "").strip()]
    response_rate = len(responded) / total * 100 if total else 0

    print(f"\n=== Application Stats ({total} total) ===\n")
    print(f"  Response rate: {len(responded)}/{total} ({response_rate:.0f}%)\n")

    # By response type
    from collections import Counter
    type_counts = Counter(r.get("Response Type", "").strip() for r in responded if r.get("Response Type", "").strip())
    if type_counts:
        print("  By response type:")
        for rtype, count in type_counts.most_common():
            print(f"    {rtype:<25} {count}")
        print()

    # By Work Mode
    mode_stats: dict[str, dict] = {}
    for r in rows:
        mode = r.get("Work Mode", "Unknown") or "Unknown"
        if mode not in mode_stats:
            mode_stats[mode] = {"total": 0, "responded": 0}
        mode_stats[mode]["total"] += 1
        if r.get("Date Response Received", "").strip():
            mode_stats[mode]["responded"] += 1
    print("  By work mode:")
    for mode, s in sorted(mode_stats.items()):
        rate = s["responded"] / s["total"] * 100 if s["total"] else 0
        print(f"    {mode:<12} {s['responded']}/{s['total']} ({rate:.0f}%)")
    print()

    # By Easy Apply vs direct
    ea_rows = [r for r in rows if r.get("Easy Apply") == "Yes"]
    dir_rows = [r for r in rows if r.get("Easy Apply") != "Yes"]
    ea_resp  = sum(1 for r in ea_rows if r.get("Date Response Received", "").strip())
    dir_resp = sum(1 for r in dir_rows if r.get("Date Response Received", "").strip())
    if ea_rows:
        print(f"  Easy Apply:  {ea_resp}/{len(ea_rows)} responded ({ea_resp/len(ea_rows)*100:.0f}%)")
    if dir_rows:
        print(f"  Direct:      {dir_resp}/{len(dir_rows)} responded ({dir_resp/len(dir_rows)*100:.0f}%)")
    print()

    # Avg days to response
    delays = []
    for r in responded:
        try:
            applied = datetime.strptime(r["Date Applied"], "%Y-%m-%d")
            received = datetime.strptime(r["Date Response Received"], "%Y-%m-%d")
            delays.append((received - applied).days)
        except (ValueError, KeyError):
            pass
    if delays:
        print(f"  Avg days to response: {sum(delays)/len(delays):.1f} days")
        print(f"  Fastest: {min(delays)}d  |  Slowest: {max(delays)}d")
    print()


def cmd_repair(args):
    """Backfill missing Tailored Resume File paths from the applications/ folder."""
    rows = read_csv(TRACKER_FILE, TRACKER_HEADERS)
    fixed, missing = 0, 0
    for row in rows:
        if row.get("Tailored Resume File", "").strip():
            continue
        path = find_resume_for_application(row.get("Company", ""), row.get("Job Title", ""))
        if path:
            row["Tailored Resume File"] = path
            fixed += 1
            print(f"  [fixed] {row['Job Title']} @ {row['Company']} -> {path}")
        else:
            missing += 1
            print(f"  [miss]  {row['Job Title']} @ {row['Company']} — no folder found")
    write_csv(TRACKER_FILE, TRACKER_HEADERS, rows)
    print(f"\n[ok] Repaired {fixed} row(s). {missing} still missing (no applications/ folder match).")


# ── CLI ────────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Job application tracker & Q&A knowledge base")
    sub = parser.add_subparsers(dest="command", required=True)

    # log
    p_log = sub.add_parser("log", help="Log a new job application")
    p_log.add_argument("--company", required=True)
    p_log.add_argument("--title", required=True)
    p_log.add_argument("--url")
    p_log.add_argument("--mode", help="Remote | Hybrid | On-site")
    p_log.add_argument("--salary")
    p_log.add_argument("--easy-apply", action="store_true")
    p_log.add_argument("--notes")
    p_log.add_argument("--resume-file")
    p_log.add_argument("--follow-up")

    # question
    p_q = sub.add_parser("question", help="Record an unanswered question from an application")
    p_q.add_argument("--q", required=True, help="The question text")
    p_q.add_argument("--context", help="Where this question appeared (company/form)")

    # answer
    p_a = sub.add_parser("answer", help="Answer a recorded question")
    p_a.add_argument("--id", required=True, help="Question ID (e.g. Q001)")
    p_a.add_argument("--answer", required=True)
    p_a.add_argument("--notes")

    # pending
    sub.add_parser("pending", help="Show all unanswered questions")

    # list
    sub.add_parser("list", help="Show all logged applications")

    # lookup
    p_lu = sub.add_parser("lookup", help="Find previously answered similar questions")
    p_lu.add_argument("--q", required=True, help="Question to search for")

    # update-status
    p_us = sub.add_parser("update-status", help="Update application status")
    p_us.add_argument("--company", required=True)
    p_us.add_argument("--title", required=True)
    p_us.add_argument("--status", required=True,
                      help="e.g. Applied, Phone Screen, Interview, Offer, Rejected, Withdrawn")
    p_us.add_argument("--notes")

    # repair
    sub.add_parser("repair", help="Backfill missing resume file paths from applications/ folder")

    # log-response
    p_lr = sub.add_parser("log-response", help="Record a company response to an application")
    p_lr.add_argument("--company", required=True)
    p_lr.add_argument("--title", required=True)
    p_lr.add_argument("--response-type", required=True,
                      help="e.g. Phone Screen, Interview, Offer, Rejected, Assessment, Ghosted")
    p_lr.add_argument("--date", help="Date received (YYYY-MM-DD), defaults to today")
    p_lr.add_argument("--notes")

    # stats
    sub.add_parser("stats", help="Show response rate analytics across all applications")

    args = parser.parse_args()
    {
        "log": cmd_log,
        "question": cmd_question,
        "answer": cmd_answer,
        "pending": cmd_pending,
        "list": cmd_list,
        "lookup": cmd_lookup,
        "update-status": cmd_update_status,
        "repair": cmd_repair,
        "log-response": cmd_log_response,
        "stats": cmd_stats,
    }[args.command](args)


if __name__ == "__main__":
    main()
