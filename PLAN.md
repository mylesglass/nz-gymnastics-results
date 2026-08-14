# PLAN — Admin Activity → Usage Dashboard

## Goal

Turn the admin activity page into a usage dashboard:

1. Capture **all** usage (anonymous public traffic + logged-in users) without
   storing IPs or user-agents.
2. Add **graphs** (Chart.js, lazy-loaded so it stays out of the entry bundle).
3. Make the page **mobile responsive** (cards under `md`, charts single column).

Decisions confirmed with the user:

- Anonymous capture = **aggregated counters** in a new `traffic_daily` table
  (per day/hour/path-group). The detailed `activity_logs` table stays
  authenticated-only (audit trail stays small).
- **Bot filtering**: anonymous requests with bot-like user-agents are excluded
  from aggregation (UA is checked in the middleware, never stored).
- **Chart.js** (lazy-loaded via dynamic `import()`), wrapped in a small Svelte
  component.

---

## 1. Backend — data capture

### 1.1 New model `TrafficDaily` (`backend/app/models.py`)

Add after `ActivityLog`:

```python
class TrafficDaily(Base):
    __tablename__ = "traffic_daily"

    __table_args__ = (
        UniqueConstraint(
            "date", "hour", "kind", "path_group", "anonymous",
            name="uq_traffic_daily",
        ),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(Date, nullable=False)
    hour = Column(Integer, nullable=False)
    kind = Column(String, nullable=False)          # 'page' | 'api'
    path_group = Column(String, nullable=False)    # normalized path
    anonymous = Column(Boolean, nullable=False, default=False)
    count = Column(Integer, nullable=False, default=0)
    error_count = Column(Integer, nullable=False, default=0)
    total_duration_ms = Column(Float, nullable=False, default=0.0)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
```

- The `UniqueConstraint` backs the SQLite UPSERT key.
- `init_db()` in `database.py` already runs `Base.metadata.create_all(engine)`
  so the table is created automatically; no ALTER migration needed.

### 1.2 Path normalization (`backend/app/traffic.py`, new module)

Module-level docstring + `normalize_path(path: str) -> str`:

- Strip the query string (`?` onwards).
- Replace pure-numeric segments (`/\d+`) with `/[id]`.
- Replace 10-char hex segments (`/[0-9a-fA-F]{10}`) with `/[slug]`.
- Leave everything else verbatim (e.g. `/club/Some%20Club`).
- Also `is_bot(user_agent: str | None) -> bool`: regex on
  `bot|spider|crawl|slurp|curl|wget|python-requests|Go-http-client|HeadlessChrome|UptimeRobot|pingdom`.

### 1.3 Batched writer (`backend/app/activity_log.py`)

- Queue items already are `dict`s; add a `_target` discriminator:
  - `{"_target": "activity", username, role, type, ...}` — existing ActivityLog row.
  - `{"_target": "traffic", date, hour, kind, path_group, anonymous, status_code, duration_ms}` — aggregate upsert.
- `_insert(rows)`: split into activity rows and traffic rows. For traffic,
  aggregate counts/error_count/total_ms in Python per key
  `(date, hour, kind, path_group, anonymous)`, then run one parameterized
  upsert per key:

  ```sql
  INSERT INTO traffic_daily (date, hour, kind, path_group, anonymous, count,
                             error_count, total_duration_ms, created_at)
  VALUES (:date, :hour, :kind, :path_group, :anonymous, :count, :error_count,
          :total_duration_ms, :created_at)
  ON CONFLICT(date, hour, kind, path_group, anonymous)
  DO UPDATE SET count = count + :count,
                error_count = error_count + :error_count,
                total_duration_ms = total_duration_ms + :total_duration_ms
  ```

- New public `enqueue_traffic(kind, path_group, anonymous, status_code, duration_ms) -> None`:
  computes `date`/`hour` from local `datetime.now()`, tags `_target="traffic"`,
  and either queues it or writes synchronously (when the writer isn't started,
  i.e. test contexts), mirroring `enqueue()`.
- An `error` is a status code `>= 400`.
- `duration_ms` may be `None` for page views → treat as 0 in totals.

### 1.4 Optional-auth dependency (`backend/app/auth.py`)

Add `get_optional_user`:

```python
async def get_optional_user(authorization: str | None = Header(None)) -> dict | None:
    """Like get_current_user but returns None instead of raising for anonymous."""
    if not _is_auth_enabled():
        return None
    if not authorization:
        return None
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer":
        return None
    payload = decode_token(token)
    if payload is None:
        return None
    return {"username": payload["sub"], "role": payload["role"]}
```

### 1.5 Middleware (`backend/app/main.py`)

Rewrite `log_activity` (the `@app.middleware("http")` at `main.py:166`):

- Keep `start = time.perf_counter()` / duration measurement.
- Skip paths:
  - `/api/track/page` (handled in the endpoint itself — body has the path)
  - `/api/admin/activity*` (no self-logging)
  - `/api/health` (Docker healthcheck pings would pollute counts)
  - non-`/api` paths
- Decode the Bearer token if present.
- Anonymous (no valid token):
  - If `is_bot(user_agent)` → return response (no count).
  - Else `enqueue_traffic("api", normalize_path(path), anonymous=True, status, duration)`.
- Authenticated:
  - `_log_activity(...)` detail row (as today).
  - `enqueue_traffic("api", normalize_path(path), anonymous=False, status, duration)`.

### 1.6 Page-view endpoint (`backend/app/main.py`)

`track_page` changes:

- Dependency: `Depends(get_optional_user)` (import it).
- No user → `enqueue_traffic("page", normalize_path(body.path), anonymous=True, 200, None)`.
- User present → existing `_log_activity` detail row **and**
  `enqueue_traffic("page", normalize_path(body.path), anonymous=False, 200, None)`.

The middleware already skips `/api/track/page`, so no double counting.

### 1.7 Timezone (`docker-compose.yml` + `docker-compose.prod.yml`)

Add `TZ: Pacific/Auckland` to the backend service `environment:` so production
day/hour buckets match the admin's local day. Dev (`./.dev.sh`) runs on the host
which is already local time.

---

## 2. Backend — analytics endpoint

### 2.1 Schemas (`backend/app/schemas.py`)

```python
class TrafficPoint(BaseModel):
    date: str                    # YYYY-MM-DD
    page_views: int = 0
    api_requests: int = 0
    errors: int = 0

class HourPoint(BaseModel):
    hour: int
    page_views: int = 0
    api_requests: int = 0

class TopPath(BaseModel):
    path: str
    count: int = 0
    errors: int = 0

class TopUser(BaseModel):
    username: str
    role: str
    page_views: int = 0
    api_requests: int = 0

class ActivityTotals(BaseModel):
    page_views: int
    api_requests: int
    errors: int
    avg_duration_ms: float | None
    active_days: int
    anon_page_views: int
    auth_page_views: int
    anon_api_requests: int
    auth_api_requests: int

class ActivitySummaryResponse(BaseModel):
    range_days: int
    totals: ActivityTotals
    daily_series: list[TrafficPoint]
    auth_daily_series: list[TrafficPoint]
    hourly_series: list[HourPoint]
    top_pages: list[TopPath]
    top_api: list[TopPath]
    top_users: list[TopUser]
```

### 2.2 Endpoint `GET /api/admin/activity/summary` (`backend/app/main.py`)

- `require_role("admin")`, `days: int = 30` clamped to `{7, 30, 90, 0}` (0 = all time).
- `flush_activity()` first so queued rows appear.
- Queries against `traffic_daily`:
  - **totals** (range): sum count by kind × anonymous, sum error_count,
    avg_duration = `sum(total_duration_ms)/sum(count)` when any count.
  - **daily_series**: `GROUP BY date, kind` → map to `{date, page_views, api_requests, errors}`.
  - **hourly_series**: `GROUP BY hour, kind`.
  - **top_pages**: `kind='page'` `GROUP BY path_group ORDER BY SUM(count) DESC LIMIT 15`.
  - **top_api**: `kind='api'` same + `errors`.
- Queries against `activity_logs` (authenticated history, full range):
  - **auth_daily_series**: `GROUP BY date(created_at)` split page/api/errors.
  - **top_users**: `GROUP BY username`, type split, last role seen. Limit 10.
- Build the response. Range is applied to `traffic_daily` via `date >= today - days + 1`.

### 2.3 `days` filter on the existing log list

`GET /api/admin/activity` gains optional `days: int = None`; when set, filter
`ActivityLog.created_at >= now - days`.

---

## 3. Frontend

### 3.1 Install Chart.js

`cd frontend && npm install chart.js` (runtime dep; lazy-imported).

### 3.2 `lib/charts/ChartJs.svelte` (new)

Generic Svelte 5 wrapper:

- Props `{ type, data, options }` typed via `import type { Chart, ChartConfiguration } from "chart.js"`.
- `onMount`: `const mod = await import("chart.js/auto")`, instantiate
  `new mod.default(canvas, { type, data, options })`.
- `$effect`: when `data`/`options` change, `chart.data = data; chart.options = options; chart.update()`.
- `onDestroy`: `chart.destroy()`.
- Accessibility: canvas gets `role="img"` + `aria-label` (title + one-line summary), plus a visually-hidden `<div>` fallback listing the data.
- `maintainAspectRatio: false` default; the wrapper sets an explicit responsive height via a container class (e.g. `h-64`).

### 3.3 `lib/api.ts`

- `getActivitySummary(days: number)` → `ActivitySummary` (typed interfaces mirroring the response).

### 3.4 Beacon for anonymous page views (`src/routes/+layout.svelte`)

In the `$effect` at `+layout.svelte:134`:

- Fire when `authCfg` is true regardless of login state.
- Dedupe key: `${u.username}|${path}` when logged in, `anon|${path}` otherwise.
- `trackPage(path)` already sends `authHeaders()` (empty for guests) — no api.ts change needed.

### 3.5 `admin/activity/+page.svelte` redesign

Layout (top → bottom):

1. **Back link + title + total badge** (keep).
2. **Range selector**: radio-input tabs styled like the year tabs — `7 days / 30 days / 90 days / All`. One selector drives both the summary and the detail table.
3. **Stat cards** `grid-cols-2 md:grid-cols-5` (DaisyUI `stat` cards like the admin dashboard):
   - Page views — sub-line `anon X · logged-in Y`
   - API requests — sub-line `anon X · logged-in Y`
   - Errors — value + `(rate%)`
   - Avg response — `123 ms`
   - Active days — out of the selected range
4. **Charts** `grid-cols-1 md:grid-cols-2`:
   1. "Traffic over time" — line chart, two datasets (Page views, API requests) from `daily_series`.
   2. "Hour of day" — bar chart (24 buckets) from `hourly_series`.
   3. "Top pages" — horizontal bar (`indexAxis: "y"`) from `top_pages`.
   4. "Top users" — horizontal bar from `top_users` (logged-in only).
5. **Detail log** (existing table + filters), mobile-responsive:
   - `md+`: existing `table` with `overflow-x-auto`.
   - `<md`: each row renders as a stacked card — time, user + role badge, type badge, wrapped path + query, status, ms. No horizontal scroll.
   - Keep username/type filters, pagination, auto-refresh, clear-log dialog.
   - Auto-refresh reloads the summary too.
6. Loading / error / empty states for both the summary and the table.

Note: "All time" on the summary may show big date ranges — the daily line chart
labels every Nth day.

---

## 4. Tests (`backend/tests/test_activity.py`)

- Update:
  - `test_middleware_skips_anonymous` → assert no `activity_logs` rows but a
    `traffic_daily` row exists (`kind='api'`, `anonymous=True`).
  - `test_track_page_requires_auth` → rename/rework: anonymous beacon now returns
    200 and writes a `traffic_daily` row (no `activity_logs` row).
- Add:
  - authenticated request → detail row **and** traffic row (`anonymous=False`).
  - bot UA (e.g. `Googlebot/2.1`) → no `traffic_daily` row for anonymous request.
  - `/api/health` → no traffic row.
  - `normalize_path`: numeric → `[id]`, hex slug → `[slug]`, query stripped, club paths kept.
  - summary endpoint: shape, range filter, totals, top_pages/top_users, errors, 403 for member, 401 for no token.
  - `days` param on the log list endpoint.
- Run: `cd backend && source .venv/bin/activate && pytest` (expect all pass).

---

## 5. Docs

- Update the **Activity tracking** section of `AGENTS.md` (it currently states
  anonymous traffic is skipped). Document `traffic_daily`, bot filtering,
  `/api/health` exclusion, TZ bucketing, summary endpoint.
- Prepend a patch-notes entry to `frontend/static/patch_notes.json`
  (admin-facing "Activity dashboard" entry).
- Optionally note in `MEMORY.md` if the existing entry references the old behavior.

---

## 6. Verification

1. `cd backend && source .venv/bin/activate && pytest`.
2. `cd frontend && npm run build`.
3. Manual smoke test (dev server):
   - Browse the site logged-out (a few pages) → summary shows anonymous counts.
   - Log in as admin → activity page shows graphs + anon/auth split; detailed log
     still shows only logged-in rows.
   - Resize to ~375px → charts stack, log rows become cards, no horizontal scroll.
   - Range tabs switch summary + table range; auto-refresh still works.

## Notes / caveats

- Anonymous stats start accumulating from the deploy date (historical anonymous
  traffic was never captured). Logged-in history is backfilled from
  `activity_logs`.
- `traffic_daily` growth is bounded (per day/hour/path-group); no retention
  needed for v1.
- The detailed log remains authenticated-only; anonymous usage is visible in the
  graphs/counters.

---

# Phase 2 — Consolidate admin into one tabbed page

## Goal

All administrator functionality (dashboard/overview, activity usage dashboard,
upload, user management) on a single page at `/admin`, organised as tabs.
Old routes `/upload`, `/admin/activity` and `/admin/users` are deleted.

Decisions confirmed with the user:

- Include user management as a tab too (all admin stuff on one page).
- **Tabs** layout (not collapsible sections).
- **Delete** the old routes (no redirects).
- Use **Material Symbols** for icons (self-hosted `material-symbols` npm
  package, `@import "material-symbols/outlined.css"` in `app.css`).

## 1. Components (`frontend/src/lib/admin/`)

Each area is extracted into a component (minus its `<svelte:head>`, page
wrapper and h1; headings become `h2`):

- `Overview.svelte` — from `/admin`: stats cards, Refresh Cache button,
  Identity Review (merge/split/dismiss + toasts). Quick-action cards removed
  (the tabs replace them).
- `Activity.svelte` — from `/admin/activity`: range tabs, filters, stat cards,
  Chart.js graphs, detail table + mobile cards, clear-log dialog. "Back to
  Admin" link removed.
- `Upload.svelte` — from `/upload`: host-club datalist, dropzone, URL import,
  upload status list, club-mapping dialog. `authCfg && !loggedIn` gate + auth
  state removed (page is admin-only now).
- `Users.svelte` — from `/admin/users`: user table, add/reset/delete dialogs,
  permission checkboxes, toasts.

## 2. Tabbed shell (`/admin/+page.svelte`)

- `TABS` = overview (space_dashboard), activity (monitoring), upload
  (upload_file), users (group).
- `activeTab` derived from `$page.url.searchParams.get("tab")`, falling back to
  `overview` for missing/invalid — URL is the single source of truth, so
  back/forward and deep links (`/admin?tab=activity`) work.
- daisyUI `tabs tabs-box` of real `<a class="tab">` links (icon + label,
  `aria-current="page"` on active, no `role=tab`), wrapped in `overflow-x-auto`
  for mobile.
- Panels `{#if activeTab === …}` → components mount only when active (charts,
  known-clubs, identity review and the activity auto-refresh interval all load
  on demand and clean up on unmount).

## 3. Navigation (`+layout.svelte`)

- New `adminTab(key)` helper (pathname `/admin` + `?tab=` match).
- Desktop admin dropdown + mobile drawer: Dashboard → `/admin`,
  Activity → `/admin?tab=activity`, Upload → `/admin?tab=upload`,
  Users → `/admin?tab=users`, with Material Symbols icons.

## 4. Route deletions + link updates

- Delete `src/routes/upload/`, `src/routes/admin/activity/`,
  `src/routes/admin/users/` (all client-only pages, no `+page.server.ts`).
- `events/+page.svelte` and `results/+page.svelte` empty-state "Upload an
  event" buttons → `/admin?tab=upload`.

## 5. Icons

- `npm install material-symbols`; `@import "material-symbols/outlined.css"` in
  `app.css` plus a `.material-symbols-outlined` base rule (font-size 1.25em,
  line-height 1, vertical-align middle, FILL 0/wght 400/GRAD 0/opsz 24).
- Icons are decorative: `<span class="material-symbols-outlined"
  aria-hidden="true">name</span>` with a visible text label.

## 6. Docs

- `AGENTS.md`: routes tree (drop the three routes, add `lib/admin/` +
  `charts/ChartJs.svelte`), Activity-tracking UI URL → `/admin?tab=activity`,
  Material Symbols note in Styling.
- `README.md` + `MEMORY.md`: route-tree / routes list updated.
- `patch_notes.json`: "Admin: everything on one page" entry.

## 7. Verification

- `cd frontend && npm run build`.
- Preview-server smoke test: `/admin` + `/admin?tab=users` → 200; removed
  routes → 404. Full tab behaviour is client-side (admin pages are
  client-gated until auth resolves, so SSR shows only the shell).
- Manual: tab switching + deep links, back/forward, mobile (~375px) tab bar,
  responsive activity cards/charts, upload + club-mapping dialog,
  identity merge/split, user add/reset/delete.
