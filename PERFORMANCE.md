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
- **Cache:** GranularTTLCache with per-key TTL + per-event prefix invalidation (68 lines)
- **HTTP caching:** `Cache-Control: public, max-age=300, stale-while-revalidate=60` on read endpoints; `no-store` on admin/write

---

## 2. Database Schema & Indexes

### Table: `events` — 81 rows

| Column | Type | Indexed? |
|--------|------|----------|
| `id` | INTEGER PK | ✓ auto-index |
| `name` | STRING | |
| `start_date` | STRING | |
| `end_date` | STRING | |
| `discipline` | STRING | |
| `year` | INTEGER | |
| `is_national` | BOOLEAN (default false) | |
| `created_at` | DATETIME | |

### Table: `long_scores` — 90,602 rows

| Column | Type | Indexed? | Used in filter |
|--------|------|----------|----------------|
| `id` | INTEGER PK | ✓ auto-index | — |
| `event_id` | INTEGER FK | ✓ B-tree (`idx_long_scores_event_id`) | every per-event query |
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

### Table: `users` — 1 row

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
| Total `long_scores` rows | 90,602 |
| Total `events` | 81 |
| Avg scores per event | ~1,119 |
| Distinct level categories | 26 |
| Years | 2025, 2026 |
| Disciplines | WAG, MAG |

---

## 3. Backend Query Patterns

### Endpoints: Read (with ETag caching)

| Endpoint | Queries | Scan vs Index | Notes |
|----------|---------|---------------|-------|
| `GET /api/stats` | 4 aggregate queries | **SCAN** long_scores x3, events x1 | 4 separate full scans |
| `GET /api/clubs` | SELECT club_name, COUNT(DISTINCT gymnast_name) GROUP BY club_name | **SCAN** long_scores + temp B-tree GROUP BY | |
| `GET /api/gymnasts` | SELECT DISTINCT gymnast_name, gnz_id, club_name WHERE gnz_id IS NOT NULL | **SCAN** long_scores + temp B-tree DISTINCT | Only ~3,700 distinct gymnasts from 90K rows |
| `GET /api/events` | 1. SELECT FROM events 2. 1 extra query per event: COUNT(DISTINCT gymnast_name) WHERE event_id=? | **SCAN** events + **SCAN** long_scores x81 | **N+1: 82 queries for 81 events** |
| `GET /api/events/{id}/results` | event by PK + COUNT gymnasts + SELECT WHERE event_id=? | PK search + **SCAN** long_scores x2 | |
| `GET /api/events/{id}/results/wide` | event by PK + SELECT WHERE event_id=? (inside pivot) | PK search + **SCAN** long_scores | In-memory cached |
| `GET /api/results/wide-all` | 1. SELECT events 2. 1 pivot per event: full scan + Pandas transform | **SCAN** events + **SCAN** long_scores xN | **1+N: up to 82 scans** |
| `GET /api/rankings/steps` | SELECT DISTINCT level_category FROM long_scores JOIN events WHERE year=? | **SCAN** long_scores (90K rows) + PK lookup events | Scans all rows even for single year |
| `GET /api/rankings` | 1. SELECT id FROM events 2. SELECT FROM long_scores WHERE event_id IN (...) | **SCAN** events + **SCAN** long_scores | No cache (auth-required) |

### Endpoints: Admin (no cache, auth-required)

| Endpoint | Queries | Notes |
|----------|---------|-------|
| `GET /api/admin/duplicates` | SELECT GROUP BY 4 columns | **SCAN** long_scores + temp B-tree |
| `POST /api/admin/duplicates/fix` | Same query + 1 UPDATE per conflicting ID | Multiple individual UPDATEs |
| `POST /api/admin/duplicates/apply` | SELECT DISTINCT gnz_id + UPDATE per fix | **SCAN** long_scores per fix |
| `GET /api/admin/suggested-merges` | 1. SELECT DISTINCT gymnast_name 2. 4 queries per similar pair | **N+1: 1 + 4N queries, O(n^2) difflib** |
| `POST /api/admin/merge-names` | UPDATE + canonical query + reconcile_athletes() | Same scan pattern |

### EXPLAIN QUERY PLAN — Key Findings

Every query on `long_scores` shows `SCAN long_scores` (90K rows) + `USE TEMP B-TREE FOR ...`.

Most expensive patterns:

1. **Per-event gymnast count** — `COUNT(DISTINCT gymnast_name) WHERE event_id=?` — SCAN + temp B-tree, runs 81x for events page
2. **Rankings/steps** — JOIN long_scores + events with `WHERE events.year=?` — SCAN long_scores, no way to pre-filter by year
3. **Suggested merges** — `SELECT DISTINCT gymnast_name` — SCAN + DISTINCT sort, then 4N additional queries

---

## 4. Frontend Rendering Patterns

### Data Fetching

All data fetching is client-side in `onMount()` or `$effect` hooks. No SSR for data pages — every page load shows a loading spinner.

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

- **Type:** In-memory dict `dict[str, tuple[int, Any]]`
- **Key:** `:`-joined string from tuple parts
- **Versioning:** Global `_version` counter, incremented on every write
- **Invalidation:** `invalidate()` bumps `_version`, clears ALL entries at once
- **TTL:** None — cache lives until version bump or process restart
- **Eviction:** No LRU, no size limit
- **Scope:** Only `pivot_to_wide_dict()` uses it — cached per `(event_id, gnz_id, club)` tuple
- **HTTP caching:** `Cache-Control: no-cache, must-revalidate` + `ETag: <version>`. Browser revalidates every request (304 avoids body but backend still runs queries)

### Invalidation Triggers

| Action | Calls `invalidate()`? |
|--------|----------------------|
| Upload | Yes |
| Delete event | Yes |
| Rename event | Yes |
| Reconcile athletes | Yes |
| Fix duplicates | Yes |
| Merge names | Yes |
| Save club aliases | Yes |

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
   -> delete existing events with same (name, start_date, discipline) (re-upload)
   -> INSERT all rows into long_scores
  -> call reconcile_athletes() (auto-fix ID inconsistencies)
  -> return EventResponse with counts + reconcile report
```

## 8. Data Pipeline: Results/Display Flow

```
Browser request
  -> SvelteKit client-side fetch in onMount/$effect
  -> hooks.server.ts (production) or Vite dev proxy -> backend
  -> FastAPI endpoint:
       a) Single event: SELECT WHERE event_id=? -> pivot_to_wide_dict() (SQL + Pandas) -> JSON
       b) All events: SELECT all events -> loop pivot_to_wide_dict per event -> concat -> JSON
       c) Rankings: SELECT scores -> Python aggregation (group by gymnast, pick top 2) -> sort -> rank -> JSON
       d) Gymnasts: SELECT DISTINCT -> group by lowercase name -> merge alt_ids/clubs -> JSON
  -> JSON response to browser
  -> Svelte $state stores response
  -> $derived/$effect computes filtered/sorted data
  -> {#each} renders all DOM nodes
  -> User interacts (filter, sort, search) -> client-side re-compute -> Svelte reactivity updates DOM
```
