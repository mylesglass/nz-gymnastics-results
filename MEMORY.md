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

**Routes:**
- `/` — Upload page: drag-and-drop JSON file, DaisyUI card drop-zone, loading spinner, alert for errors, success card with links
- `/events` — Event list: `table table-zebra table-pin-rows`, loading spinner, empty-state card with upload link
- `/events/[id]` — Results page:
  - DaisyUI `tabs tabs-boxed` for WAG/MAG switching
  - Columns dynamically split: front meta (ID, Name, Club, STEP/Level, Division, Round), apparatus (single cells showing `D / Total`), back meta (AA, Rank)
  - APPARATUS headers are dynamic: shows "STEP" for WAG, "Level" for MAG
  - Rich hover tooltip (`ScoreTooltip` component using DaisyUI dropdown): full breakdown with D, E, N, Total, Bonus (green), Rank. Multi-pass vaults show per-pass details + display aggregate.
  - Filter bar: search by name/ID, filter by STEP/Level, Club, Division, Round. Filters and search reset on tab switch.
  - Sortable by any column; CSV/XLSX export buttons
- **API client:** `src/lib/api.ts` — typed wrappers, dev mode proxies `/api/*` to `:8000`.

## Test Suite (191 tests)
- `test_decoder.py`: 13 tests — output map building, decoding, DNS detection
- `test_resolver.py`: 21 tests — all resolver functions
- `test_models.py`: 4 tests — CRUD, cascade delete
- `test_parser.py`: 13 known-file parametrized tests + bulk 2025 scan + real-data tests
- `test_api.py`: 12 tests — health, upload validation, list, results, CSV/XLSX export

Run: `cd backend && source .venv/bin/activate && pytest`

## Recent Work (last 10 commits)
- Per-pass vault columns with level-aware aggregation
- DNS/DNF handling + decimal formatting + round_type grouping
- Fix round-type showing as None in wide view
- Add /results/wide endpoint with WAG/MAG tabbed view
- Division extraction (UNDER/OVER/INTERNATIONAL) from competition nodes
- Robust parsing improvements + bulk test suite

## Recent Session (this session)
- Tailwind CSS v4 + DaisyUI v5 integration (dark theme, nav bar)
- Restyled all frontend pages with DaisyUI components (upload, events list, results)
- Grouped apparatus cells with rich hover tooltips (`ScoreTooltip` component)
- Filter bar: search by name/ID, dropdowns for STEP/Level, Club, Division, Round
- Dynamic STEP/Level column header switching between WAG/MAG tabs
- Full-width results page layout AA/Rank last
- Decoded `Bonus` field from publicOutputs, propagated across vault passes
- Added `bonus` column to `LongScore` model
- Bonus displayed in tooltips (green "+0.200" text)
- Updated vault aggregation rules with proper level/round-type distinctions
- Changed `_fmt3` from round → truncate (floor) with floating-point noise cleanup
- Fixed WAG/MAG tab split: switched from apparatus-based heuristic (VT/FX matched both) to using the actual `discipline` field
- Rewrote `pivot_to_wide()` to include all columns in CSV/XLSX exports (per-pass vault details, bonus, division, round_type)

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

## Docker
- `docker compose up --build` starts both services
- Backend: `:8000`, Frontend: `:5173`
- SQLite persists in `backend/data/` via named volume `backend_data`
- Vite proxies `/api/*` to backend in dev mode

## Open Questions / Next Potential Areas
- [ ] Mixed WAG+MAG events: should the frontend show all tabs or auto-detect?
- [ ] Caching: repeated `pivot_to_wide_dict()` calls for same event_id hit SQLite each time
- [ ] Mobile-responsive table: wide tables don't scroll well on mobile
- [ ] Pagination: large events (3000+ gymnasts) may need server-side pagination
- [ ] Edit/re-rank: no mechanism to correct parsed data after upload