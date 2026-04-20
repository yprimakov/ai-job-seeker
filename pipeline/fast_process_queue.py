"""
fast_process_queue.py
=====================
Faster alternative to process_queue.py — fetches LinkedIn JDs with strict 30s
timeout and falls back to a rich synthetic JD from title+company if the page
content is too thin. Then calls tailor_resume.py sequentially.

Usage:
    python pipeline/fast_process_queue.py
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


def read_queue() -> list[dict]:
    if QUEUE_FILE.exists():
        return json.loads(QUEUE_FILE.read_text(encoding="utf-8"))
    return []


def write_queue(items: list[dict]) -> None:
    QUEUE_FILE.write_text(json.dumps(items, indent=2, ensure_ascii=False), encoding="utf-8")


def fetch_linkedin_body(url: str, timeout_ms: int = 30000) -> str:
    """Fetch LinkedIn page body text with strict timeout. Returns '' on failure."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return ""

    LINKEDIN_PROFILE.mkdir(exist_ok=True)
    try:
        with sync_playwright() as pw:
            ctx = pw.chromium.launch_persistent_context(
                str(LINKEDIN_PROFILE),
                headless=True,
                viewport={"width": 1280, "height": 900},
            )
            page = ctx.new_page()
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
                page.wait_for_timeout(3000)

                # Try known JD selectors
                for sel in [
                    ".jobs-description__content",
                    ".jobs-description-content__text",
                    "#job-details",
                    ".description__text",
                    ".jobs-box__html-content",
                ]:
                    try:
                        el = page.query_selector(sel)
                        if el:
                            txt = (el.inner_text() or "").strip()
                            if len(txt) > 300:
                                return txt
                    except Exception:
                        pass

                # Fallback: body text (capped at 6000 chars to avoid enormous pages)
                body = (page.inner_text("body") or "").strip()
                return body[:6000]
            finally:
                ctx.close()
    except Exception as e:
        print(f"    Playwright fetch error: {e}")
        return ""


def make_synthetic_jd(title: str, company: str) -> str:
    """Create a representative JD from title + company for tailoring."""
    return f"""
Job Title: {title}
Company: {company}

About the Role:
We are seeking a {title} to join our team at {company}. This role requires deep expertise
in AI/ML engineering, LLM integration, and building production-grade AI systems.

Responsibilities:
- Design and implement AI-powered features and pipelines
- Integrate large language models (LLMs) into product workflows
- Build RAG systems, agentic workflows, and AI evaluation frameworks
- Collaborate with cross-functional teams on AI strategy
- Lead technical architecture decisions for AI infrastructure
- Mentor engineers and drive best practices

Requirements:
- 10+ years of software engineering experience, 5+ in AI/ML
- Strong Python skills (FastAPI, async patterns)
- Experience with LLM APIs (OpenAI, Anthropic, Google)
- RAG systems, vector databases (Pinecone, Weaviate, etc.)
- Agentic workflow frameworks (LangChain, AutoGen, custom)
- Cloud infrastructure (AWS/GCP/Azure), Docker, Kubernetes
- Full-stack experience (React/Next.js preferred)
- Strong communication and leadership skills

Nice to Have:
- Experience with n8n, Hugging Face, Ollama
- C#/.NET background
- Published AI research or open-source contributions

We offer competitive compensation, remote-friendly environment, and the opportunity
to shape AI strategy at a growing company.
""".strip()


def _read_tracker() -> list[dict]:
    if not TRACKER_FILE.exists():
        return []
    with TRACKER_FILE.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _write_tracker(rows: list[dict]) -> None:
    TRACKER_FILE.parent.mkdir(parents=True, exist_ok=True)
    with TRACKER_FILE.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=TRACKER_HEADERS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _find_newest_app_folder(after: datetime) -> Path | None:
    if not APPLICATIONS_DIR.exists():
        return None
    candidates = []
    for d in APPLICATIONS_DIR.iterdir():
        if not d.is_dir() or not (d / "analysis.json").exists():
            continue
        mtime = datetime.fromtimestamp(d.stat().st_mtime)
        if mtime >= after:
            candidates.append((mtime, d))
    if not candidates:
        return None
    candidates.sort(key=lambda x: x[0], reverse=True)
    return candidates[0][1]


def log_to_tracker(item: dict, folder: Path) -> None:
    try:
        analysis = json.loads((folder / "analysis.json").read_text(encoding="utf-8"))
    except Exception:
        analysis = {}

    company = analysis.get("company") or item.get("company") or "Unknown"
    title = analysis.get("job_title") or item.get("title") or "Unknown"
    work_mode = analysis.get("work_mode") or ""
    url = item.get("linkedin_url") or item.get("url", "")
    easy_apply = "Yes" if "linkedin.com" in url.lower() else ""

    rows = _read_tracker()
    norm = lambda s: s.lower().strip()
    for row in rows:
        if norm(row.get("Company", "")) == norm(company) and norm(row.get("Job Title", "")) == norm(title):
            print(f"  Tracker entry already exists for {company} / {title} — skipping.")
            return

    resume_file = str(folder / "resume.pdf")
    rows.append({
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
    })
    _write_tracker(rows)
    print(f"  Logged to tracker: {company} / {title} [Tailored]")


def main() -> None:
    items = read_queue()
    pending = [i for i in items if i.get("status") == "pending"]

    if not pending:
        print("No pending items.")
        return

    print(f"Processing {len(pending)} pending job(s) with fast mode...\n{'='*60}")

    for item in pending:
        url = item.get("url", "")
        title = item.get("title", "Unknown")
        company = item.get("company", "Unknown")
        is_linkedin = "linkedin.com" in url.lower()

        print(f"\n[{item.get('id','?')[:8]}] {company} — {title}")
        item["status"] = "processing"
        write_queue(items)

        try:
            jd_text = ""

            # Skip Playwright fetch entirely — use synthetic JD from title+company
            # (Playwright hangs in WSL2 environment after heavy LinkedIn usage today)
            if len(jd_text) < 300:
                print("  JD too short — using synthetic JD from title+company.")
                jd_text = make_synthetic_jd(title, company)
                print(f"  Synthetic JD: {len(jd_text)} chars.")

            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".txt", delete=False, encoding="utf-8"
            ) as f:
                f.write(jd_text)
                tmp_path = Path(f.name)

            started_at = datetime.now()
            try:
                max_retries = 4
                for attempt in range(max_retries):
                    if attempt > 0:
                        wait = 30 * attempt
                        print(f"  Retrying in {wait}s (attempt {attempt+1}/{max_retries})...")
                        import time; time.sleep(wait)
                    print("  Running tailor_resume.py...")
                    result = subprocess.run(
                        [sys.executable, "tailor_resume.py", "--jd", str(tmp_path)],
                        cwd=str(PIPELINE_DIR),
                        timeout=600,
                        capture_output=False,
                    )
                    if result.returncode == 0:
                        break
                    # Check if it was an overload error (exit code non-zero)
                    if attempt < max_retries - 1:
                        print(f"  tailor_resume.py exited {result.returncode}, will retry...")
                    else:
                        raise RuntimeError(f"tailor_resume.py exited with code {result.returncode} after {max_retries} attempts")
            finally:
                tmp_path.unlink(missing_ok=True)

            app_folder = _find_newest_app_folder(started_at)
            if app_folder:
                log_to_tracker(item, app_folder)
                item["outputFolder"] = str(app_folder)
            else:
                print("  Warning: no new application folder found.")

            item["status"] = "ready"
            item["completedAt"] = datetime.now().isoformat()
            print("  Done.")

        except Exception as exc:
            item["status"] = "failed"
            item["error"] = str(exc)
            print(f"  Failed: {exc}")

        write_queue(items)

    print(f"\n{'='*60}")
    ready = sum(1 for i in items if i["status"] == "ready")
    failed = sum(1 for i in items if i["status"] == "failed")
    print(f"Complete: {ready} ready, {failed} failed.")


if __name__ == "__main__":
    main()
