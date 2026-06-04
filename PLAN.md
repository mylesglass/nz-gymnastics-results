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

### Step 4: ID Resolver
- [ ] Create `backend/app/resolver.py` — lookup maps for the flat JSON structure
- [ ] `eventParticipants` -> name, GNZ ID, club
- [ ] `performanceIndividuals` -> link entity IDs to participants and units
- [ ] `eventOrganizations` -> club name
- [ ] `units` -> unit name, discipline
- [ ] **Test:** Unit tests with mock data

### Step 5: JSON Parser (Long Format)
- [ ] Create `backend/app/parser.py`
- [ ] Parse uploaded JSON, resolve all IDs, decode scores, extract rankings
- [ ] Produce long-format rows: one per gymnast per apparatus pass
- [ ] Handle DNS, Zero, multi-pass vaults, multi-unit gymnasts
- [ ] Store in SQLite via SQLAlchemy
- [ ] Re-upload: delete existing event data, re-parse
- [ ] **Test:** End-to-end test with real JSON file from `data-collection/2026/`

### Step 6: FastAPI Endpoints
- [ ] Create `backend/app/main.py`
- [ ] `POST /api/upload` — JSON file upload -> parse -> store -> return summary
- [ ] `GET /api/events` — list stored events
- [ ] `GET /api/events/{id}/results` — wide-format JSON
- [ ] `GET /api/events/{id}/export/csv`
- [ ] `GET /api/events/{id}/export/xlsx`
- [ ] **Test:** httpx integration tests against running FastAPI

### Step 7: Pandas Transformer
- [ ] Create `backend/app/transformer.py`
- [ ] Query long-format from SQLite
- [ ] Pivot to wide format: apparatus columns per gymnast per round
- [ ] WAG: VT, UB, BB, FX + AA
- [ ] MAG: FX, PH, SR, VT, PB, HB + AA
- [ ] Generate CSV/XLSX byte streams
- [ ] **Test:** Verify wide-format output matches expected schema

### Step 8: Frontend — Upload Page
- [ ] `routes/+page.svelte` — drag-and-drop JSON upload
- [ ] File validation, loading state, success/error feedback
- [ ] `src/lib/api.ts` — typed fetch wrappers
- [ ] **Test:** Manual browser test with sample JSON

### Step 9: Frontend — Events & Results
- [ ] `routes/events/+page.svelte` — event list table
- [ ] `routes/events/[id]/+page.svelte` — wide-format results table
- [ ] Sortable columns, CSV/XLSX download buttons
- [ ] **Test:** Manual browser test

### Step 10: Docker & Polish
- [ ] Backend Dockerfile (python:3.12-slim)
- [ ] Frontend Dockerfile (node:20-alpine, adapter-node)
- [ ] docker-compose.yml final configuration
- [ ] Volume mount for SQLite persistence
- [ ] **Test:** Full `docker compose up` end-to-end
