# AI Job Search Pipeline

An AI-powered job application pipeline that uses the Claude API to tailor your resume and cover letter to each job description, maximizing ATS keyword match and relevance.

## What it does

- **Analyzes** a job description with Claude Opus to extract ATS keywords, match score, and gaps
- **Rewrites** your base resume to match the JD's language, priorities, and required skills
- **Generates** a targeted cover letter snippet
- **Exports** to Markdown, HTML, and print-ready PDF
- **Tracks** every application and Q&A knowledge base across all jobs

## Quick start

### 1. Clone and install

```bash
git clone <repo-url>
cd job-seeker
pip install -r pipeline/requirements.txt
```

### 2. Add your API key

```bash
cp .env.example .env
# edit .env and add your ANTHROPIC_API_KEY
```

### 3. Create your base resume

```bash
cp pipeline/resume_base.example.md pipeline/resume_base.md
# edit pipeline/resume_base.md with your own content
```

### 4. Tailor a resume

```bash
# From a JD file
python pipeline/tailor_resume.py --jd path/to/job_description.txt

# From pasted text (with analysis output)
python pipeline/tailor_resume.py --jd-text "paste full JD here" --show-analysis

# Output as .docx
python pipeline/tailor_resume.py --jd path/to/jd.txt --format docx
```

Output is saved to `applications/<Date>_<Company>_<Title>/`.

## Project structure

```
job-seeker/
├── pipeline/
│   ├── tailor_resume.py        # Main tailoring script (Claude API)
│   ├── tracker.py              # Application tracker + Q&A knowledge base
│   ├── resume_base.example.md  # Resume template — copy to resume_base.md
│   ├── dialog_watcher.py       # Windows file dialog helper (for browser uploads)
│   ├── fonts/                  # Fonts used for PDF generation
│   └── requirements.txt
├── resume/                     # Your original resume files (gitignored)
├── applications/               # Per-job output folders (gitignored)
├── jobs/                       # Tracker CSVs and search results (gitignored)
├── output/                     # Legacy output folder (gitignored)
└── .env                        # API keys (gitignored)
```

## Tracking applications

```bash
# Log a new application
python pipeline/tracker.py log \
  --company "Acme Corp" \
  --title "Senior AI Engineer" \
  --url "https://linkedin.com/jobs/view/..." \
  --mode Remote \
  --salary '$200K-$220K' \
  --easy-apply \
  --resume-file "applications/20260101_Acme_Senior_AI_Engineer/resume.pdf"

# Record a question encountered during application
python pipeline/tracker.py question \
  --q "What is your expected salary?" \
  --context "Acme Easy Apply"

# List all pending unanswered questions
python pipeline/tracker.py pending

# Answer a question (stored for reuse)
python pipeline/tracker.py answer --id Q001 --answer "My target is $200K-$250K base"

# Look up if a question was answered before
python pipeline/tracker.py lookup --q "salary expectations"

# Update application status
python pipeline/tracker.py update-status \
  --company "Acme Corp" --title "Senior AI Engineer" --status "Phone Screen"

# List all applications
python pipeline/tracker.py list
```

## Requirements

- Python 3.10+
- `anthropic` — Claude API client
- `python-docx` — .docx export
- `python-dotenv` — .env loading
- `reportlab` or `weasyprint` — PDF generation (see requirements.txt)
- Anthropic API key (set `ANTHROPIC_API_KEY` in `.env`)

## Resume formatting rules

The pipeline enforces these rules in every tailored output:

- No em dashes — use commas, colons, or semicolons
- No horizontal rules between sections
- Section headers wrapped in `<div align="center">` tags
- Company entries: `**Company** <span style="float:right">Date</span>` / `*Title*`
- Contact bar: `&nbsp;·&nbsp;` separators, centered
- Education and Certifications: plain text, no bullets

See `pipeline/resume_base.example.md` for a full template.
