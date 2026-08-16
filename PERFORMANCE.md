# NZ Gymnastics Results — Performance Analysis

## 1. Architecture Overview

```
[Browser] <--> [SvelteKit (adapter-node)] <--> [FastAPI] <--> [SQLite]
                  ^ frontend:3000            ^ /api proxied    ^ results.db
```

- **Backend:** Python 3.12+, FastAPI, SQLAlchemy ORM, SQLite, Pandas
- **Frontend:** SvelteKit 5 (adapter-node, SSR via +page.server.ts), Tailwind CSS v4, DaisyUI v5
- **Infrastructure:** Docker Compose, single-server self-hosted deployment
- **API proxy:** `hooks.server.ts` forwards `/api/*` from frontend Node server to backend container in production; Vite dev proxy in development
- **Cache:** GranularTTLCache with per-key TTL + per-event prefix invalidation + single-flight `cached()` (concurrent misses compute once)
- **Precomputed store:** a materialized SQLite store (`data/results.materialized.db`) holds wide rows + ranking marks, rebuilt in the background after every mutation — the heavy read endpoints are cheap lookups instead of per-request pivots (fall back to live compute when the store isn't ready)
- **HTTP caching:** `Cache-Control: public, max-age=300, stale-while-revalidate=60` on read endpoints; `no-store` on admin/write and on the two wide results endpoints (`/api/events/{id}/results/wide`, `/api/results/wide-all`) so inline edits never sit behind a browser-cached copy

---

## 2. Database Schema & Indexes

### Table: `events` — 183 rows (live DB snapshot, Aug 2026)

| Column | Type | Indexed? |
|--------|------|----------|
| `id` | INTEGER PK | ✓ auto-index |
| `name` | STRING | |
| `start_date` | STRING | |
| `end_date` | STRING | |
| `discipline` | STRING | |
| `year` | INTEGER | |
| `is_national` | BOOLEAN (default false) | |
| `host_club` | STRING | |
| `created_at` | DATETIME | |

### Table: `long_scores` — 191,511 rows

| Column | Type | Indexed? | Used in filter |
|--------|------|----------|----------------|
| `id` | INTEGER PK | ✓ auto-index | — |
| `event_id` | INTEGER FK | ✓ B-tree (`idx_long_scores_event_id`) | every per-event query |
| `athlete_id` | INTEGER FK | ✓ B-tree | athlete-keyed queries |
| `identity_override` | STRING | | admin force-split marker |
| `event_name` | STRING | | — |
| `gymnast_name` | STRING | ✓ B-tree (`idx_long_scores_gymnast_name`) | duplicates, merge, counts |
| `gnz_id` | STRING | ✓ B-tree (`idx_long_scores_gnz_id`) | gymnasts list, duplicates |
| `club_name` | STRING | ✓ B-tree (`idx_long_scores_club_name`) | clubs list, counts |
| `discipline` | STRING | | rankings, steps |
| `level_category` | STRING | | rankings, steps |
| `division` | STRING | | filter |
| `apparatus` | STRING | | — |
| `pass_number` | INTEGER | | — |
| `d_score` | FLOAT | | — |
| `e_score` | FLOAT | | — |
| `neutral_deductions` | FLOAT | | — |
| `pass_final_score` | FLOAT | ✓ compound (`idx_long_scores_rankings`) | rankings (not null) |
| `bonus` | FLOAT | | — |
| `start_value` | FLOAT | | — |
| `apparatus_rank` | INTEGER | | — |
| `aa_score` | FLOAT | | rankings (not null) |
| `aa_rank` | INTEGER | | — |
| `round_type` | STRING | | — |
| `date_created` | DATETIME | | — |

### Table: `users` — a few rows

| Column | Type | Indexed? |
|--------|------|----------|
| `id` | INTEGER PK | ✓ auto-index |
| `username` | STRING | ✓ UNIQUE INDEX (`ix_users_username`) |

**Critical finding (resolved):** Zero indexes on `long_scores` or `events` beyond primary keys. Every query against `long_scores` (90K rows) was a full table scan. Seven B-tree indexes (5 single-column + 2 compound) now cover all expensive query patterns.

### SQLite PRAGMA Settings

| Setting | Value | Implication |
|---------|-------|-------------|
| `journal_mode` | `WAL` | Write-Ahead Logging — reads don't block writes |
| `synchronous` | `NORMAL` | Safe in WAL mode, reduced fsync overhead |
| `cache_size` | `-64000` (~64MB) | Large page cache holds most of the DB in RAM |
| `temp_store` | `MEMORY` | Temp tables/indexes in RAM during GROUP BY/DISTINCT |
| `foreign_keys` | `ON` | FK constraints enforced |
| `auto_vacuum` | `0` (NONE) | DB file never shrinks |

### Data Volume

| Metric | Value |
|--------|-------|
| Total `long_scores` rows | 191,511 |
| Total `events` | 183 |
| Total `athletes` | 4,421 |
| Avg scores per event | ~1,047 |
| Years | 2023–2026 |
| Disciplines | WAG, MAG |

---

## 3. Backend Query Patterns

### Endpoints: Read (with ETag caching)

> Since the materialized store landed, `/api/events/{id}/results/wide`, `/api/results/wide-all`, `/api/rankings` and `/api/rankings/apparatus` are **store lookups** (indexed `wide_rows` / `ranking_marks` blobs) rather than the scans below; the old live-compute paths remain only as a fallback when the store isn't ready. `/api/rankings/wellington` is still live-computed per request (low traffic, needs immediacy).

| Endpoint | Queries | Scan vs Index | Notes |
|----------|---------|---------------|-------|
| `GET /api/stats` | 4 aggregate queries | **SCAN** long_scores x3, events x1 | 4 separate full scans |
| `GET /api/clubs` | SELECT club_name, COUNT(DISTINCT gymnast_name) GROUP BY club_name | **SCAN** long_scores + temp B-tree GROUP BY | |
| `GET /api/gymnasts` | SELECT DISTINCT gymnast_name, gnz_id, club_name WHERE gnz_id IS NOT NULL | **SCAN** long_scores + temp B-tree DISTINCT | ~3,700 distinct gymnasts from 190K rows |
| `GET /api/events` | 1. SELECT FROM events 2. 1 extra query per event: COUNT(DISTINCT gymnast_name) WHERE event_id=? | **SCAN** events + **SCAN** long_scores xN | N+1 (was resolved for counts via grouping; re-check per deploy) |
| `GET /api/events/{id}/results` | event by PK + COUNT gymnasts + SELECT WHERE event_id=? | PK search + **SCAN** long_scores x2 | |
| `GET /api/events/{id}/results/wide` | store read by event_id | indexed | falls back to live pivot |
| `GET /api/results/wide-all` | store read by athlete/club/year | indexed | falls back to live multi-event pivot |
| `GET /api/rankings/steps` | SELECT DISTINCT level_category FROM long_scores JOIN events WHERE year=? | **SCAN** long_scores (190K rows) + PK lookup events | |
| `GET /api/rankings` | store read of `ranking_marks` blob per key | indexed | derivation happens in memory |
| `GET /api/rankings/apparatus` | store read of `ranking_marks` blob per key | indexed | server-cached + single-flight |
| `GET /api/rankings/wellington` | live SELECT + `_build_event_marks` | **SCAN** long_scores | always live (~130 ms/step) |

### Endpoints: Admin (no cache, auth-required)

| Endpoint | Queries | Notes |
|----------|---------|-------|
| `GET /api/admin/identity-review` | athlete/event aggregation | athlete-level conflict review |
| `POST /api/admin/athletes/{merge-preview,merge,split}` | row rewrites + rebuild | rebuild re-clusters athletes |
| `POST /api/admin/scores/gymnast` | targeted UPDATEs + sync store refresh | inline edit |
| `GET /api/admin/activity` / `summary` | activity_logs / traffic_daily reads | flush queued rows first |
| `GET /api/admin/cloudflare/summary` | external GraphQL | cached 300s, single-flight |
| `GET /api/admin/rebuild/status` | materialized `meta` table | `{ready, building, needs_rebuild, ...}` |
| Legacy: `GET/POST /api/admin/duplicates*`, `GET /api/admin/suggested-merges`, `POST /api/admin/merge-names` | old scan patterns | still in the API + tested, no longer called by the UI |

### EXPLAIN QUERY PLAN — Key Findings

Every query on `long_scores` shows `SCAN long_scores` (90K rows) + `USE TEMP B-TREE FOR ...`.

Most expensive patterns:

1. **Per-event gymnast count** — `COUNT(DISTINCT gymnast_name) WHERE event_id=?` — SCAN + temp B-tree, runs 81x for events page
2. **Rankings/steps** — JOIN long_scores + events with `WHERE events.year=?` — SCAN long_scores, no way to pre-filter by year
3. **Suggested merges** — `SELECT DISTINCT gymnast_name` — SCAN + DISTINCT sort, then 4N additional queries

---

## 4. Frontend Rendering Patterns

### Data Fetching

Public pages are server-rendered via `+page.server.ts` loads that fetch lightweight cached endpoints (`/api/stats`, `/api/events`, `/api/gymnasts`, `/api/clubs`, `/api/gymnast`) — the HTML carries real headings/counts. The heavy wide tables and ranking data hydrate client-side (never SSR'd): `WideResultsTable` and the ranking pages fetch in `onMount()` / `$effect` and render with a loading spinner until data arrives.

### Rendering: All Pages Use "Fetch All -> Render All"

No virtualization, pagination, or lazy loading anywhere.

| Page | Data Source | Typical Rows | Estimated DOM Nodes |
|------|-------------|-------------|-------------------|
| Single event results | `/api/events/{id}/results/wide` | 100-400 per disc | 15K-100K |
| All results | `/api/results/wide-all` | 500-5,000+ | 75K-1.25M |
| Club results | `/api/results/wide-all?club=X` | 50-500 | 7.5K-125K |
| Gymnast results | `/api/results/wide-all?gnz_id=X` | 5-50 | 750-12.5K |
| Rankings | `/api/rankings` | 20-100 | 500-5K |
| Gymnasts list | `/api/gymnasts` | 500-2,000 | 5K-20K |
| Clubs list | `/api/clubs` | 50-200 | 500-2K |
| Events list | `/api/events` | 20-100 | 500-2K |

### DOM Complexity — WideResultsTable

Each row generates ~150-250 DOM nodes:

- 1 `<tr>`
- ~7 `<td>` for metadata (gnz-id, name, club, region, step, division, round-type) with nested `<a>` links, region badge, filter dropdowns
- 4-6 `<td>` for apparatus, each containing `ScoreTooltip` (40-60 nodes with D/E/N/bonus/rank/pass details dropdowns)
- 1-2 `<td>` for AA with `AATooltip` (20-30 nodes)

**"All Results" page worst case:** ~30 events x 200 gymnasts = 6,000 rows x ~200 DOM nodes = **1.2M DOM nodes** simultaneously.

### Filtering

- Entirely client-side on full dataset
- Text search O(n) with no debounce
- Multi-select column filters use `Set.has()` for O(1) lookups
- Filter chain: `[...rows].filter(...).filter(...)` creates new array per step

### Sorting

- Client-side, `localeCompare()` with `numeric: true`, re-runs on every header click

### Gymnasts Page

- Fetches all gymnasts (API returns alt_ids/alt_clubs grouped by name)
- Renders all in 2-column A-Z grid
- Search via `$derived` on every keystroke

---

## 5. Caching Layer

### Backend Cache (`app/cache.py`)

- **Type:** In-memory `GranularTTLCache` — `dict[str, value]` with per-key TTL.
  - No-TTL entries (pivot caches) stored as direct values.
  - TTL entries stored as `(expiry, value)` tuples, auto-evicted on read.
- **Key:** `:`-joined string from tuple parts (e.g. `event:{id}:pivot:{gnz_id}:{club}`).
- **Versioning:** global `_version` counter bumped on every invalidation, returned as an ETag for conditional requests.
- **Invalidation:** `invalidate(event_id)` clears the `event:{id}:*` prefix; `invalidate()` (no arg) clears everything and bumps the materialized-store rebuild epoch.
- **Single-flight:** `cached()` dedupes concurrent misses — one in-flight computation is shared, so a cold cache can't hammer SQLite with parallel identical queries.
- **Cached endpoints:** `/api/stats`, `/api/gymnasts`, `/api/clubs`, `/api/medals`, `/api/rankings/apparatus` (all TTL 300s), plus the live-compute fallback paths for `/api/results/wide-all` and `/api/events/{id}/results/wide`.
- **HTTP caching:** `Cache-Control: public, max-age=300, stale-while-revalidate=60` + `ETag` on read endpoints; `no-store` on admin/write and the two wide results endpoints.

### Materialized store (`app/materialize.py`)

The heavy derivations live in a precomputed SQLite file (`data/results.materialized.db`, rebuilt in the background after every mutation):

- `wide_rows` — the pivot output flattened to one row per `(event, discipline, athlete, round_type)` with `payload` JSON, indexed by `event_id` / `athlete_id, year` / `club, year`.
- `ranking_marks` — `_build_event_marks` output as a JSON blob per `(year, discipline, step, division)` key.
- Rebuilt in one transaction (old + new never partially visible to readers); status exposed via `GET /api/admin/rebuild/status`. ~34s full rebuild on the live DB (~84 MB store).
- Wellington rankings are **not** stored — always live-computed so intent toggles reflect immediately.
- `MATERIALIZED_READS=0` forces every rewritten endpoint back to live compute (instant rollback); `MATERIALIZE_WORKERS` caps the worker pool.

### Invalidation Triggers

| Action | Cache invalidated | Store rebuild |
|--------|-------------------|---------------|
| Upload | Yes | Yes (event inserted synchronously + full rebuild queued) |
| Delete / rename event | Yes | Yes |
| Inline edit | Yes (incl. `apparatus-rankings` prefix) | Yes (edited event refreshed synchronously, then full rebuild) |
| Reconcile / identity merge / split | Yes | Yes |
| Fix duplicates / merge names | Yes | Yes |
| Save club aliases | Yes | Yes |
| Intent toggle | Yes | No (Wellington stays live) |
| Admin refresh-cache | Yes | Yes |

---

## 6. Identified Bottlenecks (Ranked by Impact)

1. ~~**Zero indexes on `long_scores`** — every query is a full table scan of 90K rows~~ *(resolved)*
2. ~~**N+1 in events list** — 82 queries for 81 events~~ *(resolved: outerjoin + group_by)*
3. ~~**N+1 in wide-all** — 1 + N queries for cross-event results~~ *(resolved: single multi-event pivot query)*
4. ~~**No pagination on any endpoint** — all data fetched and rendered every time~~ *(resolved: paginated in WideResultsTable)*
5. ~~**No virtualization in frontend** — all rows rendered simultaneously (up to 1.2M DOM nodes)~~ *(resolved: 50 rows/page pagination)*
6. ~~**O(n^2) name matching** in suggested merges with difflib~~ *(resolved: bulk pre-loaded maps + quick_ratio filter)*
7. ~~**Global cache invalidation** — no per-key granularity~~ *(resolved: GranularTTLCache + prefix-based invalidation)*
8. ~~**No WAL mode** — reads block writes and vice versa~~ *(resolved)*
9. ~~**Synchronous mode FULL** — fsync on every commit~~ *(resolved)*
10. **No server-side filtering/pagination** for rankings (handled at query time)
11. ~~**No debounced search** — every keystroke re-filters on the full dataset~~ *(resolved)*
12. ~~**No SSR for data pages** — every page load shows spinner before content~~ *(resolved: +page.server.ts load functions)*

---

## 7. Data Pipeline: Upload Flow

```
JSON file
  -> POST /api/upload
  -> validate_upload_structure() (checks top-level keys)
  -> find_unknown_clubs() (scans eventOrganizations, skips GFA-only orgs)
  -> parse_json() (full parsing pipeline)
       -> build_output_map (decoder.py)
       -> resolve_* (resolver.py):
            - resolve_clubs: org_id -> club_name
            - resolve_participants: participant_id -> {name (cleaned), gnz_id, org_id}
            - resolve_individuals: entity_id -> {participant_id, unit_id}
            - resolve_units: unit_id -> {name, discipline}
            - resolve_level: extract STEP/Level from unit name
       -> index performanceScores with decoded outputs
       -> process performanceResultTables:
            - single-set -> individual apparatus rows
            - multi-set -> AA aggregate scores
            - deduplicate by score _id
       -> extract division from competition node names
       -> infer round_type from unit + node names
       -> sanitise floats/ranks (DNS/DNF -> None)
       -> strip parenthetical metadata from names
       -> skip GFA units, non-competitive levels
   -> backfill missing GNZ IDs from existing DB (by name match)
   -> delete existing events with same (name, start_date, discipline) (re-upload dedup)
   -> INSERT all rows into long_scores
  -> call reconcile_athletes() (evidence-based ID consistency report)
  -> call rebuild_athletes() (cluster rows into `athletes` identities)
  -> insert the new event's wide rows into the materialized store synchronously
  -> trigger background full store rebuild (cache.invalidate() bumps the epoch)
  -> return EventResponse with counts + warnings
```

## 8. Data Pipeline: Results/Display Flow

```
Browser request
  -> SvelteKit client-side fetch (public pages SSR-loaded first, tables hydrate client-side)
  -> hooks.server.ts (production) or Vite dev proxy -> backend
  -> FastAPI endpoint:
       a) Single event wide: store lookup by event_id (indexed) — live pivot fallback
       b) All events wide: store lookup by athlete/club/year (indexed) — live multi-event pivot fallback
       c) Rankings: store `ranking_marks` blob -> in-memory derivation (national/apparatus);
          Wellington always live-computed
       d) Gymnasts: SELECT DISTINCT -> group by lowercase name -> merge alt_ids/clubs -> JSON
  -> JSON response to browser
  -> Svelte $state stores response
  -> $derived/$effect computes filtered/sorted data
  -> {#each} renders DOM nodes (wide tables paginated 50/page)
  -> User interacts (filter, sort, search) -> client-side re-compute -> Svelte reactivity updates DOM
```
