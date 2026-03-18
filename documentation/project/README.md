# AI Job Search Pipeline

An AI-powered job application pipeline that uses the Claude API to tailor your resume, auto-fill application forms, and track every application — with zero manual rewriting and minimal human intervention.

---

## What it does

Given a job description, the pipeline:

1. **Analyzes** the JD with Claude — extracts ATS keywords, match score, skill gaps, and the best angles to highlight
2. **Rewrites** your base resume using the JD's exact language and priorities
3. **Generates** a targeted 3-paragraph cover letter snippet
4. **Exports** everything to a per-job folder: Markdown, styled HTML, and print-ready PDF
5. **Auto-fills** application forms — detects the ATS, batch-injects all fields in one JS call, selects comboboxes without screenshots
6. **Polls** your forwarding inbox for security codes automatically after submission
7. **Tracks** every application and builds a Q&A knowledge base so you never answer the same question twice
8. **Auto-logs** each application when the confirmation page is detected

---

## Prerequisites

- Python 3.10+
- Google Chrome (used for PDF generation via Chrome DevTools Protocol)
- An [Anthropic API key](https://console.anthropic.com/)

---

## Quick Start

### 1. Clone and install

```bash
git clone <repo-url>
cd job-seeker
pip install -r pipeline/requirements.txt
```

### 2. Run the setup wizard

The wizard reads your resume, extracts your contact details automatically, and writes everything to `.env`.

```bash
python pipeline/init.py
```

You'll be asked to:
- Provide your Anthropic API key (if not already set)
- Drop your resume (PDF or DOCX) into the `resume/` folder
- Review the auto-extracted profile fields and correct anything
- Provide a forwarding email address (where Claude reads security codes)

> **Email convention:** All application forms use `yourname+jobs-<company>@gmail.com`. Set up a Gmail filter to forward emails containing `+jobs` to your forwarding inbox. This lets the pipeline intercept security codes automatically and tells you which companies share your email.

### 3. Create your base resume

```bash
cp pipeline/resume_base.example.md pipeline/resume_base.md
```

Fill in your experience, skills, and contact info. See [Resume formatting rules](#resume-formatting-rules) below.

> `pipeline/resume_base.md` is gitignored — your personal resume is never committed.

---

## Tailoring a resume

```bash
# From a saved JD file
python pipeline/tailor_resume.py --jd path/to/job_description.txt

# From pasted text (with full analysis printed)
python pipeline/tailor_resume.py --jd-text "paste the full JD here" --show-analysis

# Skip cover letter generation
python pipeline/tailor_resume.py --jd path/to/jd.txt --no-cover
```

Output is saved to `applications/YYYYMMDD_CompanyName_JobTitle/`:

| File | Contents |
|------|----------|
| `resume.md` | Tailored resume in Markdown |
| `resume.html` | Styled, print-ready HTML |
| `resume.pdf` | PDF generated via Chrome CDP |
| `cover_letter.md` | 3-paragraph cover letter snippet |
| `analysis.json` | Full JD analysis: ATS keywords, match score, gaps |
| `posting.md` | Job metadata summary |
| `job_description.txt` | Original JD text |

> `applications/` is gitignored — generated resumes are never committed.

---

## Application form automation

The `pipeline/ats/` module handles browser-based form filling with minimal human interaction.

### How it works

```
URL → detect ATS → discover fields → match Q&A → batch fill → select comboboxes → submit → poll email → auto-log
```

1. **ATS detection** — identifies Greenhouse, Lever, Workday, Ashby, iCIMS, or SmartRecruiters from the URL
2. **Field discovery** — scans the page for all fillable fields in one JS call
3. **Q&A matching** — matches each field label against your knowledge base (exact → keyword → Claude semantic); only escalates genuinely new questions
4. **Batch fill** — injects all text/textarea answers in a single JS call via React's synthetic event system
5. **Combobox selection** — selects dropdown options by label text, no screenshot or coordinate math needed
6. **Security code polling** — after submit, polls your forwarding inbox every 5 seconds and enters the code automatically
7. **Auto-log** — detects the confirmation page and logs the application to `tracker.csv` with an auto-set follow-up date

### ATS module reference

| Module | Purpose |
|--------|---------|
| `ats/detector.py` | Identify ATS from URL or DOM |
| `ats/filler.py` | Batch JS field injection |
| `ats/greenhouse.py` | Greenhouse field maps, EEO answers, question discovery |
| `ats/combobox.py` | JS combobox selection by label text |
| `ats/qa_matcher.py` | Match form questions to Q&A knowledge base |
| `ats/poller.py` | Poll forwarding inbox for security codes |
| `ats/auto_log.py` | Detect confirmation page + auto-log to tracker |

---

## Application tracking

All tracking data lives in `jobs/` (gitignored, auto-created on first use).

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

# Record a new question encountered mid-application
python pipeline/tracker.py question \
  --q "How many years of ML experience do you have?" \
  --context "Acme Corp Easy Apply"

# See all unanswered questions
python pipeline/tracker.py pending

# Answer a question (stored for reuse across all future applications)
python pipeline/tracker.py answer --id Q001 --answer "5 years of applied ML/AI"

# Look up a previously answered question
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
│   ├── init.py                 # First-time setup wizard
│   ├── tailor_resume.py        # Resume tailoring (Claude API)
│   ├── tracker.py              # Application tracker + Q&A knowledge base
│   ├── profile.py              # Candidate profile loaded from .env
│   ├── ats/
│   │   ├── detector.py         # ATS fingerprinting
│   │   ├── filler.py           # Batch JS field injection
│   │   ├── greenhouse.py       # Greenhouse-specific field maps
│   │   ├── combobox.py         # JS combobox selector
│   │   ├── qa_matcher.py       # Q&A auto-matching engine
│   │   ├── poller.py           # Security code email poller
│   │   └── auto_log.py         # Confirmation detection + auto-log
│   ├── resume_base.example.md  # Resume template (copy to resume_base.md)
│   ├── resume_base.md          # YOUR resume (gitignored)
│   └── requirements.txt
├── applications/               # Per-job output folders (gitignored)
├── jobs/                       # Tracker CSVs + Q&A knowledge base (gitignored)
├── resume/                     # Your original resume files (gitignored)
├── command-center/             # Next.js web UI (see documentation/command-center/)
├── documentation/              # Project documentation
├── .env                        # API key + candidate profile (gitignored)
├── .env.example                # Template — copy to .env and fill in
└── CLAUDE.md                   # Instructions for AI assistants
```

---

## Resume formatting rules

The pipeline enforces these rules in every tailored output. Your `resume_base.md` must follow them or the PDF layout will break.

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

## How PDF generation works

The pipeline uses **Chrome DevTools Protocol (CDP)** to render the HTML resume and export it to PDF with no browser headers or footers. Chrome is auto-detected on Windows, macOS, and Linux.

If Chrome is not found, Markdown and HTML outputs are still saved — only the PDF step is skipped.

---

## Q&A knowledge base

Every new question you encounter during an application is stored in `jobs/application_qa.csv`. Once answered, it's reused for similar questions in all future applications. The matcher uses exact match, keyword overlap, and Claude semantic matching — so "What is your salary expectation?" and "Expected compensation?" resolve to the same answer.

The ATS automation layer consults this database automatically before filling any form. Only genuinely new questions are surfaced for your input.
