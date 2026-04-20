"""
Auto-Log on Confirmation
========================
Detects ATS confirmation pages and automatically logs the application
to application_tracker.csv — no manual `tracker.py log` call needed.

Usage:
    from ats.auto_log import is_confirmation_page, log_application

    # 1. After submitting, check the current page
    js_result = javascript_tool(CONFIRM_JS)   # via mcp__claude-in-chrome__javascript_tool

    if js_result["confirmed"]:
        log_application(
            company     = "Anthropic",
            title       = "Forward Deployed Engineer, Applied AI",
            url         = "https://job-boards.greenhouse.io/anthropic/jobs/4985877008",
            resume_file = "applications/20260317_Anthropic_.../resume.pdf",
            mode        = "Hybrid",
        )
"""

import subprocess
import sys
from datetime import date, timedelta
from pathlib import Path

# ── JS: detect confirmation page ───────────────────────────────────────────────

CONFIRM_JS = """\
(function() {
    const url   = window.location.href.toLowerCase();
    const title = document.title.toLowerCase();
    const body  = (document.body && document.body.innerText) ? document.body.innerText.toLowerCase() : '';

    const confirmed = (
        url.includes('/confirmation') ||
        url.includes('/thank') ||
        url.includes('/success') ||
        url.includes('/submitted') ||
        title.includes('thank you') ||
        title.includes('application received') ||
        title.includes('application submitted') ||
        body.includes('thank you for applying') ||
        body.includes('application has been submitted') ||
        body.includes('application has been received')
    );

    return {
        confirmed: confirmed,
        url:       window.location.href,
        title:     document.title,
    };
})()
"""


# ── Python: log to tracker ─────────────────────────────────────────────────────

TRACKER = Path(__file__).parent.parent / "tracker.py"


def log_application(
    company: str,
    title: str,
    url: str,
    resume_file: str = "",
    mode: str = "",
    salary: str = "",
    easy_apply: bool = False,
    notes: str = "",
    follow_up_days: int = 7,
) -> bool:
    """
    Log a submitted application to application_tracker.csv via tracker.py.

    Args:
        company:        Company name
        title:          Job title
        url:            Application / job posting URL
        resume_file:    Relative path to the tailored resume PDF
        mode:           "Remote" | "Hybrid" | "On-site"
        salary:         Salary range string, e.g. "$200K-$250K"
        easy_apply:     True if submitted via LinkedIn Easy Apply
        notes:          Free-text notes to attach
        follow_up_days: Days from today to set the follow-up date (default 7)

    Returns:
        True if tracker.py exited successfully, False otherwise.
    """
    follow_up = (date.today() + timedelta(days=follow_up_days)).strftime("%Y-%m-%d")

    cmd = [
        sys.executable, str(TRACKER),
        "log",
        "--company",   company,
        "--title",     title,
        "--url",       url,
        "--follow-up", follow_up,
    ]
    if mode:        cmd += ["--mode",        mode]
    if salary:      cmd += ["--salary",      salary]
    if resume_file: cmd += ["--resume-file", resume_file]
    if notes:       cmd += ["--notes",       notes]
    if easy_apply:  cmd += ["--easy-apply"]

    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode == 0:
        print(f"[auto-log] {title} @ {company} → logged (follow-up: {follow_up})")
        return True
    else:
        print(f"[auto-log] ERROR: {result.stderr.strip()}")
        return False


def find_resume_for_application(company: str, title: str) -> str:
    """
    Find the tailored resume PDF for a given company/title in the applications/ folder.
    Returns the relative path string, or empty string if not found.
    """
    apps_dir = Path(__file__).parent.parent.parent / "applications"
    if not apps_dir.exists():
        return ""

    import re as _re
    company_slug = _re.sub(r"[^a-z0-9]+", "_", company.lower()).strip("_")
    for folder in sorted(apps_dir.iterdir(), reverse=True):
        if not folder.is_dir():
            continue
        name_lower = folder.name.lower()
        if company_slug in name_lower:
            pdf = folder / "resume.pdf"
            if pdf.exists():
                return str(pdf.relative_to(apps_dir.parent))
    return ""
