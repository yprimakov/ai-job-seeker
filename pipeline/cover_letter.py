"""
Full Cover Letter Generator
===========================
Generates a polished, submission-ready 3-paragraph cover letter for a specific
job application. Unlike the snippet in tailor_resume.py, this produces a
complete letter with salutation, body, and sign-off.

The generator uses the JD analysis from analysis.json (if available in the
applications/ folder for this role) to personalize the content.

Usage:
    # From an existing applications/ folder (auto-loads analysis.json + JD)
    python pipeline/cover_letter.py --company "Anthropic" --title "AI Engineer"

    # From a JD file
    python pipeline/cover_letter.py --company "Acme" --title "Staff AI Engineer" \
        --jd path/to/jd.txt

    # From pasted text
    python pipeline/cover_letter.py --company "Acme" --title "Staff AI Engineer" \
        --jd-text "Full JD here..."

    # Print to stdout instead of saving
    python pipeline/cover_letter.py --company "Acme" --title "Staff AI Engineer" \
        --jd path/to/jd.txt --stdout
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path

import anthropic
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

sys.path.insert(0, str(Path(__file__).parent))
from profile import PROFILE

APPS_DIR = Path(__file__).parent.parent / "applications"
APPS_DIR.mkdir(exist_ok=True)


# ── Prompt ─────────────────────────────────────────────────────────────────────

COVER_LETTER_PROMPT = """\
You are writing a professional cover letter for {full_name}, a Principal AI Engineer \
with 15+ years of experience specializing in LLM integration, RAG systems, and \
autonomous agentic AI workflows.

CANDIDATE PROFILE:
- Name: {full_name}
- Current employer: {current_employer}
- Location: {location}
- Core strengths: LLM integration, RAG systems, autonomous AI agents, agentic \
workflows, multi-model orchestration, Python/FastAPI, Next.js/React, \
Docker/Kubernetes, C#/.NET
- AI tools: Claude API, OpenAI API, Gemini API, Ollama, Pinecone, LangChain, n8n

TARGET ROLE:
- Company: {company}
- Title: {role_title}

JOB DESCRIPTION:
{jd_text}

{analysis_block}

Write a compelling, professional cover letter with exactly 3 paragraphs:

1. OPENING: Start with a strong, specific hook tied to {company}'s mission or \
a notable thing they are known for. Immediately connect it to the candidate's \
most directly relevant strength or recent project. Do NOT start with \
"I am writing to apply for..." or "I am excited to apply..."

2. BODY: Highlight 2-3 concrete achievements or projects that directly address \
the top requirements from the JD. Be specific: name the technology, the outcome, \
the scale. Show, don't tell. One of these examples should come from the candidate's \
independent AI engineering work.

3. CLOSING: Express genuine enthusiasm for THIS company specifically. Reference \
one thing that makes this role or company unique. Close with a direct, confident \
call to action requesting an interview to discuss how the candidate can contribute \
to a specific goal or challenge the company faces.

STRICT RULES:
- Address the letter to "Dear Hiring Team," (do not invent a name)
- Length: 300-360 words for the body (3 paragraphs combined)
- No em dashes anywhere (use commas, colons, or semicolons instead)
- Natural and confident tone, not formal or stuffy
- Never mention "I'm passionate about" or "I believe I would be a great fit"
- No bullet points in the letter body
- End with this exact sign-off block (on separate lines):

Sincerely,
{full_name}
{phone}  |  {email}  |  {website}

Return only the letter text, starting with "Dear Hiring Team," \
and ending with the sign-off block. No preamble.
"""


# ── Helpers ────────────────────────────────────────────────────────────────────

def _find_app_folder(company: str, title: str) -> Path | None:
    """Find the most recent applications/ folder for this company + title."""
    company_slug = re.sub(r"[^a-z0-9]+", "_", company.lower()).strip("_")
    title_slug   = re.sub(r"[^a-z0-9]+", "_", title.lower()).strip("_")
    best_folder, best_score = None, 0
    for folder in sorted(APPS_DIR.iterdir(), reverse=True):
        if not folder.is_dir():
            continue
        name = folder.name.lower()
        co_hits    = sum(1 for t in company_slug.split("_") if t and t in name)
        title_hits = sum(1 for t in title_slug.split("_")   if t and t in name)
        score = co_hits + title_hits
        if score > best_score:
            best_score = score
            best_folder = folder
    return best_folder if best_score >= 2 else None


def _load_jd_and_analysis(company: str, title: str, jd_path: str | None,
                           jd_text: str | None) -> tuple[str, dict | None]:
    """
    Return (jd_text, analysis_dict | None).
    Priority: explicit --jd / --jd-text > applications folder.
    """
    analysis = None

    if jd_text:
        return jd_text, analysis

    if jd_path:
        jd_text = Path(jd_path).read_text(encoding="utf-8")
        # Try to load analysis.json from the same folder
        folder = _find_app_folder(company, title)
        if folder:
            aj = folder / "analysis.json"
            if aj.exists():
                try:
                    analysis = json.loads(aj.read_text(encoding="utf-8"))
                except json.JSONDecodeError:
                    pass
        return jd_text, analysis

    # No explicit JD: look in applications folder
    folder = _find_app_folder(company, title)
    if folder:
        jd_file = folder / "job_description.txt"
        if jd_file.exists():
            jd_text = jd_file.read_text(encoding="utf-8")
        aj = folder / "analysis.json"
        if aj.exists():
            try:
                analysis = json.loads(aj.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                pass

    if not jd_text:
        sys.exit(
            "Error: No JD found. Provide --jd, --jd-text, or ensure an "
            "applications/ folder exists for this company + title."
        )
    return jd_text, analysis


def _build_analysis_block(analysis: dict | None) -> str:
    if not analysis:
        return ""
    lines = ["JD ANALYSIS (use this to prioritize which strengths to highlight):"]
    if analysis.get("key_requirements"):
        lines.append("Top requirements: " + ", ".join(analysis["key_requirements"][:5]))
    if analysis.get("resume_angles"):
        lines.append("Recommended angles: " + " | ".join(analysis["resume_angles"]))
    if analysis.get("match_gaps"):
        gaps = analysis["match_gaps"][:2]
        lines.append(f"Gaps to address or reframe: {', '.join(gaps)}")
    return "\n".join(lines)


def _output_path(company: str, title: str) -> Path:
    """Return the cover_letter_full.md path inside the applications/ folder."""
    folder = _find_app_folder(company, title)
    if folder:
        return folder / "cover_letter_full.md"
    # Fallback: create a dated folder name
    slug_co = re.sub(r"[^a-z0-9]+", "_", company.lower()).strip("_")
    slug_ti = re.sub(r"[^a-z0-9]+", "_", title.lower()).strip("_")
    date = datetime.now().strftime("%Y%m%d")
    folder = APPS_DIR / f"{date}_{slug_co}_{slug_ti}"
    folder.mkdir(parents=True, exist_ok=True)
    return folder / "cover_letter_full.md"


# ── Generator ──────────────────────────────────────────────────────────────────

def generate_cover_letter(
    company: str,
    title: str,
    jd_text: str,
    analysis: dict | None = None,
) -> str:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        sys.exit("Error: ANTHROPIC_API_KEY not set.")

    client = anthropic.Anthropic(api_key=api_key)

    prompt = COVER_LETTER_PROMPT.format(
        full_name=PROFILE["full_name"],
        current_employer=PROFILE["current_employer"],
        location=PROFILE["location"],
        phone=PROFILE["phone"],
        email=f"{PROFILE['email_base']}@{PROFILE['email_domain']}",
        website=PROFILE["website"],
        company=company,
        role_title=title,
        jd_text=jd_text[:6000],  # trim very long JDs
        analysis_block=_build_analysis_block(analysis),
    )

    print(f"> Generating cover letter for {title} @ {company}...")
    response = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=1200,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text.strip()


# ── CLI ────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Full cover letter generator")
    parser.add_argument("--company", required=True)
    parser.add_argument("--title", required=True)
    parser.add_argument("--jd", help="Path to job description text file")
    parser.add_argument("--jd-text", help="Paste the job description directly")
    parser.add_argument("--stdout", action="store_true",
                        help="Print to stdout instead of saving to file")
    args = parser.parse_args()

    jd_text, analysis = _load_jd_and_analysis(
        args.company, args.title,
        jd_path=args.jd,
        jd_text=args.jd_text,
    )

    letter = generate_cover_letter(
        company=args.company,
        title=args.title,
        jd_text=jd_text,
        analysis=analysis,
    )

    if args.stdout:
        print("\n" + letter)
        return

    out_path = _output_path(args.company, args.title)
    out_path.write_text(letter, encoding="utf-8")
    print(f"[ok] Cover letter saved to {out_path}")
    print(f"\n--- Preview (first 400 chars) ---\n{letter[:400]}...")


if __name__ == "__main__":
    main()
