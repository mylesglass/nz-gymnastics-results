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
 8. Sanitise floats/ranks (DNS/DNF → None); skip any score item whose decoded `pass_final_score` is not numeric (DNS/no-score passes) at emit time — phantom DNS rows are never stored, the wide table renders missing apparatus as "DNS" anyway
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
| year | INTEGER |
| is_national | BOOLEAN (default false) |
| host_club | STRING nullable (national events default "Gymnastics NZ") |
| created_at | DATETIME |

### long_scores table (one row = one apparatus pass for one gymnast)
| Column | Type |
|--------|------|
| id | INTEGER PK |
| event_id | FK → events |
| athlete_id | FK → athletes (nullable; set by `rebuild_athletes()`) |
| identity_override | STRING nullable (admin force-split boundary) |
| event_name, gymnast_name, gnz_id, club_name, discipline, level_category, division | STRING |
| apparatus | STRING (VT/UB/BB/FX/PH/SR/PB/HB) |
| pass_number | INTEGER |
| d_score, e_score, neutral_deductions, pass_final_score, bonus, start_value | FLOAT |
| apparatus_rank, aa_rank | INTEGER |
| aa_score | FLOAT |
| round_type | STRING |
| date_created | DATETIME |

### athletes table (stable identity layer)
| Column | Type |
|--------|------|
| id | INTEGER PK |
| slug | STRING UNIQUE (`a{sha1-hex10}`, content-addressed) |
| signature_hash | STRING |
| canonical_name | STRING (most-frequent spelling) |
| gnz_id | STRING (most-frequent numeric ID) |
| identity_override | STRING nullable |

### users table
| Column | Type |
|--------|------|
| id | INTEGER PK |
| username | STRING UNIQUE |
| hashed_password | STRING |
| role | STRING (admin/member) |
| permissions | STRING (comma-separated: rankings.national, rankings.wellington) |
| created_at | DATETIME |

### Other tables
- `slug_redirects` — `old_slug` → `athlete_id`, keeps old gymnast URLs working after merges/splits
- `wellington_intents` — `UNIQUE(athlete_id, year)`, intent-submitted gymnasts
- `activity_logs` — logged-in request detail (username, role, method, path, query, status, duration)
- `traffic_daily` — anonymous + logged-in aggregates per `(date, hour, kind, path_group, anonymous)`

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
- `GET /api/rankings/steps` → available steps per `(year, discipline)` (either ranking permission)
- `GET /api/rankings` → national rankings (national permission; qualifier/quota/division params)
- `GET /api/rankings/apparatus` → national apparatus leaderboards (national permission; cached, single-flight)
- `GET /api/rankings/wellington` → Wellington rankings (wellington permission; always live-computed)
- `GET /api/medals` → medal tallies per gymnast / club / region
- `GET /api/gymnast` → lightweight single-gymnast identity lookup by slug or gnz_id (public)
- `GET /api/clubs/known` → known club names (searchable, admin event editing)
- `POST /api/track/page` → page-view beacon (all visitors; anonymous traffic row)
- `GET /api/admin/identity-review` → athlete-level name/ID conflicts (similar_names, name_conflicts, id_conflicts, multi_id_athletes)
- `POST /api/admin/athletes/merge-preview` → read-only per-event change preview for a merge
- `POST /api/admin/athletes/merge` / `POST /api/admin/athletes/split` → merge two athletes / split one into two
- `POST /api/admin/refresh-cache` → clears in-memory cache + bumps materialized-store epoch
- `GET /api/admin/rebuild/status` → `{ready, building, needs_rebuild, last_rebuild_at, last_rebuild_ms, last_rebuild_size_bytes}`
- `GET /api/admin/activity` (+ `DELETE`) → logged-in detail log; `GET /api/admin/activity/summary?days=7|30|90|0` → usage summaries + series
- `GET /api/admin/cloudflare/summary?days=7|30` → Cloudflare edge analytics
- Legacy (still in the API + tested, no longer called by the UI): `GET/POST /api/admin/duplicates*`, `GET /api/admin/suggested-merges`, `POST /api/admin/merge-names`

### Frontend
- JWT stored in `localStorage`, read by `getToken()` / `setToken()`
- `currentUser` Svelte store holds `{ username, role, permissions }`; permissions persisted to `localStorage` under `nzgr_permissions`
- `setPermissions()` / `hasPermission()` in `lib/auth.ts` (admins always pass)
- `+layout.svelte` refreshes permissions via `me()` on mount and gates the Rankings nav links (desktop + mobile); its route guard (`requiresAuth`/`routeAllowed`) redirects signed-out users and members without the relevant permission away from `/admin`, `/rankings` (+ `/rankings/apparatus`), and `/wellington-ranking`. On mount it awaits `checkAuthStatus()` + `me()` via `Promise.allSettled` before `authResolved`; a 401 from `me()` (expired token / rotated JWT secret) auto-logs-out and sets `authRedirectTarget` to `/login`; `parseToken` rejects tokens past `exp`
- `logout()` clears token + store
- Nav bar shows/hides Upload/Admin/Rankings links based on role/permissions
- All write API calls send `Authorization: Bearer <token>` header

## Frontend

**Tech:** SvelteKit 5 (runes: `$state`, `$effect`, `$derived`), Tailwind CSS v4 (Vite plugin), DaisyUI v5 (dark theme).

**Shared components:**
- `WideResultsTable.svelte` — encapsulate all table rendering, filtering, sorting, sticky headers, scroll sync, duplicate header column width alignment, configurable pinned column (`stickyCol` prop, default `name`), region column with colored dots (checker square on mobile), truncated event names, admin inline-edit mode, optional `onData` callback + `afterHeader`/`nameBadge`/`nameMeta` snippets. Used by all result pages.
- `Dialog.svelte` — a11y dialog: `role="dialog"` + `aria-modal`, labelled heading, initial-focus move, Tab/Shift+Tab focus trap, Escape close, focus restore to opener, backdrop click, Escape/Tab stop-propagation for nested inner dialogs. Used by all modals (upload club mapping, users, identity review, edit/delete event).
- `Tooltip.svelte` — shared accessible tooltip: `<button>` trigger with `aria-label` (visible text) + `aria-describedby` → `role="tooltip"` fixed-position panel (auto-flips to stay in viewport, escapes `overflow-x-auto` clipping); opens on hover AND focus, closes on leave/blur/Escape. Base for ScoreTooltip/AATooltip, SeasonBest, RegionCheck, rankings/wellington score + specialist tooltips, header info icons.
- `ScoreTooltip.svelte` / `AATooltip.svelte` — thin wrappers over `Tooltip.svelte` for apparatus score breakdowns (D/E/N/Bonus/Rank, multi-pass vault) and AA totals (summed D/E/N + rank). Used by `WideResultsTable`.
- `RegionBadge.svelte` — region pill with 2x2 checkerboard (primary+secondary colors) on primary fill, `whitespace-nowrap`, used in rankings and clubs pages
- `RegionCheck.svelte` — compact 20px 2x2 checkerboard square + tooltip with the region name; used on mobile for the region column in results tables and the Apparatus Rankings table
- `FilterDropdown.svelte` — multi-select funnel dropdown (menuitemcheckbox options, count badge on the funnel, stays open while toggling, bottom sheet on <768px). Used for rankings Club/Region filters.
- `NZRegionMap.svelte` — interactive SVG map of 15 regions; hovered/selected regions fill with a scrolling checker pattern (each region has its own CSS-var-driven direction + duration; seamless loop, respects `prefers-reduced-motion`). Regions are keyboard-focusable `role="button"`s with `focus-visible` outline, `aria-pressed` on the active region, `aria-live` announcement on selection.
- `SeasonBest.svelte` — gymnast Personal Bests card (best per apparatus + D, best achieved AA, Best Possible AA), rendered via `WideResultsTable`'s `afterHeader` snippet when a specific year is selected.
- `Timeline.svelte` — train-map-style season timeline on the `/events` page (desktop only): theme-aware SVG with week column, station dots, region checkerboard markers, hover/focus tooltips, click-to-navigate.
- `charts/ChartJs.svelte` — lazy-loaded Chart.js wrapper (canvas `role="img"` + `aria-label` + visually-hidden data fallback) used by the admin dashboard.
- `regions.ts` — `REGION_PALETTES` constant mapping 15 NZ regions to 2-3 hex colors (NZ sports team inspired), plus `REGION_ORDER` (north→south). `textColor()`/`gradientTextColor()` pick `#000` vs `#fff` via WCAG relative-luminance contrast.
- `ExportMenu.svelte` — DaisyUI export dropdown (CSV/XLSX/PDF); `export.ts` builds files, XLSX honors `colFormat` (hidden columns + widths), PDF renders table-like columns with header + page numbers, libraries lazy-loaded
- `Seo.svelte` + `seo.ts` — shared `<svelte:head>` component (title, description, canonical, OG/twitter, optional JSON-LD) + `pageTitle`/`kebabName`/`gymnastPath` helpers
- `medals.ts` + `MedalBadges.svelte`/`MedalDot.svelte` — medal tally display helpers
- `admin/` — dashboard components: `Overview`, `Activity`, `ActivityCharts`, `CloudflareOverview`, `ActivityLog`, `Upload`, `Users`, `IdentityReview`, `StatTile`

**Routes:**
- `/` — Landing page: three plain info items (WAG & MAG, Export & Share, Smart Filtering) above clickable nav cards with live stat badges; a member-only Rankings card appears for users with national/wellington ranking access (links to `/rankings` or `/wellington-ranking`); "What's new" section from `static/patch_notes.json` (fetched, all entries in a scrollable list)
- `/login` — Username + password form, redirects to `/`
- `/admin` — Single admin page arranged in source-grouped sections (all before the fold on desktop): **Site** (Events/Gymnasts/Scores/Clubs stat tiles + prebuilt-data status), **Manage** (button pills: Refresh Cache + Upload / Users / Identity Review (conflict-count badge)), then a 2/3–1/3 grid: the left two-thirds holds **Server usage** (shared range tabs 24h/7/30/90/All + auto-refresh + 5 usage stat tiles, then the wide stacked charts — traffic over time, peak hour, top pages, top users — each a full-width card with a value header) and below it **Cloudflare** (overview band: selected date range + four stacked long/low sparkline cards — unique visitors, total requests, percent cached, total data served; range follows the shared selector, 90/all-time clamp to the 30-day retention with a badge, configured via `CLOUDFLARE_ZONE_ID` + `CLOUDFLARE_API_TOKEN`, shows a "not configured" note otherwise), while the right third is the logged-in activity log as a scrollable pane that stretches the full height of both sections (its own range/filter/pagination/clear). Each group sits in a subtle rounded flex band (`bg-base-200/50 rounded-2xl`). Upload (drag-and-drop JSON + import-from-URL + club-mapping dialog), Users (create/delete/reset + permissions), Identity Review (merge/split) and Request errors (from clicking the Errors tile) each open in a Dialog. The old `/upload`, `/admin/activity` and `/admin/users` routes are removed — admin components live in `$lib/admin/` and the shared `Dialog.svelte` supports nesting (Escape/Tab stop propagation so inner dialogs like club-mapping/add-user close independently).
- `/rankings` — National Rankings with discipline tabs, STEP dropdown, a callout card at the top (STEP 5+) explaining the ranking system, qualifying marks and the toggles, WAG-only Division dropdown (All/Over/Under, resets on step/discipline change, recomputes the ranking server-side via a `division` query param on `GET /api/rankings` so qualifier/Q/quota/exports all respect it), region quotas + qualifier filter (info tooltips; hidden for STEP 1–4 / MAG Level 1–3), STEP 5/6 use the average of the top 3 marks (three score columns), STEP 1–4 show a rightmost Q column (✓ when 52.000 reached twice), an "Apparatus Qualifiers" section below the table for STEP 8–10 / MAG Level 7+ / Junior+Senior International (gymnasts not in the qualifier-filtered AA table who hit the Wellington apparatus marks — colour-coded badges + tooltips, follows the Club/Region filters), Club/Region header funnel dropdowns filter the loaded rows client-side (exports follow), Total column hidden (bolded Average), "Can't find someone?" note under the table when the qualifier filter is on, partial AA support
- `/rankings/apparatus` — National Apparatus Rankings: WAG/MAG toggle, step select, apparatus radio tabs (WAG `VT,UB,BB,FX`, MAG `FX,PH,SR,VT,PB,HB` + stragglers), WAG division select (disabled for STEP 9/10 + Internationals), Club/Region funnel filters, D-score column, Best column with competition tooltip, CSV/XLSX/PDF export. Ranks each gymnast's best single mark per apparatus for the season.
- `/wellington-ranking` — Wellington Rankings (member+, `rankings.wellington` permission): config callout card, WAG/MAG tabs, step dropdown, main ranking table with slot-aligned score columns + category badges + per-pass apparatus tooltips, admin Intent checkboxes, "Apparatus Specialists" table (solid vs ghost badges with per-competition tooltips), "Not on the Ranking" table (alphabetical, checklist tooltip per athlete), CSV/XLSX/PDF export. No filter toggles — the main table always shows qualified + intended athletes; `not_ranked` captures everyone else. Ranked live on every read (not from the materialized store) so intent toggles reflect immediately.
- `/events` — Event list with search bar, year filter, rename/delete, Nationals trophy toggle; a season timeline (`Timeline.svelte`, train-map style) appears at the top on desktop when a specific year is selected
- `/events/[id]` — Per-event results (thin wrapper around `WideResultsTable`)
- `/results` — All events results (thin wrapper around `WideResultsTable`, adds Event filter column)
- `/gymnast/[slug]` — Individual gymnast results at a readable URL (`/gymnast/{slug}-{kebab-name}`); plain-slug and legacy gnz_id URLs 301-redirect to the canonical form; defaults to the current year; when a specific year is selected it shows a Personal Bests card (best per-apparatus score + D, best achieved AA, Best Possible AA), a region badge beside the name, and GNZ ID / club / steps underneath
- `/gymnasts` — Gymnast list (A-Z grouped, live search, GNZ ID shown subtly, ⚠ for multi-ID, comma-separated clubs for multi-club). Sticky header: search box + alphabet jump bar inline, active-letter highlight on scroll, collapsing title, "Back to top" button once scrolled
- `/club/[club]` — Club results across all events
- `/clubs` — Club list: desktop has the interactive NZ map (sticky left) + selected region box (right); mobile (`<lg`) replaces the map with a collapsible accordion of region cards (tap to expand, one open at a time), listed north→south via `REGION_ORDER`
- `/robots.txt` + `/sitemap.xml` — dynamic routes: disallows `/api`, `/login`, `/admin`, `/upload`, `/rankings`, `/wellington-ranking`; sitemap enumerates static pages + events + gymnasts (readable URLs) + clubs

**Shared stores:**
- `src/lib/year.ts` — `selectedYear` and `yearOptions` stores populated from `GET /api/years`; used globally in nav toggle
- `src/lib/rankingState.svelte.ts` — module-level `$state` object `{ discipline, selectedStep }` shared by the three ranking pages, so discipline/step survive navigation (viewing a gymnast and going back keeps your place)
- `src/lib/auth.ts` — `currentUser`, `setToken()`, `getToken()`, `logout()`, `hasPermission()` + persisted `nzgr_permissions`

**Nav bar layout:**
- Logo → Year toggle (DaisyUI `tabs tabs-box` radio inputs) → Role-based links → User badge dropdown (or Login button)
- Theme toggle in footer bottom-right

### Table Features
- Column widths synced between duplicate sticky headers and main table via JS measurement + ResizeObserver
- Name cells link to `/gymnast/[slug]`, club cells link to `/club/[club]`
- Horizontal scroll synced between duplicate headers and main table
- Client-side CSV/XLSX/PDF export via `export.ts` + `ExportMenu.svelte` (SheetJS + jsPDF lazy-loaded; XLSX supports hidden columns and widths via `colFormat`)
- Row hover highlight (`hover:bg-base-300 transition-colors`), `py-1.5` vertical padding
- `whitespace-nowrap` on apparatus score cells
- `truncate max-w-40 md:max-w-56` on event_name column (tighter truncation on mobile)
- `min-w-full` table fills container width
- Region column filterable via column header dropdown
- **Mobile (below `md`):** low-value columns hidden (`gnz-id`, sometimes `club`/`region`); rank + name (or `stickyCol`, default `name`) pinned together via `sticky left-*` with zebra-aware backgrounds; region cells collapse to a compact checker square (`RegionCheck.svelte`); column-header filters and `FilterDropdown` (rankings Club/Region) open as full-width bottom sheets with a sticky `Close (n selected)` button; `event_name` truncates at `max-w-40`

### Accessibility (STEP 24 — complete, all 6 public pages 100/100 on Lighthouse)
- Shared `Dialog.svelte` for all modals: `role="dialog"`/`aria-modal`, focus trap, Escape, focus restore, labelled heading.
- Tabs are native radios (no `role="tab"`); WAG/MAG toggles are `aria-pressed` buttons.
- Tooltips are the shared `Tooltip.svelte` (`<button>` trigger, `role="tooltip"`, `aria-describedby`, label-in-name); its `position: fixed` panel escapes table `overflow-x-auto` clipping.
- `textColor()`/`gradientTextColor()` use WCAG relative-luminance contrast (`#000` vs `#fff`).
- Skip link, `<main id="main">`, `<nav>` landmarks, `aria-current` on active links, `aria-live`/`role="status"` toasts, `role="alert"` errors, 24px min button targets, reduced-motion gating.
- Reports in `a11y-reports/` (rerun: `./a11y-reports/run.sh before|after [pages...]`, needs `CHROME_PATH`).

## Test Suite (424 pass, 87 conditional skip — 511 collected)
- `test_parser.py`: 131 tests — parsing, validation, known files, bulk scans, edge cases
- `test_auth.py`: 40 tests — auth/permissions endpoints + JWT
- `test_api.py`: 38 tests — health, upload, events/results, exports, slug endpoints
- `test_resolver.py`: 34 tests — resolver + name-cleaner (McEwan/O'Sullivan/hyphens) + ID fixes
- `test_rankings.py`: 27 tests — national rankings logic
- `test_activity.py`: 26 tests — traffic aggregation, bot exclusion, summaries
- `test_wellington_ranking.py`: 24 tests — Wellington ranking configs/selections/qualifiers
- `test_materialize.py`: 22 tests — store-vs-live equivalence, rebuild idempotence, failure safety
- `test_identity_review.py`: 22 tests — admin identity review, merge/split, merge-preview, slug redirects
- `test_athlete_identity.py`: 17 tests — athlete clustering, back-write, rebuild idempotency
- `test_admin_edit.py`: 15 tests — inline edit, scoped updates, edit-during-rebuild freshness
- `test_decoder.py`: 14 tests — output map building, decoding, DNS detection, Start Value
- `test_repair_identities.py`: 13 tests — consensus repair, dry-run, idempotency
- `test_medals.py`: 13 tests — medal tallies, apparatus rank awards
- `test_reconcile.py`: 12 tests — evidence-based athlete ID reconciliation
- `test_apparatus_rankings.py`: 12 tests — apparatus leaderboards + un-resolvable apparatus
- `test_scoreholder.py`: 11 tests — Scoreholder URL fetch/redirect/brotli
- `test_cloudflare.py`: 11 tests — config gating, query building, response parsing
- `test_reverse_merges.py`: 5 tests — merge reversal (event splits, same-name override, backup derivation)
- `test_ingest.py`: 5 tests — upload ingest, backfill guard
- `test_dedupe.py`: 5 tests — duplicate-event cleanup
- `test_models.py`: 4 tests — CRUD, cascade delete
- `test_transformer.py`: 3 tests — pivot/vault aggregation helpers
- `test_repair_merges.py`: 3 tests — wrong-merge repair (dry-run, apply, idempotent)
- `test_fix_apparatus.py`: 3 tests — All-around apparatus relabel CLI
- `test_database.py`: 1 test — init_db migration of a pre-existing schema

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
- **Athlete identity table (`athletes`)**: `long_scores.athlete_id` → `Athlete` (stable `slug` `a{sha1-hex10}`, `canonical_name`, `gnz_id`), built by `rebuild_athletes()` in `app/athlete_identity.py`. Clustering merges variant spellings of one person (shared ID + similar name) but splits same-event ID collisions, discipline conflicts, and disjoint-club sets (two Madison Lynches). Rebuild is idempotent/signature-stable, **back-writes** every row to its canonical spelling (orphan athletes deleted only after re-pointing rows), and runs after every ingest/edit/refresh. Rebuild manually with `python -m app.athlete_identity`. Query layers and gymnast URLs are keyed on `athlete_id`/`slug`.
- **Admin identity review (Phase 4)**: `GET /api/admin/identity-review` surfaces athlete-level conflicts — `similar_names`, `name_conflicts`, `id_conflicts`, `multi_id_athletes` (each with per-athlete evidence). `POST /api/admin/athletes/merge` combines two athletes; `POST /api/admin/athletes/split` (by gnz_id/event/club) breaks one into two using a fresh synthetic gnz_id + an `identity_override` token column that clustering honors until a merge clears it. The `/admin` Identity Review card replaced the old ID Reconciliation + Suggested Merges cards. **Aug 2026 fix**: the similar-names "Keep" buttons were wired backwards (each kept the *other* athlete — the empty-ID spelling won and, when both sides had an ID, the wrong ID). Each Keep now keeps the adjacent profile, buttons show the kept name + GNZ ID, and every merge opens a read-only `merge-preview` dialog (`POST /api/admin/athletes/merge-preview`) listing per-event row changes before committing. Wrong merges from the old buttons are fixed with `python -m app.repair_merges` (rewrite confirmed athletes) or `python -m app.reverse_merges` (split a merged athlete back into its pre-merge profiles per event; specs via `--spec-file` or derived from a pre-merge backup with `--from-backup … --for <ids>`). Both rebuild so slug redirects restore original URLs and Wellington intents re-point.
- **Merges reversed 15–16 Aug 2026**: dev — repaired Mathew Arck-weeber (568463), Annabelle Cochrane (833663), Sophie Chisholm (617735); reversed Isabella Matherson/Matheson, Harriet Shuurman/Schuurman, Daesharn Ewansmcmahon/Ewans-mcmahon, Bianca Mendes Mattos (both spellings same, kept apart by `identity_override`). Production — deployed the new build and reversed all 13 buggy-button merges against `results.pre-identity-fix.db` (three needed event-id correction because CSG Classic 2026 was re-imported: backup event 164 → live 402). Both DBs backed up first (`results.pre-reversal-*.db`); original pre-merge slugs are live again and merged slugs 301 to the restored profiles. Pairs remain flagged in the identity review for manual re-merge (keep the ID-bearing side).
- **Production repair applied (14 Aug 2026)**: the one-time `repair_identities --apply` was run against the **prod** DB (it had never received the repair dev had, so prod/dev identity layers differed — e.g. the two Madison Lynches were one athlete on prod). 1,237 ID + 13,159 name fixes across 14,254 rows; athletes 5,128 → 5,156; Madison Lynch split (OMNI `716561` / Onslow `249317`). The prod image has no `data-collection/` — mount it and stop the backend first; see BUGS.md.
- **Two JSON formats exist** — `data-collection/2025/json/` uses the new format (`eventOrganizations`, `performanceRules`, etc); `data-collection/JSON 2025/quar/` and `Archive/json/` use an old format (`event`, `sessions`, `rounds`). Old format is not supported and won't be used going forward.
- **`new URL()` breaks with relative URLs** — `api.ts`: `new URL("/api/results/wide-all")` throws when `API_BASE = ""` in dev mode. All API functions must use string concatenation for relative URLs.
- **Numpy types in JSON responses** — pandas/numpy produce `numpy.int64` and `numpy.float64` values that FastAPI's `jsonable_encoder` can't serialize. Must convert to native Python types in transformer.py.
- **DaisyUI z-index**: `.dropdown-content` sets `z-index: 1` and overrides Tailwind `z-*` classes because imported after Tailwind — use inline `style="z-index: 50"` to beat specificity.
- **$effect reactivity**: `$effect` tracks all reactive dependencies read inside it — avoid reading state that the effect itself modifies to prevent cycles. Fixed sort-revert bug by using `loaded` flag. Fixed page-reset-next-button bug by reading only filter state, not currentPage.
- **AA score fallback**: `_build_wide_row` now computes AA score from apparatus totals when stored `aa_score` is NULL. This handles cases where the parser's round_type mismatch prevents AA lookup.
- **resolver regex**: `resolve_level()` uses `r"level\s*(\d+)"` (zero-or-more whitespace) — consistent with STEP regex — to handle no-space variants like `"MAG Level3"`.
- **Region enrichment**: Club→region lookup at pivot time via `clubs_and_regions.json`. Changes to lookup file require re-upload of events. Run `reconcile_clubs.py` after adding aliases to fix existing data.
- **Club-data persistence (`app/clubdata.py`)**: the ACTIVE file is `data/clubs_and_regions.json` (inside the `backend_data` volume) so runtime alias saves survive redeploys; the repo `backend/clubs_and_regions.json` is the seed, copied into `data/` on first run (via `ensure_seed()`, called from `init_db()` and each reader). To commit UI-saved aliases to git, copy `data/clubs_and_regions.json` over the repo seed.
- **Unknown-club check fix**: `find_unknown_clubs()` was reading `orgId`/`participantId` fields that never exist in real Scoreholder files (real: `_id` on `eventOrganizations`, `_id`+`organizationId` on `eventParticipants`) — so it always returned `[]` and variant club names silently passed through. Fixed to use real field names; uploads now 409 with the club-mapping dialog. Regional teams (e.g. `Counties - Manukau`) are stored as club names and resolve to themselves; `Gymsport Manukau` retargets to `Counties - Manukau`.

## Docker
- `docker compose up --build` starts both services
- Backend: `:8000`, Frontend: `:5173`
- SQLite persists in `backend/data/` via named volume `backend_data`
- Vite proxies `/api/*` to backend in dev mode

## Deploy consistency
- **New-version banner**: `svelte.config.js` sets `kit.version.pollInterval = 60_000`; `+layout.svelte` renders a dismissible "new version available" reload bar via `updated` from `$app/state` (`updated.check()` also on mount + tab refocus). Open-tab users are told to reload after a deploy; fresh page loads already pick up new hashed bundles automatically.
- **Healthchecks** (`docker-compose.prod.yml`): backend python `urllib`→`/api/health`, frontend `node fetch`→`/`, frontend `depends_on backend: condition: service_healthy`. Shrinks the deploy window; with single replicas a brief 502/second gap while a container restarts is still possible.

## Cache Architecture
- **GranularTTLCache** — in-memory dict with per-key TTL.
  - No-TTL entries (pivot caches) stored as direct values.
  - TTL entries stored as `(expiry, value)` tuples, auto-evicted on read.
  - Prefix-based invalidation: `invalidate(event_id)` clears `event:{id}:*` keys.
  - Full clear: `invalidate()` without event_id (used by admin bulk operations).
- **Materialized stores** (STEP 30) — `data/results.materialized.db` (`app/materialize.py`), the persistent precomputed layer: `wide_rows` (flattened pivot output, JSON payload + athlete/club/event/year indexes), `ranking_marks` (per `(year, discipline, step, division)` blob of `_build_event_marks` output, typed-array serialization so int IDs survive JSON). Rebuilt in the background after every mutation (`cache.invalidate()` bumps the persisted `epoch` + kicks `rebuild_async()` when the app is running; boot auto-rebuilds when `needs_rebuild()` or the store is cold). Phase A parallelises event pivots via a `ProcessPoolExecutor` (events independent, workers pure-pandas, no DB); both stores swap atomically in one transaction. The heavy GET endpoints read the store when `MATERIALIZED_READS` (default 1) and `is_ready()`, falling back to the unchanged live compute otherwise — the live and store paths share derived helpers so output can't drift. Rebuild ~34s on the live DB (84 MB store). Status via `GET /api/admin/rebuild/status`. **Wellington rankings are deliberately NOT in the store** — `/api/rankings/wellington` is always live-computed (~130 ms/step, low traffic) so intent toggles reflect on the very next read with no stale window.
- **Cached endpoints:**
  - `/api/stats` — key `"stats"`, TTL 300s
  - `/api/gymnasts` — key `"gymnasts"`, TTL 300s
  - `/api/clubs` — key `"clubs"`, TTL 300s
  - `/api/medals` — key `"medals:{...}"`, TTL 300s
  - `/api/rankings/apparatus` — key `"apparatus-rankings:{year}:{step}:{discipline}:{division}"`, TTL 300s, single-flight
  - `/api/results/wide-all` — key `"wide-all:{year}:{gnz_id}:{club}"`, TTL 300s (live-compute fallback only; store-backed reads bypass the memory cache)
  - `/api/events/{id}/results/wide` — key `"event:{id}:pivot:{gnz_id}:{club}"`, no TTL (invalidation-driven) (live-compute fallback only)
- **HTTP caching:** `Cache-Control: public, max-age=300, stale-while-revalidate=60` on GET read endpoints, set via middleware. `no-store, no-cache, private` on admin/write.
- **ETag** — global version counter, incremented on every invalidation. Returned in response headers for conditional requests.

## HTTP Cache-Control
- Middleware at `main.py` `@app.middleware("http")` applies headers based on path + method:
  - Read endpoints → `public, max-age=300, stale-while-revalidate=60`
  - Admin/write (POST/PUT/DELETE/PATCH) → `no-store, no-cache, private`
- Individual endpoint `cache_headers()` now only sets the ETag (removed Cache-Control).
- `stale-while-revalidate=60` caps how long browsers/CDNs may serve stale public data while revalidating in the background (was 3600; users could otherwise sit on hour-old data after an upload/edit).

## Docs Convention
- Whenever updating project docs (MEMORY/README/PLAN/DESIGN-DOCUMENT/BUGS) for a notable user-facing change, also prepend a matching entry to `frontend/static/patch_notes.json` (full history, newest first; landing page shows all entries in a scrollable section). Patch notes are public — never reference real athlete names; use dummy/famous names (e.g. `Ewan McGregor`, "the two Simone Biles") and genericise real club names.
