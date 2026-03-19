"""
merge_linkedin_results.py
=========================
Merges multiple per-query LinkedIn result files (jobs/.tmp_results_*.md)
into a single jobs/linkedin_results.md, deduplicating by URL and sorting
by score descending.

Called by the batch launcher after running the scraper for each query.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
JOBS_DIR = REPO_ROOT / "jobs"
OUTPUT = JOBS_DIR / "linkedin_results.md"
TMP_GLOB = ".tmp_results_*.md"

TABLE_HEADER = "| Job Title | Company | Location | Salary | Easy Apply | Score | Posted | Fit Reason | URL |"
TABLE_SEP    = "|-----------|---------|----------|--------|------------|-------|--------|------------|-----|"


def _split_cells(line: str) -> list[str]:
    """Split a markdown table row into cells, preserving empty cells.

    Slices off the leading and trailing empty strings produced by splitting
    on the outer pipes, but does NOT remove empty cells in the middle.
    This prevents column misalignment when optional fields (e.g. salary) are blank.
    """
    parts = line.strip().split("|")
    # parts[0] is empty (before first |), parts[-1] is empty (after last |)
    return [c.strip() for c in parts[1:-1]]


def parse_rows(path: Path) -> list[dict]:
    """Parse all data rows from a linkedin_results.md-style file."""
    rows = []
    in_table = False
    headers: list[str] = []

    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped.startswith("|"):
            in_table = False
            continue
        if stripped.startswith("|---"):
            in_table = True
            continue
        if not in_table:
            # Header row — record column names
            headers = [c.lower() for c in _split_cells(line)]
            continue

        cells = _split_cells(line)
        if not cells:
            continue

        def get(name: str) -> str:
            try:
                idx = next(i for i, h in enumerate(headers) if name in h)
                return cells[idx] if idx < len(cells) else ""
            except StopIteration:
                return ""

        url_raw = get("url")
        url_match = re.search(r"\((.+?)\)", url_raw)
        url = url_match.group(1) if url_match else url_raw

        try:
            score = int(get("score"))
        except (ValueError, TypeError):
            score = 0

        rows.append({
            "title":      get("title") or get("job"),
            "company":    get("company"),
            "location":   get("location"),
            "salary":     get("salary"),
            "easyApply":  get("easy").lower() == "yes",
            "score":      score,
            "fit_reason": get("fit"),
            "posted":     get("posted"),
            "url":        url,
        })

    return rows


def merge(queries: list[str]) -> None:
    tmp_files = sorted(JOBS_DIR.glob(TMP_GLOB))
    if not tmp_files:
        print("No temp result files found — nothing to merge.", file=sys.stderr)
        return

    seen_urls: set[str] = set()
    all_rows: list[dict] = []
    for f in tmp_files:
        for row in parse_rows(f):
            if row["url"] and row["url"] in seen_urls:
                continue
            seen_urls.add(row["url"])
            all_rows.append(row)
        f.unlink()

    # Sort by score descending
    all_rows.sort(key=lambda r: r["score"], reverse=True)

    from datetime import datetime
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    query_str = " | ".join(queries) if queries else "multiple"

    lines = [
        "# LinkedIn Job Results",
        "",
        f"**Query:** {query_str}  ",
        f"**Generated:** {now}  ",
        f"**Total jobs found:** {len(all_rows)}",
        "",
        TABLE_HEADER,
        TABLE_SEP,
    ]

    for row in all_rows:
        url_cell = f"[Link]({row['url']})" if row["url"] else ""
        ea = "Yes" if row["easyApply"] else "No"
        lines.append(
            f"| {row['title']} | {row['company']} | {row['location']} | "
            f"{row['salary']} | {ea} | {row['score']} | {row.get('posted', '')} | {row['fit_reason']} | {url_cell} |"
        )

    lines.append("")
    JOBS_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"Merged {len(all_rows)} unique jobs → {OUTPUT}")


if __name__ == "__main__":
    # argv[1:] = the queries that were run (for the header)
    merge(sys.argv[1:])
