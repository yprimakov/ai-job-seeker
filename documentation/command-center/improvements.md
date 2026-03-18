# Command Center — Improvements Backlog

Persistent record of completed fixes and planned enhancements for the Command Center UI.

---

## Completed

### v1.0 — Initial Build (2026-03-17)
- [x] Full Next.js 14 App Router setup with custom `server.js`
- [x] Glassmorphic card system (`SpotlightCard`, `AmbientBackground`)
- [x] Fixed left sidebar with logo, nav, theme toggle
- [x] All pages: Dashboard, Applications, Application Detail, Jobs, Q&A, Analytics, Settings
- [x] All API routes (applications CRUD, Q&A CRUD, analytics, settings, file serving, pipeline triggers)
- [x] WebSocket server with chokidar file watching
- [x] Password auth middleware (Edge Runtime compatible, WebCrypto SHA-256)

### v1.1 — Bug Fix Pass (2026-03-17)

**1. Border bleed at card corners**
- Replaced 4 separate `card-border-*` divs with a single CSS `::before` pseudo-element
  using `-webkit-mask-composite: xor` trick on `.glass-card-wrapper`
- Border now natively clips to `border-radius` without `overflow: hidden`

**2. Date off-by-one (activity feed, application table)**
- `formatDate()` in `lib/utils.ts` was parsing `YYYY-MM-DD` strings as UTC midnight
  which rendered as the previous day in US timezones
- Fixed: parse with `new Date(year, month-1, day)` to force local time interpretation

**3. PDF file serving 403 Forbidden**
- Root cause: CSV stores relative paths (`applications/20260315_.../resume.pdf`)
  but `path.resolve()` was resolving against `command-center/` CWD not project root
- Fixed in `app/api/file/route.ts`: `const ROOT = path.resolve(process.cwd(), '..')`
  and `path.resolve(ROOT, filePath)` for relative paths
- Also added case-insensitive path comparison for Windows

**4. LinkedIn scraper silent failure**
- Playwright requires a headed browser — can't run as a silent background process
- Fixed: spawn a visible Windows terminal (`cmd /c start cmd /k ...`), detached
  so Next.js doesn't wait for it
- WebSocket `results_updated` event fires automatically when `linkedin_results.md`
  changes via chokidar, refreshing the Jobs page

**5. Glassmorphic cards not rendering correctly**
- `--glass-outer` and `--glass-inner` CSS variables were referenced in `SpotlightCard`
  but never defined
- Fixed: added definitions to `:root` and `.dark` in `globals.css`
- Added `background: var(--glass-inner)` to `.spotlight-card` class

**6. Background orbs static (no animation)**
- Added 3 independent `@keyframes` lava lamp animations in `globals.css`:
  `orbFloat1` (28s), `orbFloat2` (35s), `orbFloat3` (22s)
- Added `.orb-1`, `.orb-2`, `.orb-3` animation classes
- Added wrapper divs inside each orb in `AmbientBackground.tsx`

**7. Q&A answers not persisting**
- Client was sending `{ answer }` (lowercase) in PATCH body
- API route expected `{ Answer }` (capital A, matching CSV column header)
- Fixed in `app/qa/page.tsx`: `JSON.stringify({ Answer: answer })`
- Also fixed field name references: `row.Context` → `row['Context (where it appeared)']`

**8. Spotlight corner artifacts + glow too bright**
- Both spotlight orbs (`::before`, `::after`) had non-zero opacity at rest
  causing visible glow at `translate(0,0)` = top-left corner
- Fixed: both orbs start `opacity: 0`, only revealed on `.spotlight-card:hover`
- Switched to `radial-gradient(..., transparent 70%)` for soft fade edges
- Reduced orb sizes and opacity values for subtler effect

**9. PDF preview ChunkLoadError / Object.defineProperty TypeError**
- `react-pdf` / `pdfjs-dist` has a webpack incompatibility with Next.js App Router
  (webpack redefines module properties that pdfjs locks on first load)
- Dropped `react-pdf` entirely. Replaced `PdfModal` with native `<iframe>` approach
- Zoom via `#zoom=` URL fragment (Chrome/Edge native PDF viewer supports it)
- `key={zoom}` forces iframe remount on zoom change

**10. Analysis panel 403 Forbidden**
- `analysisPath` was constructed from `resumePath` but `resumePath` is a PDF path
- Fixed: `resumePath.replace(/resume\.pdf$/i, 'analysis.json')` for correct path

**11. PDF thumbnail in Resume tab**
- Added small clickable scaled iframe thumbnail (200px wide) in Application Detail
- Click opens full-screen `PdfModal`
- Hover overlay indicates "Click to expand"

---

## Pending / Planned

### P1 — High Impact

- [ ] **Streaming pipeline output** (Task #8)
  Wire `POST /api/pipeline/tailor`, `cover-letter`, `followup` to stream stdout
  back to the browser via Server-Sent Events or WebSocket. Currently the output
  panel on Application Detail is static. Goal: real-time log lines as the Python
  scripts run.

- [ ] **Slug-based application IDs** (Task #9)
  Currently `/applications/[id]` uses the CSV row index as the ID. This breaks
  when rows are reordered or deleted. Replace with a stable slug derived from
  `YYYYMMDD_Company_Title` (the folder name), which is already the canonical key.
  - Update `GET /api/applications` to include a `slug` field
  - Update `PATCH /api/applications/[id]` to match by slug
  - Update the applications table to generate `href="/applications/{slug}"`

- [ ] **Job queue auto-processing** (Task #10)
  When a URL is added to the queue (POST /api/jobs/queue), automatically:
  1. Fetch the JD text from the URL (headless fetch or Playwright)
  2. Run `tailor_resume.py` against the JD
  3. Run `cover_letter.py`
  4. Mark queue entry as `ready`, broadcast via WebSocket
  Currently the queue is manual-only.

### P2 — Quality

- [ ] **Application detail timeline**
  Show ordered list of status changes with timestamps. Currently the detail
  page shows current status only. Requires adding a `Status History` field
  to the tracker CSV or a separate events log.

- [ ] **Bulk actions on Applications table**
  "Mark selected as Ghosted" and "Export selected rows as CSV" buttons.
  Currently all row actions are per-row only.

- [ ] **Q&A search / filter**
  Add keyword search and answered/unanswered filter to the Q&A page.
  Currently the full list is shown unsorted (unanswered at top).

- [ ] **Follow-up due badge on Dashboard**
  The "Follow-ups Due Today" metric card exists but clicking it doesn't
  navigate to a filtered Applications view. Wire it up.

### P3 — Strategic

- [ ] **Mobile-responsive layout**
  Sidebar collapses to bottom tab bar on narrow screens. Currently desktop-only.

- [ ] **Markdown resume editor**
  Inline editor for `resume.md` in the Application Detail file panel.
  Currently read-only preview. Would allow quick tweaks without touching the filesystem.

- [ ] **Cover letter preview**
  `cover_letter_full.md` preview tab in Application Detail currently shows
  raw markdown. Add rendered HTML preview (same approach as resume.md tab).
