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
| role | STRING (admin/member) |
| permissions | STRING (comma-separated: rankings.national, rankings.wellington) |
| created_at | DATETIME |

## Auth (JWT-based, role-based access)

### Backend
- `backend/app/auth.py`: bcrypt hashing, JWT create/decode (HS256, 7-day expiry), `require_role()` and `require_permission()` FastAPI dependency factories
- `require_permission(*keys)`: DB lookup of `User.permissions`; admins always pass; used by ranking endpoints (`/api/rankings`→national, `/api/rankings/wellington` + `GET /api/wellington/intents`→wellington, `/api/rankings/steps`→either)
- `effective_permissions()`: admins report all permissions, members report their stored list
- `seed_admin_user()`: reads `ADMIN_USERNAME`/`ADMIN_PASSWORD`/`ADMIN_ROLE` env vars on startup; creates admin user if not exists
- Auto-generated `JWT_SECRET` persisted to `data/jwt_secret.txt` (survives container restarts)
- When `ADMIN_PASSWORD` env var is unset, auth is disabled (all endpoints public)

### Endpoints
- `POST /api/auth/login` → returns JWT token + user info (incl. effective permissions)
- `POST /api/auth/register` → create user (admin only); new members default to `rankings.national`
- `GET /api/auth/users` → list users (admin only)
- `PATCH /api/auth/users/{id}/permissions` → update a user's ranking-page access (admin only)
- `GET /api/auth/me` → DB-fresh `{ username, role, permissions }` for the token holder
- `POST /api/auth/users/{id}/reset-password` → change password (admin only)
- `DELETE /api/auth/users/{id}` → delete user (admin only)
- `GET /api/admin/duplicates` → list duplicate GNZ ID groups by name (with club/level instances)
- `POST /api/admin/duplicates/fix` → auto-fix high-confidence duplicates, return low-confidence for review
- `POST /api/admin/duplicates/apply` → apply manual ID selections

### Frontend
- JWT stored in `localStorage`, read by `getToken()` / `setToken()`
- `currentUser` Svelte store holds `{ username, role, permissions }`; permissions persisted to `localStorage` under `nzgr_permissions`
- `setPermissions()` / `hasPermission()` in `lib/auth.ts` (admins always pass)
- `+layout.svelte` refreshes permissions via `me()` on mount and gates the Rankings nav links (desktop + mobile); its route guard (`requiresAuth`/`routeAllowed`) redirects signed-out users and members without the relevant permission away from `/admin`, `/rankings`, and `/wellington-ranking`
- `logout()` clears token + store
- Nav bar shows/hides Upload/Admin/Rankings links based on role/permissions
- All write API calls send `Authorization: Bearer <token>` header

## Frontend

**Tech:** SvelteKit 5 (runes: `$state`, `$effect`, `$derived`), Tailwind CSS v4 (Vite plugin), DaisyUI v5 (dark theme).

**Shared components:**
- `WideResultsTable.svelte` — encapsulate all table rendering, filtering, sorting, sticky headers, scroll sync, duplicate header column width alignment, region column with colored dots, truncated event names. Used by all result pages.
- `Dialog.svelte` — a11y dialog: `role="dialog"` + `aria-modal`, labelled heading, initial-focus move, Tab/Shift+Tab focus trap, Escape close, focus restore to opener, backdrop click. Used by all 5 modals.
- `RegionBadge.svelte` — region pill with 2x2 checkerboard (primary+secondary colors) on primary fill, `whitespace-nowrap`, used in rankings and clubs pages
- `NZRegionMap.svelte` — interactive SVG map of 15 regions; hovered/selected regions fill with a scrolling checker pattern (each region has its own CSS-var-driven direction + duration; seamless loop, respects `prefers-reduced-motion`). Regions are keyboard-focusable `role="button"`s with `focus-visible` outline, `aria-pressed` on the active region, `aria-live` announcement on selection.
- `regions.ts` — `REGION_PALETTES` constant mapping 15 NZ regions to 2-3 hex colors (NZ sports team inspired), plus `REGION_ORDER` (north→south). `textColor()`/`gradientTextColor()` pick `#000` vs `#fff` via WCAG relative-luminance contrast.
- `ScoreTooltip.svelte` — DaisyUI `dropdown-hover` tooltip (opens on hover + focus-within) showing D, E, N, Bonus, Rank per apparatus; `<button>` trigger with `aria-label` (visible text + context) + `aria-describedby` → `role="tooltip"` panel
- `AATooltip.svelte` — same pattern for AA score/rank/summed D/E/N
- `MultiSelect.svelte` — DaisyUI dropdown with checkboxes, Clear button, `min-w-48` buttons
- `ExportMenu.svelte` — DaisyUI export dropdown (CSV/XLSX/PDF); `export.ts` builds files, XLSX honors `colFormat` (hidden columns + widths), PDF renders table-like columns with header + page numbers, libraries lazy-loaded

**Routes:**
- `/` — Landing page: three plain info items (WAG & MAG, Export & Share, Smart Filtering) above clickable nav cards with live stat badges; "What's new" section from `static/patch_notes.json` (fetched, all entries in a scrollable list)
- `/upload` — Drag-and-drop JSON upload, club mapping dialog, rich success card (gymnast/score/club counts)
- `/login` — Username + password form, redirects to `/`
- `/admin` — Admin dashboard (stats, user management, unified athlete ID reconciliation card with per-instance dropdowns, Quick Fix + Apply Selected buttons)
- `/admin/users` — User management table (create, delete, reset password)
- `/rankings` — Rankings with discipline tabs, STEP dropdown, WAG-only Division dropdown (All/Over/Under, resets on step/discipline change, recomputes the ranking server-side via a `division` query param on `GET /api/rankings` so qualifier/Q/quota/exports all respect it), region quotas + qualifier filter (info tooltips; hidden for STEP 1–4 / MAG Level 1–3), STEP 5/6 use the average of the top 3 marks (three score columns), STEP 1–4 show a rightmost Q column (✓ when 52.000 reached twice), Club/Region header funnel dropdowns filter the loaded rows client-side (exports follow), Total column hidden (bolded Average), "Can't find someone?" note under the table when the qualifier filter is on, partial AA support
- `/events` — Event list with search bar, year filter, rename/delete, Nationals trophy toggle
- `/events/[id]` — Per-event results (thin wrapper around `WideResultsTable`)
- `/results` — All events results (thin wrapper around `WideResultsTable`, adds Event filter column)
- `/gymnast/[gnz_id]` — Individual gymnast results across all events
- `/gymnasts` — Gymnast list (A-Z grouped, live search, GNZ ID shown subtly, ⚠ for multi-ID, comma-separated clubs for multi-club). Sticky header: search box + alphabet jump bar inline, active-letter highlight on scroll, collapsing title, "Back to top" button once scrolled
- `/club/[club]` — Club results across all events
- `/clubs` — Club list: desktop has the interactive NZ map (sticky left) + selected region box (right); mobile (`<lg`) replaces the map with a collapsible accordion of region cards (tap to expand, one open at a time), listed north→south via `REGION_ORDER`

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
- Client-side CSV/XLSX/PDF export via `export.ts` + `ExportMenu.svelte` (SheetJS + jsPDF lazy-loaded; XLSX supports hidden columns and widths via `colFormat`)
- Row hover highlight (`hover:bg-base-300 transition-colors`), `py-1.5` vertical padding
- `whitespace-nowrap` on apparatus score cells
- `truncate max-w-56` on event_name column
- `min-w-full` table fills container width
- Region column filterable via column header dropdown

### Accessibility (STEP 24 — complete, all 6 public pages 100/100 on Lighthouse)
- Shared `Dialog.svelte` for all modals: `role="dialog"`/`aria-modal`, focus trap, Escape, focus restore, labelled heading.
- Tabs are native radios (no `role="tab"`); WAG/MAG toggles are `aria-pressed` buttons.
- Tooltips are DaisyUI `dropdown-hover` (`<button>` trigger, `role="tooltip"`, `aria-describedby`, label-in-name).
- `textColor()`/`gradientTextColor()` use WCAG relative-luminance contrast (`#000` vs `#fff`).
- Skip link, `<main id="main">`, `<nav>` landmarks, `aria-current` on active links, `aria-live`/`role="status"` toasts, `role="alert"` errors, 24px min button targets, reduced-motion gating.
- Reports in `a11y-reports/` (rerun: `./a11y-reports/run.sh before|after [pages...]`, needs `CHROME_PATH`).

## Test Suite (251 tests)- `test_decoder.py`: 14 tests — output map building, decoding, DNS detection, Start Value
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
- **$effect reactivity**: `$effect` tracks all reactive dependencies read inside it — avoid reading state that the effect itself modifies to prevent cycles. Fixed sort-revert bug by using `loaded` flag. Fixed page-reset-next-button bug by reading only filter state, not currentPage.
- **AA score fallback**: `_build_wide_row` now computes AA score from apparatus totals when stored `aa_score` is NULL. This handles cases where the parser's round_type mismatch prevents AA lookup.
- **resolver regex**: `resolve_level()` uses `r"level\s*(\d+)"` (zero-or-more whitespace) — consistent with STEP regex — to handle no-space variants like `"MAG Level3"`.
- **Region enrichment**: Club→region lookup at pivot time via `clubs_and_regions.json`. Changes to lookup file require re-upload of events. Run `reconcile_clubs.py` after adding aliases to fix existing data.
- **Unknown-club check fix**: `find_unknown_clubs()` was reading `orgId`/`participantId` fields that never exist in real Scoreholder files (real: `_id` on `eventOrganizations`, `_id`+`organizationId` on `eventParticipants`) — so it always returned `[]` and variant club names silently passed through. Fixed to use real field names; uploads now 409 with the club-mapping dialog. Regional teams (e.g. `Counties - Manukau`) are stored as club names and resolve to themselves; `Gymsport Manukau` retargets to `Counties - Manukau`.

## Docker
- `docker compose up --build` starts both services
- Backend: `:8000`, Frontend: `:5173`
- SQLite persists in `backend/data/` via named volume `backend_data`
- Vite proxies `/api/*` to backend in dev mode

## Cache Architecture
- **GranularTTLCache** — in-memory dict with per-key TTL.
  - No-TTL entries (pivot caches) stored as direct values.
  - TTL entries stored as `(expiry, value)` tuples, auto-evicted on read.
  - Prefix-based invalidation: `invalidate(event_id)` clears `event:{id}:*` keys.
  - Full clear: `invalidate()` without event_id (used by admin bulk operations).
- **Cached endpoints:**
  - `/api/stats` — key `"stats"`, TTL 300s
  - `/api/gymnasts` — key `"gymnasts"`, TTL 300s
  - `/api/clubs` — key `"clubs"`, TTL 300s
  - `/api/results/wide-all` — key `"wide-all:{year}:{gnz_id}:{club}"`, TTL 300s
  - `/api/events/{id}/results/wide` — key `"event:{id}:pivot:{gnz_id}:{club}"`, no TTL (invalidation-driven)
- **HTTP caching:** `Cache-Control: public, max-age=300, stale-while-revalidate=3600` on GET read endpoints, set via middleware. `no-store, no-cache, private` on admin/write.
- **ETag** — global version counter, incremented on every invalidation. Returned in response headers for conditional requests.

## HTTP Cache-Control
- Middleware at `main.py` `@app.middleware("http")` applies headers based on path + method:
  - Read endpoints → `public, max-age=300, stale-while-revalidate=3600`
  - Admin/write (POST/PUT/DELETE/PATCH) → `no-store, no-cache, private`
- Individual endpoint `cache_headers()` now only sets the ETag (removed Cache-Control).

## Docs Convention
- Whenever updating project docs (MEMORY/README/PLAN/DESIGN-DOCUMENT/BUGS) for a notable user-facing change, also prepend a matching entry to `frontend/static/patch_notes.json` (full history, newest first; landing page shows all entries in a scrollable section).
