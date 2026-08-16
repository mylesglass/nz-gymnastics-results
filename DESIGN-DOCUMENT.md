# AI Agent Design Document: Gymnastics Score Parsing Pipeline & Web Viewer

## 1. Project Overview
- **Goal:** Build an end-to-end pipeline to ingest complex, flat-relational JSON gymnastics scoring data (from Scoreholder), parse it, store it in a normalized database, dynamically pivot it into a wide format, export to CSV/XLSX, and display it in a web interface.
- **Data Source Architecture:** The input JSON files use a flat, reference-based `performance*` model with 22 top-level arrays (e.g., `events`, `eventParticipants`, `performanceScores`, `performanceResultTables`).
- **Target Environment:** Self-hosted home server, low traffic. Containerized deployment.

## 2. Technology Stack
- **Backend:** Python 3.12+ with FastAPI.
- **Data Processing:** Python native `json` library, `pandas` for data manipulation, pivoting, and `.csv`/`.xlsx` export.
- **Database:** SQLite via SQLAlchemy.
- **Auth:** bcrypt password hashing, PyJWT (HS256, 7-day expiry), role-based access (admin/member) with per-user ranking permissions.
- **Precomputed layer:** a materialized SQLite store (`data/results.materialized.db`) rebuilds wide rows + ranking marks after every upload.
- **Analytics:** batched background writer for `activity_logs` + `traffic_daily`; optional Cloudflare GraphQL edge analytics.
- **Frontend:** SvelteKit 5 with Tailwind CSS v4 and DaisyUI v5 (dark theme).
- **Infrastructure:** Docker Compose.

## 3. Storage Schema (SQLite — "Long Format")
One row = one apparatus pass for one gymnast.

| Column | Type | Description |
| :--- | :--- | :--- |
| id | INTEGER PK | Auto-increment |
| event_id | INTEGER FK | References events(id) |
| event_name | STRING | From `events[].name` |
| gymnast_name | STRING | From `eventParticipants[].name` (cleaned: `(L#)`, `(STEP 10)`, `(YI)` suffixes stripped) |
| gnz_id | STRING | From `eventParticipants[].identifier` (GS prefix stripped) |
| club_name | STRING | From `eventOrganizations[].name` |
| discipline | STRING | WAG or MAG |
| level_category | STRING | From `units[].name` (e.g., "STEP 6 AA") |
| division | STRING | From competition node names (UNDER/OVER/INTERNATIONAL) |
| apparatus | STRING | VT/UB/BB/FX/PH/SR/PB/HB |
| pass_number | INTEGER | From `performanceScores[].unitPassId` |
| round_type | STRING | All Around / Apparatus Finals / Qualification |
| d_score | FLOAT | Difficulty score (decoded from publicOutputs) |
| e_score | FLOAT | Execution score (decoded from publicOutputs) |
| neutral_deductions | FLOAT | Penalties (decoded from publicOutputs) |
| pass_final_score | FLOAT | Total score for this pass (decoded from publicOutputs) |
| bonus | FLOAT | Apparatus-level modifier (propagated across passes in same entityId+unitEventId group) |
| start_value | FLOAT | Vault-specific Start Value (decoded from publicOutputs) |
| apparatus_rank | INTEGER | From performanceResultTables |
| aa_score | FLOAT | All-Around aggregate score (from multi-set result tables) |
| aa_rank | INTEGER | All-Around rank (from multi-set result tables) |
| date_created | DATETIME | Auto timestamp |

### events table
| Column | Type |
| :--- | :--- |
| id | INTEGER PK |
| name | STRING |
| start_date | STRING |
| end_date | STRING |
| discipline | STRING (WAG/MAG/WAG+MAG) |
| year | INTEGER |
| is_national | BOOLEAN (default false) |
| host_club | STRING nullable |
| created_at | DATETIME |

### users table
| Column | Type |
| :--- | :--- |
| id | INTEGER PK |
| username | STRING UNIQUE |
| hashed_password | STRING (bcrypt) |
| role | STRING (admin/member) |
| permissions | STRING (comma-separated: `rankings.national`, `rankings.wellington`) |
| created_at | DATETIME |

### Other tables
- **`athletes`** — the stable identity layer (`slug`, `signature_hash`, `canonical_name`, `gnz_id`, `identity_override`); every `long_scores` row carries an `athlete_id` FK.
- **`slug_redirects`** — `old_slug` → `athlete_id`, keeps old gymnast URLs alive after merges/splits.
- **`wellington_intents`** — `UNIQUE(athlete_id, year)` intent submissions.
- **`activity_logs`** / **`traffic_daily`** — logged-in request detail + anonymous/logged-in aggregates (no IPs or user agents stored).

## 4. Export & Display Schema (Pandas — "Wide Format")
The wide-format output groups long-format data by gymnast/round, aggregates vault scores (level-aware), and enriches with region. The wide row contains:

**Meta columns:** gnz_id, name, club, region, step, division, competition, round_type, day

**Apparatus columns** (WAG: VT, UB, BB, FX; MAG: FX, PH, SR, VT, PB, HB):
- `{app}-total` — display score (aggregated if multi-pass)
- `{app}-d`, `{app}-e`, `{app}-n` — D/E/Neutral components
- `{app}-rank` — apparatus rank
- `{app}-bonus` — bonus modifier

**Vault-specific per-pass columns** (when multi-pass vault): vt-1-total, vt-1-d, vt-1-e, vt-1-n, vt-2-total, vt-2-d, vt-2-e, vt-2-n

**AA columns:** aa-score, aa-rank

Vault aggregation rules: STEP 6/7 always average; high-level AA uses best-mark; high-level Apparatus Finals average. See `_use_vault_average()` in transformer.py.

Region enrichment at pivot time via `_find_region()` lookup in `clubs_and_regions.json`.

## 5. Core Parsing Logic Requirements

1. **ID Resolution Chains:** Data is not nested. Resolve foreign keys through chains: entityId → performanceIndividuals → participantId → eventParticipants → name/identifier, orgId → eventOrganizations → name.

2. **Node-Tree Score Decoding:** Values for Difficulty, Execution, Final Score are behind dynamic opaque keys in `performanceScores[].publicOutputs`. Cross-reference `performanceRules[].scores[].nodeTree` to map keys to human-readable metrics. Also maps Bonus and Start Value.

3. **Ranking Extraction:** Official apparatus ranks and AA ranks from `performanceResultTables`, mapped via entityId. Multi-set tables capture AA aggregate scores.

4. **Bonus Propagation:** Bonus is an apparatus-level modifier stored on only one pass's score definition. Propagated at parse time across all passes in the same `(entityId, unitEventId)` group.

5. **Multi-Unit Deduplication:** ~38% of gymnasts compete in two units (e.g., Day 1 AA + Day 2 Apparatus). Handled via entity_event_passes tracking.

6. **Name Cleaning:** Strip `(L#)`, `(STEP 10)`, `(YI)` suffixes from gymnast names at parse time via regex.

7. **Division Extraction:** Heuristic text matching (UNDER/OVER/A/B/INTERNATIONAL) from competition node names.

8. **Athlete Identity Layer:** variant name spellings and duplicate GNZ IDs are clustered into stable `athletes` profiles by `rebuild_athletes()` (`app/athlete_identity.py`). Clustering merges a person's variant spellings (shared ID + similar name) but splits same-event ID collisions, discipline (WAG/MAG) conflicts, and disjoint-club sets — never auto-merging two different people. It runs after every ingest/edit and **back-writes** rows to each cluster's canonical spelling. The admin Identity Review tool surfaces name/ID conflicts and lets an admin Merge/Split profiles (with a read-only preview). The old name-keyed `POST /api/admin/reconcile-athletes` unify-by-name approach was replaced by this evidence-based layer.

## 6. Application Flow

1. **Upload:** User uploads a `.json` file (or pastes a Scoreholder public URL) to the SvelteKit frontend.
2. **Ingestion & Parsing:** FastAPI endpoint passes the file to parser.py, which decodes the node-tree, resolves IDs, propagates bonus, cleans names, extracts divisions, and grabs scores/ranks.
3. **Storage:** Data is written to SQLite in the "Long Format."
4. **Identity & Reconciliation:** `rebuild_athletes()` clusters rows into `athletes` profiles (evidence-based, runs after every ingest/edit); an optional Identity Review lets admins merge/split.
5. **Precompute:** the materialized store rebuilds wide rows + ranking marks in the background (`cache.invalidate()` bumps an epoch and kicks `rebuild_async()`); new events are inserted into the store synchronously so their page renders instantly.
6. **Transformation:** Pandas queries SQLite, pivots data into "Wide Format," enriches with region, applies vault aggregation rules, and formats decimals.
7. **View:** SvelteKit fetches pivoted wide-format data (from the store, or live-computed as a fallback) via FastAPI and displays in a DaisyUI table with sticky headers, sort, filter, export, and tooltips. Public pages are SSR-loaded.
8. **Export:** CSV and XLSX download via FastAPI byte streams, plus client-side CSV/XLSX/PDF from a shared export dropdown.

## 7. Auth Model
- JWT-based (HS256, 7-day expiry), role-based access (admin/member).
- Admin user seeded from env vars (ADMIN_USERNAME, ADMIN_PASSWORD, ADMIN_ROLE) on startup.
- JWT_SECRET auto-generated and persisted to `data/jwt_secret.txt`.
- When ADMIN_PASSWORD is unset, auth is disabled (all endpoints public).
- Ranking endpoints gate on per-user permissions (`rankings.national` / `rankings.wellington`) via `require_permission()`; write ops are admin-only and require `Authorization: Bearer <token>`.
- Frontend route guard redirects signed-out users / members without the matching permission away from protected pages.

## 8. Rankings
- **National Rankings** (`/api/rankings`) — one mark per `(gymnast, event)` competition per season; STEP 5/6 average the top 3 marks, other steps sum the top 2; optional qualifier/quota/division filters. `_QUALIFIER_CONFIG` defines GNZ qualifying marks per step.
- **Apparatus Rankings** (`/api/rankings/apparatus`) — best single mark per apparatus per gymnast, with D-score.
- **Wellington Rankings** (`/api/rankings/wellington`) — event classification (regional/club/away), per-step-range selection rules, GNZ + Wellington dual qualifiers, intent tracking, "not on the ranking" checklists, and apparatus specialist fallback (STEP 8–10, MAG Level 7+, Junior/Senior International). Always live-computed so intent toggles reflect immediately.

## 9. Analytics & Monitoring
- A FastAPI middleware measures every `/api` request: authenticated requests get a detail `activity_logs` row; every request (including anonymous page-view beacons via `/api/track/page`) is aggregated into `traffic_daily`. Bots and `/api/health` are excluded. Writes go through a non-blocking batched background writer so logging never stalls a response.
- Optional **Cloudflare edge analytics** (`/api/admin/cloudflare/summary`) pulls zone HTTP traffic via GraphQL for the admin dashboard.
- The admin dashboard visualizes both on one page with Chart.js.

## 10. SEO
- All public pages have SSR loads (`+page.server.ts`) fetching lightweight cached endpoints, so the rendered HTML carries real headings and counts.
- Gymnast URLs are readable (`/gymnast/{slug}-{kebab-name}`), with 301s from plain slugs and legacy GNZ IDs.
- Dynamic `robots.txt` + `sitemap.xml`; shared `Seo.svelte` injects `<title>`, meta description, canonical, OG/twitter and optional JSON-LD.

## 11. Frontend Architecture
- SvelteKit 5 with Svelte 5 runes (`$state`, `$effect`, `$derived`).
- Tailwind CSS v4 via Vite plugin; DaisyUI v5 via `@plugin "daisyui"`.
- Shared components: WideResultsTable (main table + inline editing), Tooltip/Dialog/FilterDropdown (a11y primitives), ScoreTooltip/AATooltip (score breakdowns), RegionBadge/RegionCheck/NZRegionMap (regions), SeasonBest (Personal Bests), Timeline (season chart), ExportMenu (CSV/XLSX/PDF), Seo (head), ChartJs (lazy-loaded charts), admin/* (dashboard).
- Global stores: year toggle (`selectedYear`), shared ranking state (`rankingState.svelte.ts` — discipline/step persist across navigation), auth (`currentUser`).
- Nav: logo, year toggle, role-based links, user badge dropdown or login.
- Theme toggle in footer. Dark theme via `data-theme` attribute persisted in localStorage.
- Client-side export via `frontend/src/lib/export.ts` + `ExportMenu.svelte` (CSV/XLSX/PDF, SheetJS + jsPDF lazy-loaded). No frontend unit tests yet (verified with `npm run build`).

## Additional Resources:
- `data-collection/data-structure-analysis` contains analysed JSON files with structural insights.
- `data-collection/2025/json/` uses the new Scoreholder format (supported). Old format (`quar/`, `Archive/json/`) is not supported.
- `clubs_and_regions.json` maps club names to regions (15 regions; the active file lives in the `backend_data` volume at `data/clubs_and_regions.json`).
