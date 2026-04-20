"""
process_queue.py
================
Processes pending items in jobs/queue.json.

For each pending item:
  - LinkedIn URLs: uses Playwright with the saved ~/.job-seeker-linkedin session
    (same profile used by the scraper, already logged in)
  - Other URLs: plain HTTP fetch
Then runs tailor_resume.py with the extracted JD and marks the item ready/failed.

Usage:
    python pipeline/process_queue.py
"""

from __future__ import annotations

import csv
import json
import re
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path

load_dotenv_path = Path(__file__).parent.parent / ".env"
try:
    from dotenv import load_dotenv
    load_dotenv(load_dotenv_path)
except ImportError:
    pass

REPO_ROOT = Path(__file__).parent.parent
QUEUE_FILE = REPO_ROOT / "jobs" / "queue.json"
TRACKER_FILE = REPO_ROOT / "jobs" / "application_tracker.csv"
APPLICATIONS_DIR = REPO_ROOT / "applications"
PIPELINE_DIR = Path(__file__).parent
LINKEDIN_PROFILE = Path.home() / ".job-seeker-linkedin"

TRACKER_HEADERS = [
    "Date Applied", "Company", "Job Title", "LinkedIn URL", "Work Mode",
    "Salary Range", "Easy Apply", "Application Status", "Notes",
    "Tailored Resume File", "Follow Up Date", "Date Response Received", "Response Type",
]


# ---------------------------------------------------------------------------
# Queue I/O
# ---------------------------------------------------------------------------

def read_queue() -> list[dict]:
    try:
        if QUEUE_FILE.exists():
            return json.loads(QUEUE_FILE.read_text(encoding="utf-8"))
    except Exception:
        pass
    return []


def write_queue(items: list[dict]) -> None:
    QUEUE_FILE.parent.mkdir(parents=True, exist_ok=True)
    QUEUE_FILE.write_text(json.dumps(items, indent=2, ensure_ascii=False), encoding="utf-8")


# ---------------------------------------------------------------------------
# JD fetching
# ---------------------------------------------------------------------------

def _strip_html(html: str) -> str:
    text = re.sub(r"<script[^>]*>[\s\S]*?</script>", " ", html, flags=re.IGNORECASE)
    text = re.sub(r"<style[^>]*>[\s\S]*?</style>", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    for entity, char in [("&nbsp;", " "), ("&amp;", "&"), ("&lt;", "<"), ("&gt;", ">")]:
        text = text.replace(entity, char)
    return " ".join(text.split())


def fetch_jd_http(url: str) -> str:
    import urllib.request
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=20) as r:
        html = r.read().decode("utf-8", errors="replace")
    return _strip_html(html)


def fetch_jd_playwright(url: str) -> str:
    try:
        from playwright.sync_api import sync_playwright  # type: ignore
    except ImportError:
        raise RuntimeError(
            "Playwright not installed.\n"
            "Run: pip install playwright && playwright install chromium"
        )

    LINKEDIN_PROFILE.mkdir(exist_ok=True)
    jd_selectors = [
        ".jobs-description__content",
        ".jobs-description-content__text",
        "#job-details",
        ".description__text",
        ".job-view-layout",
    ]

    with sync_playwright() as pw:
        context = pw.chromium.launch_persistent_context(
            str(LINKEDIN_PROFILE),
            headless=True,
            viewport={"width": 1280, "height": 900},
        )
        page = context.new_page()
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(3000)

            jd_text = ""
            for selector in jd_selectors:
                try:
                    el = page.query_selector(selector)
                    if el:
                        jd_text = (el.inner_text() or "").strip()
                        if len(jd_text) > 200:
                            break
                except Exception:
                    pass

            if len(jd_text) < 200:
                # Fallback: full page text (strip nav/header noise)
                jd_text = (page.inner_text("body") or "").strip()
        finally:
            context.close()

    return jd_text


# ---------------------------------------------------------------------------
# Tracker auto-log
# ---------------------------------------------------------------------------

def _find_newest_app_folder(after: datetime) -> Path | None:
    """Return the most recently created application folder created after `after`."""
    if not APPLICATIONS_DIR.exists():
        return None
    candidates = []
    for d in APPLICATIONS_DIR.iterdir():
        if not d.is_dir():
            continue
        if not (d / "analysis.json").exists():
            continue
        mtime = datetime.fromtimestamp(d.stat().st_mtime)
        if mtime >= after:
            candidates.append((mtime, d))
    if not candidates:
        return None
    candidates.sort(key=lambda x: x[0], reverse=True)
    return candidates[0][1]


def _read_tracker() -> list[dict]:
    if not TRACKER_FILE.exists():
        return []
    try:
        with TRACKER_FILE.open(newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            return list(reader)
    except Exception:
        return []


def _write_tracker(rows: list[dict]) -> None:
    TRACKER_FILE.parent.mkdir(parents=True, exist_ok=True)
    with TRACKER_FILE.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=TRACKER_HEADERS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def log_to_tracker(item: dict, folder: Path) -> None:
    """Add a 'Tailored' tracker entry for the processed queue item."""
    try:
        analysis_path = folder / "analysis.json"
        analysis = json.loads(analysis_path.read_text(encoding="utf-8")) if analysis_path.exists() else {}
    except Exception:
        analysis = {}

    company = analysis.get("company") or item.get("company") or "Unknown"
    title = analysis.get("job_title") or item.get("title") or "Unknown"
    work_mode = analysis.get("work_mode") or ""
    url = item.get("url", "")
    easy_apply = "Yes" if "linkedin.com" in url.lower() and analysis else ""

    # Check for duplicate (same company + title already in tracker)
    rows = _read_tracker()
    norm = lambda s: s.lower().strip()
    for row in rows:
        if norm(row.get("Company", "")) == norm(company) and norm(row.get("Job Title", "")) == norm(title):
            print(f"  Tracker entry already exists for {company} / {title} — skipping.")
            return

    resume_file = str(folder / "resume.pdf")
    new_row = {
        "Date Applied": datetime.now().strftime("%Y-%m-%d"),
        "Company": company,
        "Job Title": title,
        "LinkedIn URL": url,
        "Work Mode": work_mode,
        "Salary Range": item.get("salary", ""),
        "Easy Apply": easy_apply,
        "Application Status": "Tailored",
        "Notes": "",
        "Tailored Resume File": resume_file,
        "Follow Up Date": "",
        "Date Response Received": "",
        "Response Type": "",
    }
    rows.append(new_row)
    _write_tracker(rows)
    print(f"  Logged to tracker: {company} / {title} [Tailored]")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    items = read_queue()
    pending = [i for i in items if i.get("status") in ("pending", "failed")]

    if not pending:
        print("No pending items in the queue.")
        return

    print(f"Processing {len(pending)} queued job(s)...\n")
    print("=" * 60)

    for item in pending:
        url = item.get("url", "")
        item_id = item.get("id", "?")
        is_linkedin = "linkedin.com" in url.lower()

        print(f"\n[{item_id}] {url}")

        item["status"] = "processing"
        write_queue(items)

        try:
            if is_linkedin:
                print("  Fetching JD via Playwright (LinkedIn session)...")
                jd_text = fetch_jd_playwright(url)
            else:
                print("  Fetching JD via HTTP...")
                jd_text = fetch_jd_http(url)

            if len(jd_text) < 200:
                raise RuntimeError(
                    "Page content too short — LinkedIn may require a fresh login. "
                    "Run the scraper once to refresh the session."
                )

            print(f"  JD extracted ({len(jd_text):,} chars). Running tailor_resume.py...")

            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".txt", delete=False, encoding="utf-8"
            ) as f:
                f.write(jd_text)
                tmp_path = Path(f.name)

            started_at = datetime.now()
            try:
                result = subprocess.run(
                    [sys.executable, "tailor_resume.py", "--jd", str(tmp_path)],
                    cwd=str(PIPELINE_DIR),
                    timeout=900,
                )
                if result.returncode != 0:
                    raise RuntimeError(f"tailor_resume.py exited with code {result.returncode}")
            finally:
                tmp_path.unlink(missing_ok=True)

            # Auto-log to application tracker
            app_folder = _find_newest_app_folder(started_at)
            if app_folder:
                log_to_tracker(item, app_folder)
                item["outputFolder"] = str(app_folder)
            else:
                print("  Warning: could not find generated application folder to log to tracker.")

            item["status"] = "ready"
            item["completedAt"] = datetime.now().isoformat()
            print("  Done.")

        except Exception as exc:
            item["status"] = "failed"
            item["error"] = str(exc)
            print(f"  Failed: {exc}")

        write_queue(items)

    print("\n" + "=" * 60)
    ready = sum(1 for i in items if i["status"] == "ready")
    failed = sum(1 for i in items if i["status"] == "failed")
    print(f"Queue complete: {ready} ready, {failed} failed.")
    if failed:
        print("Failed items remain in the queue — check the error field for details.")


if __name__ == "__main__":
    main()
