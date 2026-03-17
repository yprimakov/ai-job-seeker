# Release Notes

---

## v0.9.0 — 2026-03-17

### Full Cover Letter Generator (`pipeline/cover_letter.py`)

- **New: `pipeline/cover_letter.py`** — Generates a complete, submission-ready 3-paragraph cover letter via Claude Opus. Auto-loads `analysis.json` and `job_description.txt` from the matching `applications/` folder when available. Saves to `cover_letter_full.md` alongside the tailored resume. `--stdout` flag for quick preview.

---

## v0.8.0 — 2026-03-17

### Response Tracking + Analytics (`pipeline/response_tracker.py`)

- **Updated: `tracker.py`** — Added `Date Response Received` and `Response Type` columns to `TRACKER_HEADERS`. Added `log-response` command to manually record a response. Added `stats` command: response rate by work mode, easy apply vs direct, response type breakdown, average days to response.

- **New: `pipeline/response_tracker.py`** — Polls `leoprime.dev@gmail.com` for replies from applied companies. Matches sender domain to company name using subdomain stripping + token overlap; handles ATS notification domains (Greenhouse, Lever, Workday, etc.) by extracting company name from Subject. Classifies responses (Phone Screen / Interview / Assessment / Offer / Rejected / Other) via Claude Haiku batch call. Updates tracker CSV in place. `--dry-run`, `--install` (Task Scheduler, daily at 09:05), `--setup` (Gmail OAuth).

---

## v0.7.0 — 2026-03-17

### LinkedIn Job Scraper (`pipeline/linkedin_scraper.py`)

- **New: `pipeline/linkedin_scraper.py`** — LinkedIn job discovery in two modes:
  - **Module mode** (Claude browser session): `SCRAPE_JOBS_JS` extracts all job cards from the current LinkedIn search page with multiple fallback selectors. `NEXT_PAGE_JS` paginates. `LOGIN_CHECK_JS` verifies auth state. `build_search_url()` constructs search URLs with remote/easy-apply/date filters. `score_jobs()` uses Claude Haiku to score each job 1-5 against Yury's profile with fit reason and gap notes. `save_results()` writes a ranked markdown table to `jobs/linkedin_results.md`.
  - **CLI mode** (standalone): `python pipeline/linkedin_scraper.py --query "..." --pages 3 --remote --easy-apply` — uses Playwright in headed mode for authenticated scraping. Requires `pip install playwright && playwright install chromium`.

---

## v0.6.0 — 2026-03-17

### Application Folder as Source of Truth (`tracker.py repair`)

- **Updated: `tracker.py`** — `cmd_log` now auto-resolves `Tailored Resume File` from the `applications/` folder when `--resume-file` is not provided. Uses token-score matching against folder names (company slug + title slug, score >= 2 required to prevent false positives).

- **New: `tracker.py repair`** — Backfills missing `Tailored Resume File` paths across all existing tracker rows. Safe to re-run; skips rows that already have a path. Ran on existing data: 1 row fixed (FDE @ Anthropic).

---

## v0.5.0 — 2026-03-17

### Tracker Dedup, Salary Normalization, and Follow-Up Automation

- **Updated: `tracker.py`** — `cmd_log` now checks for duplicate (Company + Job Title) before writing; skips silently if already logged. Salary is normalized to `$NNNk-$MMMk` format via new `normalize_salary()`. `Follow Up Date` auto-sets to today + 7 days when not provided.

- **New: `pipeline/followup.py`** — Daily follow-up draft creator.
  - Reads `application_tracker.csv`, finds rows where `Application Status == "Applied"` and `Follow Up Date <= today`.
  - Creates Gmail drafts for each due application (addressed to self for review before sending).
  - `--dry-run` mode lists due applications without creating drafts.
  - `--install` registers a Windows Task Scheduler job (`JobSeekerFollowUp`) to run daily at 09:00.
  - `--setup` runs one-time Gmail OAuth flow (`gmail.compose` scope).

- **Updated: `pipeline/requirements.txt`** — Added `google-auth`, `google-auth-oauthlib`, `google-auth-httplib2`, `google-api-python-client` for Gmail API access.

---

## v0.4.0 — 2026-03-17

### ATS Automation — Combobox, Q&A, and Auto-Log (`pipeline/ats/`)

- **New: `ats/combobox.py`** — JS-based combobox selector. `build_select_script(label, option)` and `build_select_many_script(selections)` generate async JS that finds a combobox by its visible label text, opens the dropdown, waits for React to render, and clicks the matching option — all in one `javascript_tool` call. Eliminates the screenshot → coordinate calculation → click → verify cycle for every dropdown. Supports React Select, native `<select>`, and generic `ul > li` dropdown patterns.

- **New: `ats/qa_matcher.py`** — Q&A auto-injection engine. `match_questions(discovered)` takes the list of form fields from `DISCOVER_QUESTIONS_JS` and matches each against `application_qa.csv` using a 3-tier strategy: exact label match → domain-specific keyword overlap (with an expanded stopword list to prevent false positives) → Claude Haiku semantic batch match. Returns `(matched_dict, unmatched_list)` — matched answers go straight into `fill_script(extra_fields=)`, unmatched are surfaced for user input.

- **New: `ats/auto_log.py`** — Automatic application logging on confirmation. `CONFIRM_JS` detects confirmation pages via URL patterns (`/confirmation`, `/thank`, `/success`), page title, and body text. `log_application(...)` calls `tracker.py log` via subprocess with all relevant fields including auto-calculated follow-up date (+7 days). `find_resume_for_application(company, title)` searches the `applications/` folder to resolve the resume path automatically.

---

## v0.3.0 — 2026-03-17

### ATS Automation Layer (`pipeline/ats/`)

- **New: `ats/detector.py`** — Identifies the ATS from the job posting URL (Greenhouse, Lever, Workday, Ashby, iCIMS, SmartRecruiters, LinkedIn). Also provides `DETECT_JS` for in-browser DOM detection when URLs are ambiguous (white-labeled domains).

- **New: `ats/filler.py`** — Batch JS field injector. `build_fill_script(field_map)` generates a single self-contained JS snippet that fills all text/textarea fields at once via React's synthetic event system. One `javascript_tool` call replaces ~20 individual fill-and-verify cycles. Also provides `DISCOVER_JS` to enumerate all fillable fields on any page.

- **New: `ats/greenhouse.py`** — Greenhouse-specific field maps and fill strategy. `fill_script(company_name, extra_fields)` generates a ready-to-inject batch fill script with standard fields pre-populated from `PROFILE` and the company's `+jobs` email address. `EEO_ANSWERS` maps all 5 EEO combobox labels to the correct option text. `DISCOVER_QUESTIONS_JS` enumerates all `question_*` custom fields per form.

- **New: `ats/poller.py`** — Security code poller. Two modes:
  - **Module mode** (used by Claude during sessions): `build_query(company, after)` generates a Gmail search string; `extract_code(body)` extracts the 8-char code via a 3-tier regex strategy (near trigger words → digit+letter mix → mixed case). Tested against 6 real code formats.
  - **CLI mode** (standalone): `python pipeline/ats/poller.py --company anthropic` polls the Gmail API directly in a configurable loop. One-time OAuth setup via `--setup` flag.

---

## v0.2.0 — 2026-03-17

### Candidate Profile System
- **New: `pipeline/profile.py`** — Single source of truth for all personal information. Loads from environment variables so the pipeline is reusable by anyone without code changes.
  - `PROFILE` dict exposes `first_name`, `last_name`, `full_name`, `email_base`, `email_domain`, `forwarding_email`, `phone`, `website`, `linkedin`, `location`, `current_employer`
  - `application_email(company)` helper constructs `+jobs-<company>` tagged addresses automatically (e.g. `myemail+jobs-google@gmail.com`)
- **Updated: `.env`** — Added 10 `CANDIDATE_*` variables for all personal info. API key remains the only non-profile variable.
- **New: `.env.example`** — Committed template with placeholder values so new users know exactly what to configure.
- **Updated: `pipeline/tailor_resume.py`** — Removed hardcoded name and employer references from prompt strings. Now reads from `PROFILE`.

### First-Time Setup Command
- **New: `pipeline/init.py`** — Interactive initialization wizard. Run once when setting up the pipeline for the first time.
  - Prompts for `ANTHROPIC_API_KEY` if not already set
  - Asks user to place their resume in `resume/` folder, then auto-extracts contact details (supports PDF via pypdf, DOCX via python-docx)
  - Uses Claude Haiku to parse name, email, phone, website, LinkedIn, location, and current employer from resume text
  - Presents extracted values as editable defaults — press Enter to accept, type to override
  - Always asks manually for `CANDIDATE_FORWARDING_EMAIL` (bot inbox, not on any resume)
  - Writes each field individually via `dotenv.set_key()` — safe to re-run without clobbering existing values
- **Updated: `pipeline/requirements.txt`** — Added `pypdf>=4.0.0` for PDF resume parsing.

### Email Forwarding Convention
- All job application forms now use `{email_base}+jobs-{company}@{email_domain}` format
- Zapier MCP Gmail integration verified working end-to-end with test send/receive

### Planning
- **New: `pipeline/PIPELINE_IMPROVEMENTS.md`** — Backlog of 12 planned pipeline enhancements across 3 priority tiers (P1 Speed, P2 Quality, P3 Strategic). See that file for details.

---

## v0.1.0 — 2026-03-15

### Initial Pipeline

- **`pipeline/tailor_resume.py`** — Core resume tailoring script. Takes a job description (file or pasted text), runs a two-stage Claude Opus pipeline (JD analysis → resume rewrite), and outputs a tailored resume as Markdown, HTML, and PDF.
  - JD analysis extracts: job title, company, role type, seniority, tech stack, ATS keywords, match score, gaps, and resume angles
  - HTML resume rendered with print-optimized CSS; PDF generated via Chrome DevTools Protocol (no headers/footers)
  - Cover letter snippet generated automatically unless `--no-cover` is passed
  - All output saved to `applications/YYYYMMDD_Company_JobTitle/` with `resume.md`, `resume.html`, `resume.pdf`, `cover_letter.md`, `analysis.json`, `posting.md`, `job_description.txt`

- **`pipeline/tracker.py`** — Application tracker and Q&A knowledge base CLI.
  - `log` — records a new application to `jobs/application_tracker.csv`
  - `question` — saves an unanswered form question to `jobs/application_qa.csv`
  - `answer` — stores the answer to a recorded question for future reuse
  - `pending` — lists all unanswered questions
  - `lookup` — semantic search across answered questions using Claude Haiku
  - `update-status` — updates application status (Applied, Phone Screen, Interview, Offer, Rejected, Withdrawn)
  - `list` — shows all logged applications

- **`pipeline/resume_base.md`** — Candidate's base resume in Markdown+HTML format. Source of truth for all tailored versions.

- **`jobs/application_qa.csv`** — Q&A knowledge base pre-populated with 16 common application questions and answers (salary, visa, EEO, AI policy, availability, etc.)

- **Google Drive integration** — Job Search 2026 folder structure created with sub-folders for Tailored Resumes, Job Listings, and Tracker. Accessible via Zapier MCP.

- **here.now integration** — Static file hosting for sharing resume previews via public URL. 24-hour TTL by default; permanent links on request.

- **Resume formatting rules** enforced in tailoring prompt:
  - No em dashes (`—`) anywhere
  - No horizontal rules (`---`)
  - Section headers wrapped in `<div align="center">`
  - Company entries: bold name with `float:right` date span, italic title on next line
  - Contact bar uses `&nbsp;·&nbsp;` separator

### First Applications Submitted
- 14 LinkedIn Easy Apply applications (March 15–16)
- 2 Greenhouse applications to Anthropic (Solutions Architect and Forward Deployed Engineer, March 16–17)
