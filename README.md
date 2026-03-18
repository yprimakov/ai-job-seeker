# AI Job Search Pipeline

An AI-powered job search system that tailors your resume, tracks every application, and manages the full pipeline from job discovery to follow-up — with a local web Command Center and Claude API at the core.

## Screenshots

### Dashboard
![Dashboard](documentation/screenshots/dashboard.png)

### Applications List
![Applications](documentation/screenshots/applications-list.png)

### Application Detail — ATS Analysis
![ATS Analysis](documentation/screenshots/application-detail-ats.png)

### Job Queue
![Job Queue](documentation/screenshots/jobs-queue.png)

---

## What it does

Given a job description URL or text, the pipeline:

1. **Analyzes** the JD with Claude — extracts ATS keywords, match score (0-100), skill gaps, and the best angles to highlight
2. **Rewrites** your base resume using the JD's exact language and priorities
3. **Generates** a targeted 3-paragraph cover letter snippet
4. **Exports** everything to a per-job folder: Markdown, styled HTML, and print-ready PDF
5. **Tracks** every application and builds a Q&A knowledge base so you never answer the same question twice
6. **Monitors** ATS keyword coverage: shows before-tailoring and after-tailoring percentages per application
7. **Scores** each application with a match score and surfaces follow-up dates automatically

---

## Prerequisites

- Python 3.10+
- Node.js 18+
- Google Chrome (for PDF generation via Chrome DevTools Protocol)
- An [Anthropic API key](https://console.anthropic.com/)

---

## Quick Start

### 1. Clone and install

```bash
git clone <repo-url>
cd job-seeker
pip install -r pipeline/requirements.txt
cd command-center && npm install
```

### 2. Set up your environment

Copy `.env.example` to `.env` and fill in your details:

```bash
cp .env.example .env
```

Required variables:

```env
ANTHROPIC_API_KEY=sk-ant-...
CANDIDATE_NAME=Your Name
CANDIDATE_EMAIL=you@example.com
CANDIDATE_PHONE=555-555-5555
CANDIDATE_LOCATION=City, State
```

### 3. Create your base resume

```bash
cp pipeline/resume_base.example.md pipeline/resume_base.md
```

Edit `pipeline/resume_base.md` with your experience. See [Resume formatting rules](#resume-formatting-rules) below.

> `pipeline/resume_base.md` is gitignored — your personal resume is never committed.

### 4. Start the Command Center

```bash
cd command-center && npm run dev
```

Open [http://localhost:3000](http://localhost:3000). The Command Center provides a live dashboard, application table with ATS scores, job queue, Q&A knowledge base, and pipeline action buttons.

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
| `job_description.txt` | Original JD text |

> `applications/` is gitignored — generated resumes are never committed.

---

## Command Center

The Command Center is a Next.js web app (`command-center/`) that runs on `localhost:3000`. It provides:

- **Dashboard** — key metrics (total apps, response rate, pipeline stage counts, follow-ups due), funnel chart, recent activity
- **Applications** — sortable, filterable table with Match Score and ATS Coverage (before and after tailoring)
- **Application Detail** — editable status/notes, resume and cover letter preview, ATS keyword analysis with keyword-level breakdown, inline pipeline actions with streaming output
- **Job Queue** — paste a URL to queue a tailoring job; queue processes automatically in the background
- **Q&A Base** — unanswered questions flagged, click any row to edit inline
- **Analytics** — charts for application volume, funnel, response rates, match score vs response correlation
- **Settings** — candidate profile, pipeline config, integration status

See [documentation/command-center/](documentation/command-center/) for detailed usage and improvement history.

---

## Application tracking

```bash
# Log a completed application
python pipeline/tracker.py log \
  --company "Acme Corp" \
  --title "Senior AI Engineer" \
  --url "https://linkedin.com/jobs/view/..." \
  --mode Remote \
  --salary '$180K-$200K' \
  --easy-apply

# Record a question encountered mid-application
python pipeline/tracker.py question \
  --q "How many years of ML experience do you have?" \
  --context "Acme Corp Easy Apply"

# See all unanswered questions
python pipeline/tracker.py pending

# Answer a question (stored for reuse)
python pipeline/tracker.py answer --id Q001 --answer "5 years of applied ML/AI"

# Update an application's status
python pipeline/tracker.py update-status \
  --company "Acme Corp" --title "Senior AI Engineer" --status "Phone Screen"
```

---

## Project structure

```
job-seeker/
├── pipeline/
│   ├── tailor_resume.py        # Resume tailoring (Claude API)
│   ├── tracker.py              # Application tracker + Q&A knowledge base
│   ├── cover_letter.py         # Cover letter generation
│   ├── followup.py             # Follow-up email generator
│   ├── resume_base.md          # YOUR resume (gitignored)
│   ├── resume_base.example.md  # Template
│   └── requirements.txt
├── command-center/             # Next.js 14 web UI
│   ├── app/                    # App Router pages + API routes
│   ├── components/             # Reusable UI components
│   ├── lib/                    # CSV, WebSocket, utilities
│   └── server.js               # Custom server: Next.js + WebSocket + file watcher
├── applications/               # Per-job output folders (gitignored)
├── jobs/                       # Tracker CSVs + queue (gitignored)
├── resume/                     # Original resume files (gitignored)
├── documentation/              # Project and feature docs
├── .env                        # API keys + candidate profile (gitignored)
├── .env.example                # Template
└── CLAUDE.md                   # Instructions for AI assistants
```

---

## Resume formatting rules

The pipeline enforces these rules in every tailored output. Your `resume_base.md` must follow them or the PDF layout will break.

- **No em dashes (`---`)** — use commas, colons, or semicolons instead
- **No horizontal rules** between sections
- **Section headers** wrapped in `<div align="center">` tags
- **Company entries** use this exact format:
  ```
  **Company Name** <span style="float:right">Month YYYY – Month YYYY</span>
  *Job Title*
  ```
- **Contact bar** uses `&nbsp;·&nbsp;` as separator, centered in a `<div align="center">` block
- **Education and Certifications** — plain text lines, no bullets

---

## How PDF generation works

The pipeline uses Chrome DevTools Protocol (CDP) to render the HTML resume and export it to PDF with no browser headers or footers. Chrome is auto-detected on Windows, macOS, and Linux.

If Chrome is not found, Markdown and HTML outputs are still saved — only the PDF step is skipped.

---

## Q&A knowledge base

Every question encountered during an application is stored in `jobs/application_qa.csv`. Once answered, it's reused for similar questions across all future applications. The matcher uses exact match, keyword overlap, and Claude semantic matching.

Questions are surfaced in the Command Center Q&A page with unanswered ones highlighted at the top.
