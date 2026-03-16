"""
Resume Tailoring Pipeline
=========================
Analyzes a job description and generates a tailored version of your resume
optimized for that specific role. Uses Claude API for intelligent analysis.

Usage:
    python tailor_resume.py --jd "path/to/job_description.txt"
    python tailor_resume.py --jd-text "Paste job description here..."
    python tailor_resume.py --jd "jd.txt" --output "output/tailored_resume.md"
    python tailor_resume.py --jd "jd.txt" --format docx
"""

import argparse
import base64
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

import anthropic
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

# ── Paths ──────────────────────────────────────────────────────────────────────
SCRIPT_DIR = Path(__file__).parent
BASE_RESUME = SCRIPT_DIR / "resume_base.md"
APPLICATIONS_DIR = SCRIPT_DIR.parent / "applications"
APPLICATIONS_DIR.mkdir(exist_ok=True)
# Keep output/ for legacy compatibility
OUTPUT_DIR = SCRIPT_DIR.parent / "output"
OUTPUT_DIR.mkdir(exist_ok=True)

def _find_chrome() -> str:
    """Auto-detect Chrome executable path across platforms."""
    import platform
    system = platform.system()
    candidates = []
    if system == "Windows":
        candidates = [
            "C:/Program Files/Google/Chrome/Application/chrome.exe",
            "C:/Program Files (x86)/Google/Chrome/Application/chrome.exe",
            os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
        ]
    elif system == "Darwin":
        candidates = ["/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"]
    else:
        candidates = [
            "/usr/bin/google-chrome",
            "/usr/bin/google-chrome-stable",
            "/usr/bin/chromium-browser",
            "/usr/bin/chromium",
        ]
    for c in candidates:
        if Path(c).exists():
            return c
    return candidates[0]  # fall back to first candidate; error handled at call site

CHROME_PATH = _find_chrome()


# ── Claude client ──────────────────────────────────────────────────────────────
def get_client() -> anthropic.Anthropic:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        sys.exit(
            "Error: ANTHROPIC_API_KEY environment variable not set.\n"
            "Set it with: export ANTHROPIC_API_KEY=your_key"
        )
    return anthropic.Anthropic(api_key=api_key)


# ── Step 1: Analyze the job description ───────────────────────────────────────
ANALYSIS_PROMPT = """\
You are an expert technical recruiter and resume strategist. Analyze the following job description and extract structured information.

JOB DESCRIPTION:
{jd}

Return a JSON object with exactly these fields:
{{
  "job_title": "exact job title from the posting",
  "company": "company name if visible, else 'Unknown'",
  "role_type": "one of: AI/ML Engineer, Full Stack Engineer, AI Solutions Architect, Staff/Principal Engineer, Other",
  "seniority": "Junior | Mid | Senior | Staff | Principal | Director",
  "work_mode": "Remote | Hybrid | On-site",
  "key_requirements": ["top 8-10 required skills/experiences, most important first"],
  "preferred_requirements": ["nice-to-have skills"],
  "tech_stack": ["specific technologies, frameworks, tools mentioned"],
  "keywords_ats": ["exact keywords/phrases for ATS matching — pull directly from the JD text"],
  "core_responsibilities": ["3-5 main things this person will actually do day-to-day"],
  "domain": "Industry or domain focus (e.g., Insurance, FinTech, Healthcare, General, SaaS, etc.)",
  "match_score": "0-100 integer — how well does the candidate's background match this role based on the BASE RESUME provided",
  "match_gaps": ["skills or experiences in the JD that the candidate may lack or should emphasize more"],
  "resume_angles": ["2-3 specific angles to highlight in the candidate's resume for this role"]
}}

Return only valid JSON, no markdown fences, no explanation.
"""

def analyze_jd(client: anthropic.Anthropic, jd_text: str) -> dict:
    print("> Analyzing job description...")
    response = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=2000,
        messages=[{"role": "user", "content": ANALYSIS_PROMPT.format(jd=jd_text)}],
    )
    raw = response.content[0].text.strip()
    # Strip markdown fences if present
    raw = re.sub(r"^```json\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)
    return json.loads(raw)


# ── Step 2: Generate tailored resume ──────────────────────────────────────────
TAILOR_PROMPT = """\
You are an elite resume writer specializing in AI/tech roles. Your task is to rewrite the candidate's resume to perfectly target a specific job, maximizing ATS score and recruiter impact — without fabricating any experience.

BASE RESUME:
{base_resume}

TARGET JOB ANALYSIS:
{analysis}

TAILORING RULES:
1. Professional Summary: Rewrite to speak directly to this role. Mirror language from the JD. Lead with the most relevant experience. Keep to 3-4 sentences. No trailing punctuation artifacts.
2. Technical Skills: Reorder skill categories so the most relevant to this JD appear first. Move JD-mentioned technologies to the top of their category. Do not add skills Yury doesn't have. End each skill line cleanly — no trailing punctuation or separators.
3. Experience Bullets: Rewrite bullets to use JD keywords where genuinely applicable. Quantify impact where possible. Lead each bullet with a strong action verb. For Prime Solutions especially — connect Yury's independent work directly to what this role needs.
4. Experience Order: Always keep chronological order but trim bullets in less relevant roles to 1-2 lines max.
5. ATS Keywords: Naturally embed the top ATS keywords from the analysis into the summary, skills, and bullets. Never keyword-stuff — every keyword must be in context.
6. Do NOT fabricate experience, tools, or results. Only reframe what's genuinely there.
7. If the JD has a domain Yury lacks (e.g., P&C insurance), briefly acknowledge transferable skills rather than pretending domain expertise.

STRICT FORMATTING RULES — violating any of these is unacceptable:
- NEVER use em dashes (—). Replace with a comma, colon, semicolon, or rewrite the sentence.
- NEVER insert horizontal rules (---) anywhere in the output — not between sections, not at the end of lines, not anywhere.
- NEVER append stray punctuation or separator characters (---, |, —) at the end of any line or sentence.
- Section headers (PROFESSIONAL SUMMARY, TECHNICAL SKILLS, etc.) must be wrapped in <div align="center"> tags exactly as in the base resume.
- Every company entry must use this exact format — company name bold on left, date with float:right span on same line, role italic on the next line:
  **Company Name** <span style="float:right">Month YYYY – Month YYYY</span>
  *Job Title*
- Contact bar must use &nbsp;·&nbsp; as separator, centered inside a <div align="center"> block.
- Preserve all HTML tags from the base resume exactly (<div align="center">, <span style="float:right">, etc.).

Return ONLY the tailored resume in Markdown+HTML. No explanations, no preamble, no trailing content after the last certification line.
"""

def tailor_resume(client: anthropic.Anthropic, base_resume: str, analysis: dict) -> str:
    print("> Generating tailored resume...")
    response = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=4000,
        messages=[
            {
                "role": "user",
                "content": TAILOR_PROMPT.format(
                    base_resume=base_resume,
                    analysis=json.dumps(analysis, indent=2),
                ),
            }
        ],
    )
    return response.content[0].text.strip()


# ── Resume header parser ───────────────────────────────────────────────────────
def parse_resume_header(resume_md: str) -> dict:
    """Extract name, title, and raw contact line from the resume markdown header."""
    result = {"name": "", "title": "", "contact": ""}
    for line in resume_md.splitlines():
        s = line.strip()
        if s.startswith("# ") and not result["name"]:
            result["name"] = s[2:].strip()
        elif s.startswith("### ") and not result["title"]:
            result["title"] = s[4:].strip()
        elif "&nbsp;" in s and not result["contact"]:
            result["contact"] = s
        if result["name"] and result["title"] and result["contact"]:
            break
    return result


# ── Step 3: Generate cover letter snippet (optional) ──────────────────────────
COVER_PROMPT = """\
Write a compelling 3-paragraph cover letter opening for a candidate applying to the role below.
Keep it punchy and specific — reference exact details from the JD. No generic fluff.

CANDIDATE NAME: {candidate_name}
JOB: {job_title} at {company}
KEY REQUIREMENTS: {requirements}
CORE RESPONSIBILITIES: {responsibilities}

Most relevant angles for this role: {angles}

Format: 3 short paragraphs. No salutation, no sign-off. Just the body copy.
"""

def generate_cover_snippet(client: anthropic.Anthropic, analysis: dict, candidate_name: str = "") -> str:
    print("> Generating cover letter snippet...")
    response = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=800,
        messages=[
            {
                "role": "user",
                "content": COVER_PROMPT.format(
                    candidate_name=candidate_name or "the candidate",
                    job_title=analysis.get("job_title", "AI Engineer"),
                    company=analysis.get("company", "the company"),
                    requirements=", ".join(analysis.get("key_requirements", [])[:5]),
                    responsibilities="; ".join(analysis.get("core_responsibilities", [])[:3]),
                    angles="; ".join(analysis.get("resume_angles", [])),
                ),
            }
        ],
    )
    return response.content[0].text.strip()


# ── Step 4: Build HTML resume ─────────────────────────────────────────────────
def build_html(resume_md: str, job_title: str, company: str) -> str:
    """Convert the tailored resume markdown into a styled, print-ready HTML file."""
    import html as html_lib

    header = parse_resume_header(resume_md)
    candidate_name = header["name"] or "Candidate"
    candidate_title = header["title"] or job_title

    # Parse contact line: "site · email · phone · location"
    contact_parts = []
    if header["contact"]:
        raw_parts = re.split(r"&nbsp;·&nbsp;", header["contact"])
        for part in raw_parts:
            part = part.strip()
            if part.startswith("<div") or part.startswith("</div") or not part:
                continue
            contact_parts.append(part)

    # Split name into first + last for the blue-last-name styling
    name_parts = candidate_name.split(None, 1)
    first_name = html_lib.escape(name_parts[0]) if name_parts else ""
    last_name = html_lib.escape(name_parts[1]) if len(name_parts) > 1 else ""

    # Extract sections from the markdown
    def between(text, start_marker, end_marker=None):
        try:
            start = text.index(start_marker) + len(start_marker)
            end = text.index(end_marker, start) if end_marker else len(text)
            return text[start:end].strip()
        except ValueError:
            return ""

    # Pull the raw resume lines for processing
    lines = resume_md.split("\n")

    # Parse skills block
    skills_lines = []
    exp_blocks = []
    in_exp = False
    current_job = None
    summary_text = ""
    education_lines = []
    cert_lines = []

    section = None
    for line in lines:
        stripped = line.strip()
        if "## PROFESSIONAL SUMMARY" in stripped:
            section = "summary"
        elif "## TECHNICAL SKILLS" in stripped:
            section = "skills"
        elif "## PROFESSIONAL EXPERIENCE" in stripped:
            section = "experience"
        elif "## EDUCATION" in stripped:
            section = "education"
        elif "## CERTIFICATIONS" in stripped:
            section = "certs"
        elif stripped in ("<div align=\"center\">", "</div>", ""):
            continue
        elif section == "summary" and stripped and not stripped.startswith("#"):
            summary_text += " " + stripped
        elif section == "skills" and stripped.startswith("**"):
            skills_lines.append(stripped)
        elif section == "experience":
            if stripped.startswith("**") and "<span" in stripped:
                if current_job:
                    exp_blocks.append(current_job)
                # Parse company and date
                company_part = re.sub(r"\*\*(.+?)\*\*.*", r"\1", stripped)
                date_part = re.search(r"float:right[^>]*>([^<]+)<", stripped)
                date_str = date_part.group(1) if date_part else ""
                current_job = {"company": company_part, "date": date_str, "title": "", "bullets": []}
            elif current_job and stripped.startswith("*") and not stripped.startswith("**"):
                current_job["title"] = stripped.strip("*")
            elif current_job and stripped.startswith("- "):
                current_job["bullets"].append(stripped[2:])
        elif section == "education" and stripped and not stripped.startswith("#"):
            education_lines.append(stripped)
        elif section == "certs" and stripped and not stripped.startswith("#"):
            cert_lines.append(stripped)

    if current_job:
        exp_blocks.append(current_job)

    def skill_to_html(s):
        m = re.match(r"\*\*(.+?):\*\*\s*(.*)", s)
        if m:
            return f'<p><strong>{html_lib.escape(m.group(1))}:</strong> {html_lib.escape(m.group(2))}</p>'
        return f"<p>{html_lib.escape(s)}</p>"

    skills_html = "\n".join(skill_to_html(s) for s in skills_lines)

    def job_to_html(j):
        bullets = "\n".join(f"<li>{html_lib.escape(b)}</li>" for b in j["bullets"])
        return f"""
  <div class="job">
    <div class="job-header">
      <span class="job-company">{html_lib.escape(j['company'])}</span>
      <span class="job-date">{html_lib.escape(j['date'])}</span>
    </div>
    <div class="job-title">{html_lib.escape(j['title'])}</div>
    <ul>{bullets}</ul>
  </div>"""

    exp_html = "\n".join(job_to_html(j) for j in exp_blocks)
    edu_html = "\n".join(f"<p>{html_lib.escape(l)}</p>" for l in education_lines if l)
    cert_html = "\n".join(f"<p>{html_lib.escape(l)}</p>" for l in cert_lines if l)

    # Build contact bar HTML from parsed parts
    contact_html_parts = []
    for part in contact_parts:
        if part.startswith("http") or "." in part.split("@")[0] if "@" not in part else False:
            contact_html_parts.append(f'<a href="https://{html_lib.escape(part)}">{html_lib.escape(part)}</a>')
        elif "@" in part:
            contact_html_parts.append(f'<a href="mailto:{html_lib.escape(part)}">{html_lib.escape(part)}</a>')
        else:
            contact_html_parts.append(html_lib.escape(part))
    contact_bar = ' <span class="sep">·</span> '.join(contact_html_parts)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>{first_name} {last_name} — {html_lib.escape(job_title)}</title>
<style>
  /* ── Page setup: consistent margins on ALL pages via @page ── */
  @page {{
    size: letter;
    margin: 0.55in 0.65in;
  }}

  * {{ margin: 0; padding: 0; box-sizing: border-box; }}

  body {{
    font-family: 'Calibri', 'Gill Sans', 'Trebuchet MS', Arial, sans-serif;
    font-size: 10.5pt; color: #1a1a1a; background: #fff;
    padding: 0.55in 0.65in; max-width: 8.5in; margin: 0 auto; line-height: 1.4;
  }}

  .header {{ text-align: center; margin-bottom: 6px; }}
  .header h1 {{ font-size: 28pt; font-weight: 700; letter-spacing: 0.5px; color: #1a1a1a; line-height: 1.1; }}
  .header h1 span {{ color: #2563EB; }}
  .header .title {{ font-size: 10pt; letter-spacing: 2.5px; text-transform: uppercase; color: #555; margin: 3px 0 6px; font-weight: 400; }}
  .contact {{ font-size: 9.5pt; color: #333; }}
  .contact a {{ color: #2563EB; text-decoration: none; }}
  .contact .sep {{ margin: 0 6px; color: #999; }}

  .section-header {{
    text-align: center; font-size: 9.5pt; font-weight: 700; letter-spacing: 2px;
    text-transform: uppercase; color: #1a1a1a; margin: 14px 0 6px;
    padding-bottom: 3px; border-bottom: 1px solid #d0d0d0;
    /* Keep header glued to the content that follows it */
    page-break-after: avoid; break-after: avoid;
  }}

  .skills p {{ margin-bottom: 3px; font-size: 10pt; }}

  .job {{ margin-bottom: 12px; }}
  .job-header {{
    display: flex; justify-content: space-between; align-items: baseline; margin-bottom: 1px;
    page-break-after: avoid; break-after: avoid;
  }}
  .job-company {{ font-weight: 700; font-size: 10.5pt; color: #1a1a1a; }}
  .job-date {{ font-size: 10pt; color: #333; white-space: nowrap; margin-left: 12px; }}
  .job-title {{
    font-style: italic; font-size: 10pt; color: #444; margin-bottom: 4px;
    page-break-after: avoid; break-after: avoid;
  }}
  .job ul {{ padding-left: 16px; margin: 0; }}
  .job ul li {{
    margin-bottom: 3px; font-size: 10pt; line-height: 1.45;
    page-break-inside: avoid; break-inside: avoid;
  }}

  .summary {{ font-size: 10.5pt; line-height: 1.5; text-align: justify; orphans: 3; widows: 3; }}
  .simple-list p {{ font-size: 10.5pt; margin-bottom: 2px; }}

  /* ── Print: zero out body padding — @page margin handles all spacing ── */
  @media print {{
    body {{ padding: 0; max-width: 100%; margin: 0; }}
  }}
</style>
</head>
<body>
<div class="header">
  <h1>{first_name} <span>{last_name}</span></h1>
  <div class="title">{html_lib.escape(candidate_title)}</div>
  <div class="contact">{contact_bar}</div>
</div>
<div class="section-header">Professional Summary</div>
<div class="summary">{html_lib.escape(summary_text.strip())}</div>
<div class="section-header">Technical Skills</div>
<div class="skills">{skills_html}</div>
<div class="section-header">Professional Experience</div>
{exp_html}
<div class="section-header">Education</div>
<div class="simple-list">{edu_html}</div>
<div class="section-header">Certifications</div>
<div class="simple-list">{cert_html}</div>
</body>
</html>"""


# ── CDP PDF generation (no headers/footers) ───────────────────────────────────
def _generate_pdf_cdp(html_path: Path, pdf_path: Path) -> None:
    """Generate a clean PDF via Chrome DevTools Protocol with no header/footer."""
    import json as _json
    import random
    import urllib.request
    import websocket  # websocket-client

    chrome = Path(CHROME_PATH)
    if not chrome.exists():
        print(f"  Chrome not found at {CHROME_PATH} — skipping PDF")
        return

    # Use a random high port to avoid conflicts with existing Chrome sessions
    debug_port = random.randint(19000, 19999)
    proc = subprocess.Popen(
        [
            str(chrome),
            "--headless=new",
            "--disable-gpu",
            "--no-sandbox",
            f"--remote-debugging-port={debug_port}",
            "--remote-allow-origins=*",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    try:
        # Wait for Chrome to be ready — poll /json (not /json/new)
        ws_url = None
        for _ in range(40):
            time.sleep(0.5)
            try:
                with urllib.request.urlopen(
                    f"http://localhost:{debug_port}/json", timeout=2
                ) as resp:
                    tabs = _json.loads(resp.read())
                    # Find a page tab or open a new one
                    for tab in tabs:
                        if tab.get("type") == "page":
                            ws_url = tab["webSocketDebuggerUrl"]
                            break
                    if not ws_url:
                        with urllib.request.urlopen(
                            f"http://localhost:{debug_port}/json/new", timeout=2
                        ) as r2:
                            tab = _json.loads(r2.read())
                            ws_url = tab["webSocketDebuggerUrl"]
                    break
            except Exception:
                continue

        if not ws_url:
            print("  CDP: Chrome did not start in time — skipping PDF")
            return

        ws = websocket.create_connection(ws_url, timeout=30)

        def send(method, params=None):
            _id = send._counter
            send._counter += 1
            msg = _json.dumps({"id": _id, "method": method, "params": params or {}})
            ws.send(msg)
            while True:
                raw = ws.recv()
                data = _json.loads(raw)
                if data.get("id") == _id:
                    return data
        send._counter = 1

        # Enable Page domain and navigate
        send("Page.enable")
        send("Page.navigate", {"url": html_path.resolve().as_uri()})

        # Wait for page load
        time.sleep(2)

        # Print to PDF — no header/footer, use CSS @page size
        result = send("Page.printToPDF", {
            "displayHeaderFooter": False,
            "printBackground": True,
            "preferCSSPageSize": True,
        })

        pdf_data = base64.b64decode(result["result"]["data"])
        pdf_path.write_bytes(pdf_data)
        ws.close()
        print(f">> PDF: {pdf_path}")

    except Exception as e:
        print(f"  PDF generation failed: {e}")
    finally:
        proc.terminate()
        proc.wait(timeout=5)


# ── Step 5: Save all files to per-job folder ──────────────────────────────────
def save_job_folder(
    jd_text: str,
    analysis: dict,
    tailored_resume: str,
    cover_snippet: str,
) -> Path:
    """Save all files into applications/YYYYMMDD_Company_JobTitle/"""
    company_slug = re.sub(r"\W+", "_", analysis.get("company", "Unknown")).strip("_")[:25]
    title_slug = re.sub(r"\W+", "_", analysis.get("job_title", "Role")).strip("_")[:35]
    date_slug = datetime.now().strftime("%Y%m%d")
    folder_name = f"{date_slug}_{company_slug}_{title_slug}"
    job_dir = APPLICATIONS_DIR / folder_name
    job_dir.mkdir(exist_ok=True)

    # 1. Job description
    (job_dir / "job_description.txt").write_text(jd_text, encoding="utf-8")

    # 2. Posting metadata
    posting = f"""# {analysis.get('job_title')} @ {analysis.get('company')}

- **Date Found:** {datetime.now().strftime('%Y-%m-%d')}
- **Location:** {analysis.get('work_mode')}
- **Seniority:** {analysis.get('seniority')}
- **Domain:** {analysis.get('domain')}
- **Match Score:** {analysis.get('match_score')}/100
- **Application Status:** Not yet applied

## Key Requirements
{chr(10).join('- ' + r for r in analysis.get('key_requirements', []))}

## Gaps to Address
{chr(10).join('- ' + g for g in analysis.get('match_gaps', []))}

## ATS Keywords
{', '.join(analysis.get('keywords_ats', []))}
"""
    (job_dir / "posting.md").write_text(posting, encoding="utf-8")

    # 3. Resume markdown
    (job_dir / "resume.md").write_text(tailored_resume, encoding="utf-8")

    # 4. Cover letter
    (job_dir / "cover_letter.md").write_text(cover_snippet, encoding="utf-8")

    # 5. Analysis JSON
    (job_dir / "analysis.json").write_text(json.dumps(analysis, indent=2), encoding="utf-8")

    # 6. HTML resume
    html_content = build_html(tailored_resume, analysis.get("job_title", ""), analysis.get("company", ""))
    html_path = job_dir / "resume.html"
    html_path.write_text(html_content, encoding="utf-8")

    # 7. PDF via Chrome CDP (no headers/footers)
    pdf_path = job_dir / "resume.pdf"
    _generate_pdf_cdp(html_path, pdf_path)

    print(f">> Saved to: {job_dir}")
    return job_dir


# ── Main ───────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(
        description="Tailor your resume to a specific job description using Claude."
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--jd", type=Path, help="Path to job description text file")
    group.add_argument("--jd-text", type=str, help="Job description as a string")

    parser.add_argument(
        "--no-cover", action="store_true",
        help="Skip cover letter snippet generation"
    )
    parser.add_argument(
        "--show-analysis", action="store_true",
        help="Print the JD analysis to stdout"
    )
    args = parser.parse_args()

    # Load job description
    if args.jd:
        if not args.jd.exists():
            sys.exit(f"Error: JD file not found: {args.jd}")
        jd_text = args.jd.read_text(encoding="utf-8")
    else:
        jd_text = args.jd_text

    if not jd_text.strip():
        sys.exit("Error: Job description is empty.")

    # Load base resume
    if not BASE_RESUME.exists():
        example = BASE_RESUME.parent / "resume_base.example.md"
        sys.exit(
            f"Error: Base resume not found at {BASE_RESUME}\n"
            f"Copy the template and fill in your details:\n"
            f"  cp {example} {BASE_RESUME}"
        )
    base_resume = BASE_RESUME.read_text(encoding="utf-8")

    # Initialize Claude client
    client = get_client()

    # Run pipeline
    print("\n=== Resume Tailoring Pipeline ===\n")

    analysis = analyze_jd(client, jd_text)

    if args.show_analysis:
        print("\n--- JD Analysis ---")
        print(json.dumps(analysis, indent=2))
        print()

    print(f"  Job: {analysis.get('job_title')} @ {analysis.get('company')}")
    print(f"  Match score: {analysis.get('match_score')}/100")
    print(f"  Gaps: {', '.join(analysis.get('match_gaps', ['None']))}")

    tailored = tailor_resume(client, base_resume, analysis)

    candidate_name = parse_resume_header(base_resume)["name"]
    cover = ""
    if not args.no_cover:
        cover = generate_cover_snippet(client, analysis, candidate_name)

    # Save everything to per-job folder
    job_dir = save_job_folder(jd_text, analysis, tailored, cover)

    print("\n=== Done ===")
    print(f"\nFolder: {job_dir}")
    print(f"\nTop ATS keywords to verify are in your resume:")
    for kw in analysis.get("keywords_ats", [])[:10]:
        print(f"  - {kw}")


if __name__ == "__main__":
    main()
