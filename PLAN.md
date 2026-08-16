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

### STEP 25: Athlete Identity & Name Reconciliation ✅
- [x] Investigated root causes (see below)
- [x] Phase 1a — Fix `_clean_name()` capitalization (resolver.py:9 `w.capitalize()` mangles `McEwan`→`Mcewan`, `O'Sullivan`→`O'sullivan`; use NZ-aware title-casing that preserves `Mc`/`Mac`/`O'`/`D'`/hyphenated/apostrophe forms)
- [x] Phase 1b — Make `reconcile_athletes()` evidence-based: never auto-merge same-name rows when a name has 2+ IDs *within the same event* (unambiguous different people) or when club/discipline conflict; route those to `conflicts`
- [x] Phase 1c — Upload-time collision detection in parser: same-name-2-IDs and same-ID-2-names per event → warnings in `EventResponse`, skip those rows in reconcile
- [x] Phase 1d — Backfill guard: only assign an ID from name lookup when the name maps to exactly one existing ID
- [x] Phase 0 — `repair_identities.py`: source JSONs (data-collection/) as ground truth, restore correct gnz_id + capitalization, dry-run + `--apply`; **consensus-driven** (per-(name, club) majority across all source files, winner must beat runner-up ≥2x) so a single file's typo never overwrites a consistent ID — splits Madison Lynch back into two athletes, rejects the Alexandra Boys `6511229` typo; fully-unmatched athletes untouched
- [x] Phase 2 — `athletes` identity table (`athlete_id` FK on `long_scores`), query layers grouped by `athlete_id` (transformer, rankings, medals, gymnasts, wide-all, wellington intents), frontend gymnast URLs keyed on athlete slug
  - **`athletes` table** (`Athlete` model: `slug`, `signature_hash`, `canonical_name`, `gnz_id`) + `long_scores.athlete_id` FK, migrated/seeded in `init_db()` (`python -m app.athlete_identity` to rebuild manually). Clustering lives in `backend/app/athlete_identity.py`: union-find over `(normalized name, gnz_id)` signatures — within a name, split on same-event ID collision / discipline conflict / disjoint clubs (the two Madison Lynches), merge otherwise; across names, two athletes sharing a numeric gnz_id merge only when names are similar (`difflib` ≥ 0.85, so `Eva Mcewan`/`Eva McEwan` collapse while the 33 distinct-people-shared-ID cases stay separate). Empty-ID rows join their name's dominant ID. `rebuild_athletes()` is **idempotent and signature-stable** (reuses athlete rows by hash so slugs survive re-uploads) and runs after every ingest, inline edit, name merge, duplicate fix, refresh-cache, and at startup.
  - **Query layers re-keyed on `athlete_id`**: transformer pivot groups by athlete identity (canonical name + `slug` in wide rows), medals/gymnasts/wide-all accept `athlete_id`/`slug`, rankings/apparatus/wellington group by athlete key (variant spellings rank as one gymnast). Gymnast URLs are `/gymnast/{slug}` (opaque `a` + sha1 hex, back-compat accepts a legacy gnz_id). Wellington intents re-keyed to `athlete_id` (table rebuilt with `UNIQUE(athlete_id, year)`, backfilled from gnz_id).
- [x] Phase 3 — Canonical-name auto-unify: pick most-common spelling per athlete cluster, unify variants in display + back-write
  - `rebuild_athletes()` **back-writes** each `long_scores` row to its cluster's canonical (most-frequent) spelling after re-clustering, so the raw `gymnast_name` column stops carrying variants (idempotent — the UPDATE matches zero rows once applied; live DB normalized ~3,000 rows across 304 athletes). Orphan `Athlete` rows are now deleted **after** the `athlete_id` reassignment (a rebuild that changes a cluster's identity would otherwise try to delete an athlete still referenced by old rows → FK violation). `_compute_wide_all`'s "gymnast not found" fallback `name` now comes from `Athlete.canonical_name` instead of the last raw spelling. Gymnast counts (`/api/stats` `total_gymnasts`, event-list `gymnast_count`) count `distinct COALESCE(athlete_id, gymnast_name)` so variant spellings and same-name different-people each count once.
- [x] Phase 4 — Admin review tooling: both-direction ID/name conflicts + Split action
  - `GET /api/admin/identity-review` (admin) returns athlete-level conflicts in four sections: `similar_names` (fuzzy canonical-name pairs, athlete-level, replaces the old Suggested Merges), `name_conflicts` (same canonical name on 2+ athletes), `id_conflicts` (same gnz_id on 2+ athletes), and `multi_id_athletes` (one athlete carrying 2+ gnz_ids — the Split candidates). Each athlete carries evidence (slug, gnz_id, clubs, events/event_ids, years, disciplines, rows, wellington intent years).
  - `POST /api/admin/athletes/merge` — sets the merged athlete's rows to the survivor's canonical name + gnz_id, clears `identity_override` on both sides, moves Wellington intents (UNIQUE(athlete_id, year): dropped on conflict), then rebuilds; the survivor's Athlete row is reused (re-created if its gnz_id was promoted). `POST /api/admin/athletes/split` — assigns the chosen rows (by gnz_id/event_id/club_name) a fresh synthetic gnz_id (`S…`, or an admin-supplied real ID) **plus** a unique `identity_override` token, then rebuilds.
  - New `long_scores.identity_override` column (nullable, ALTER TABLE in `init_db()`) — the admin force-split boundary: `_cluster_name_signatures()` treats each distinct override token as its own person (hard no-merge) and clusters unmarked rows with the normal rules, so a split survives rebuilds/re-uploads until a merge clears the token. The synthetic gnz_id alone can't force separation when the two halves share a club (the primary live case — e.g. `Te Ahorangi Milsted-Raika` 3 IDs at 1 club), hence the marker.
  - Admin UI: `/admin` "Athlete ID Reconciliation" + "Suggested Merges" cards **replaced** by a single "Identity Review" card (four collapsible sections, Merge-into-X per athlete, client-side Dismiss, per-athlete Split panel with dimension/value selects + optional real-ID field). The old endpoints (`/api/admin/duplicates*`, `/api/admin/suggested-merges`, `/api/admin/merge-names`) remain in the API (still tested) but are no longer called by the UI.
- [x] Phase 5 — Tests + docs (capitalization, no-merge rules, backfill guard, repair dry-run); update AGENTS.md/MEMORY.md + patch_notes.json
  - The four listed test areas were already covered by the per-phase suites: capitalization (`test_resolver.py::TestCleanName`), no-merge rules (`test_reconcile.py` same-event/discipline + `test_athlete_identity.py` disjoint-clubs), backfill guard (`test_ingest.py`), repair dry-run + consensus (`test_repair_identities.py`). Added the one missing regression test — `test_database.py` verifies `init_db()` migrates a **pre-existing** old schema (adds `athlete_id`/`identity_override`/`host_club`/`is_national`/`permissions`, re-keys wellington intents, seeds athletes) while preserving seeded rows. Full suite **332 pass / 87 skip**; frontend builds clean. Docs swept: AGENTS.md + README.md test counts updated, MEMORY.md admin/test sections refreshed, BUGS.md known-issue reworded to point at the Identity Review tool, patch_notes already carries the Phase 2/3/4 user-facing entries.
- [x] **Production deployment (14 Aug 2026)** — prod had never received the identity work's one-time repair, so its clustering differed from dev (the two Madison Lynches were a single athlete under one ID). Ran `repair_identities --apply` on prod (mounting `data-collection/`, backend stopped first): 1,237 ID + 13,159 name fixes, athletes 5,128 → 5,156, Madison Lynch split with the same slugs as dev. Rollback backups kept in the `backend_data` volume (`results.pre-identity.db`, `results.pre-identity-fix.db`).

**Root causes found (Aug 2026):**
1. `_clean_name` uses `w.capitalize()` → lowercases the rest of each word, so `Eva McEwan` → `Eva Mcewan` (live DB confirmed).
2. `reconcile_athletes()` is name-keyed and runs after every upload (main.py:2052): two different people sharing a name (e.g. Madison Lynch — OMNI STEP 1 `716561` vs Onslow STEP 5/6/7 `249317`) get irreversibly merged into one ID.
3. Source data itself has bad identifiers: 61 collision events in `data-collection/` (same numeric ID on 2+ different names within one event; club codes like `TRI`/`ARG`/`HOW` in the `identifier` field); 3,723 DB rows have empty `gnz_id`, and the ingest backfill (main.py:2006-2027) assigns IDs by name only.
4. Scale: 369 IDs carry 2+ distinct names — 336 are spelling variants of one person (~424 duplicate gymnast-list entries), 33 are genuinely different people sharing an ID.

### STEP 26: Admin Activity → Usage Dashboard ✅ (14 Aug 2026)
- [x] Capture **all** usage (anonymous public traffic + logged-in users) without storing IPs or user-agents:
  - New `traffic_daily` aggregate table (`TrafficDaily` model) — per `date`/`hour`/`kind`/`path_group`/`anonymous` counters with a `UniqueConstraint` backing the SQLite UPSERT (`INSERT … ON CONFLICT DO UPDATE`). Created automatically by `init_db()` (`Base.metadata.create_all`), no ALTER migration.
  - New `backend/app/traffic.py`: `normalize_path()` (query stripped, pure-numeric segments → `[id]`, 10-char hex slugs → `[slug]`) + `is_bot()` regex (`bot|spider|crawl|slurp|curl|wget|python-requests|Go-http-client|HeadlessChrome|UptimeRobot|pingdom`; UA inspected, never stored).
  - `activity_log.py` batched writer extended with a `_target` discriminator (`"activity"` vs `"traffic"`); traffic rows aggregated in Python per key, then one parameterized upsert per key. New public `enqueue_traffic(kind, path_group, anonymous, status_code, duration_ms)` — queues, or writes synchronously when the writer isn't started (test contexts). Errors = status ≥ 400; `duration_ms=None` (page views) → 0.
  - Optional-auth dependency `get_optional_user` in `auth.py` (returns `None` for anonymous, never raises).
  - `log_activity` middleware rewritten: skips `/api/track/page` (handled in the endpoint), `/api/admin/activity*` (no self-logging), `/api/health` (Docker healthcheck noise), and non-`/api` paths; anonymous bot user-agents are excluded; every other `/api` request is counted as `kind='api'`; authenticated requests also keep their existing detail `activity_logs` row.
  - `track_page` beacon now fires for all visitors (via `get_optional_user`) — guests get a 200 + `kind='page'` traffic row instead of 401.
  - `TZ: Pacific/Auckland` added to the backend service in both compose files so day/hour buckets match the admin's local day.
- [x] Analytics endpoint:
  - `GET /api/admin/activity/summary?days=7|30|90|0` (admin; 0 = all time) — `flush_activity()` first so queued rows appear; totals split anonymous vs logged-in (page/api/errors/avg duration/active days), `daily_series`, `auth_daily_series` (from `activity_logs`, so logged-in history predates the dashboard), `hourly_series` (0–23), `top_pages`, `top_api`, `top_users`.
  - `GET /api/admin/activity` gains an optional `days` filter.
- [x] Frontend dashboard:
  - `npm install chart.js` (runtime dep, lazy-imported).
  - New `lib/charts/ChartJs.svelte` wrapper: `onMount` dynamic `import("chart.js/auto")`, `$effect` on data/options updates, `onDestroy` destroy; canvas `role="img"` + `aria-label` + visually-hidden data fallback; `maintainAspectRatio: false` + explicit container height (`h-64`).
  - `getActivitySummary(days)` in `lib/api.ts`; beacon `$effect` in `+layout.svelte` fires when auth is configured regardless of login state, deduped with a plain `let` keyed `username|path` (users) / `anon|path` (guests).
  - `/admin/activity` redesigned as a responsive dashboard: range tabs (7/30/90/All) driving both summary and detail table, 5 stat cards (`grid-cols-2 md:grid-cols-5`), 4 Chart.js graphs (traffic over time, hour of day, top pages, top users), detail log rows → stacked cards below `md` (no horizontal scroll), auto-refresh reloads the summary too.
- [x] **Tests:** `test_activity.py` updated/extended — anonymous request → traffic row (no detail row), guest beacon → 200 + traffic row, authenticated → detail **and** traffic row, bot UA excluded, `/api/health` skipped, `normalize_path` cases, summary shape/range/totals/top-lists/errors, 403 for member, `days` param. Full suite **332 pass / 87 skip**; frontend builds.
- **Files:** `backend/app/{activity_log,auth,main,models,schemas,traffic}.py`, `backend/tests/test_activity.py`, `docker-compose.yml`, `docker-compose.prod.yml`, `frontend/src/lib/charts/ChartJs.svelte` (new), `frontend/src/lib/api.ts`, `frontend/src/routes/+layout.svelte`, `frontend/src/routes/admin/activity/+page.svelte`, `frontend/static/patch_notes.json`

### STEP 27: Consolidated Admin Dashboard ✅ (14 Aug 2026)
- [x] All administrator functionality on a single `/admin` page; old routes `/upload`, `/admin/activity` and `/admin/users` **deleted** (no redirects).
- [x] Layout — four labelled bands fitting above the fold on desktop: **Site stats** (Events/Gymnasts/Scores/Clubs stat tiles) and **Manage tools** (Refresh Cache + Upload/Users/Identity Review/Logged-in activity dialog buttons) share one row; **Usage** band (range tabs, auto-refresh, five usage stat tiles); **Graphs** band (4-across Chart.js, `h-44`). Each group sits in a subtle rounded flex band.
- [x] Areas extracted into `frontend/src/lib/admin/` components: `Overview.svelte`, `Activity.svelte`, `ActivityCharts.svelte`, `ActivityLog.svelte`, `Upload.svelte`, `Users.svelte`, `IdentityReview.svelte`, `StatTile.svelte`.
- [x] Material Symbols icon font (self-hosted `material-symbols` npm package; `@import "material-symbols/outlined.css"` + a `.material-symbols-outlined` base rule in `app.css`). Icons are decorative: `<span class="material-symbols-outlined" aria-hidden="true">…</span>` with a visible text label.
- [x] Upload/Users/Identity Review/Logged-in activity open as dialogs from Manage tools; `Dialog.svelte` got Escape/Tab **stop-propagation** so nested inner dialogs (club mapping, add user) close independently.
- [x] Activity chart data lifted to the page via an `onData` callback so the graph band can span full width.
- [x] Nav (desktop dropdown + mobile drawer) → `/admin` + `?tab=…` via a new `adminTab()` helper; `events/+page.svelte` + `results/+page.svelte` empty-state buttons → `/admin?tab=upload`.
- **Files:** `frontend/src/routes/admin/+page.svelte`, `frontend/src/lib/admin/*` (new), `frontend/src/routes/+layout.svelte`, `frontend/src/app.css`, `frontend/src/lib/Dialog.svelte`, deleted `frontend/src/routes/{upload,admin/activity,admin/users}/`

### STEP 28: Cloudflare Edge Analytics ✅ (14 Aug 2026)
- [x] `GET /api/admin/cloudflare/summary?days=7|30` (admin-only) shows the HTTP traffic Cloudflare sees at the edge — everything the server-side tracking misses (HTML pages, static assets, bots).
- [x] New `backend/app/cloudflare.py` posts GraphQL to `https://api.cloudflare.com/client/v4/graphql`: `httpRequests1dGroups` for the window (requests/bytes/cached/threats + `uniq.uniques`), and `httpRequestsAdaptiveGroups` **clamped to the last 24 hours** (the adaptive quota rejects wider ranges — the breakdown queries failed with a GraphQL quota error at 7 days) grouped by country/status code/path/cache status/device type plus a `datetimeHour` series (the Analytics:Read token can't access `httpRequests1mGroups`, hence `datetimeHour`).
- [x] Config via `CLOUDFLARE_ZONE_ID` + `CLOUDFLARE_API_TOKEN` (zone-scoped, Analytics:Read, read from env/`.env`); unset → `{configured: False}`. Server-cached via `cached(("cloudflare", days), ttl=300)` (single-flight so rate limits aren't hit); fetch failures return `{configured: True, error}` and are **not** cached.
- [x] Frontend: `/admin` regrouped by data source — **Server usage** band (range tabs + usage stat tiles + 4 site charts) and **Cloudflare** band (stat tiles + 9 charts: requests/day, status codes, top countries, unique visitors/day, bandwidth/day, hourly requests, top paths, cache-status mix, device split). Cloudflare range follows the shared tabs, clamped to 7/30 (90/all-time → 30). `StatTile` now borderless content inside the rounded bands.
- [x] **Tests:** `test_cloudflare.py` — config gating, query building, `parse_zone_response()`/`_parse_breakdown()`. Live fetch path isn't unit-tested (needs real credentials).
- **Files:** `backend/app/cloudflare.py` (new), `backend/app/{main,schemas}.py`, `backend/tests/test_cloudflare.py` (new), `docker-compose.yml`, `docker-compose.prod.yml`, `frontend/src/lib/admin/{StatTile,CloudflareCharts}.svelte`, `frontend/src/routes/admin/+page.svelte`

### STEP 29: SEO — SSR content, readable gymnast URLs, sitemap + robots ✅ (15 Aug 2026)
- [x] `+page.server.ts` SSR loads for all public pages (home, events, event detail, results, gymnasts, gymnast, clubs, club) via a new `lib/backend.ts` helper (`BACKEND_URL = PROXY_TARGET || dev localhost:8000 || backend:8000`, works in dev, dev-Docker and prod). Loads fetch lightweight cached endpoints (`/api/stats`, `/api/events`, `/api/gymnasts`, `/api/clubs`, `/api/gymnast`) — never the heavy wide pivots — so the server-rendered HTML carries real headings, entity names and counts instead of a spinner shell.
- [x] Shared `lib/Seo.svelte` head component: `<title>`, meta description, canonical, `og:*` + `twitter:card`, optional JSON-LD. JSON-LD injected as `{@html \`<script type="application/ld+json">…</script>\`}` at the `svelte:head` level (`{@html}` is NOT evaluated inside a `<script>` element). `lib/seo.ts`: `pageTitle`/`kebabName`/`gymnastPath`/`SITE_NAME`/`SITE_DESCRIPTION`.
- [x] **Readable gymnast URLs** — `/gymnast/{slug}-{kebab-name}` is canonical; plain-slug and legacy gnz_id URLs 301-redirect to the readable form; unknown identities 404. `lib/seo.ts::gymnastPath()` generates links (WideResultsTable, gymnasts list, ranking pages, IdentityReview, sitemap).
- [x] New lightweight `GET /api/gymnast` identity endpoint (by `slug` or `gnz_id`; cached; falls back to a raw `long_scores` name row when no athlete cluster exists) + tests — `/api/medals` only returns medalists, so it can't be used for name lookup.
- [x] Dynamic `robots.txt` and `sitemap.xml` routes: static pages + all events + gymnasts (readable URLs, gnz_id fallback) + clubs, XML-escaped; robots disallows `/api`, `/login`, `/admin`, `/upload`, `/rankings`, `/wellington-ranking`.
- [x] `SEO_VERIFICATION_META` env hook: `+layout.server.ts` reads the raw string, `+layout.svelte` injects it via `{@html}` in `svelte:head` — Google/Bing site verification without code changes.
- [x] Internal gymnast links updated to readable URLs; patch notes + docs (AGENTS.md SEO section).
- **Files:** `frontend/src/lib/{Seo.svelte,seo.ts,backend.ts}` (new), `frontend/src/routes/{+layout.server.ts,+layout.svelte,+page.server.ts,+page.svelte}` + SSR loads on `events/`, `events/[id]/`, `results/`, `gymnasts/`, `gymnast/[slug]/`, `clubs/`, `club/[club]/`; `frontend/src/routes/{robots.txt,sitemap.xml}/+server.ts` (new); `backend/app/main.py` (`/api/gymnast`), `backend/tests/test_api.py`

### STEP 30: Precomputed Data Stores (Materialized After Upload)
Rebuild derived data after every mutation so ranking toggles, event/gymnast/club pages and all-results respond near-instantly. **Zero API or frontend changes** — the speedup is entirely backend: replace per-request Pandas pivots and ranking SQL with lookups into a persistent, precomputed layer.

- **Why now:** writes are rare (admin-only) and already funnel through `invalidate()` (`cache.py:76`); reads dominate. The expensive units today are the wide pivots (300s TTL, recomputed on every miss) and the rankings — `/api/rankings` (`main.py:1161`) and `/api/rankings/wellington` (`main.py:1498`) are **not cached at all**, re-running SQL + `_build_event_marks` on every toggle.

- **New file `data/materialized.db`** (separate from `results.db`, same PRAGMAs + passive checkpoint as `database.py:12-21`, own `create_engine`/`SessionLocal` in `materialize.py`). Derived data is rebuildable, so a bug can never corrupt source data and the 75 MB main DB doesn't bloat:
  - `meta(key, value)` — `schema_version`, `ready`, `building`, `needs_rebuild`, `last_rebuild_at`, `last_rebuild_ms`, `last_rebuild_size_bytes`.
  - `materialized_events(event_id, year, event_name, event_sort, present_apps JSON, has_wag, has_mag)` — per-event metadata for exact column/ordering fidelity.
  - `wide_rows(id, event_id, year, event_sort, discipline, athlete_id, club, gnz_id, name, payload JSON)` — the output of `_pivot_long_rows`, one row per `(event, discipline, athlete, round_type)`; `payload` is the wide row dict. Indexed `(event_id)`, `(athlete_id, year)`, `(club, year)`.
  - `ranking_marks(key, payload JSON)` — `_build_event_marks` output as a JSON blob per `(year, discipline, step, division)` (key e.g. `WAG|2025|STEP 2|OVER`, division `""` = unfiltered). `rebuild_all` injects `slug` into each `meta_by_key` entry so the blob is self-contained (derivation no longer needs a live `Athlete` map).
  - ~~`wellington_cache(key, payload JSON)`~~ — a Wellington store was trialled (full `WellingtonRankingResponse` per `(year, discipline, step)`) but **removed**: the page is low traffic and an intent toggle must reflect on the very next read, so `/api/rankings/wellington` stays **always live-computed** (~130 ms/step) and the ~11 s rebuild Phase C was dropped.

- **Rebuild pipeline** (`materialize.py`): `rebuild_all()` in one transaction — Phase A loops `_compute_pivot(event_id, session)` per event → `materialized_events` + `wide_rows`; Phase B discovers distinct `(year, discipline, step, division)` and replays the `main.py:1183-1208` query into `_build_event_marks` per key → `ranking_marks`. (Phase C, which computed Wellington blobs, was removed along with the Wellington store.) Commit sets `ready=1`/`building=0`. All reuses the **existing tested** pivot/marks functions — no duplicated ranking logic. WAL readers always see the previous or new complete version, never a partial one.

- **Triggers — the single hook:** `invalidate()` (already called on upload `main.py:2852`, intent toggle `1643`, club aliases `808`, merge/split `2629/2709`, inline edit `2343`, dedupe/backfill/reconcile CLIs, refresh-cache `1865`) additionally sets `needs_rebuild=1` + kicks `rebuild_async()` (daemon thread, single lock). `_ingest_event` first inserts the new event's `wide_rows` + `materialized_events` row **synchronously** so the event page is instantly correct, then triggers the background full rebuild.

- **Boot + readiness model:** rebuild **in the background on every boot** (after `init_db()` → `rebuild_athletes()`). This is required because several mutation paths run as **separate processes** (`dedupe_events.py`, `repair_identities.py`, `reconcile_clubs.py`, `backfill_host_club.py`) whose `invalidate()` only touches their own memory — and `repair_identities` rewrites names/gnz_ids without changing row counts/ids, so any count/id fingerprint would miss it. Every rewritten endpoint keeps a 2-line fallback guard `if not store.ready: return <old live compute>` (the old functions are retained anyway), giving zero-downtime boots/rebuilds.

- **Endpoint rewiring** (fidelity requirements):
  - `GET /api/events/{id}/results/wide` (`main.py:2999`) → `SELECT payload FROM wide_rows WHERE event_id=?` grouped by discipline. **Columns have NO `event_name`** (matches `_compute_pivot`); columns rebuilt via `_wide_column_list_for_prefixes(prefixes, present_apps)`.
  - `GET /api/results/wide-all` (`main.py:3019`) → resolve `slug`/`gnz_id` → `athlete_id` via `resolve_identity`, then indexed `wide_rows` filter. **Columns DO include `event_name` at index 0** and rows carry `event_name`+`event_id` (matches `_compute_pivot_multi`). Preserve the `{"name": …}` no-results fallback from `Athlete.canonical_name`.
  - `GET /api/rankings` (`main.py:1161`) → `ranking_marks` blob → existing in-memory derivation (`main.py:1220-1350`; `_is_qualifier`, `_RANKING_MARKS`, quota, rank/tie, `_compute_apparatus_specialists`). Toggles become µs-scale.
  - `GET /api/rankings/apparatus` (`main.py:1363`) → same blob → `main.py:1431-1493` derivation.
  - `GET /api/rankings/wellington` (`main.py:1636`) → **not rewired** — stays always live-computed (low traffic; an intent toggle must show immediately). The `wellington_cache` Phase 3 store was built then removed.

- **Rollout safety:** env flag `MATERIALIZED_READS` (default `1`); `0` forces every rewritten endpoint through the live-compute fallback unconditionally — instant rollback without redeploy. Each rebuild logs per-phase timings + final size into `meta`, surfaced via `GET /api/admin/rebuild/status` (Phase 3) and server logs.

- **Phases:**
  - [x] **Phase 0 — benchmark:** `backend/app/bench_materialize.py` (`python -m app.bench_materialize`) — baseline `_compute_pivot` (largest event) / `_build_event_marks` (WAG 2025 STEP 2) / full `/api/rankings`; full rebuild wall time (per phase + total) + resulting `materialized.db` size; equivalence sample (divisions, STEP 5/6 average, STEP 1-4 `_MARK_INDICATOR`, quota/qualifier, wide-all per athlete/club/year/all). Go/no-go: full rebuild ≤ ~60s, per-event insert ≤ ~1s, store ≤ ~100 MB.
  - [x] **Phase 1 — store + rebuild:** `materialize.py`, `init_materialized()`, rebuild pipeline, boot/background wiring, `invalidate()` hook, per-event sync insert on ingest. No endpoint rewiring yet.
  - [x] **Phase 2 — rewire:** wide-all, event-wide, national rankings, apparatus rankings → stores. User-visible speedup lands here.
  - [x] **Phase 3 — Wellington + status:** a `wellington_cache` store + `GET /api/admin/rebuild/status` + admin dashboard note. The Wellington store was later **reverted out** (always live-computed instead) for immediacy + rebuild time; the status endpoint remains.
  - [ ] **Phase 4 — docs:** AGENTS.md/MEMORY.md + `patch_notes.json` entry ("pages pre-built after each upload — much faster loads").

- **Tests** (`tests/test_materialize.py`, plain asserts / real data / no mocks): store-backed vs computed equivalence across param samples; column-fidelity (single-event no `event_name` vs wide-all `event_name` first — guards the gymnast-page `stickyCol="event_name"` contract); rebuild idempotence (second run no-op); failure safety (mid-rebuild exception leaves prior version + `needs_rebuild` set); boot-staleness (mutate source DB via a second connection simulating `repair_identities`, assert boot rebuild refreshes); upload immediacy (new event queryable instantly, `needs_rebuild` set). Existing 332 tests stay green.
- **Files:** `backend/app/materialize.py` (new), `backend/app/bench_materialize.py` (new), `backend/app/{cache,main}.py`, `backend/tests/test_materialize.py` (new)

### Next Steps
- [x] Medal counts + totals for gymnasts, clubs and regional teams
  - Gold/silver/bronze (G/S/B) medal tallies per gymnast, per club, and per regional/provincial team, aggregated from `LongScore.apparatus_rank` / `aa_rank` (1 = gold, 2 = silver, 3 = bronze) across scored ranking rows. Regional teams (e.g. `Counties - Manukau`) resolve via the club→region lookup, and National Championships (`is_national` events) medals can be tallied separately as "Nationals medals" alongside season totals.
  - Decide scope: per-year vs all-time, whether apparatus ranks count alongside AA (or AA only), and whether Nationals medals are broken out separately. Ties in the source rankings need a rule (e.g. both athletes share gold, or count by distinct rank value).
  - Backend: aggregation endpoint(s) — e.g. `GET /api/medals?year=` returning per-gymnast, per-club and per-region counts (golds, silvers, bronzes, total, plus a nationals breakdown), cached like `/api/stats`.
  - Frontend: medal badges/totals on the gymnast page (`/gymnast/[gnz_id]`), club page (`/club/[club]`), the `/clubs` region lists, and optionally the `/gymnasts` list; exportable alongside existing tables.
  - **Files:** `backend/app/main.py`, `backend/app/schemas.py`, `backend/app/cache.py`, `frontend/src/lib/api.ts`, `frontend/src/routes/gymnast/[gnz_id]/+page.svelte`, `frontend/src/routes/club/[club]/+page.svelte`, `frontend/src/routes/gymnasts/+page.svelte`, `frontend/src/routes/clubs/+page.svelte`
- [x] Edit row functionality for admin
  - Inline edit (admin Edit toggle on results tables) updates name / GNZ ID / club / division / round-type. `PATCH /api/admin/scores/gymnast` matches rows by `(event_id, slug)` when a slug is sent (same-name athletes edit independently) else `(event_id, case-insensitive name)`. Name/GNZ ID edits propagate across all the athlete's events (so `rebuild_athletes`'s majority-canonical back-write can't revert them); club/division/round-type stay event-scoped, with round-type/division scoped by the currently-displayed value. `rebuild_athletes` runs only for identity-affecting edits (division/round saves are ~instant); the event's materialized wide rows are sync-refreshed (`rebuild_event`) so the table reflects the change immediately. Frontend reloads with a no-store fetch (bypassing the 300s browser cache) and restores the current tab/search/filters/sort/page; edits are keyed by stable `(event, slug)` so sorting/paging mid-edit can't mis-apply values, and the row's Save button shows a spinner while an identity edit re-clusters.
  - **Files:** `frontend/src/lib/WideResultsTable.svelte`, `frontend/src/lib/api.ts`, `backend/app/main.py`, `backend/app/schemas.py`, `backend/tests/test_admin_edit.py`
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
- [x] Interactive season timeline (train-map style)
  - A reusable `Timeline` component (`frontend/src/lib/Timeline.svelte`) embedded at the top of the `/events` page (hidden on mobile via `hidden md:block`, desktop only): a horizontally-scrollable chart of every competition in the selected year, drawn like a London Underground map — theme-aware "ink" lines (`var(--color-base-content)`, dark in light mode / light in dark mode) with a consistent stroke width, 45° elbow joins, inline station-style labels. No backend changes needed: the events page already loads `listEvents()` + `listKnownClubs()` and passes both as props, so the component makes no fetches of its own.
  - Layout: a full-width SVG with a fixed-pitch week column along the x-axis (month labels + faint gridlines). The chart spans from **1 week before the first event to 1 week after the last event** (no long empty off-season stretch). A main line runs horizontally; each week that hosts a competition gets a white (base-100) station dot on the line (painted above the branches), and each competition branches off its week's dot with a 45° elbow to an inline label showing the event name (truncated to 22 chars on the chart, full name in the tooltip) with a small date line below.
  - Colouring: each competition's region identity is carried by a 2×2 rounded checkerboard marker (first two colours of its host club's `REGION_PALETTES` entry, club→region resolved via `listKnownClubs()`, same pattern as the events page host-club badge) sitting at the elbow end of its branch. Nationals (`is_national`) and events with no/unknown host club fall back to a neutral grey checkerboard; a National Championships week keeps an accent ring around its dot. Branch lines, dots and labels are drawn in three layers (all lines → all labels/checkerboards → week dots) so no diagonal can overpaint a checkerboard or date label; bottom-half dates are offset right so the next stacked diagonal doesn't cross them. WAG/MAG and multi-day spans noted via the tooltip. No legend under the chart.
  - Interaction: clicking a competition label/dot navigates to `/events/{id}`; hover/focus highlights that branch and dims the rest; a fixed-position tooltip shows date, host club, region and a WAG/MAG badge (content duplicated in the element's `aria-label`).
  - Year selector: the timeline reads `selectedYear` read-only and is hidden when "All" (null) is selected — the /events page keeps its normal All tab and the timeline only appears for a specific year, so the chart and the events table always show the same year. The standalone `/timeline` route was removed (no nav link).
  - A11y: competition labels are focusable SVG `<a>` elements with `aria-label` (WCAG 2.5.3), min 24px target size; label text drawn with a halo stroke so overlaps stay readable; tooltip content duplicated in the `aria-label` for keyboard/screen-reader users.
  - **Files:** `frontend/src/lib/Timeline.svelte` (new component), `frontend/src/routes/events/+page.svelte` (embeds the timeline, hidden on mobile), `frontend/src/routes/+layout.svelte` (removed `/timeline` nav links + year-selector handling), `frontend/static/patch_notes.json` (notable user-facing change)
- [x] Gymnast page Personal Bests card + season meta
  - `SeasonBest.svelte` renders at the top of `/gymnast/[gnz_id]` when a specific year is selected (not "All"): the best score on each apparatus that season (secondary-coloured box + D-score underneath, tooltip shows the competition/round), the best all-around actually achieved (`aa-score` max, excluding apparatus-finals/day-2 rounds), and the Best Possible AA (sum of the per-apparatus bests, primary-coloured box, with an explanatory tooltip). A vertical divider separates the apparatus from the Best Possible AA.
  - When a year is selected, the gymnast's GNZ ID, club (linked), region badge and the step(s) they competed in are shown under the name (`nameBadge`/`nameMeta` snippets); the page now defaults to the current year (most recent year with data as a fallback) by setting the global `selectedYear` once if still unset.
  - **Files:** `frontend/src/lib/SeasonBest.svelte` (new), `frontend/src/lib/WideResultsTable.svelte` (new optional `onData` callback + `afterHeader`/`nameBadge`/`nameMeta` snippets), `frontend/src/routes/gymnast/[gnz_id]/+page.svelte`
- [x] Event page Nationals badge should show next to name, not discipline, also use accent badge
- [x] Parser: skip DNS / no-score passes at ingest time
  - Scoreholder emits an explicit DNS score item (`pass_final_score` decodes to `"dns"`, `d_score=0`, `e_score=10`) for every apparatus/day an athlete didn't compete on multi-day meets. The parser previously stored these as normal `long_scores` rows (`_sanitise_float("dns")` → NULL total), creating phantom 2+ pass structures. `_build_wide_row` (transformer.py) tolerates a DNS pass-1 (a DNS pass never hides a real pass-2 score and is never averaged into vault aggregation), and the wide table renders missing apparatus as "DNS" anyway, so dropping the rows at ingest is safe. The parser emission loop now skips any score item whose decoded `pass_final_score` is not numeric (parser.py, in the `for si in source_items:` loop) — this drops `"dns"`/`"dnf"`/`"zero"` strings and missing scores before a row is built. The `scores_by_id` indexing loops are untouched so pass numbering and bonus propagation still work. Existing stored DNS rows intentionally left in place — harmless since the transformer handles them.
  - **Files:** `backend/app/parser.py`, `backend/tests/test_parser.py` (regression test `TestSkipDnsRows`, parametrized over mgi-wag-2026.json + hve-2026.json)

### Deployment: Homeserver infra upgrade (tunnel + auto-deploys + R2 backups)
Maintenance-window task — run late at night when traffic is ~0. Rollback-safe: keep NPM + port-forward until the tunnel is verified, then remove.

- [ ] **Cloudflare Tunnel (replaces NPM + port-forward, kills all cert management)**
  - Cloudflare Zero Trust → Networks → Tunnels → create "home" tunnel → copy connector token → put in server `.env` as `TUNNEL_TOKEN`.
  - Add `cloudflared` service to `docker-compose.prod.yml` (same internal network as `frontend`; `command: tunnel run`; `restart: unless-stopped`).
  - Add public hostname on the tunnel: `results.coach.tools` → HTTP → `frontend:3000` (Cloudflare creates the DNS route + serves its own edge cert — no Let's Encrypt, no origin cert, no renewals).
  - Cutover: `docker compose up -d` → verify `https://results.coach.tools` + `/api/health` through the tunnel → then delete NPM proxy host + remove router 80/443 port-forward. Roll back by re-enabling NPM/port-forward.
  - **Files:** `docker-compose.prod.yml`, server `.env`, Cloudflare dashboard
- [ ] **Pull-based automated deploys (no inbound SSH needed)**
  - CI: on push to `main`, build backend + frontend images → push to GHCR as `latest` + `sha-<short>` (public images → anonymous pull on the server).
  - Server cron every ~5 min runs `scripts/deploy.sh`: compare remote GHCR digest of `latest` vs a stamp file → if changed, `docker compose pull && docker compose up -d` → verify `/api/health` → update stamp.
  - `docker-compose.prod.yml` services pinned to GHCR `image:` tags (server never builds).
  - **Files:** `.github/workflows/build.yml` (new), `scripts/deploy.sh` (new), `docker-compose.prod.yml`
- [ ] **Nightly off-site backups → Cloudflare R2**
  - `scripts/backup.sh` (cron 02:30): one-off container mounts `backend_data` volume → `sqlite3 .backup` (WAL-safe) + tar `clubs_and_regions.json` + `jwt_secret.txt` → `rclone copy` → R2 bucket `nz-gymnastics-backups`. Retention 14 daily + 12 monthly. Optional healthchecks.io ping so a silent failure is noticed.
  - `scripts/restore.sh`: list R2 backups, restore a chosen one into the volume.
  - **Files:** `scripts/backup.sh` (new), `scripts/restore.sh` (new)
- [ ] **Monitoring**
  - Cloudflare health check on `https://results.coach.tools/api/health` (catches box/power/internet outages).
  - Watchdog in `deploy.sh`/cron: restart any container stuck unhealthy.
  - **Files:** Cloudflare dashboard, `scripts/deploy.sh`
- [ ] **Docs**
  - Update `DEPLOYMENT.md` (tunnel runbook replaces the NPM cert-diagnosis runbook) + `AGENTS.md` (deploy/backup/restore/monitor commands + scaling notes).
  - **Files:** `DEPLOYMENT.md`, `AGENTS.md`

Note: no app code changes. The tunnel, GHCR pull and R2 backup are all independent of each other — each can ship alone if a step stalls.