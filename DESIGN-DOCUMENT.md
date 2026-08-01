# AI Agent Design Document: Gymnastics Score Parsing Pipeline & Web Viewer

## 1. Project Overview
- **Goal:** Build an end-to-end pipeline to ingest complex, flat-relational JSON gymnastics scoring data (from Scoreholder), parse it, store it in a normalized database, dynamically pivot it into a wide format, export to CSV/XLSX, and display it in a web interface.
- **Data Source Architecture:** The input JSON files use a flat, reference-based `performance*` model with 22 top-level arrays (e.g., `events`, `eventParticipants`, `performanceScores`, `performanceResultTables`).
- **Target Environment:** Self-hosted home server, low traffic. Containerized deployment.

## 2. Technology Stack
- **Backend:** Python 3.12+ with FastAPI.
- **Data Processing:** Python native `json` library, `pandas` for data manipulation, pivoting, and `.csv`/`.xlsx` export.
- **Database:** SQLite via SQLAlchemy.
- **Auth:** bcrypt password hashing, PyJWT (HS256, 7-day expiry), role-based access (admin/uploader).
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
| created_at | DATETIME |

### users table
| Column | Type |
| :--- | :--- |
| id | INTEGER PK |
| username | STRING UNIQUE |
| hashed_password | STRING (bcrypt) |
| role | STRING (admin/uploader) |
| created_at | DATETIME |

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

8. **Athlete ID Reconciliation:** Name-based unification of duplicate GNZ IDs across events. POST /api/admin/reconcile-athletes groups by name, picks the best ID (most frequent, then most recent). Conflicts reported when frequency is equal.

## 6. Application Flow

1. **Upload:** User uploads a `.json` file to the SvelteKit frontend.
2. **Ingestion & Parsing:** FastAPI endpoint passes the file to parser.py, which decodes the node-tree, resolves IDs, propagates bonus, cleans names, extracts divisions, and grabs scores/ranks.
3. **Storage:** Data is written to SQLite in the "Long Format."
4. **Reconciliation (optional/manual):** Admin triggers athlete ID reconciliation to unify duplicate GNZ IDs across events.
5. **Transformation:** Pandas queries SQLite, pivots data into "Wide Format," enriches with region, applies vault aggregation rules, and formats decimals.
6. **View:** SvelteKit fetches pivoted wide-format data via FastAPI and displays in a DaisyUI table with sticky headers, sort, filter, export, and tooltips.
7. **Export:** CSV and XLSX download via FastAPI byte streams.

## 7. Auth Model
- JWT-based (HS256, 7-day expiry), role-based access (admin/uploader).
- Admin user seeded from env vars (ADMIN_USERNAME, ADMIN_PASSWORD, ADMIN_ROLE) on startup.
- JWT_SECRET auto-generated and persisted to `data/jwt_secret.txt`.
- When ADMIN_PASSWORD is unset, auth is disabled (all endpoints public).
- Protected write ops (upload, delete, rename, reconcile) require `Authorization: Bearer <token>` with appropriate role.

## 8. Frontend Architecture
- SvelteKit 5 with Svelte 5 runes (`$state`, `$effect`, `$derived`).
- Tailwind CSS v4 via Vite plugin; DaisyUI v5 via `@plugin "daisyui"`.
- Shared components: WideResultsTable (main table), ScoreTooltip (apparatus hover), AATooltip (AA score tooltip), MultiSelect (filter dropdowns), ExportMenu (CSV/XLSX/PDF export dropdown).
- Global stores: year toggle (`selectedYear`), auth state (`currentUser`).
- Nav: logo, year toggle, role-based links, user badge dropdown or login.
- Theme toggle in footer. Dark theme via `data-theme` attribute persisted in localStorage.
- Client-side export via `frontend/src/lib/export.ts` + `ExportMenu.svelte` (CSV/XLSX/PDF, SheetJS + jsPDF lazy-loaded). No frontend tests yet.

## Additional Resources:
- `data-collection/data-structure-analysis` contains analysed JSON files with structural insights.
- `data-collection/2025/json/` uses the new Scoreholder format (supported). Old format (`quar/`, `Archive/json/`) is not supported.
- `clubs_and_regions.json` maps club names to regions (15 regions, 180 lookup entries).
