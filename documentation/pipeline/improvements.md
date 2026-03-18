# Pipeline Improvement Backlog

## P1 — Speed (Immediate Impact)

- [x] **A. ATS Detection + Pre-Built Form Strategies** — Fingerprint the ATS on page load (Greenhouse, Lever, Workday, Ashby, iCIMS) and load a pre-built field map so form structure is known upfront, eliminating per-form discovery.
- [x] **B. Batch JS Injection** — Fill all text/textarea fields in a single JS call instead of one field at a time. Cuts form-filling tool calls by ~60%.
- [x] **E. Auto-Poll for Security Code** — After hitting Submit, automatically poll leoprime.dev@gmail.com every 5 seconds (up to 2 min) for a verification email matching the company name. No human relay needed.
- [x] **C. Combobox Keyboard Navigation** — Replace screenshot→coordinate→click cycle with Tab + type-to-filter + Enter. No screenshot needed between combobox steps.

## P2 — Quality & Reliability

- [x] **F. ATS-Aware Q&A Auto-Injection** — Before filling any form, semantically match every visible question against `application_qa.csv` and pre-populate answers. Only escalate unknowns to Yury.
- [x] **G. Auto-Log on Submit Confirmation** — Detect confirmation page (URL `/confirmation` or title "Thank you") and auto-run `tracker.py log` with resume path, URL, and timestamp. Eliminates manual step.
- [x] **H. Tracker Dedup + Validation** — Prevent duplicate rows by (Company + Job Title). Validate salary format. Auto-set Follow Up Date to +7 days from application date.
- [x] **I. Application Folder as Source of Truth** — Folder name is canonical key; tracker always links to it. Fix missing resume file references.

## P3 — Strategic

- [x] **J. LinkedIn Job Scraping Pipeline** — Automate job discovery: run search queries, extract job cards, score against profile with Claude, output ranked shortlist.
- [x] **K. Response Tracking + Feedback Loop** — Add `Date Response Received` + `Response Type` to tracker. When leoprime.dev receives a reply from an applied company, auto-update the row. Correlate response rates with match score, resume angle, ATS, salary range over time.
- [x] **L. Full Cover Letter Generator** — For non-Easy-Apply jobs with a cover letter field, generate a full 3-paragraph personalized letter (separate prompt) rather than just a snippet.
