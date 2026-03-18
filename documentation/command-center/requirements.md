# Job Seeker Command Center — Requirements

## Overview

A locally-hosted Next.js web application that serves as the single interface for
managing the entire job search pipeline. All pipeline scripts remain CLI-compatible;
the command center is a UI layer on top of them.

---

## Stack

| Layer | Technology |
|-------|-----------|
| Framework | Next.js 14+ (App Router) |
| Language | TypeScript |
| Styling | Tailwind CSS, Shadcn/ui |
| Charts | Recharts (or Tremor) |
| Real-time | WebSocket (via Next.js API route + `ws` library) |
| Auth | HTTP Basic Auth middleware (single env-var password) |
| Tunneling | here.now or ngrok (on-demand, triggered by CLI command) |
| Data layer | File-based (reads/writes CSV + JSON directly — no database) |

---

## Design System & Branding

The command center must match the visual identity of `yuryprimakov.com` exactly.
All design tokens, components, and motion behaviour are derived from
`brand/design_guide/` and `brand/assets/`.

### Logo

| Variant | File | Usage |
|---------|------|-------|
| White on black | `brand/assets/logo-iMadeFire-simple-white-on-black.svg` | Dark mode nav, dark backgrounds |
| Black on white | `brand/assets/logo-iMadeFire-simple-black-on-white.svg` | Light mode nav, light backgrounds |

The logo sits in the top-left of the sidebar/nav. It must **not** be re-coloured
or resized below 120px wide.

---

### Color Tokens (shadcn/ui + Tailwind Slate)

All tokens are CSS custom properties (`hsl(var(--token))`), applied via the
`.dark` class on `<html>`. Values are taken verbatim from the design reference.

**Light mode:**
```css
--background:          0 0% 100%;        /* #ffffff */
--foreground:          222.2 84% 4.9%;   /* #020817  slate-950 */
--primary:             222.2 47.4% 11.2%;/* #0f172a  slate-900 */
--primary-foreground:  210 40% 98%;      /* #f8fafc  slate-50  */
--secondary:           210 40% 96.1%;    /* #f1f5f9  slate-100 */
--muted:               210 40% 96.1%;    /* #f1f5f9            */
--muted-foreground:    215.4 16.3% 46.9%;/* #64748b  slate-500 */
--border:              214.3 31.8% 91.4%;/* #e2e8f0  slate-200 */
--ring:                222.2 84% 4.9%;   /* #020817            */
--destructive:         0 84.2% 60.2%;    /* #ef4444  red-500   */
```

**Dark mode:**
```css
--background:          222.2 84% 4.9%;   /* #020817  slate-950 */
--foreground:          210 40% 98%;       /* #f8fafc  slate-50  */
--primary:             210 40% 98%;       /* #f8fafc            */
--primary-foreground:  222.2 47.4% 11.2%;/* #0f172a            */
--secondary:           217.2 32.6% 17.5%;/* #1e293b  slate-800 */
--muted:               217.2 32.6% 17.5%;/* #1e293b            */
--muted-foreground:    215 20.2% 65.1%;  /* #94a3b8  slate-400 */
--border:              217.2 32.6% 17.5%;/* #1e293b  slate-800 */
--ring:                212.7 26.8% 83.9%;/* #cbd5e1  slate-300 */
--destructive:         0 62.8% 30.6%;    /* #7f1d1d  red-900   */
```

**Brand accent** — used on active nav items, primary buttons, focus states,
card hover glow borders, and key data highlights:
```
blue-500 — #3b82f6
```

**Primary button gradient:**
```
linear-gradient(to right, #60a5fa, #3b82f6, #2563eb)   /* blue-400 → blue-500 → blue-600 */
```

---

### Typography

- **Font:** System UI stack — no web fonts.
  `system-ui, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif`
- Renders as Segoe UI on Windows, SF Pro on macOS.
- All sizing via Tailwind defaults (`text-xs` through `text-4xl`).
- Section labels: `text-xs font-semibold uppercase tracking-wider text-muted-foreground`
- Page headings: `text-2xl font-bold tracking-tight`
- Card titles: `text-sm font-semibold`

---

### Ambient Background Orbs

Three `position: fixed`, `rounded-full`, `pointer-events-none` gradient divs
sit at `z-index: 0` behind all content. They shift between light and dark mode
via class swaps. Values from `theme_architecture.jsonc`:

| Orb | Size | Position | Light gradient | Dark gradient | Blur | Opacity |
|-----|------|----------|---------------|---------------|------|---------|
| 1 | 600x600px | top: -200px, left: -200px | blue-300 → sky-200 | purple-500 → slate-950 | 80px | 0.4 |
| 2 | 500x500px | bottom: -100px, right: -100px | orange-200 → yellow-300 | amber-500 → amber-600 | 60px | 0.3 |
| 3 | 400x400px | center (50%, 40%) | purple-300 → blue-300 | violet-700 → indigo-500 | 70px | 0.25 |

A subtle grid texture overlays the orbs:
`repeating-linear-gradient` 96px grid, `rgba(0,0,0,0.03)` lines.

The orbs live in `components/AmbientBackground.tsx`.

---

### Glassmorphic Card System

Every content panel uses a two-layer wrapper. All values Playwright-verified
from the live portfolio.

**Outer wrapper** (`SpotlightCard` outer div):
```
border-radius:    1.5rem  (rounded-3xl)
padding:          1px     <- hairline gap; glow bleeds through as rim light
backdrop-filter:  blur(12px)
background (light): rgba(241, 245, 249, 0.4)   /* slate-100 @ 40% */
background (dark):  rgba(15, 23, 42, 0.4)       /* slate-900 @ 40% */
```

**Inner surface**:
```
border-radius:    inherit
backdrop-filter:  blur(12px)
background (light): rgba(241, 245, 249, 0.6)   /* slate-100 @ 60% */
background (dark):  rgba(2, 6, 23, 0.7)         /* slate-950 @ 70% */
box-shadow (light): rgba(107, 33, 168, 0.15) 0px 25px 50px -12px
box-shadow (dark):  rgba(107, 33, 168, 0.30) 0px 25px 50px -12px
inset highlight:    inset 0px 1px 0px rgba(255,255,255,0.1)
```

**Hover state:** `transform: scale(1.02)` with `transition: 200ms ease-in-out`

**Animated border** (fades in on hover):
- CSS `::before` pseudo-element with mask-composite gradient on wrapper
- Gradient: `linear-gradient(135deg, transparent 15%, rgba(96,165,250,0.9) 45%, rgba(59,130,246,1) 55%, transparent 85%)`
- Uses `-webkit-mask-composite: xor` to clip to border-radius without overflow:hidden

The `SpotlightCard` component lives in `components/SpotlightCard.tsx`. All
dashboard cards, table panels, stat widgets, and form modals use it.

---

### Spotlight Mouse-Follow Glow Effect

Every `SpotlightCard` tracks the cursor and casts a soft diffused glow.

**Key numbers:**

| Property | Value |
|----------|-------|
| `::before` (white orb) | 400x400px, `blur(60px)`, `rgba(255,255,255,0.18)`, 0→1 on hover |
| `::after` (violet orb) | 480x480px, `blur(80px)`, `rgba(99,102,241,0.12)` dark / `rgba(139,92,246,0.08)` light |
| Opacity transition | 600ms |
| Mouse update throttle | `requestAnimationFrame`-gated flag |
| Both orbs start | `opacity: 0` — shown only on hover to prevent corner artifacts |

**Component:** `components/SpotlightCard.tsx`. RAF-throttled `mousemove` listener
sets `--mouse-x`/`--mouse-y` CSS custom properties per card. `overflow: hidden`
clips orbs to card bounds.

---

### Status Badge Colours

Application statuses map to gradient pills using the brand badge palette:

| Status | Gradient | CSS class |
|--------|----------|-----------|
| Applied | blue-500 → cyan-500 | `.badge-applied` |
| Phone Screen | sky-400 → indigo-600 | `.badge-phone-screen` |
| Interview | purple-500 → pink-500 | `.badge-interview` |
| Assessment | orange-400 → yellow-400 | `.badge-assessment` |
| Offer | green-500 → teal-600 | `.badge-offer` |
| Rejected | red-500 (solid) | `.badge-rejected` |
| Ghosted | slate-500 (muted, 60% opacity) | `.badge-ghosted` |

---

### Navigation

- **Sidebar layout** (not top nav) — fixed left sidebar, 240px wide, collapses to icon-only at 64px
- Logo at top of sidebar (iMadeFire SVG, correct variant per theme)
- Nav items: pill-shaped active state (`bg-background shadow-sm rounded-full`)
- Active item text: `blue-500`
- Bottom of sidebar: theme toggle (sun/moon) + tunnel status indicator

---

## 1. Authentication

- Single password stored in `.env` as `COMMAND_CENTER_PASSWORD`
- Next.js middleware intercepts all routes; prompts for password on first visit
- Session stored in a signed HTTP-only cookie (24-hour TTL)
- SHA-256 token computed via WebCrypto API (`crypto.subtle.digest`) for Edge Runtime compatibility
- No user accounts, no registration flow

---

## 2. Real-Time Updates

- A WebSocket server runs alongside the Next.js dev server (via `server.js`)
- A file watcher (`chokidar`) monitors:
  - `jobs/application_tracker.csv`
  - `jobs/application_qa.csv`
  - `jobs/linkedin_results.md`
  - `applications/` directory (new folders)
- On any file change, the server broadcasts a typed event to all connected clients
- Client receives the event and re-fetches only the affected data (no full page reload)
- Custom server (`server.js`) integrates Next.js handler + WebSocket upgrade on `/ws`

---

## 3. Navigation / Pages

| Route | Page |
|-------|------|
| `/` | Dashboard (stats + pipeline funnel) |
| `/applications` | Application tracker table |
| `/applications/[id]` | Single application detail + actions |
| `/jobs` | Job queue + LinkedIn results |
| `/qa` | Q&A knowledge base |
| `/analytics` | Full analytics and charts |
| `/settings` | Candidate profile + env var editor |

---

## 4. Dashboard (`/`)

- **Pipeline funnel** — horizontal bar or funnel chart showing counts at each stage:
  Applied → Phone Screen → Interview → Assessment → Offer → Rejected
- **Key metrics strip:**
  - Total applications
  - Response rate (%)
  - Active pipeline (non-rejected, non-ghosted)
  - Follow-ups due today
  - Unanswered Q&A questions
- **Recent activity feed** — last 10 events (application logged, response received,
  status changed, new job scraped)
- **Quick actions:** "Submit job URL", "Find new jobs", "Run follow-up check"

---

## 5. Application Tracker (`/applications`)

### Table view
- Columns: Date | Company | Title | Work Mode | Salary | Easy Apply | Status |
  Response Type | Follow-up Date | Resume
- Sortable by any column
- Filterable by: Status, Work Mode, Easy Apply, Has Response, Follow-up Due
- Search bar (fuzzy match on Company + Title)
- Color-coded status badges

### Row actions (inline or via detail page)
- Update status (dropdown, saves immediately via API route)
- Log response received (modal: response type + date + notes)
- Open resume PDF (link to `Tailored Resume File` path)
- Open job URL
- Trigger: Tailor resume (if not yet tailored)
- Trigger: Generate full cover letter
- Trigger: Open application form (launches browser form filler)

### Bulk actions
- Mark selected as Ghosted
- Export selected rows as CSV

---

## 6. Single Application Detail (`/applications/[id]`)

- Full row data displayed as a form (editable fields: status, notes, salary, work mode)
- Save button writes back to CSV via API route
- File panel: resume.md preview, cover_letter_full.md preview, analysis.json viewer
- PDF thumbnail (small clickable iframe preview) with full-screen modal on click
- Pipeline action buttons:
  - "Re-tailor resume" (runs `tailor_resume.py`)
  - "Generate cover letter" (runs `cover_letter.py`)
  - "Fill application form" (opens ATS form filler session)
  - "Generate follow-up draft" (runs `followup.py --company --title`)
- Q&A section: shows which Q&A entries were used for this application's form fill
- Timeline: ordered list of status changes with dates

---

## 7. Job Queue (`/jobs`)

### Submit job URL
- Input field: paste any job posting URL
- On submit: added to `jobs/queue.json` with status `pending`
- Queue processor (background worker) picks up pending jobs and runs:
  1. Fetch JD text from URL (headless browser or HTTP)
  2. `tailor_resume.py` — generates tailored resume + analysis
  3. `cover_letter.py` — generates full cover letter
  4. Marks queue entry as `ready`
- WebSocket push notifies UI when job finishes processing

### Queue table
- Columns: Submitted | URL / Company / Title (auto-detected) | Status | Actions
- Statuses: pending, processing, ready, failed
- Actions: View output folder, Apply (opens form filler), Dismiss

### LinkedIn results
- Displays `jobs/linkedin_results.md` parsed as a table
- Columns: Score | Title | Company | Location | Salary | Easy Apply | URL | Actions
- Actions per row: "Add to queue", "Open URL", "Dismiss"
- "Find new jobs" button at top — triggers `linkedin_scraper.py` in an external terminal
- Shows last-scraped timestamp
- WebSocket broadcasts `results_updated` when `linkedin_results.md` changes

---

## 8. Q&A Knowledge Base (`/qa`)

- Table: Question ID | Question | Context | Answer | Date Answered
- Unanswered questions highlighted at top with badge
- Inline answer editor (click to expand, type answer, save — calls PATCH /api/qa/[id])
- Add new question button (modal form)
- Search / filter by keyword
- Bulk export to CSV

---

## 9. Analytics (`/analytics`)

All charts use real data from `application_tracker.csv`.

| Chart | Type | Description |
|-------|------|-------------|
| Applications over time | Line | Daily/weekly application count |
| Pipeline funnel | Bar | Count at each status stage |
| Response rate by work mode | Bar | Remote vs Hybrid vs On-site |
| Response rate by Easy Apply | Bar | EA vs Direct comparison |
| Response type breakdown | Pie | Phone Screen / Interview / Rejected / etc. |
| Days to response | Bar | Distribution of response lag |
| Match score vs response | Scatter | Per-application dot plot |
| Applications by salary range | Bar | Bucketed salary distribution |

Summary stats panel above charts:
- Best-performing salary range
- Best-performing work mode
- Average match score for responded vs non-responded

---

## 10. Settings (`/settings`)

### Candidate profile
- Editable form for all `CANDIDATE_*` env vars:
  - First/last name, email, phone, website, LinkedIn, location, current employer,
    forwarding email
- Save writes directly to `.env` via `dotenv.set_key()`
- Changes take effect immediately (no restart needed for pipeline scripts)

### Pipeline configuration
- Default work mode preference (Remote / Hybrid / Any)
- Default follow-up interval (days, default 7)
- LinkedIn scraper defaults: keywords, location, pages to scrape
- Anthropic model overrides (which model for JD analysis, tailoring, cover letter)

### Integrations status panel
- Gmail OAuth token: valid / expired / not set up (with "Setup" button)
- `ANTHROPIC_API_KEY`: set / not set
- here.now credentials: found / missing
- Chrome: found at path / not found

### Tunneling
- "Share publicly" button: runs here.now publish on the current server port
- Displays the public URL with copy button and TTL countdown
- "Revoke" button to stop the tunnel

---

## 11. API Routes (Next.js)

| Method | Route | Action |
|--------|-------|--------|
| GET | `/api/applications` | Read all tracker rows |
| PATCH | `/api/applications/[id]` | Update a row field |
| POST | `/api/applications/[id]/response` | Log a response |
| POST | `/api/jobs/queue` | Add URL to processing queue |
| GET | `/api/jobs/queue` | Get queue status |
| DELETE | `/api/jobs/queue/[id]` | Remove queue item |
| GET | `/api/jobs/results` | Parse linkedin_results.md |
| POST | `/api/pipeline/scrape` | Launch LinkedIn scraper in external terminal |
| GET | `/api/qa` | Read all Q&A rows |
| POST | `/api/qa` | Add a new question |
| PATCH | `/api/qa/[id]` | Save an answer |
| GET | `/api/analytics` | Aggregated stats for charts |
| GET | `/api/settings` | Read env vars (redacted) |
| PATCH | `/api/settings` | Write env vars |
| POST | `/api/pipeline/tailor` | Run tailor_resume.py |
| POST | `/api/pipeline/cover-letter` | Run cover_letter.py |
| POST | `/api/pipeline/followup` | Run followup.py |
| GET | `/api/file` | Serve application files (PDF, MD, JSON) — path-restricted |
| POST | `/api/tunnel` | Launch here.now tunnel |
| GET | `/ws` | WebSocket upgrade endpoint |

All mutating routes validate the session cookie before executing.

---

## 12. File Structure

```
command-center/
├── app/
│   ├── layout.tsx
│   ├── globals.css
│   ├── page.tsx                  # Dashboard
│   ├── login/page.tsx            # Auth
│   ├── applications/
│   │   ├── page.tsx              # Tracker table
│   │   └── [id]/page.tsx         # Detail view
│   ├── jobs/page.tsx             # Queue + LinkedIn results
│   ├── qa/page.tsx               # Q&A knowledge base
│   ├── analytics/page.tsx        # Charts
│   └── settings/page.tsx         # Profile + config
│   └── api/                      # Next.js API routes (see section 11)
├── components/
│   ├── AmbientBackground.tsx     # 3 animated orbs + grid overlay
│   ├── SpotlightCard.tsx         # Glassmorphic card + spotlight glow
│   ├── Sidebar.tsx               # Left nav with logo
│   ├── StatusBadge.tsx           # Gradient status pills
│   ├── MetricCard.tsx            # Stat widget
│   ├── PdfModal.tsx              # Native iframe PDF viewer
│   └── ThemeToggle.tsx           # Light/dark/system toggle
├── lib/
│   ├── csv.ts                    # Read/write tracker + QA CSVs
│   ├── ws-client.tsx             # WebSocket context + useWS hook
│   └── utils.ts                  # cn() and helpers
├── server.js                     # Custom Node.js server (Next.js + WS + chokidar)
├── middleware.ts                  # Auth middleware (Edge Runtime, WebCrypto)
├── next.config.mjs
├── tailwind.config.ts
├── tsconfig.json
└── package.json
```

---

## 13. Development Setup

```bash
cd command-center
npm install
npm run dev        # starts on http://localhost:3000
```

For public access (on demand):
```bash
bash ~/.agents/skills/here-now/scripts/publish.sh "http://localhost:3000" --ttl 86400
```

---

## 14. Out of Scope (v1)

- Mobile-optimized layout (desktop browser only)
- Multi-user support
- Email sending from the UI (drafts only — send from Gmail)
- Job description editor
- Resume editor (Markdown remains the source of truth)
