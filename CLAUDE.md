# Job Seeker — Claude Project Guide

## What We're Doing

Yury Primakov (Principal AI Engineer, Holmdel NJ) is actively job hunting. This project is a full AI-assisted job search pipeline. The goal is to:

1. **Find relevant jobs** on LinkedIn (remote or within 30 min of Holmdel, NJ; Easy Apply priority)
2. **Tailor his resume** to each job description using Claude API
3. **Track every application** in a spreadsheet, including questions encountered
4. **Preview files remotely** via here.now (permanent links) or Google Drive

---

## Candidate Profile

- **Name:** Yury Primakov
- **Title:** Principal AI Engineer
- **Location:** Holmdel, NJ
- **Email:** yprimakov@gmail.com | **Phone:** 718-757-6477
- **Website:** yuryprimakov.com
- **Experience:** 15+ years full-stack engineering, now specializing in applied AI
- **Core strengths:** LLM integration, RAG systems, autonomous AI agents, agentic workflows, Python/FastAPI, Next.js/React, Docker/Kubernetes, C#/.NET
- **AI tools:** Claude API, OpenAI API, Gemini API, Ollama, n8n, Pinecone, Hugging Face, LangChain

### Job Search Preferences
- **Location:** Remote OR within ~30 minutes drive from Holmdel, NJ
- **Priority filter:** Easy Apply on LinkedIn
- **Target roles:** Principal AI Engineer, Staff AI Engineer, Senior AI Engineer, AI Solutions Architect, AI/ML Engineer, Full Stack AI Engineer
- **Not interested in:** Mainframe, legacy enterprise without AI component

---

## Project Structure

```
C:\.Projects\job-seeker\
├── CLAUDE.md                        ← this file
├── .env                             ← ANTHROPIC_API_KEY (never commit)
├── .gitignore
├── resume\
│   ├── resume.pdf                   ← original resume
│   └── resume.docx                  ← original resume (Word)
├── pipeline\
│   ├── tailor_resume.py             ← main tailoring script (Claude API)
│   ├── tracker.py                   ← application tracker + Q&A knowledge base
│   ├── resume_base.md               ← base resume in Markdown (source of truth)
│   └── requirements.txt             ← anthropic, python-docx, python-dotenv
├── command-center\                  ← Next.js web UI (localhost:3000)
├── jobs\
│   ├── linkedin_results.md          ← LinkedIn search results with fit scores
│   ├── application_tracker.csv      ← one row per application
│   └── application_qa.csv           ← questions encountered + answers (memory)
├── applications\
│   └── YYYYMMDD_Company_JobTitle\   ← one folder per job
│       ├── job_description.txt      ← raw JD
│       ├── posting.md               ← metadata (salary, URL, match score, status)
│       ├── resume.md                ← tailored resume (markdown)
│       ├── resume.html              ← styled HTML version
│       ├── resume.pdf               ← print-ready PDF
│       ├── cover_letter.md          ← cover letter snippet
│       └── analysis.json            ← full JD analysis + ATS keywords
└── documentation\                   ← project documentation
    ├── project\
    │   ├── README.md                ← project overview and quick start
    │   └── release-notes.md         ← changelog
    ├── command-center\
    │   ├── requirements.md          ← full UI spec and design system
    │   └── improvements.md          ← completed fixes + pending backlog
    └── pipeline\
        └── improvements.md          ← pipeline feature backlog
```

---

## Pipeline Scripts

### tailor_resume.py
Analyzes a job description with Claude Opus and produces:
- A tailored resume (rewritten to match JD language and ATS keywords)
- A cover letter snippet
- A full JD analysis (match score, gaps, ATS keywords, angles)

```bash
# Install dependencies (first time)
pip install -r pipeline/requirements.txt

# Tailor resume from a JD file
python pipeline/tailor_resume.py --jd path/to/jd.txt

# Tailor from pasted text, show analysis
python pipeline/tailor_resume.py --jd-text "full JD here" --show-analysis

# Output as .docx
python pipeline/tailor_resume.py --jd path/to/jd.txt --format docx
```

Output saved to `output/<Company>_<Title>_<Date>.md`

### tracker.py
Manages two CSV files — the application log and the Q&A knowledge base.

```bash
# Log a new application
python pipeline/tracker.py log --company "People In AI" --title "Principal AI Engineer" \
    --url "https://linkedin.com/jobs/view/..." --mode Remote --salary "$275K-$325K" \
    --easy-apply --resume-file "output/PeopleInAI_Principal_20260315.md"

# Record a question you don't know how to answer during an application
python pipeline/tracker.py question --q "What is your expected salary?" \
    --context "People In AI Easy Apply"

# Show all unanswered questions (ask Yury for answers)
python pipeline/tracker.py pending

# Answer a question (stored for future reuse across all applications)
python pipeline/tracker.py answer --id Q001 --answer "My target is $200K-$250K base"

# Look up if a similar question was answered before
python pipeline/tracker.py lookup --q "salary expectations"

# Update application status
python pipeline/tracker.py update-status --company "People In AI" \
    --title "Principal AI Engineer" --status "Phone Screen"

# List all applications
python pipeline/tracker.py list
```

---

## Resume Formatting Rules

The base resume (`pipeline/resume_base.md`) and all tailored outputs must follow these rules — the tailor prompt enforces them:

- **NO em dashes (—)** — use commas, colons, or semicolons instead
- **NO horizontal rules (`---`)** — not between sections, not anywhere
- **Section headers** wrapped in `<div align="center">` tags
- **Company entries** formatted as:
  ```
  **Company Name** <span style="float:right">Month YYYY – Month YYYY</span>
  *Job Title*
  ```
- **Contact bar** uses `&nbsp;·&nbsp;` as separator, centered in a `<div align="center">` block
- **Education and Certifications** use plain text lines, no bullet points

---

## Remote File Access

### here.now (temporary public links)
- Account: yprimakov@gmail.com | API key: `~/.herenow/credentials`
- **Default: always use `--ttl 86400` (expires in 24 hours).** Only omit `--ttl` if Yury explicitly asks for a permanent link.
- Publish (default — 24hr expiry):
  ```bash
  bash ~/.agents/skills/here-now/scripts/publish.sh "/unix/path/to/file" --ttl 86400 --client claude-code
  ```
- Publish permanent (only when explicitly requested):
  ```bash
  bash ~/.agents/skills/here-now/scripts/publish.sh "/unix/path/to/file" --client claude-code
  ```
- Requires: `curl`, `jq`, `file` (jq installed via Chocolatey)
- Always use Unix-style paths: `/c/.Projects/...` not `C:\.Projects\...`

### Google Drive (secure, private)
Folder structure in Google Drive under **Job Search 2026**:

| Folder | Drive ID |
|--------|----------|
| Job Search 2026 (root) | `1uxwotEEGih6XZHfEpVAteemHKcaa-k-b` |
| Tailored Resumes | `19Gw4n_pkGc-sPLQgv-68vxQqAgfMOr20` |
| Job Listings | `12MA306S-weSkRl1Ah7f9r51JBV169O2n` |
| Tracker | `1i6B0AlDKgZkEAvrK_QICjajSEzAGlcHL` |

Google Drive is accessible via the Zapier MCP integration (`mcp__claude_ai_Zapier__google_drive_*`).

---

## Top Job Leads Found (2026-03-15)

| # | Role | Company | Salary | Fit |
|---|------|---------|--------|-----|
| 1 | Principal AI Engineer | People In AI | $275K–$325K | ⭐⭐⭐⭐⭐ |
| 2 | Staff ML/AI Engineer | D24 Search | $220K–$300K | ⭐⭐⭐⭐⭐ |
| 3 | AI Solutions Engineer – GenAI & Agentic AI | techolution | — | ⭐⭐⭐⭐⭐ |
| 4 | Senior Applied AI Eng / Tech Lead / Architect | Sectech Solutions | — | ⭐⭐⭐⭐ |
| 5 | Founding AI Engineer | Pocket | $150K | ⭐⭐⭐⭐ |
| 6 | AI Engineer | Hanalytica GmbH | $60/hr | ⭐⭐⭐ |
| 7 | AI Engineer (P&C Insurance) | James Search Group | — | ⭐⭐⭐ |

Full details in `jobs/linkedin_results.md`.

---

## Current Status (as of 2026-03-17)

- [x] Resume reviewed and base markdown created
- [x] Tailoring pipeline built (`tailor_resume.py`)
- [x] Application tracker + Q&A knowledge base built (`tracker.py`)
- [x] Google Drive folder structure created
- [x] here.now installed and authenticated
- [x] Resume formatting rules defined and enforced in prompt
- [x] Command Center web UI built and running (`command-center/`, localhost:3000)
- [ ] First tailored resume generated (next step: People In AI)
- [ ] First application submitted
- [ ] LinkedIn search expanded to additional role titles

See `documentation/command-center/improvements.md` for the full Command Center backlog.

---

## Notes & Preferences

- Yury prefers **concise responses** — no filler, no summaries of what was just done
- All file previews go via **here.now** (public, permanent) or **Google Drive** (private)
- The Q&A system in `tracker.py` is the memory for application questions — always check it before asking Yury for an answer
- When a question comes up during an application that isn't in the Q&A database, flag it to Yury and store his answer immediately
- Do not apply to jobs without generating a tailored resume first
- When asked to run the pipeline and submit applications, treat that as explicit confirmation to submit
