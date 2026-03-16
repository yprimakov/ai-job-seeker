# AI Job Search Pipeline

An AI-powered job application pipeline that uses the Claude API to tailor your resume and cover letter to each job description — maximizing ATS keyword match and recruiter relevance, with zero manual rewriting.

---

## What it does

Given a job description, the pipeline:

1. **Analyzes** the JD with Claude — extracts ATS keywords, match score, skill gaps, and the best angles to highlight
2. **Rewrites** your base resume using the JD's exact language and priorities
3. **Generates** a targeted 3-paragraph cover letter snippet
4. **Exports** everything to a per-job folder: Markdown, styled HTML, and print-ready PDF
5. **Tracks** every application and builds a Q&A knowledge base so you never answer the same question twice

---

## Prerequisites

- Python 3.10+
- Google Chrome (used for PDF generation via Chrome DevTools Protocol)
- An [Anthropic API key](https://console.anthropic.com/)

---

## Setup

### 1. Clone the repo

```bash
git clone <repo-url>
cd job-seeker
```

### 2. Install dependencies

```bash
pip install -r pipeline/requirements.txt
```

### 3. Add your API key

```bash
cp .env.example .env
```

Edit `.env` and set your key:

```
ANTHROPIC_API_KEY=sk-ant-...
```

### 4. Create your base resume

The pipeline rewrites your resume for every job. Your base resume is the source of truth — fill it in once.

```bash
cp pipeline/resume_base.example.md pipeline/resume_base.md
```

Open `pipeline/resume_base.md` and replace the placeholder content with your own experience, skills, and contact info. Follow the formatting rules at the bottom of the example file — the pipeline depends on them for clean PDF output.

> **Note:** `pipeline/resume_base.md` is gitignored. Your personal resume never gets committed.

---

## Tailoring a resume

```bash
# From a saved JD file
python pipeline/tailor_resume.py --jd path/to/job_description.txt

# From text pasted directly (with full analysis printed)
python pipeline/tailor_resume.py --jd-text "paste the full job description here" --show-analysis

# Skip cover letter generation
python pipeline/tailor_resume.py --jd path/to/jd.txt --no-cover
```

Output is saved to `applications/YYYYMMDD_CompanyName_JobTitle/` and includes:

| File | Contents |
|------|----------|
| `resume.md` | Tailored resume in Markdown |
| `resume.html` | Styled, print-ready HTML |
| `resume.pdf` | PDF generated via Chrome |
| `cover_letter.md` | 3-paragraph cover letter snippet |
| `analysis.json` | Full JD analysis: ATS keywords, match score, gaps |
| `posting.md` | Job metadata summary |
| `job_description.txt` | Original JD text |

> **Note:** `applications/` is gitignored. Generated resumes never get committed.

---

## Tracking applications

All tracking data lives in `jobs/` (also gitignored). The `jobs/` folder and its CSV files are created automatically on first use.

```bash
# Log a completed application
python pipeline/tracker.py log \
  --company "Acme Corp" \
  --title "Senior AI Engineer" \
  --url "https://linkedin.com/jobs/view/..." \
  --mode Remote \
  --salary '$180K-$200K' \
  --easy-apply \
  --resume-file "applications/20260101_Acme_Corp_Senior_AI_Engineer/resume.pdf"

# Record a question you don't know how to answer mid-application
python pipeline/tracker.py question \
  --q "How many years of ML experience do you have?" \
  --context "Acme Corp Easy Apply"

# See all unanswered questions
python pipeline/tracker.py pending

# Answer a question (stored for reuse across all future applications)
python pipeline/tracker.py answer --id Q001 --answer "5 years of applied ML/AI"

# Look up if a similar question was already answered
python pipeline/tracker.py lookup --q "machine learning experience"

# Update an application's status
python pipeline/tracker.py update-status \
  --company "Acme Corp" --title "Senior AI Engineer" --status "Phone Screen"

# List all applications
python pipeline/tracker.py list
```

---

## Project structure

```
job-seeker/
├── pipeline/
│   ├── tailor_resume.py        # Main tailoring script (Claude API)
│   ├── tracker.py              # Application tracker + Q&A knowledge base
│   ├── resume_base.example.md  # Resume template — copy to resume_base.md
│   ├── resume_base.md          # YOUR resume (gitignored — create this yourself)
│   ├── dialog_watcher.py       # Windows helper: auto-fills file upload dialogs
│   ├── fonts/                  # Fonts used for HTML/PDF rendering
│   └── requirements.txt
├── applications/               # Per-job output folders (gitignored, auto-created)
├── jobs/                       # Tracker CSVs and Q&A knowledge base (gitignored, auto-created)
├── resume/                     # Your original resume files — PDF, DOCX (gitignored)
├── .env                        # Your API key (gitignored)
├── .env.example                # Template for .env
└── CLAUDE.md                   # Instructions for AI assistants working on this project
```

---

## Resume formatting rules

The pipeline enforces these rules in every tailored output. Your `resume_base.md` must follow them too, or the PDF layout will break.

- **No em dashes (`—`)** — use commas, colons, or semicolons instead
- **No horizontal rules (`---`)** between sections
- **Section headers** wrapped in `<div align="center">` tags
- **Company entries** use this exact format:
  ```
  **Company Name** <span style="float:right">Month YYYY – Month YYYY</span>
  *Job Title*
  ```
- **Contact bar** uses `&nbsp;·&nbsp;` as separator, centered in a `<div align="center">` block
- **Education and Certifications** — plain text lines, no bullets

See `pipeline/resume_base.example.md` for a complete working template.

---

## How the PDF is generated

The pipeline uses **Chrome DevTools Protocol (CDP)** to render the HTML resume and print it to PDF with no browser headers or footers. This requires Google Chrome to be installed. Chrome is auto-detected on Windows, macOS, and Linux.

If Chrome is not found, the Markdown and HTML outputs are still saved — only the PDF step is skipped.

---

## Q&A knowledge base

Every time you encounter a new question during an Easy Apply flow (salary expectations, years of experience, etc.), log it with `tracker.py question`. Once you answer it, that answer is stored and reused for similar questions in future applications — the lookup uses Claude for semantic matching, so "What is your salary expectation?" and "Expected compensation?" will match the same stored answer.
