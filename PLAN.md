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
- [x] **Test:** 191/191 pytest passing

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
- [ ] Show equals in rankings — backend: append "T" to tied rank values (attempted, reverted — needs correct approach)

### Next Steps
- [ ] Re-implement equals in rankings with correct tie detection logic
- [x] Event page: add year filter/search bar (year dropdown + text search by name)
- [x] Improve error detection when loading JSONs / expandable error details / upload stats
- [ ] Mobile-responsive table improvements
- [ ] Very simple email & password authentication to keep upload page hidden from regular users
- [ ] Allow user to DELETE an event from the event page (if logged in)
- [ ] Allow CSV export of JUST the current information displayed on the filtered table