# NZ Gymnastics Results — Session Memory

## Project Overview
Web app to ingest Scoreholder JSON exports, parse into normalized SQLite, pivot to wide format, and display/export results.

## Architecture
```
[Scoreholder JSON] → FastAPI POST /api/upload → parser.py → SQLite (long-format)
                                                   ↓
                                              transformer.py (pandas pivot)
                                                   ↓
                              CSV/XLSX export ← → SvelteKit frontend (wide table)
                                              WAG/MAG tabs, grouped cells, tooltips
```

## Core Pipeline (in order)

### 1. decoder.py — `build_output_map()` / `decode_public_outputs()`
- Maps opaque `publicOutputs` keys → human names via `performanceRules[].scores[].nodeTree.interface.outputs[]`
- Returns: `pass_final_score`, `d_score`, `e_score`, `neutral_deductions`, `bonus`
- Skips `Execution Deductions` (tracked as `_execution_deductions`)
- `has_dns()` checks for DNS strings or boolean `true` on "Did Not Start" key

### 2. resolver.py — ID chain resolution
- `resolve_clubs()`: org_id → club_name
- `resolve_participants()`: participant_id → {name, gnz_id, org_id}
- `resolve_individuals()`: entity_id → {participant_id, unit_id}
- `resolve_units()`: unit_id → {name, discipline} (infers WAG/MAG from name)
- `resolve_level()`: extracts "STEP N" or "Level N" or known keywords from unit name
- `fix_gnz_id()`: strips leading "GS" prefix

### 3. parser.py — `parse_json()` → (event_info, rows)
Core logic:
1. Build all lookup maps (clubs, participants, individuals, units, output_map, apparatus_map, division_map)
2. Index `performanceScores` by `_id` with decoded outputs
3. **Bonus propagation**: Bonus is an apparatus-level modifier. After indexing scores, propagates bonus across all passes sharing the same `(entityId, unitEventId)` group, then adds it to `pass_final_score`. Handles non-numeric bonus (DNS) safely.
4. Track per-entity per-event pass IDs for correct pass numbering
5. Process `performanceResultTables`:
   - Single-set tables → individual apparatus rankings (emit score + rank rows)
   - Multi-set tables → capture AA aggregate scores only
   - Deduplicate by score `_id` (same score may appear in multiple result sets)
6. Extract division from `resultTableConfigs` → competition node names (UNDER/OVER/INTERNATIONAL)
7. Infer `round_type` from unit name + node name (All Around / Apparatus Finals / Qualification)
8. Sanitise floats/ranks (DNS/DNF → None)

### 4. transformer.py — `pivot_to_wide()` / `pivot_to_wide_dict()`
- `pivot_to_wide()`: For CSV/XLSX — reuses `pivot_to_wide_dict()` to build rich wide rows, then flattens WAG+MAG into a single DataFrame. Includes all columns: meta, apparatus display scores, per-pass vault details (vt-1-*, vt-2-*), bonus, division, round_type.
- `pivot_to_wide_dict()`: For `/results/wide` endpoint — per-pass columns, level-aware vault aggregation, WAG/MAG split tabs using the actual `discipline` field from data (not apparatus heuristic — fixes VT/FX appearing in both tabs).
- **Vault aggregation rules** (`_use_vault_average()`):
  - STEP 6 & STEP 7 → always average both vaults
  - STEP 10, Senior International, Junior International, Youth on Apparatus Finals day → average both vaults
  - STEP 10, Senior International, Junior International on All Around day → best mark (take the higher)
  - Youth on All Around day → best mark (take the higher)
  - Everything else → best mark
- **Decimal formatting** (`_fmt3`): Rounds to 6 decimals first (eliminates floating-point noise), then floors to 3. E.g., `11.5499999` → `11.550`, `11.2995` → `11.299`.
- `_build_wide_row()`: Handles single-pass, multi-pass, DNS/DNF per apparatus, calculates AA total from completed apparatuses

## Database Schema

### events table
| Column | Type |
|--------|------|
| id | INTEGER PK |
| name | STRING |
| start_date | STRING |
| end_date | STRING |
| discipline | STRING (WAG/MAG/WAG+MAG) |
| created_at | DATETIME |

### long_scores table (one row = one apparatus pass for one gymnast)
| Column | Type |
|--------|------|
| id | INTEGER PK |
| event_id | FK → events |
| event_name, gymnast_name, gnz_id, club_name, discipline, level_category, division | STRING |
| apparatus | STRING (VT/UB/BB/FX/PH/SR/PB/HB) |
| pass_number | INTEGER |
| d_score, e_score, neutral_deductions, pass_final_score, bonus | FLOAT |
| apparatus_rank, aa_rank | INTEGER |
| aa_score | FLOAT |
| round_type | STRING |
| date_created | DATETIME |

## Frontend

**Tech:** SvelteKit 5 (runes: `$state`, `$effect`, `$derived`), Tailwind CSS v4 (Vite plugin), DaisyUI v5 (dark theme).

**Shared component:** `WideResultsTable.svelte` — encapsulates all table rendering, filtering, sorting, sticky headers, scroll sync, and duplicate header column width alignment. Used by all result pages.

**Routes:**
- `/` — Upload page: drag-and-drop JSON file, DaisyUI card drop-zone, loading spinner, alert for errors, success card with links
- `/events` — Event list: `table table-zebra table-pin-rows`, loading spinner, empty-state card with upload link
- `/events/[id]` — Per-event results page (thin wrapper around `WideResultsTable`)
- `/results` — All events results page (thin wrapper around `WideResultsTable`, adds Event filter + column)
- `/gymnast/[gnz_id]` — Individual gymnast results (thin wrapper, shows matches across all events)
- `/club/[club]` — Club results (thin wrapper, shows all gymnasts from that club across all events)
- **API client:** `src/lib/api.ts` — typed wrappers, dev mode proxies `/api/*` to `:8000`.
- **MultiSelect:** `src/lib/MultiSelect.svelte` — DaisyUI dropdown with checkboxes, Clear button, `min-w-48` buttons
- **ScoreTooltip:** `src/lib/ScoreTooltip.svelte` — DaisyUI dropdown hover card showing D, E, N, Bonus, Rank for each apparatus

### Table Features
- Column widths synced between duplicate sticky headers and main table via JS measurement + explicit `width`/`min-width` styles
- Name cells link to `/gymnast/[gnz_id]`, club cells link to `/club/[club]` (only when value is present)
- Horizontal scroll synced between duplicate headers and main table
- Client-side CSV export via download snippet

## Test Suite (201 tests)
- `test_decoder.py`: 14 tests — output map building, decoding, DNS detection, Start Value
- `test_resolver.py`: 21 tests — all resolver functions
- `test_models.py`: 4 tests — CRUD, cascade delete
- `test_parser.py`: 35 parametrized tests + validation + equal-discarded regression — 15 known-file tests + bulk 2025 scan + real-data + validation + edge case tests
- `test_api.py`: 13 tests — health, upload validation, list, results, CSV/XLSX export

Run: `cd backend && source .venv/bin/activate && pytest`

CLI batch validation: `python -m app.validate_json path/to/file.json [path/...]`

## Recent Work (last 10 commits)
- Parser robustness: equal-discarded fix, Start Value mapping, input validation, batch CLI
- Per-pass vault columns with level-aware aggregation

## Recent Work (last 10 commits)
- Per-pass vault columns with level-aware aggregation
- DNS/DNF handling + decimal formatting + round_type grouping
- Fix round-type showing as None in wide view
- Add /results/wide endpoint with WAG/MAG tabbed view
- Division extraction (UNDER/OVER/INTERNATIONAL) from competition nodes
- Robust parsing improvements + bulk test suite

## Recent Session (this session)

### Refactor: shared WideResultsTable component
- Extracted ~90% duplicated logic from `events/[id]/+page.svelte` and `results/+page.svelte` into `$lib/WideResultsTable.svelte`
- Component props: `loadData`, `showEventFilter`, `extraHeadLabels`, `download` snippet, `empty` snippet
- Both pages are now thin wrappers (~30 lines each)

### Duplicate header column width alignment
- Added `columnWidths` state + measurement `$effect` that queries `<th>` widths from the main `<thead>`
- ResizeObserver catches window resize and re-measures
- Applied explicit `width` + `min-width` to duplicate header `<th>` elements
- Applied `min-width` to main table `<th>` elements for column stability

### Gymnast & Club filter routes
- New `GET /api/results/wide-all?gnz_id=...&club=...` query params (backend `pivot_to_wide_dict` + `main.py`)
- New `/gymnast/[gnz_id]` route — shows all results for a gymnast across events
- New `/club/[club]` route — shows all results for a club across events
- Name and club cells are clickable links in the table (conditional on value being present)
- Client-side CSV download on both pages

### Bug fixes
- `api.ts`: replaced `new URL()` with string concat + `URLSearchParams` — `new URL` throws on relative paths in dev mode
- `transformer.py`: added `numpy.int64` → `int` / `numpy.floating` → `float` conversion in NaN cleanup loop to fix JSON serialization 500 error on filtered queries

### UX tweaks
- `MultiSelect` buttons: `max-w-52` → `min-w-48` (wider filter buttons)
- Column widths synced between duplicate headers and main table

### Parser robustness analysis
- Scanned all 40 real JSON files in `data-collection/2025/json/` for structural variations
- Found 1 real data bug: `"equal-discarded"` status not filtered (31 files affected)
- Found 1 missing field: `"Start Value"` output not mapped (kaitaia_2025.json)
- Found 44 unit name patterns that fall through `resolve_level` (cosmetic, not breaking)
- Old format files (`quar/`, `Archive/json`) use a completely different JSON structure (`{event, sessions, rounds, scores, competitors, organizations}`) — not relevant, won't be used going forward

## Recent Session (this session)

### Parser robustness (Step 13)
- **`equal-discarded` fix**: Changed status check in `parser.py` from `== "discarded"` to `in ("discarded", "equal-discarded")` in two locations (ranking-level and source-item-level). Prevents duplicate rows from tied-then-discarded scores affecting 31/40 files.
- **`Start Value` mapping**: Added `"Start Value": "start_value"` to `_OUTPUT_NAMES_TO_COLUMNS` in decoder.py; added `start_value` to default result dict; added `start_value` column to `LongScore` model + row construction in parser. Vault-specific field from kaitaia_2025.json now decoded and stored.
- **Input validation**: Added `validate_upload_structure(data)` that checks for all 7 required top-level keys + non-empty `events` list + event name. Returns list of error messages. Upload endpoint returns 422 with structured errors.
- **Parse error handling**: `parse_json()` now raises `ParseError` for internal errors; upload endpoint catches it and returns 422.
- **Batch validation CLI**: `python -m app.validate_json path/to/file.json [path/...]`. Accepts files and directories. Runs structural validation + full parse on each, prints PASS/FAIL per file. Exits non-zero if any fail.
- **Regression tests**: 10 new tests: `validate_upload_structure` (6), `equal-discarded` filtering (2), `Start Value` decode (1), API validation error (1). Total: 201 tests, all pass.

## Known Edges & Gotchas
- **WAG/MAG discipline split**: Tab assignment now uses the `discipline` field from data. Previously used apparatus presence (VT/FX appeared in both lists, causing all gymnasts to show in both tabs).
- **Vault aggregation**: Different levels use different rules (average vs best-of-2). See `_use_vault_average()` in transformer.py for complete NZ-specific rule table.
- **Bonus**: Bonus is an apparatus-level modifier stored on only one pass's score definition. Propagated at parse time across all passes in the same `(entityId, unitEventId)` group.
- **Floating point**: `11.35 + 0.2` = `11.549999999999999` in IEEE 754. `_fmt3` rounds to 6 decimals before flooring to compensate.
- **Division extraction**: `_extract_division()` in parser.py uses heuristic text matching (UNDER/OVER/A/B). Some competitions may have non-standard naming.
- **Multi-unit gymnasts**: ~38% compete in 2 units (e.g., Day 1 AA + Day 2 Apparatus). Entity tracking handles this via entity_event_passes tracking.
- **Score deduplication**: Same `performanceScore._id` can appear in multiple result sets. `emitted_score_ids` set prevents duplicates.
- **Discipline inference**: WAG from "STEP" or "WAG" in unit name; MAG from "Level" or "MAG". Falls back to event-level hint.
- **GNZ ID**: Stored without "GS" prefix after `fix_gnz_id()` cleanup.
- **5-key DNS variants**: Some files encode DNS via 5-key node-tree instead of 4-key normal. `has_dns()` handles both string and boolean forms.
- **Frontend builds take ~7 min on first Docker run** (npm install). Subsequent builds are cached.
- **Parser: `"equal-discarded"` status** — appears in 31/40 files from tied scores; not filtered out. Could produce duplicate rows.
- **Parser: `"Start Value"` output** — vault-specific field in `kaitaia_2025.json`; not mapped in `_OUTPUT_NAMES_TO_COLUMNS`, silently dropped.
- **Parser: 44 unit name patterns** fall through `resolve_level()` returning raw name (e.g. "Bronze All Around & Apparatus", "WAG Step1 C1", "MAG Grade 1"). Cosmetic only — no data loss.
- **Parser: `"Open"` division** — competitions like affinity, dga-invitational, tristar have open-section competitors with no division tag; returns `None`, still correct.
- **Two JSON formats exist** — `data-collection/2025/json/` uses the new format (`eventOrganizations`, `performanceRules`, etc); `data-collection/JSON 2025/quar/` and `Archive/json/` use an old format (`event`, `sessions`, `rounds`). Old format is not supported and won't be used going forward.
- **`new URL()` breaks with relative URLs** — `api.ts`: `new URL("/api/results/wide-all")` throws when `API_BASE = ""` in dev mode. All API functions must use string concatenation for relative URLs.
- **Numpy types in JSON responses** — pandas/numpy produce `numpy.int64` and `numpy.float64` values that FastAPI's `jsonable_encoder` can't serialize. Must convert to native Python types in transformer.py.

## Docker
- `docker compose up --build` starts both services
- Backend: `:8000`, Frontend: `:5173`
- SQLite persists in `backend/data/` via named volume `backend_data`
- Vite proxies `/api/*` to backend in dev mode

## Open Questions / Next Potential Areas
- [ ] Parser robustness: fix `"equal-discarded"` filter, add input validation, add batch validation CLI (see PLAN.md Step 13)
- [ ] Caching: repeated `pivot_to_wide_dict()` calls for same event_id hit SQLite each time
- [ ] Mobile-responsive table: wide tables don't scroll well on mobile
- [ ] Pagination: large events (3000+ gymnasts) may need server-side pagination
- [ ] Edit/re-rank: no mechanism to correct parsed data after upload