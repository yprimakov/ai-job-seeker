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

TABLE_HEADER = "| Job Title | Company | Location | Salary | Easy Apply | Score | Fit Reason | URL |"
TABLE_SEP    = "|-----------|---------|----------|--------|------------|-------|------------|-----|"


def parse_rows(path: Path) -> list[dict]:
    """Parse all data rows from a linkedin_results.md-style file."""
    rows = []
    in_table = False
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip().startswith("| Job Title"):
            in_table = True
            continue
        if in_table and line.strip().startswith("|---"):
            continue
        if in_table and line.strip().startswith("|"):
            cells = [c.strip() for c in line.strip().split("|")]
            cells = [c for c in cells if c != ""]  # drop empty from split
            if len(cells) < 7:
                continue
            url_cell = cells[7] if len(cells) > 7 else ""
            url_match = re.search(r"\((.+?)\)", url_cell)
            url = url_match.group(1) if url_match else url_cell
            try:
                score = int(cells[5])
            except (ValueError, IndexError):
                score = 0
            rows.append({
                "title":     cells[0],
                "company":   cells[1],
                "location":  cells[2],
                "salary":    cells[3],
                "easyApply": cells[4].lower() == "yes",
                "score":     score,
                "fit_reason": cells[6] if len(cells) > 6 else "",
                "url":       url,
            })
        elif in_table and not line.strip().startswith("|"):
            in_table = False
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
            f"{row['salary']} | {ea} | {row['score']} | {row['fit_reason']} | {url_cell} |"
        )

    lines.append("")
    JOBS_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"Merged {len(all_rows)} unique jobs → {OUTPUT}")


if __name__ == "__main__":
    # argv[1:] = the queries that were run (for the header)
    merge(sys.argv[1:])
