# NZ Gymnastics Results — Implementation Plan

## Architecture Overview
- **Backend:** Python/FastAPI, SQLAlchemy + SQLite, Pandas
- **Frontend:** SvelteKit (adapter-node)
- **Infrastructure:** Docker Compose

## Steps

### Step 1: Project Scaffolding ✅
- [x] Create `backend/` directory with `pyproject.toml` (fastapi, uvicorn, sqlalchemy, pandas, openpyxl, python-multipart, pytest, httpx)
- [x] Create `backend/app/__init__.py`
- [x] Create `frontend/` with SvelteKit via `npm create svelte@latest`
- [x] Create `docker-compose.yml` with backend + frontend services
- [x] Create `.gitignore` (Python + Node patterns)
- [x] **Test:** Backend starts and responds on :8000

### Step 2: Database Models ✅
- [x] Create `backend/app/models.py` — `Event`, `LongScore` SQLAlchemy models
- [x] Create `backend/app/database.py` — engine, session, `init_db()`
- [x] Create `backend/app/schemas.py` — Pydantic models for API
- [x] **Test:** 4/4 `pytest` — DB creates tables, CRUD operations work

### Step 3: Node-Tree Decoder ✅
- [x] Create `backend/app/decoder.py` — maps opaque `publicOutputs` keys to field names
- [x] Build from `performanceRules[].scores[].nodeTree.interface.outputs[]`
- [x] Handle 4-key (normal) and 5-key (DNS) variants
- [x] **Test:** 13/13 unit tests + verified against real hve-2026.json data

### Step 4: ID Resolver ✅
- [x] Create `backend/app/resolver.py` — lookup maps for the flat JSON structure
- [x] `eventParticipants` -> name, GNZ ID, club
- [x] `performanceIndividuals` -> link entity IDs to participants and units
- [x] `eventOrganizations` -> club name
- [x] `units` -> unit name, discipline
- [x] **Test:** 21/21 unit tests with mock data

### Step 5: JSON Parser (Long Format) ✅
- [x] Create `backend/app/parser.py`
- [x] Parse uploaded JSON, resolve all IDs, decode scores, extract rankings
- [x] Produce long-format rows: one per gymnast per apparatus pass
- [x] Handle DNS, Zero, multi-pass vaults, multi-unit gymnasts
- [x] Store in SQLite via SQLAlchemy
- [x] Re-upload: delete existing event data, re-parse
- [x] **Test:** 51/51 tests (13 parser tests against hve-2026.json and mgi-wag-2026.json)

### Step 6: FastAPI Endpoints ✅
- [x] Create `backend/app/main.py`
- [x] `POST /api/upload` — JSON file upload -> parse -> store -> return summary
- [x] `GET /api/events` — list stored events
- [x] `GET /api/events/{id}/results` — long-format JSON
- [x] `GET /api/events/{id}/export/csv`
- [x] `GET /api/events/{id}/export/xlsx`
- [x] **Test:** 9/9 httpx integration tests against real data (60/60 total)

### Step 7: Pandas Transformer ✅
- [x] Create `backend/app/transformer.py`
- [x] Query long-format from SQLite
- [x] Pivot to wide format: apparatus columns per gymnast per round
- [x] WAG: VT, UB, BB, FX + AA
- [x] MAG: FX, PH, SR, VT, PB, HB + AA
- [x] Generate CSV/XLSX byte streams
- [x] **Test:** 63/63 total (export endpoints test CSV and XLSX downloads)

### Step 8: Frontend — Upload Page ✅
- [x] `routes/+page.svelte` — drag-and-drop JSON upload
- [x] File validation, loading state, success/error feedback
- [x] `src/lib/api.ts` — typed fetch wrappers
- [x] **Test:** Builds successfully with `npm run build`

### Step 9: Frontend — Events & Results ✅
- [x] `routes/events/+page.svelte` — event list table
- [x] `routes/events/[id]/+page.svelte` — wide-format results table
- [x] Sortable columns, CSV/XLSX download buttons
- [x] **Test:** Builds successfully with `npm run build`

### Step 10: Docker & Polish ✅
- [x] Backend Dockerfile (python:3.12-slim, ~17s build)
- [x] Frontend Dockerfile (node:20-alpine, ~7min first build with npm install)
- [x] docker-compose.yml with volume mounts for dev hot-reload
- [x] Volume mount for SQLite persistence
- [x] **Test:** Full `docker compose up` end-to-end verified

### Step 11: Frontend Styling — Tailwind + DaisyUI ✅
- [x] Install tailwindcss v4, @tailwindcss/vite, daisyui v5
- [x] Configure Vite plugin, remove postcss config
- [x] Dark theme via `data-theme="dark"`
- [x] Global nav bar in layout (Upload / Events)
- [x] Restyle upload page (DaisyUI card, alert, loading spinner)
- [x] Restyle events list (zebra table, loading, empty state)
- [x] Restyle results page (DaisyUI tabs, zebra table, sort indicators)
- [x] Apparatus columns grouped into single cells with hover tooltips
- [x] **Test:** Builds successfully with `npm run build`

### Step 12: Backend Polish ✅
- [x] Decode `Bonus` field from publicOutputs
- [x] Propagate bonus across all passes in same (entityId, unitEventId) group
- [x] Clarify vault aggregation rules (STEP 6/7 avg, high-level AA best, high-level Apps avg)
- [x] Change `_fmt3` from round to truncate (floor), with floating-point noise cleanup
- [x] **Test:** 191/251 pytest passing

### Step 13: Parser Robustness ✅
- [x] Fix `"equal-discarded"` status not being filtered — causes duplicate rows from tied-then-discarded scores (31/40 files affected)
- [x] Add `validate_upload_structure(data)` to check for required top-level keys before parsing, returning clear error messages instead of silent empty results
- [x] Wrap `parse_json()` in try/except in the upload endpoint with user-friendly error responses (`ParseError` + 422 response)
- [x] Map `"Start Value"` output in decoder.py (vault-specific field in kaitaia_2025.json) — stored as `start_value` column in LongScore
- [x] Add batch validation CLI: `python -m app.validate_json path/to/file.json`
- [x] Add regression tests for all known edge cases (equal-discarded, Start Value, Open division, unit name patterns, known structural variations)
- [x] **Test:** 201/201 pytest passing; batch CLI validates all 40 files cleanly

### STEP 14: Frontend UI Improvements ✅
- [x] Integrate filter dropdowns into column headers (remove separate MultiSelect buttons)
- [x] Add per-column min-width system via `COL_MIN_CLASS` (Tailwind classes)
- [x] Hide Division column in MAG view
- [x] Left-align apparatus columns
- [x] Responsive column sizing (columns shrink/grow with viewport)
- [x] Add footer with GitHub link and Ko-fi donation support
- [x] Sticky footer layout (min-height flex, footer at bottom on short pages)
- [x] Last apparatus column tooltip opens left to avoid clipping
- [x] Additional bottom padding for table tooltip clearance

### STEP 15: Feature Polishing ✅
- [x] Event page — discipline badges (daisyUI `badge-primary`/`badge-secondary`), clickable rows with `goto()`, remove View button column
- [x] AA Tooltip — new `AATooltip.svelte` component with summed D/E/N across apparatus; integrated into `aa-score` column
- [x] Show equals in rankings — backend appends "T" to tied rank values via `rank_text` (`T{rank}` when total equals a neighbour); surfaced as `RankingRow.rank`

### STEP 16: Athlete ID Reconciliation ✅
- [x] Create `backend/app/reconcile.py` — name-based ID unification logic
- [x] Add `POST /api/admin/reconcile-athletes` endpoint (admin-only)
- [x] Add `ReconcileReport` + `ConflictItem` schemas
- [x] Add `reconcileAthletes()` to frontend API client
- [x] Add reconciliation card to /admin page with conflict viewer
- [x] Write 9 tests for reconciliation logic
- [x] **Test:** 9/9 reconcile tests pass; 242 total tests pass
- [x] Update BUGS.md with remaining edge cases

### STEP 17: Auth Overhaul (Password → JWT) ✅
- [x] Add `User` SQLAlchemy model (id, username, hashed_password, role, created_at)
- [x] Rewrite `auth.py` with bcrypt hashing, JWT create/decode (HS256, 7-day expiry)
- [x] Add `require_role()` FastAPI dependency factory
- [x] Add `seed_admin_user()` from env vars (ADMIN_USERNAME, ADMIN_PASSWORD, ADMIN_ROLE)
- [x] Auto-generate JWT_SECRET persisted to `data/jwt_secret.txt`
- [x] Add endpoints: POST /api/auth/login, POST /api/auth/register, GET /api/auth/users, POST /api/auth/users/{id}/reset-password, DELETE /api/auth/users/{id}
- [x] Add GET /api/rankings (member+ placeholder)
- [x] Replace frontend auth: JWT in localStorage, currentUser store with role
- [x] Update login page with username+password fields
- [x] Add admin user management page at /admin/users
- [x] Nav bar: role-based visibility for Upload/Admin/Rankings, user badge dropdown
- [x] **Test:** 251/251 tests pass; frontend builds

### STEP 18: UI/UX Improvements ✅
- [x] Move theme toggle from nav to footer bottom-right
- [x] Add `pt-6` to main content for breathing room
- [x] Replace "More" dropdown with direct Gymnasts/Clubs links in nav
- [x] Fix dropdown z-index issue (inline `style="z-index: 50"`)
- [x] Global year toggle in nav (DaisyUI `tabs tabs-box` radio inputs)
- [x] Add GET /api/years endpoint; shared selectedYear store
- [x] Landing page: Upload card hidden for non-admins; grid switches to 2 columns
- [x] Fix sort-revert bug in WideResultsTable ($effect cycle → loaded flag)
- [x] Add region column to wide results (enriched at pivot time, filterable)
- [x] Table improvements: max-w-full layout, min-w-full, whitespace-nowrap cells, hover:bg-base-300, py-1.5
- [x] Event name truncation (truncate max-w-56)
- [x] Add name cleaning regex: strips (L#), (STEP 10), (YI) at parse time
- [x] Add "Levin Gymsports" and "Kapiti" club aliases to clubs_and_regions.json
- [x] Fix clubs_and_regions.json: Franklin Gymsports, ARGOS alias cleanup, Buller restoration

### STEP 19: Season Rankings + Nationals Flag ✅
- [x] Add `is_national` boolean column to Event model with DB migration
- [x] Add Nationals toggle to events page (admin-only badge/button in action column)
- [x] Add `events` list API: include `is_national` in response
- [x] Extend `PATCH /api/events/{id}` to update `is_national` (alongside existing rename)
- [x] Build `GET /api/rankings` endpoint (member+): best 2 comps per gymnast per STEP per year (excludes Nationals events), summed total, tie detection with "T" prefix
- [x] Build `GET /api/rankings/steps` endpoint: list available STEP levels per year/discipline
- [x] Rankings page with year selector, discipline tabs, STEP dropdown, rankings table with competition-name tooltips
- [x] **Test:** 251/251 tests pass; frontend builds cleanly

### STEP 20: Incomplete AA in Rankings ✅
- [x] Include gymnasts who don't have a complete All-Around aggregate in rankings by computing partial AA from individual apparatus passes
  - When no `aa_score` exists for a gymnast+event, sum per-apparatus `pass_final_score` values (applying `_use_vault_average()` rules for vault)
  - Changed rankings query to fetch all score rows (not just those with non-null AA) and aggregate in Python
  - **File:** `backend/app/main.py`

### STEP 21: Duplicate Detection in Admin Dashboard ✅
- [x] Unified Reconcile + Duplicates into single "Athlete ID Reconciliation" card grouped by name
- [x] Per-instance (club/level) ID dropdowns with >2x confidence auto-fix
- [x] "Quick Fix" and "Apply Selected Fixes" buttons
- **Files:** `backend/app/main.py`, `backend/app/schemas.py`, `frontend/src/routes/admin/+page.svelte`, `frontend/src/lib/api.ts`

### STEP 22: Import JSON from URL ✅
- [x] `POST /api/import-url` endpoint (admin) accepting `{ url, allow_unknown }` — fetches the Scoreholder public export via `app/scoreholder.py`, validates, parses, stores
- [x] Frontend: URL input field on upload page alongside drag-and-drop area, same success/error UX
- [x] Handles timeouts, invalid URLs, fetch errors (502), non-JSON responses gracefully
- [x] Reuses the club mapping dialog for unknown clubs (`allow_unknown` retry path)
- [x] Handles Scoreholder 307 redirect + Brotli (`Content-Encoding: br`) compression
- **Files:** `backend/app/main.py`, `backend/app/scoreholder.py`, `frontend/src/routes/upload/+page.svelte`, `frontend/src/lib/api.ts`

### Minor Polish
- [x] RegionBadge component — 2x2 checkerboard (primary+secondary) + primary fill + whitespace-nowrap
- [x] Region color palettes (NZ sports team inspired, 15 regions, 2-3 colors each)
- [x] Region color dots (two 6px circles) in wide results table region column
- [x] Truncate competition names in wide results table (max-w-56, ellipsis)
- [x] Refresh docs

### STEP 23: Wellington Regional Rankings ✅
- [x] New `backend/app/wellington_ranking.py` module with event classification (regional/club/away), per-step-range selection rules, distinct-event enforcement, GNZ + Wellington dual qualifier filters
- [x] `GET /api/rankings/wellington` endpoint (auth: member+)
- [x] Wellington Rankings page with WAG/MAG tabs, STEP selector, qualifier toggles, CSV export, apparatus tooltips
- [x] Rankings nav dropdown with National Rankings / Wellington Rankings
- [x] Config: WAG STEP 5-6 (GNZ 50.0 2×+away, Wgtn 53.0), WAG STEP 7-10 (GNZ 43.0 1×), MAG Level 4-6 (Wgtn 58.0), MAG Level 7+ (Wgtn 63.0)
- [x] Not-on-the-ranking table: `compute_wellington_rankings` returns a single `not_ranked` list of every Wellington athlete who isn't on the ranking with a `why` headline + `checks` ✓/✗ requirements checklist (competition mix via `_selection_checks()`, intent, and GNZ/Wellington marks via `_qualifier_checks()`, each with "x of y" detail). Frontend renders it as "Not on the Ranking", sorted alphabetically, with a trailing column whose tooltip shows the checklist; no filter toggles — the main table always shows only qualified + intended athletes, and ticking Intent moves selection-capable athletes up immediately. Score columns are slot-aligned (the 4 selectors return `None`-placeholder slots; partial selections fill the correct category column with dashes elsewhere).

### STEP 24: Accessibility (a11y) ✅
- [x] **Tier 1 — High-value quick wins**
  - [x] Layout/nav: skip-to-content link + `id="main"`; wrap navbar + mobile drawer in `<nav>`; `aria-current="page"` on active nav links; mobile hamburger `<label>` → `<button aria-expanded aria-controls>` (`+layout.svelte:78`)
  - [x] Landing page: route both `in:fly` animations through reduced-motion-aware `reveal()`; init `motion` synchronously from `matchMedia` (`+page.svelte:42,73`)
  - [x] Upload: dropzone `onclick`+`onkeydown` → `fileInput.click()`; `aria-label` on file input; keep input reachable (`upload/+page.svelte:258-277`)
  - [x] NZ map: remove `role="img"` from root `<svg>`; visible focus indicator replacing `outline:none`; `aria-pressed` on active region; single name source (`NZRegionMap.svelte:73,102,122,170`)
  - [x] Tables: keyboard sort on apparatus `<th>`s; `aria-sort` on active column; `aria-label` on `« »`/filter triggers; `aria-expanded` + Escape on filter menus (`WideResultsTable.svelte`)
  - [x] Tooltips: `role="tooltip"`/`aria-describedby`; fix `AATooltip` `role="menu"` misuse; keyboard+focus open for `ScoreTooltip`/`AATooltip`; make wellington/rankings hover-only tooltips reachable
  - [x] Labels/live regions: login, user modals, edit-event, step/page-size/"Correct ID" selects, intent checkboxes, table search; `role="status"`/`aria-live` on admin toasts, edit toast, upload status; `role="alert"` on rankings/wellington errors; `aria-label` on icon-only buttons; events clickable `<td>` → real link
  - [x] Contrast quick wins: `text-base-content/40–60` bumps; `ScoreTooltip` header `opacity-70`
- [x] **Tier 2 — Dialogs, tabs, map focus**
  - [x] New shared `frontend/src/lib/Dialog.svelte` — `role="dialog"`, `aria-modal`, labelled heading, initial-focus move, focus trap, Escape close, focus restore, backdrop click
  - [x] Migrate all 5 modals to `Dialog.svelte` (upload club dialog, add/reset/delete user, edit/delete event)
  - [x] Tabs: remove `role="tab"` from radio year selector + WAG/MAG radios (native `checked` announced); rankings/Wellington button tabs → `aria-pressed` buttons
  - [x] Map→card: `aria-live` announcement + focus move on region select; accordion `aria-expanded`/`aria-controls`; stop nesting links inside `role="button"` card
  - [x] Filter dropdowns: focus into menu on open, focus return, Escape
- [x] **Tier 3 — Contrast + polish**
  - [x] `RegionBadge`/`textColor` palette contrast → WCAG relative-luminance contrast selection (pure `#000` vs `#fff`); map boundary stroke kept on hover/active
  - [x] `aria-hidden` on decorative emojis; heading-order fix on landing (feature h3 → p); patch-notes scroll region `tabindex`+`role="region"`; `scope="col"` on tables; `aria-hidden` on sticky dup header; drawer Escape-close; user/rankings dropdowns → real buttons with `role="menu"`/`aria-haspopup`
- [x] **Verification:** Lighthouse baseline before/after in `a11y-reports/` (tracked, committed per tier); all 6 public pages scored **100/100** after tier 3 (home/events/results/clubs/gymnasts/login; baseline 93/99/92/96/95/100); `cd frontend && npm run build` passes after each tier
- **Files:** `+layout.svelte`, `+page.svelte`, `upload/+page.svelte`, `NZRegionMap.svelte`, `WideResultsTable.svelte`, `ScoreTooltip.svelte`, `AATooltip.svelte`, `Dialog.svelte` (new), `regions.ts`, `RegionBadge.svelte`, all form/dialog pages

### Next Steps
- [ ] Medal counts + totals for gymnasts, clubs and regional teams
  - Gold/silver/bronze (G/S/B) medal tallies per gymnast, per club, and per regional/provincial team, aggregated from `LongScore.apparatus_rank` / `aa_rank` (1 = gold, 2 = silver, 3 = bronze) across scored ranking rows. Regional teams (e.g. `Counties - Manukau`) resolve via the club→region lookup, and National Championships (`is_national` events) medals can be tallied separately as "Nationals medals" alongside season totals.
  - Decide scope: per-year vs all-time, whether apparatus ranks count alongside AA (or AA only), and whether Nationals medals are broken out separately. Ties in the source rankings need a rule (e.g. both athletes share gold, or count by distinct rank value).
  - Backend: aggregation endpoint(s) — e.g. `GET /api/medals?year=` returning per-gymnast, per-club and per-region counts (golds, silvers, bronzes, total, plus a nationals breakdown), cached like `/api/stats`.
  - Frontend: medal badges/totals on the gymnast page (`/gymnast/[gnz_id]`), club page (`/club/[club]`), the `/clubs` region lists, and optionally the `/gymnasts` list; exportable alongside existing tables.
  - **Files:** `backend/app/main.py`, `backend/app/schemas.py`, `backend/app/cache.py`, `frontend/src/lib/api.ts`, `frontend/src/routes/gymnast/[gnz_id]/+page.svelte`, `frontend/src/routes/club/[club]/+page.svelte`, `frontend/src/routes/gymnasts/+page.svelte`, `frontend/src/routes/clubs/+page.svelte`
- [ ] Edit row functionality for admin
  - Inline edit of gymnast name / GNZ ID / club already saves to DB, but the results table doesn't feel reactive after save — needs investigation into the data reload path (`doLoad()` / `applyTab()`). Cache invalidation on `wide-all` works but the frontend may still show stale rows.
  - **Files:** `frontend/src/lib/WideResultsTable.svelte`, `frontend/src/lib/api.ts`, cache invalidation in `backend/app/main.py`
- [x] MAG Wellington ranking thresholds
  - MAG per-step-range qualifying scores configured in the Wellington ranking module.
- [x] Look at not-admin logged in functionality
  - Per-user ranking-page access: `User.permissions` (comma-separated `rankings.national`, `rankings.wellington`) editable from User Management (`PATCH /api/auth/users/{id}/permissions`, admin); new members default to National only, admins always full.
  - Backend enforcement via `require_permission()` in `auth.py` (DB lookup, admins bypass): `/api/rankings`→national, `/api/rankings/wellington` + intents→wellington, `/api/rankings/steps`→either. `GET /api/auth/me` returns DB-fresh permissions.
  - Client-side route guard in `+layout.svelte`: signed-out users and members lacking the required role/permission are redirected to `/` from `/admin` (admin role), `/rankings` (national), and `/wellington-ranking` (wellington), with no flash while the auth check resolves.
  - Nav gating in `+layout.svelte`: Rankings links (desktop + mobile) shown only per permission; Upload/Admin links remain admin-role only; Login button now shown on every page.
  - **Files:** `backend/app/auth.py`, `backend/app/main.py`, `backend/app/schemas.py`, `backend/app/models.py`, `frontend/src/lib/auth.ts`, `frontend/src/lib/api.ts`, `+layout.svelte`, `admin/users/+page.svelte`, `rankings/+page.svelte`, `wellington-ranking/+page.svelte`
- [x] Apparatus Specialist Wellington Qualifying
  - WAG STEP 8-10 fallback: athletes not in the AA table who reach ≥11.000 TWICE at DIFFERENT COMPETITIONS on the same apparatus are returned as `apparatus_specialists` (best per apparatus across eligible events, per-competition best tracked in `apparatus_events`). Athletes who reached the mark only once appear as `qualified: False` rows rendered with greyed-out `badge-outline` ghost badges (tooltip explains they need a second competition). MAG Level 7+ (11.500 × 1) and the International per-apparatus marks (× 1) are unaffected since 1 mark qualifies. May need expansion to other STEP ranges.
  - **Files:** `backend/app/wellington_ranking.py`, `backend/app/schemas.py`, `backend/app/main.py`, `backend/app/transformer.py`, `frontend/src/routes/wellington-ranking/+page.svelte`, `frontend/src/lib/api.ts`
- [x] International Divisions Wellington Qual
  - WAG International divisions (Youth/Junior/Senior International) now appear on the Wellington rankings page: ranked by the single highest All Around mark (no competition-mix selection), Gymnastics NZ qualifying 42.500 / 43.000 / 45.000 on one occasion. Junior + Senior also qualify via per-apparatus specialist marks (count 1): JI VT 12.2/UB 10.4/BB 10.5/FX 11.4, SI VT 12.50/UB 11.30/BB 11.20/FX 11.40 (vault is avg of two). MAG Level 7+ (L7–10, U18, Senior Open) now also computes apparatus specialists at 11.500 (count 1). Apparatus specialist thresholds support a per-apparatus dict (`apparatus_qualifying_scores`) alongside the existing single float; vault specialist scores apply `_use_vault_average` rules per event. New `marks_required` config field (default 3, International = 1) drives the can't-form-selection check and `_selection_checks` (empty for single-mark configs). Step dropdown no longer excludes "international".
  - **Files:** `backend/app/wellington_ranking.py`, `frontend/src/routes/wellington-ranking/+page.svelte`
- [x] Order /clubs by region (Northland → Southland)
  - Desktop uses the interactive NZ map (geographic selection). Mobile replaced the map with a collapsible accordion of the region cards, so a latitudinal ordering is needed again — `REGION_ORDER` in `frontend/src/lib/regions.ts` drives the `grouped` sort on `/clubs` (north→south, "Other" last). Rendered via the shared `RegionCard` snippet.
  - **Files:** `frontend/src/routes/clubs/+page.svelte`, `frontend/src/lib/regions.ts`
- [x] Put provincial teams next to header, separate from clubs
  - Distinguish regional/provincial teams (e.g. `Counties - Manukau`) from regular clubs on the /clubs page — show them next to the region header rather than mixed into the club list.
  - **Files:** `frontend/src/routes/clubs/+page.svelte`
- [x] xlsx format export
  - Client-side CSV/XLSX/PDF export dropdown on all result/ranking pages. `frontend/src/lib/export.ts` builds CSV, XLSX (SheetJS `xlsx`), and PDF (jsPDF + autotable); `ExportMenu.svelte` is the shared dropdown. Libraries lazy-loaded via dynamic `import()` so they only download on first export click. Backend `/api/events/{id}/export/csv|xlsx` endpoints unchanged.
  - XLSX honors a `colFormat` map: hides `region`, per-pass vault cols (`vt-1-*`, `vt-2-*`) and all `*-bonus`, widens name/club (30) + event_name (45). PDF renders the table view (one column per apparatus, D/Total), with title header + `Page X of Y` footer. Filenames are descriptive and kebab-cased via `slugifyFilename()`.
  - **Files:** `frontend/src/lib/export.ts`, `frontend/src/lib/ExportMenu.svelte`, the 4 `WideResultsTable` pages + `rankings` + `wellington-ranking`
- [ ] a11y — see **STEP 24** (tiered plan with Lighthouse baseline/comparison; tracked reports in `a11y-reports/`)
- [x] Index remix: update index page, combine stats with badges, add Patch notes, streamline, add animation?
  - Live stat counts moved onto the nav cards as badges (Events/Gymnasts/Scores/Clubs), separate stats row removed. Added a "What's new" patch-notes section driven by `frontend/static/patch_notes.json` (full history, newest first; the page fetches it and renders everything in a scrollable list). Feature cards kept but copy tightened (CSV/XLSX/PDF). Subtle staggered fade/fly on-load reveal, gated on `prefers-reduced-motion`.
  - **Files:** `frontend/src/routes/+page.svelte`, `frontend/static/patch_notes.json`
- [x] Vetical sticky alphabet searcher on Gymnasts page.
- [ ] Rethink how Year Selector works
- [ ] Interactive season timeline (train-map style)
  - A reusable `Timeline` component (`frontend/src/lib/Timeline.svelte`) embedded at the top of the `/events` page (hidden on mobile via `hidden md:block`, desktop only): a horizontally-scrollable chart of every competition in the selected year, drawn like a London Underground map — theme-aware "ink" lines (`var(--color-base-content)`, dark in light mode / light in dark mode) with a consistent stroke width, 45° elbow joins, inline station-style labels. No backend changes needed: the events page already loads `listEvents()` + `listKnownClubs()` and passes both as props, so the component makes no fetches of its own.
  - Layout: a full-width SVG with a fixed-pitch week column along the x-axis (month labels + faint gridlines). The chart spans from **1 week before the first event to 1 week after the last event** (no long empty off-season stretch). A main line runs horizontally; each week that hosts a competition gets a white (base-100) station dot on the line (painted above the branches), and each competition branches off its week's dot with a 45° elbow to an inline label showing the event name (truncated to 22 chars on the chart, full name in the tooltip) with a small date line below.
  - Colouring: each competition's region identity is carried by a 2×2 rounded checkerboard marker (first two colours of its host club's `REGION_PALETTES` entry, club→region resolved via `listKnownClubs()`, same pattern as the events page host-club badge) sitting at the elbow end of its branch. Nationals (`is_national`) and events with no/unknown host club fall back to a neutral grey checkerboard; a National Championships week keeps an accent ring around its dot. Branch lines, dots and labels are drawn in three layers (all lines → all labels/checkerboards → week dots) so no diagonal can overpaint a checkerboard or date label; bottom-half dates are offset right so the next stacked diagonal doesn't cross them. WAG/MAG and multi-day spans noted via the tooltip. No legend under the chart.
  - Interaction: clicking a competition label/dot navigates to `/events/{id}`; hover/focus highlights that branch and dims the rest; a fixed-position tooltip shows date, host club, region and a WAG/MAG badge (content duplicated in the element's `aria-label`).
  - Year selector: the timeline reads `selectedYear` read-only and is hidden when "All" (null) is selected — the /events page keeps its normal All tab and the timeline only appears for a specific year, so the chart and the events table always show the same year. The standalone `/timeline` route was removed (no nav link).
  - A11y: competition labels are focusable SVG `<a>` elements with `aria-label` (WCAG 2.5.3), min 24px target size; label text drawn with a halo stroke so overlaps stay readable; tooltip content duplicated in the `aria-label` for keyboard/screen-reader users.
  - **Files:** `frontend/src/lib/Timeline.svelte` (new component), `frontend/src/routes/events/+page.svelte` (embeds the timeline, hidden on mobile), `frontend/src/routes/+layout.svelte` (removed `/timeline` nav links + year-selector handling), `frontend/static/patch_notes.json` (notable user-facing change)
- [x] Event page Nationals badge should show next to name, not discipline, also use accent badge