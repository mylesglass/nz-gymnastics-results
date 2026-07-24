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
- Returns: `pass_final_score`, `d_score`, `e_score`, `neutral_deductions`, `bonus`, `start_value`
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
9. **Name cleaning**: `_NAME_LEVEL_SUFFIX = re.compile(r"\s+\((?:L\d+|STEP\s*\d+|YI)\)$")` strips `(L6)`, `(STEP 10)`, `(YI)` etc. suffixes from gymnast names at parse time

### 4. transformer.py — `pivot_to_wide()` / `pivot_to_wide_dict()`
- `pivot_to_wide()`: For CSV/XLSX — reuses `pivot_to_wide_dict()` to build rich wide rows, then flattens WAG+MAG into a single DataFrame. Includes all columns: meta, apparatus display scores, per-pass vault details (vt-1-*, vt-2-*), bonus, division, round_type.
- `pivot_to_wide_dict()`: For `/results/wide` endpoint — per-pass columns, level-aware vault aggregation, WAG/MAG split tabs using the actual `discipline` field from data (not apparatus heuristic — fixes VT/FX appearing in both tabs).
- **Region enrichment**: column added between Club and Step at pivot time via `_find_region()` lookup in `clubs_and_regions.json`
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
| d_score, e_score, neutral_deductions, pass_final_score, bonus, start_value | FLOAT |
| apparatus_rank, aa_rank | INTEGER |
| aa_score | FLOAT |
| round_type | STRING |
| date_created | DATETIME |

### users table
| Column | Type |
|--------|------|
| id | INTEGER PK |
| username | STRING UNIQUE |
| hashed_password | STRING |
| role | STRING (admin/uploader) |
| created_at | DATETIME |

## Auth (JWT-based, role-based access)

### Backend
- `backend/app/auth.py`: bcrypt hashing, JWT create/decode (HS256, 7-day expiry), `require_role()` FastAPI dependency factory
- `seed_admin_user()`: reads `ADMIN_USERNAME`/`ADMIN_PASSWORD`/`ADMIN_ROLE` env vars on startup; creates admin user if not exists
- Auto-generated `JWT_SECRET` persisted to `data/jwt_secret.txt` (survives container restarts)
- When `ADMIN_PASSWORD` env var is unset, auth is disabled (all endpoints public)

### Endpoints
- `POST /api/auth/login` → returns JWT token + user info
- `POST /api/auth/register` → create user (admin only)
- `GET /api/auth/users` → list users (admin only)
- `POST /api/auth/users/{id}/reset-password` → change password (admin only)
- `DELETE /api/auth/users/{id}` → delete user (admin only)

### Frontend
- JWT stored in `localStorage`, read by `getToken()` / `setToken()`
- `currentUser` Svelte store holds `{ username, role }` decoded from JWT payload
- `logout()` clears token + store
- Nav bar shows/hides Upload/Admin/Rankings links based on role
- All write API calls send `Authorization: Bearer <token>` header

## Frontend

**Tech:** SvelteKit 5 (runes: `$state`, `$effect`, `$derived`), Tailwind CSS v4 (Vite plugin), DaisyUI v5 (dark theme).

**Shared components:**
- `WideResultsTable.svelte` — encapsulate all table rendering, filtering, sorting, sticky headers, scroll sync, duplicate header column width alignment, region column. Used by all result pages.
- `ScoreTooltip.svelte` — DaisyUI dropdown hover card showing D, E, N, Bonus, Rank for each apparatus
- `AATooltip.svelte` — DaisyUI dropdown-hover tooltip showing AA score, rank, and summed D/E/N across all apparatus
- `MultiSelect.svelte` — DaisyUI dropdown with checkboxes, Clear button, `min-w-48` buttons

**Routes:**
- `/` — Landing page: stats cards, role-based grid (Upload card hidden for non-admins)
- `/upload` — Drag-and-drop JSON upload, club mapping dialog, rich success card (gymnast/score/club counts)
- `/login` — Username + password form, redirects to `/`
- `/admin` — Admin dashboard (stats, user management link, reconcile card)
- `/admin/users` — User management table (create, delete, reset password)
- `/rankings` — Rankings placeholder (member+)
- `/events` — Event list with search bar, year filter, rename/delete for authorized users
- `/events/[id]` — Per-event results (thin wrapper around `WideResultsTable`)
- `/results` — All events results (thin wrapper around `WideResultsTable`, adds Event filter column)
- `/gymnast/[gnz_id]` — Individual gymnast results across all events
- `/gymnasts` — Gymnast list (A-Z grouped)
- `/club/[club]` — Club results across all events
- `/clubs` — Club list (region-grouped)

**Shared stores:**
- `src/lib/year.ts` — `selectedYear` and `yearOptions` stores populated from `GET /api/years`; used globally in nav toggle
- `src/lib/auth.ts` — `currentUser`, `setToken()`, `getToken()`, `logout()`

**Nav bar layout:**
- Logo → Year toggle (DaisyUI `tabs tabs-box` radio inputs) → Role-based links → User badge dropdown (or Login button)
- Theme toggle in footer bottom-right

### Table Features
- Column widths synced between duplicate sticky headers and main table via JS measurement + ResizeObserver
- Name cells link to `/gymnast/[gnz_id]`, club cells link to `/club/[club]`
- Horizontal scroll synced between duplicate headers and main table
- Client-side CSV export via download snippet
- Row hover highlight (`hover:bg-base-300 transition-colors`), `py-1.5` vertical padding
- `whitespace-nowrap` on apparatus score cells
- `truncate max-w-56` on event_name column
- `min-w-full` table fills container width
- Region column filterable via column header dropdown

## Test Suite (251 tests)
- `test_decoder.py`: 14 tests — output map building, decoding, DNS detection, Start Value
- `test_resolver.py`: 21 tests — all resolver functions
- `test_models.py`: 4 tests — CRUD, cascade delete
- `test_parser.py`: 35 parametrized tests + validation + equal-discarded regression — known-file tests + bulk 2025 scan + real-data + validation + edge case tests
- `test_api.py`: 13 tests — health, upload validation, list, results, CSV/XLSX export
- `test_reconcile.py`: 9 tests — athlete ID reconciliation logic

Run: `cd backend && source .venv/bin/activate && pytest`

CLI batch validation: `python -m app.validate_json path/to/file.json [path/...]`

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
- **Parser: `"equal-discarded"` status** — appears in 31/40 files from tied scores; now filtered out.
- **Parser: `"Start Value"` output** — vault-specific field; mapped in decoder.py, stored as `start_value` column.
- **Parser: 44 unit name patterns** fall through `resolve_level()` returning raw name (e.g. "Bronze All Around & Apparatus", "WAG Step1 C1", "MAG Grade 1"). Cosmetic only — no data loss.
- **Parser: `"Open"` division** — competitions like affinity, dga-invitational, tristar have open-section competitors with no division tag; returns `None`, still correct.
- **Name cleaning**: `_NAME_LEVEL_SUFFIX` regex strips `(L#)`, `(STEP 10)`, `(YI)` from gymnast names at parse time. Re-upload required for existing events.
- **Two JSON formats exist** — `data-collection/2025/json/` uses the new format (`eventOrganizations`, `performanceRules`, etc); `data-collection/JSON 2025/quar/` and `Archive/json/` use an old format (`event`, `sessions`, `rounds`). Old format is not supported and won't be used going forward.
- **`new URL()` breaks with relative URLs** — `api.ts`: `new URL("/api/results/wide-all")` throws when `API_BASE = ""` in dev mode. All API functions must use string concatenation for relative URLs.
- **Numpy types in JSON responses** — pandas/numpy produce `numpy.int64` and `numpy.float64` values that FastAPI's `jsonable_encoder` can't serialize. Must convert to native Python types in transformer.py.
- **DaisyUI z-index**: `.dropdown-content` sets `z-index: 1` and overrides Tailwind `z-*` classes because imported after Tailwind — use inline `style="z-index: 50"` to beat specificity.
- **$effect reactivity**: `$effect` tracks all reactive dependencies read inside it — avoid reading state that the effect itself modifies to prevent cycles. Fixed sort-revert bug by using `loaded` flag.
- **Region enrichment**: Club→region lookup at pivot time via `clubs_and_regions.json`. Changes to lookup file require re-upload of events.

## Docker
- `docker compose up --build` starts both services
- Backend: `:8000`, Frontend: `:5173`
- SQLite persists in `backend/data/` via named volume `backend_data`
- Vite proxies `/api/*` to backend in dev mode

## Open Questions / Next Potential Areas
- [ ] Re-implement equals in rankings with correct tie detection logic
- [ ] Mobile-responsive table improvements
- [ ] Performance: caching, query optimisation, application speed
- [ ] Automate reconciliation on upload — trigger reconcile after every successful JSON import
- [ ] Fuzzy name matching — detect nicknames/spelling variations (e.g. "Liz" → "Elizabeth")
- [ ] Conflict resolution UI — admin dashboard to manually pick the correct ID for ambiguous names
- [ ] GNZ ID audit log — track when and why an ID was changed for a gymnast
