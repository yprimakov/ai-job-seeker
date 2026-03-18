"""
linkedin_scraper.py
===================
LinkedIn job discovery module for the job-seeker pipeline.

Two modes of operation:

1. Module mode: Called during a Claude browser session (no Playwright needed).
   - JS strings for extracting job cards, clicking next page, checking login.
   - `build_search_url()` constructs LinkedIn search URLs with filters.
   - `score_jobs()` uses Claude Haiku to score jobs against Yury's profile.
   - `save_results()` writes a markdown results file.

2. CLI mode: Standalone Playwright-based scraper.
   - Requires: pip install playwright && playwright install chromium
   - Runs in headed mode so the user can log in if session is expired.
   - Usage: python pipeline/linkedin_scraper.py --query "principal AI engineer"

Env vars required:
    ANTHROPIC_API_KEY
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import quote_plus, urlencode

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

# Make pipeline package importable when run as a script
sys.path.insert(0, str(Path(__file__).parent))

from profile import PROFILE  # noqa: E402

import anthropic  # noqa: E402

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

LINKEDIN_JOBS_BASE = "https://www.linkedin.com/jobs/search/"

DATE_POSTED_MAP = {
    "today": "r86400",
    "week": "r604800",
    "month": "r2592000",
}

HAIKU_MODEL = "claude-haiku-4-5"

# ---------------------------------------------------------------------------
# JS snippets (module mode, injected via browser CDP/Playwright evaluate)
# ---------------------------------------------------------------------------

SCRAPE_JOBS_JS: str = """
(function() {
    // Multiple fallback selector strategies since LinkedIn changes its DOM frequently.
    var jobs = [];

    // Strategy 1: data-job-id attribute on list items (common in 2024-2025 layout)
    var cards = document.querySelectorAll('li[data-occludable-job-id], li[data-job-id]');

    // Strategy 2: job result cards via class names
    if (!cards || cards.length === 0) {
        cards = document.querySelectorAll(
            '.jobs-search-results__list-item, ' +
            '.job-card-container, ' +
            '.jobs-job-board-list__item'
        );
    }

    // Strategy 3: broader fallback for newer layouts
    if (!cards || cards.length === 0) {
        cards = document.querySelectorAll(
            '[class*="job-card"], [class*="jobs-search-result"]'
        );
    }

    function getText(el, selectors) {
        for (var i = 0; i < selectors.length; i++) {
            var found = el.querySelector(selectors[i]);
            if (found && found.innerText.trim()) {
                return found.innerText.trim();
            }
        }
        return '';
    }

    function getHref(el, selectors) {
        for (var i = 0; i < selectors.length; i++) {
            var found = el.querySelector(selectors[i]);
            if (found && found.href) {
                return found.href;
            }
        }
        return '';
    }

    cards.forEach(function(card) {
        try {
            var title = getText(card, [
                '.job-card-list__title',
                '.job-card-container__link',
                'a[class*="job-card"] span[aria-hidden]',
                '.jobs-unified-top-card__job-title a',
                'h3.base-search-card__title',
                'h3[class*="title"]',
                'a[data-tracking-control-name*="job_card"] strong'
            ]);

            var company = getText(card, [
                '.job-card-container__primary-description',
                '.job-card-container__company-name',
                '.artdeco-entity-lockup__subtitle span',
                'h4.base-search-card__subtitle',
                'h4[class*="company"]',
                '.job-card-list__company-name',
                'a[data-tracking-control-name*="company"]'
            ]);

            var location = getText(card, [
                '.job-card-container__metadata-item',
                '.job-card-container__metadata-wrapper li:first-child',
                '.artdeco-entity-lockup__caption span',
                '.job-search-card__location',
                'span[class*="location"]',
                '.job-card-list__metadata-item'
            ]);

            var salary = getText(card, [
                '.job-card-container__salary-info',
                '[class*="salary"]',
                '.compensation'
            ]);

            var easyApply = !!(
                card.querySelector('[aria-label*="Easy Apply"]') ||
                card.querySelector('.job-card-container__apply-method') ||
                card.innerText.includes('Easy Apply')
            );

            var url = getHref(card, [
                '.job-card-list__title',
                '.job-card-container__link',
                'a[class*="job-card"]',
                'a[href*="/jobs/view/"]'
            ]);

            // Extract numeric job ID from URL or data attribute
            var jobId = card.getAttribute('data-occludable-job-id') ||
                        card.getAttribute('data-job-id') || '';
            if (!jobId && url) {
                var m = url.match(/\\/jobs\\/view\\/(\\d+)/);
                if (m) jobId = m[1];
            }

            // Only keep cards where we got at minimum a title
            if (title) {
                jobs.push({
                    title: title,
                    company: company,
                    location: location,
                    salary: salary,
                    easyApply: easyApply,
                    url: url || window.location.href,
                    jobId: jobId
                });
            }
        } catch (e) {
            // Skip malformed cards silently
        }
    });

    return jobs;
})();
"""

NEXT_PAGE_JS: str = """
(function() {
    // Try multiple selectors for the "Next" pagination button
    var selectors = [
        'button[aria-label="View next page"]',
        'button[aria-label="Next"]',
        '.artdeco-pagination__button--next',
        'li.artdeco-pagination__indicator--number.active + li button',
        '[data-test-pagination-page-btn="next"]',
        'button.jobs-search-pagination__button--next'
    ];

    for (var i = 0; i < selectors.length; i++) {
        var btn = document.querySelector(selectors[i]);
        if (btn && !btn.disabled) {
            btn.click();
            return { clicked: true };
        }
    }

    return { clicked: false };
})();
"""

LOGIN_CHECK_JS: str = """
(function() {
    // Indicators of a logged-in session
    var loggedInSelectors = [
        'div[data-control-name="identity_profile_photo"]',
        '.global-nav__me-photo',
        'img.global-nav__me-photo',
        '[data-control-name="nav.homepage"]',
        '.feed-nav-item',
        '#voyager-feed'
    ];

    for (var i = 0; i < loggedInSelectors.length; i++) {
        if (document.querySelector(loggedInSelectors[i])) {
            return { loggedIn: true };
        }
    }

    // Indicators of logged-out / auth wall
    var loggedOutSelectors = [
        '.authwall-join-form',
        '.join-form',
        'form.login__form',
        'a[href*="linkedin.com/login"]'
    ];

    for (var i = 0; i < loggedOutSelectors.length; i++) {
        if (document.querySelector(loggedOutSelectors[i])) {
            return { loggedIn: false };
        }
    }

    // Ambiguous: assume logged in if we're on a jobs page with results
    var hasResults = !!(
        document.querySelector('.jobs-search-results-list') ||
        document.querySelector('.jobs-search__results-list') ||
        document.querySelector('[class*="jobs-search-result"]')
    );

    return { loggedIn: hasResults };
})();
"""

# ---------------------------------------------------------------------------
# URL builder
# ---------------------------------------------------------------------------


def build_search_url(
    keywords: str,
    location: str = "United States",
    remote: bool = False,
    easy_apply: bool = False,
    date_posted: str = "week",
) -> str:
    """Build a LinkedIn jobs search URL with the given filters.

    Args:
        keywords: Job title or keyword string.
        location: Location string (city, state, country, or "United States").
        remote: If True, adds the remote-work filter (f_WT=2).
        easy_apply: If True, adds the Easy Apply filter (f_AL=true).
        date_posted: One of "today", "week" (default), or "month".

    Returns:
        Full LinkedIn search URL string.
    """
    params: dict[str, str] = {
        "keywords": keywords,
        "location": location,
        "sortBy": "R",  # relevance
    }

    tpr = DATE_POSTED_MAP.get(date_posted, DATE_POSTED_MAP["week"])
    params["f_TPR"] = tpr

    if remote:
        params["f_WT"] = "2"

    if easy_apply:
        params["f_AL"] = "true"

    return LINKEDIN_JOBS_BASE + "?" + urlencode(params)


# ---------------------------------------------------------------------------
# Scoring via Claude Haiku
# ---------------------------------------------------------------------------

_SCORE_SYSTEM = (
    "You are a recruiter assistant. Given a candidate profile and a list of job postings, "
    "score each job on fit from 1 (poor fit) to 5 (excellent fit). "
    "Be concise. Follow the JSON schema exactly."
)

_CANDIDATE_SUMMARY = f"""
Candidate: {PROFILE['full_name']}
Title: Principal AI Engineer
Location: {PROFILE.get('location', 'Holmdel, NJ')} — open to remote or within 30-minute drive
Experience: 15+ years full-stack engineering, specializing in applied AI
Core skills: LLM integration, RAG systems, agentic workflows, autonomous AI agents,
  Python, FastAPI, Next.js, React, Docker, Kubernetes, C#, .NET
AI tools: Claude API, OpenAI API, Gemini API, Ollama, n8n, Pinecone, Hugging Face, LangChain
Target roles: Principal AI Engineer, Staff AI Engineer, Senior AI Engineer,
  AI Solutions Architect, AI/ML Engineer, Full Stack AI Engineer
Not interested in: mainframe, legacy enterprise with no AI component
""".strip()


def score_jobs(jobs: list[dict]) -> list[dict]:
    """Score a list of job dicts against Yury's profile using Claude Haiku.

    Adds `score` (int 1-5), `fit_reason` (str, one sentence),
    and `gaps` (str, one sentence or empty string) to each job dict.
    All jobs are batched into a single Claude API call.
    Returns jobs sorted by score descending.

    Args:
        jobs: List of job dicts (must have at minimum `title` and `company` keys).

    Returns:
        The same list with score/fit_reason/gaps added, sorted by score desc.
    """
    if not jobs:
        return jobs

    client = anthropic.Anthropic()

    # Build a numbered job list for the prompt
    job_lines = []
    for i, job in enumerate(jobs):
        parts = [f"{i + 1}. {job.get('title', 'N/A')} at {job.get('company', 'N/A')}"]
        if job.get("location"):
            parts.append(f"   Location: {job['location']}")
        if job.get("salary"):
            parts.append(f"   Salary: {job['salary']}")
        if job.get("easyApply"):
            parts.append("   Easy Apply: yes")
        job_lines.append("\n".join(parts))

    jobs_block = "\n\n".join(job_lines)

    prompt = f"""Candidate profile:
{_CANDIDATE_SUMMARY}

Jobs to score (numbered list):
{jobs_block}

Return a JSON array with one object per job, in the same order.
Each object must have exactly these keys:
  "index": integer (1-based, matching the job number above),
  "score": integer 1-5,
  "fit_reason": string (one sentence explaining the score),
  "gaps": string (one sentence on the main gap, or empty string if no notable gap)

Return ONLY the JSON array with no other text."""

    response = client.messages.create(
        model=HAIKU_MODEL,
        max_tokens=2048,
        system=_SCORE_SYSTEM,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = response.content[0].text.strip()

    # Strip markdown fences if present
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]

    scored: list[dict] = json.loads(raw)

    # Merge scores back into the original job dicts
    score_map: dict[int, dict] = {item["index"]: item for item in scored}
    for i, job in enumerate(jobs):
        s = score_map.get(i + 1, {})
        job["score"] = s.get("score", 0)
        job["fit_reason"] = s.get("fit_reason", "")
        job["gaps"] = s.get("gaps", "")

    jobs.sort(key=lambda j: j.get("score", 0), reverse=True)
    return jobs


# ---------------------------------------------------------------------------
# Results writer
# ---------------------------------------------------------------------------

STAR_MAP = {5: "5 stars", 4: "4 stars", 3: "3 stars", 2: "2 stars", 1: "1 star", 0: "unscored"}


def save_results(
    jobs: list[dict],
    query: str,
    output_path: Path | None = None,
) -> Path:
    """Write scored jobs to a markdown file.

    Groups jobs by score (highest first). Format: markdown table.

    Args:
        jobs: List of scored job dicts.
        query: Original search query string, used in the file header.
        output_path: Destination path. Defaults to `jobs/linkedin_results.md`
                     in the repo root.

    Returns:
        The Path where the file was written.
    """
    repo_root = Path(__file__).parent.parent
    if output_path is None:
        output_path = repo_root / "jobs" / "linkedin_results.md"

    output_path.parent.mkdir(parents=True, exist_ok=True)

    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines: list[str] = [
        f"# LinkedIn Job Results",
        f"",
        f"**Query:** {query}  ",
        f"**Generated:** {now}  ",
        f"**Total jobs found:** {len(jobs)}",
        f"",
    ]

    # Group by score
    by_score: dict[int, list[dict]] = {}
    for job in jobs:
        s = job.get("score", 0)
        by_score.setdefault(s, []).append(job)

    table_header = (
        "| Job Title | Company | Location | Salary | Easy Apply | Score | Fit Reason | URL |"
    )
    table_sep = "|-----------|---------|----------|--------|------------|-------|------------|-----|"

    for score in sorted(by_score.keys(), reverse=True):
        group = by_score[score]
        star_str = ("+" * score) if score else "?"
        section_label = f"Score {score}/5 ({star_str})"
        lines.append(f"## {section_label}")
        lines.append("")
        lines.append(table_header)
        lines.append(table_sep)

        for job in group:
            title = _md_cell(job.get("title", ""))
            company = _md_cell(job.get("company", ""))
            location = _md_cell(job.get("location", ""))
            salary = _md_cell(job.get("salary", ""))
            easy = "Yes" if job.get("easyApply") else "No"
            score_val = str(job.get("score", ""))
            fit_reason = _md_cell(job.get("fit_reason", ""))
            url = job.get("url", "")
            url_cell = f"[Link]({url})" if url else ""

            lines.append(
                f"| {title} | {company} | {location} | {salary} | {easy} | {score_val} | {fit_reason} | {url_cell} |"
            )

        lines.append("")

    output_path.write_text("\n".join(lines), encoding="utf-8")
    return output_path


def _md_cell(text: str) -> str:
    """Escape pipe characters for use inside a markdown table cell."""
    return text.replace("|", "/").replace("\n", " ").strip()


# ---------------------------------------------------------------------------
# CLI mode (Playwright)
# ---------------------------------------------------------------------------


def _cli_main() -> None:
    parser = argparse.ArgumentParser(
        description="Scrape LinkedIn job listings via Playwright (headed mode)."
    )
    parser.add_argument(
        "--query",
        required=True,
        help='Job search keywords, e.g. "principal AI engineer".',
    )
    parser.add_argument(
        "--pages",
        type=int,
        default=3,
        help="Number of result pages to scrape (default: 3).",
    )
    parser.add_argument(
        "--remote",
        action="store_true",
        help="Filter to remote jobs only.",
    )
    parser.add_argument(
        "--easy-apply",
        action="store_true",
        dest="easy_apply",
        help="Filter to Easy Apply jobs only.",
    )
    parser.add_argument(
        "--date-posted",
        default="week",
        choices=["today", "week", "month"],
        help="Date posted filter (default: week).",
    )
    parser.add_argument(
        "--location",
        default="United States",
        help='Location string for the search (default: "United States").',
    )
    parser.add_argument(
        "--output",
        help="Output path for the markdown results file.",
    )
    args = parser.parse_args()

    # Check Playwright availability
    try:
        from playwright.sync_api import sync_playwright  # type: ignore
    except ImportError:
        print(
            "Playwright is not installed. Install it with:\n"
            "    pip install playwright\n"
            "    playwright install chromium\n"
            "Then re-run this script."
        )
        sys.exit(1)

    search_url = build_search_url(
        keywords=args.query,
        location=args.location,
        remote=args.remote,
        easy_apply=args.easy_apply,
        date_posted=args.date_posted,
    )

    output_path = Path(args.output) if args.output else None
    all_jobs: list[dict] = []
    seen_ids: set[str] = set()

    # Persistent user data dir so LinkedIn session survives between scraper runs.
    # First run: log in once in the browser window. Subsequent runs: already logged in.
    user_data_dir = Path.home() / ".job-seeker-linkedin"
    user_data_dir.mkdir(exist_ok=True)

    with sync_playwright() as pw:
        # launch_persistent_context saves cookies + localStorage to disk
        context = pw.chromium.launch_persistent_context(
            str(user_data_dir),
            headless=False,
            viewport={"width": 1280, "height": 900},
            args=["--start-maximized"],
        )
        page = context.new_page()

        print(f"Navigating to LinkedIn search: {search_url}")
        page.goto(search_url, wait_until="domcontentloaded")

        # Give cookies a moment to settle
        page.wait_for_timeout(3000)

        login_state = page.evaluate(LOGIN_CHECK_JS)
        if not login_state.get("loggedIn"):
            print(
                "You do not appear to be logged in to LinkedIn. "
                "Please log in using the browser window, then press Enter here to continue.\n"
                "(Your session will be saved so you won't be asked again next time.)"
            )
            input()

        for page_num in range(1, args.pages + 1):
            # Wait for job cards to render
            try:
                page.wait_for_selector(
                    "li[data-occludable-job-id], li[data-job-id], "
                    ".jobs-search-results__list-item, .job-card-container",
                    timeout=10000,
                )
            except Exception:
                print(f"[page {page_num}] No job cards found. LinkedIn may have changed its layout.")

            page_jobs: list[dict] = page.evaluate(SCRAPE_JOBS_JS)

            # Deduplicate by jobId or url
            new_jobs = []
            for job in page_jobs:
                key = job.get("jobId") or job.get("url") or job.get("title", "")
                if key and key not in seen_ids:
                    seen_ids.add(key)
                    new_jobs.append(job)

            all_jobs.extend(new_jobs)
            print(f"[page {page_num}] scraped {len(new_jobs)} jobs (total: {len(all_jobs)})")

            if page_num < args.pages:
                time.sleep(2)
                result = page.evaluate(NEXT_PAGE_JS)
                if not result.get("clicked"):
                    print(f"[page {page_num}] No next page button found. Stopping.")
                    break
                page.wait_for_timeout(2000)

        context.close()

    if not all_jobs:
        print("No jobs scraped. Check your search terms or LinkedIn session.")
        sys.exit(0)

    print(f"\nScoring {len(all_jobs)} jobs with Claude Haiku...")
    all_jobs = score_jobs(all_jobs)

    out = save_results(all_jobs, query=args.query, output_path=output_path)
    print(f"\nResults written to: {out}")
    print(f"Top result: {all_jobs[0].get('title')} at {all_jobs[0].get('company')} (score: {all_jobs[0].get('score')})")


if __name__ == "__main__":
    _cli_main()
