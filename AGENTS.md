# AI Agent Guidelines — NZ Gymnastics Results

## Project Overview

Web app to ingest Scoreholder JSON exports, parse into normalized SQLite, pivot to wide format, and display/export results via a SvelteKit frontend.

- **Backend:** Python 3.12+, FastAPI, SQLAlchemy, SQLite, Pandas, bcrypt, PyJWT
- **Frontend:** SvelteKit 5, Tailwind CSS v4 (`@import "tailwindcss"`), DaisyUI v5 (`@plugin "daisyui"`)
- **Infrastructure:** Docker Compose

## Directory Structure

```
.
├── .dev.sh                  # Start backend + frontend concurrently
├── docker-compose.yml       # Dev Docker Compose
├── docker-compose.prod.yml  # Production Docker Compose (uses external network)
│
├── backend/
│   ├── Dockerfile           # Production-ready (no dev dependencies)
│   ├── app/
│   │   ├── main.py          # FastAPI routes
│   │   ├── models.py        # SQLAlchemy models (is_national, etc.; Athlete)
│   │   ├── database.py      # SQLite engine + session + migration (athletes, intents re-key)
│   │   ├── schemas.py       # Pydantic models (RankingRow, etc.; slug fields)
│   │   ├── auth.py          # JWT auth (bcrypt, HS256, role-based, seed_admin_user)
│   │   ├── cache.py         # GranularTTLCache with per-key TTL + per-event prefix invalidation, admin refresh-cache endpoint, single-flight cached()
│   │   ├── activity_log.py  # Non-blocking batched background writer for activity_logs + traffic_daily
│   │   ├── traffic.py       # Path normalization + bot detection for traffic aggregates
│   │   ├── athlete_identity.py # Athlete clustering + rebuild_athletes + rebuild CLI (python -m app.athlete_identity)
│   │   ├── parser.py        # Scoreholder JSON parser (~630 lines)
│   │   ├── decoder.py       # Node-tree score field decoder
│   │   ├── resolver.py      # ID chain resolver
│   │   ├── transformer.py   # Pandas long→wide pivot + CSV/XLSX export + region enrichment
│   │   ├── reconcile.py     # Evidence-based athlete ID reconciliation
│   │   ├── reconcile_clubs.py # Club name normalization script
│   │   ├── repair_identities.py # One-time repair from source JSONs (dry-run + --apply)
│   │   ├── scoreholder.py   # Fetch Scoreholder event JSON exports from public URLs
│   │   ├── validate_json.py # Batch validation CLI
│   │   └── wellington_ranking.py # Wellington regional ranking computation
│   ├── tests/               # pytest suite (332 pass, 87 skip)
│   └── pyproject.toml
│
├── frontend/
│   ├── Dockerfile           # Dev Dockerfile
│   ├── Dockerfile.prod      # Multi-stage production build
│   ├── src/
│   │   ├── hooks.server.ts  # API proxy (/api → backend in production)
│   │   ├── lib/
│   │   │   ├── api.ts              # Typed fetch wrappers (updateGymnast, etc.)
│   │   │   ├── auth.ts             # JWT auth stores (currentUser, setToken, logout)
│   │   │   ├── year.ts             # yearOptions store (selectedYear removed)
│   │   │   ├── utils/debounce.ts   # Debounce helper for search inputs
│   │   │   ├── regions.ts          # Region color palettes + REGION_ORDER (north→south) + WCAG-contrast text/gradient helpers
│   │   │   ├── RegionBadge.svelte  # Region color badge component
│   │   │   ├── Dialog.svelte       # A11y dialog (aria-modal, focus trap, Escape, focus restore)
│   │   │   ├── NZRegionMap.svelte  # Interactive NZ SVG map (15 gym regions, animated checker on hover/select)
│   │   │   ├── WideResultsTable.svelte  # Shared results table (paginated, virtualized)
│   │   │   ├── ScoreTooltip.svelte      # Apparatus score tooltip
│   │   │   ├── AATooltip.svelte         # AA score tooltip
│   │   │   ├── ExportMenu.svelte        # CSV/XLSX/PDF export dropdown
│   │   │   ├── charts/ChartJs.svelte    # Lazy-loaded Chart.js wrapper (canvas role="img" + aria-label)
│   │   │   ├── admin/
│   │   │   │   ├── Overview.svelte      # Site stats band (Events/Gymnasts/Scores/Clubs); refreshToken prop reloads after cache refresh
│   │   │   │   ├── Activity.svelte      # Usage band: range tabs + auto-refresh + stat tiles; onData feeds the charts
│   │   │   │   ├── ActivityCharts.svelte # 4 compact Chart.js graphs (4-across band, h-44)
│   │   │   │   ├── ActivityLog.svelte   # Logged-in detail log (dialog): range/filter/pagination/clear
│   │   │   │   ├── Upload.svelte        # JSON upload (file drag-drop + import-from-URL + club mapping) — dialog
│   │   │   │   ├── Users.svelte         # User management (add/reset/delete, permissions) — dialog
│   │   │   │   ├── IdentityReview.svelte # Athlete identity merge/split — dialog, onCount reports conflicts
│   │   │   │   └── StatTile.svelte      # Snug square stat tile (icon + value + label [+ sub])
│   │   │   └── export.ts                # Export builders (CSV, XLSX, PDF) + slugifyFilename + ColFormat/PdfColumn types
│   │   ├── routes/
│   │   │   ├── +layout.svelte          # Nav, footer, theme toggle, year tabs via goto()
│   │   │   ├── +page.svelte            # Landing page (info items above nav cards w/ stat badges, What's new from patch_notes.json)
│   │   │   ├── login/+page.svelte      # Username+password login
│   │   │   ├── admin/+page.svelte      # Single admin page — four labelled bands (Site stats / Manage tools / Usage stats / Graphs) + dialog buttons (Upload/Users/IdentityReview/Logged-in activity)
│   │   │   ├── rankings/+page.svelte   # National Rankings (member+)
│   │   │   ├── rankings/apparatus/+page.svelte # Apparatus Rankings (member+)
│   │   │   ├── wellington-ranking/+page.svelte # Wellington Rankings (member+)
│   │   │   ├── events/+page.server.ts  # SSR load function for event list
│   │   │   ├── events/+page.svelte     # Event list with sort/search/edit
│   │   │   ├── events/[id]/+page.server.ts # SSR load for event results
│   │   │   ├── events/[id]/+page.svelte # Event results
│   │   │   ├── results/+page.server.ts # SSR load for all results
│   │   │   ├── results/+page.svelte    # All-events results
│   │   │   ├── clubs/+page.svelte  # Interactive NZ map (desktop) / collapsible region accordion (mobile)
│   │   │   ├── club/[club]/+page.server.ts # SSR load for club results
│   │   │   ├── club/[club]/+page.svelte # Club results
│   │   │   ├── gymnasts/+page.server.ts # SSR load for gymnast list
│   │   │   ├── gymnasts/+page.svelte   # Gymnast list (A-Z jump, sticky header w/ search, back-to-top)
│   │   │   ├── gymnast/[gnz_id]/+page.svelte # Gymnast results (client-only, no server load)
│   │   ├── static/
│   │   │   └── patch_notes.json  # Full update history; landing page shows all in a scrollable section
│   │   ├── app.css              # @import "tailwindcss"; @import "material-symbols/outlined.css"; @plugin "daisyui";
│   │   └── app.html
│   ├── svelte.config.js         # adapter-node; csrf: { checkOrigin: false }
│   └── vite.config.ts          # tailwindcss() + sveltekit() plugins
│
└── data-collection/         # Reference JSON files for testing
```

## Python Backend Conventions

### Imports
stdlib first, then third-party, then local. `from X import Y` style, one per line grouped with parentheses. No wildcard imports.

```python
import json
from pathlib import Path

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from app.auth import require_role
from app.database import get_session
```

### Typing
- Python 3.10+ union syntax: `str | None`, `dict[str, float | str | None]`
- Return type on every function, `-> None` for void
- `object` as fallback for truly unknown types
- No `from __future__ import annotations`

### Naming
- `snake_case` for functions/vars/modules, `PascalCase` for classes
- Private helpers prefixed with `_`
- Constants in `UPPER_SNAKE_CASE`
- Pydantic models suffix: `Response`, `Item`, `Update`

### Error handling
- SQLAlchemy sessions: `try / finally` with `session.close()`
- Custom exceptions for domain errors (e.g., `ParseError`)
- FastAPI endpoints: `raise HTTPException(status, detail)`
- No bare `except:`, no mocks in tests

### Docstrings
- Module-level docstring in every file
- Public functions: one-line imperative summary, optional `Args:`/`Returns:` sections (Google style)
- Private helpers: one-line docstring
- All `"""double quotes"""`

### Strings & style
- f-strings exclusively
- PEP 8 line length (~100 char)
- No type comments

## Svelte Frontend Conventions

### Svelte 5 runes
- `$state()` for all reactive state (typed explicitly when not trivially inferred)
- `$derived()` for computed values
- `$props()` with destructuring + inline type annotation
- Snippets: `import type { Snippet } from "svelte"`
- `onMount` for lifecycle (return cleanup function for subscriptions)

```typescript
let loading = $state(true);
let filtered = $derived(items.filter(fn));
let { label, count = 0 }: { label: string; count?: number } = $props();
```

### Types
- `<script lang="ts">` on every component
- Co-located `interface` declarations for component data types
- `Record<string, unknown>` for generic row/column data
- `null` for optional/missing (not `undefined`)
- No `any` — use `unknown`

### API client (`api.ts`)
- `API_BASE = ""` (same-origin) — `/api` requests proxied to backend via `hooks.server.ts` in production, Vite dev proxy in development
- All functions `async`, typed return values
- Auth header: `getToken()` reads JWT from localStorage, passed as `Authorization: Bearer <token>`
- Error: throw with `await res.text()`, callers `.catch()`
- Relative URLs: use string concatenation + `URLSearchParams`, **never** `new URL()` (breaks on relative paths)

### Styling
- Tailwind CSS v4: `@import "tailwindcss"` in `app.css`
- DaisyUI v5: `@plugin "daisyui"` in `app.css`
- Icons: Material Symbols via `@import "material-symbols/outlined.css"` in `app.css` — `<span class="material-symbols-outlined" aria-hidden="true">name</span>`, always decorative with a text label
- `tailwindcss()` Vite plugin in `vite.config.ts`
- No CSS modules or scoped `<style>` blocks
- Dark/light theme via `data-theme` attribute, persisted in `localStorage`

### Routing
- File-based SvelteKit routing under `src/routes/`
- Data fetching in `+page.server.ts` load functions (SSR) for all data routes
- `goto()` from `$app/navigation` for programmatic navigation
- URL search params drive year filtering, search, and pagination state

## Testing Conventions

### Backend (pytest)
- All tests in `backend/tests/`, one file per module
- **Run:** `cd backend && source .venv/bin/activate && pytest`
- **Run single:** `pytest tests/test_parser.py -v`
- **Stats:** 332 pass, 87 skip (skipped tests rely on data-collection JSON files not always present)
- Plain `assert` statements (no `unittest` methods)
- `@pytest.mark.parametrize` for data-driven tests
- Inline fixtures (no conftest.py) — SQLite `:memory:` or temp file
- No mocks — tests use real JSON data from `data-collection/`
- Test classes group related tests (e.g., `TestBuildOutputMap`)
- Conditional skip: `pytest.skip("reason")` for missing data files

### Frontend
- No frontend tests currently
- Verify with `cd frontend && npm run build`

## Documentation Conventions

- Whenever updating project docs (MEMORY.md, README.md, PLAN.md, DESIGN-DOCUMENT.md, BUGS.md) for a **notable user-facing change**, also prepend a matching entry to `frontend/static/patch_notes.json`.
- The file is the full history, newest date group first. The landing page fetches it and renders everything in a scrollable "What's new" section, so additions are always visible without a frontend change.
- Patch-note entry shape: `{ "date": "<Day Mon YYYY>", "entries": [{ "title": "...", "items": ["..."] }] }`. Group multiple updates from the same date under one `date` key.

## Development Commands

```bash
# Start both services (standalone)
./.dev.sh

# VS Code: Ctrl+Shift+B opens dedicated terminal panels

# Backend only (with venv)
cd backend && source .venv/bin/activate
uvicorn app.main:app --reload --port 8000

# Frontend only
cd frontend && npm run dev

# Run all tests
cd backend && source .venv/bin/activate && pytest

# Validate JSON files
cd backend && source .venv/bin/activate
python -m app.validate_json path/to/file.json

# Dev Docker
docker compose up --build

# Production Docker
docker compose -f docker-compose.prod.yml up --build -d
```

## Production Deployment

- **docker-compose.prod.yml** — production config using external `yams_default` network (shared with Nginx Proxy Manager)
- **frontend/Dockerfile.prod** — multi-stage production build (adapter-node, no dev dependencies)
- **Nginx Proxy Manager** proxies `scores.mylesglass.com → frontend:3000`
- **API proxy**: `hooks.server.ts` proxies `/api` requests from frontend server to backend container
- **Env vars required**: `ADMIN_PASSWORD`, `ORIGIN` (e.g. `https://scores.mylesglass.com`)
- **Body size**: `BODY_SIZE_LIMIT=52428800` (50MB) needed for JSON uploads — the adapter-node default is 512KB
- **Healthchecks**: both services define `healthcheck`s (backend python `urllib` → `/api/health`; frontend `node fetch` → `/`), and the frontend `depends_on backend: condition: service_healthy` so it never boots ahead of a ready API. With single replicas a brief 502/second gap is still possible while a container restarts during `docker compose up -d --build`.
- **New-version banner**: `svelte.config.js` sets `version: { pollInterval: 60_000 }`; `+layout.svelte` shows a dismissible "reload" bar when `updated.current` (from `$app/state`) flips true, and calls `updated.check()` on mount + tab refocus. Fresh page loads get new hashed bundles automatically after a deploy; this covers users with the app open in a tab.

## Key Architectural Decisions & Gotchas

- **SQLite** — single file, no PostgreSQL needed
- **Scoreholder JSON parsing** — flat reference-based model with 22 top-level arrays. IDs resolved via resolver chains, scores decoded via node-tree output maps.
- **Vault aggregation** — level-dependent: STEP 6/7 always average; high-level AA best-mark, high-level Apps average. Logic in `transformer._use_vault_average()`.
- **National rankings — one mark per competition** — `/api/rankings` groups rows by `(gymnast, event, round_type)`, computes a competition score per group (max AA else apparatus sum with vault rules), then collapses to the **max score per `(gymnast, event)`** so a two-day meet (AA + Apparatus Finals) contributes only one mark; the total is always made of distinct competitions. **STEP 5/6 rank on the AVERAGE of their top 3 marks** (`_RANKING_MARKS`); all other steps use the top 2 summed (`total`). Sort/rank/ties use the average for STEP 5/6 and the total otherwise. All per-event marks (`all_events`) are kept for the qualifier check, not just the selected top marks. STEP 1–4 return a display-only `reached_mark` flag — the rankings table's rightmost **Q** column (✓ vs —) — set when a gymnast reached 52.000 on 2 distinct competitions that season (`_MARK_INDICATOR`). The endpoint accepts an optional `division` query param (`OVER`/`UNDER`) that filters rows in SQL, so qualifier marks, the Q column and quota mode all operate on division-only data. Frontend: the quota/qualifier toggles are hidden for STEP 1–4 and MAG Level 1–3 (`showRankingToggles`), the Total column is hidden (bolded Average shown), a "Can't find someone?" alert appears under the table when `qualifier` is on, a WAG-only Division `<select>` (`divisionFilter`, shown next to the step selector) triggers a server reload and is reset only when the selected step has no division (STEP 9/10 + Internationals), and the Club/Region headers have funnel-icon dropdowns that filter the already-loaded rows client-side (`filteredRankings`, exports follow the filter). The dropdowns are **multi-select** (shared `FilterDropdown.svelte` in `lib/`): each option is a `menuitemcheckbox`, the menu stays open while toggling (closes on Escape, trigger click, outside click or `focusout`), and the funnel shows a `badge-primary` **count badge** of how many clubs/regions are selected (`clubFilters`/`regionFilters` arrays; zero selected = show all). Selections persist across step/division/apparatus-tab changes — a pruning `$effect` drops any selected value absent from the newly loaded rows (so no stale empty table) — and reset only when the year or discipline changes. For steps where `showRankingToggles` is true a callout card at the top of the page (`rankings/+page.svelte`) explains the ranking system (`rankingNote` — STEP 5/6 average of top 3, else sum of top 2), the qualifying mark (`QUALIFIER_RULES`/`qualifierHint`), the apparatus marks (`APPARATUS_RULES`/`apparatusNote`, specialist steps only) and what each toggle does.
- **GNZ qualifying marks (national `qualifier` filter)** — `_QUALIFIER_CONFIG` in `main.py`: STEP 5/6 = 2 marks ≥ 50.000 with one from an event whose host club's region ≠ the athlete's home region; STEP 7–10 = 2 marks ≥ 43.000; Youth/Junior/Senior International = 1 mark ≥ 42.5/43.0/45.0; MAG Level 7–9, U18, Senior Open = 1 mark ≥ 63.0; everything else always qualifies. Marks are distinct competitions by construction. A blank/unknown host club never counts as "outside" (conservative).
- **National apparatus qualifiers** — `_APPARATUS_QUALIFIER_CONFIG` in `main.py` gives `/api/rankings` an `apparatus_specialists` section for WAG STEP 8–10 (11.000 × 2 distinct competitions), MAG Level 7/8/9/U18/Senior Open (11.500 × 1) and Junior/Senior International (per-apparatus VT/UB/BB/FX thresholds × 1); Youth International has none (mirrors Wellington). Per-(gymnast, apparatus, event) bests are accumulated during the ranking pass (round-type-merged, vault per `_use_vault_average`). The section rides on the `qualifier` filter: it's only computed when `qualifier` is true, and gymnasts already in the (filtered) AA table are excluded (`exclude_names=set(gymnast_data)` in `_compute_apparatus_specialists`), so the specialists are the non-qualifiers who hit apparatus marks and the two tables never overlap — with `qualifier` off the section is empty. Rows carry the `qualified: True/False` solid vs ghost `apparatus` badges (`{app, best, event, count, competitions[]}`) shape and respect the SQL-level `division` filter. Frontend: `rankings/+page.svelte` renders the "Apparatus Qualifiers" table below the main table whenever rows come back (i.e. the Qualified toggle is on), with colour-coded badges + structured tooltips (`appTooltip`/`appMarkText`, per-apparatus marks for International steps, `max-w-[18rem]` wrapped panels), a per-step `SPECIALIST_NOTES` blurb, and follows the Club/Region funnel filters (`filteredSpecialists`); the section is not exported.
- **Apparatus rankings** — `GET /api/rankings/apparatus` (`ApparatusRankingsResponse`, `require_permission(PERMISSION_NATIONAL)`) ranks gymnasts per apparatus by their best single mark in the season, using non-national events like the AA rankings. `main.py`'s `_build_event_marks(rows, step)` helper (extracted from the `/api/rankings` pass) groups rows by `(gymnast, event, round_type)`, collapses each event to one competition score + one per-apparatus score (round-type-merged, vault per `_use_vault_average`), and returns `(per_event, apparatus_events, meta_by_name)`; `apparatus_events` entries are `{score, event_name, d}` where `d` is the D-score of the best pass (averaged when the vault is averaged, matching `_build_wide_row`). The endpoint keeps each gymnast's max `apparatus_events` entry per apparatus → rows `{rank, name, gnz_id, club, region, best, d, event, count}` with `T`-tie ranks, ordered by `_APPARATUS_ORDER` (WAG `VT,UB,BB,FX`, MAG `FX,PH,SR,VT,PB,HB`) plus any stragglers alphabetically, respecting the SQL-level `division` filter. **Server-cached** via `cached(("apparatus-rankings", year, step, discipline, division))` (TTL 300s, ETag via `cache_headers()`) — safe because this endpoint has no qualifier/intent toggles; `cached()` is **single-flight** so concurrent misses compute once instead of hammering SQLite. Invalidated by `invalidate()`/refresh-cache (full clear), per-event `invalidate(id)`, and the inline gymnast-edit path (`cache.invalidate_prefix("apparatus-rankings")`). Frontend: `/rankings/apparatus/+page.svelte` (guard + Rankings-dropdown item + year tabs behind `currentPath.startsWith("/rankings")` in `+layout.svelte`) with WAG/MAG toggle, step select (`getRankingSteps`), apparatus radio tabs, WAG division select (disabled for STEP 9/10 + Internationals), Club/Region funnel filters, a D-score column, a Best column whose tooltip shows the competition + mark count, and CSV/XLSX/PDF export (`ExportMenu`). `getApparatusRankings` (api.ts) aborts after 20s; the page uses a plain-`let` stale-response token (`fetchToken`, Wellington pattern) so out-of-order responses are dropped.
- **Event `host_club`** — nullable column on `events` (ALTER TABLE in `init_db()`, which also drops the superseded `host_province` column), set at upload from the `host_club` form field / `ImportUrlRequest` field, otherwise a best-effort name-based guess via `transformer._guess_host_club()` (canonical club names + aliases as substrings, longest match wins). National events default to `"Gymnastics NZ"`. Editable via `PATCH /api/events/{id}` (admin events edit dialog, searchable datalist fed by `GET /api/clubs/known`). The national STEP 5/6 away rule derives the event's province from the host club via `_find_region(host_club)`. Existing events can be filled without re-upload using `python -m app.backfill_host_club` (dry-run by default, `--apply` to write; review wrong guesses on the events page). Reference worksheet: `data-collection/event_names.txt` (`YYYY<TAB>name<TAB>host`).
- **Event re-upload dedup** — `_ingest_event` replaces **all** existing events matching `(name, start_date, discipline)` (previously only the `.first()` match by name alone, which left stale copies and could delete a same-named event from a different year — e.g. re-uploading 2025 `MAG Wellington Champs` deleted the 2023 one). Re-importing a competition now never accumulates duplicates. Already-duplicated rows (same export imported repeatedly, e.g. 4× identical `Auckland Champs` 2025-03-01) are cleaned with `python -m app.dedupe_events` (dry-run by default, `--apply` to write; keeps the copy with the most `long_scores`, tie-break lowest id; ORM cascades the deleted copies' scores).
- **Bonus propagation** — apparatus-level modifier stored on one pass, propagated to all passes in same `(entityId, unitEventId)` group at parse time.
- **Floating point** — `_fmt3` in transformer.py: rounds to 6 decimals then floors to 3 to handle IEEE 754 noise.
- **WAG/MAG split** — tab assignment uses `discipline` field from data, not apparatus heuristic.
- **Division extraction** — heuristic text matching (UNDER/OVER/A/B) from competition node names.
- **Round-type day detection** — `_infer_round_type` looks for day markers (`day 2`/`day two`) in **both** the unit name and the competition node name, so multi-day meets whose day info lives only in node names (`All-around - Day 2`, `Balance Beam - Day 2`) split into `All Around - Day 2` / `Apparatus Finals` / `Day 2` rounds instead of collapsing into Day 1's `All Around`. Without this, both days merge into one wide row with mixed apparatus and a single (wrong) all-around.
- **Numpy types in JSON** — pandas/numpy produce `numpy.int64`/`numpy.float64` that FastAPI's `jsonable_encoder` can't serialize; must convert in transformer.py.
- **Auth** — JWT-based (bcrypt, HS256, 7-day expiry), role-based (admin/member). Admin seeded from env vars (`ADMIN_USERNAME`, `ADMIN_PASSWORD`, `ADMIN_ROLE`). JWT_SECRET auto-generated and persisted to `data/jwt_secret.txt`. When `ADMIN_PASSWORD` is unset, all endpoints are public.
- **Page permissions** — per-user ranking-page access. `User.permissions` is a comma-separated string of keys (`rankings.national`, `rankings.wellington`), migrated in `init_db()` (ALTER TABLE ADD COLUMN). Backend enforces via `require_permission(*keys)` in `auth.py` (DB lookup; admins bypass; dev fallback admin bypasses). New members default to `rankings.national` only; admins are always full (login/me/status/users report effective permissions via `effective_permissions`). Ranking endpoints: `/api/rankings`→national, `/api/rankings/wellington` + `GET /api/wellington/intents`→wellington, `/api/rankings/steps`→either. `PATCH /api/auth/users/{id}/permissions` (admin) updates them; `GET /api/auth/me` returns DB-fresh permissions. Frontend: `lib/auth.ts` stores permissions in localStorage (`nzgr_permissions`), `hasPermission()` (admins pass), `+layout.svelte` refreshes via `me()` on mount and gates nav links; signed-out users and members without the permission are redirected away from ranking pages by the route guard.
- **Client-side route guard** — auth lives in localStorage (no SSR cookies), so protected routes are guarded in `+layout.svelte`. `requiresAuth` (currently `/admin` prefix plus `/rankings` prefix and `/wellington-ranking`) waits for `checkAuthStatus()` **and** `me()` (the permission refresh) to settle (`Promise.allSettled` → `authResolved`/`authActive`), renders nothing until then (no flash), then `goto(authRedirectTarget)` via `$effect` when the user has no access. Signed-out users and logged-in members lacking the required role/permission are both redirected to `/`: `/admin` requires `admin`, `/rankings` (+ `/rankings/apparatus`) requires `rankings.national`, `/wellington-ranking` requires `rankings.wellington` (`routeAllowed`). Auth-disabled servers stay public. **Stale sessions** — when `me()` returns 401 (expired token / rotated JWT secret), the user is auto-logged-out (`logout()` clears localStorage) and `authRedirectTarget` is set to `/login` so protected pages land on the login page instead of bouncing. `parseToken` in `auth.ts` also rejects tokens past their `exp` claim so an expired JWT never yields a phantom logged-in user. Add new prefixes to `requiresAuth` for other logged-in-only pages.
- **Import from URL** — `POST /api/import-url` (admin) takes `{url, allow_unknown}` and fetches the Scoreholder public export via `app/scoreholder.py`. The API form is `https://scoreholder.com/api/events/{id}?context=public` (NOT the old `?scope=PUBLIC`, which now 400s). It 307-redirects to a CloudFront cache URL. The response is always Brotli-compressed (`Content-Encoding: br`) regardless of `Accept-Encoding`, so httpx needs the `brotli` package installed. No Cloudflare challenge for plain browser-UA requests. Event ID extracted via `r"/events/([0-9a-f]{24})"`; fetch errors → 502; shares `_ingest_event()` with `POST /api/upload`.
- **DB schema** — `events` table + `long_scores` table (one row per apparatus pass per gymnast) + `users` table (username, hashed_password, role).
- **`new URL()` breaks** on relative paths in dev mode — use string concatenation in api.ts.
- **Two JSON formats exist** — only the new format (`eventOrganizations`, `performanceRules`, etc.) is supported.
- **Name cleaning** — `_NAME_LEVEL_SUFFIX` regex strips `(L#)`, `(STEP 10)`, `(YI)` from gymnast names at parse time. `resolver.py`'s `_clean_name`/`_title_case_token` preserves intentional capitalization — tokens with an internal cap (`McEwan`, `O'Sullivan`, `MacIntyre`, hyphen parts like `Smith-Jones`) are kept as-is; only genuinely un-cased tokens (all-lower/all-upper) are rebuilt, capitalising each hyphen segment. A past bug used `w.capitalize()` which lowercased the rest of every word (`Eva McEwan` → `Eva Mcewan`) — live DB was repaired via `python -m app.repair_identities`.
- **Athlete identity reconciliation** — `reconcile_athletes()` (runs after every ingest) is evidence-based: it merges same-name rows to one ID **only** when there's no same-event ID collision (2+ distinct IDs for a name within one event = distinct people) and no discipline conflict (a name's IDs spanning WAG+MAG = distinct people). Those cases, plus equal-frequency ties, are reported in `conflicts` with a `reason`. Uploads also run `detect_participant_collisions()` (parser.py) which flags same-name-2-IDs / same-ID-2-names within one event, surfaced as `EventResponse.warnings` (shown on the upload page; distinct people stay separate). Ingest-time ID backfill (main.py) only assigns a missing `gnz_id` when the name maps to exactly one distinct numeric ID in the DB.
- **One-time identity repair** — `python -m app.repair_identities` (dry-run by default, `--apply` to write, `--db` to target another SQLite file) is **consensus-driven**: it counts numeric identifiers and name spellings across *all* source JSONs in `data-collection/` per `(name, club)` signature, then updates DB rows to the majority value — but only when the winner beats the runner-up by ≥2x (ties/near-ties are left alone, protecting genuine same-name two-people cases and systematic source-ID shifts). A single file's typo never overwrites an ID five other files agree on. Name fixes run through the fixed `_clean_name` so all source casings of a name collapse to the canonical spelling. Idempotent; re-running after apply reports 0. Events with no source coverage are fixed anyway when their athlete's `(name, club)` appears in any source file; fully-unmatched athletes are untouched. In the production container the source JSONs are **not** in the image — mount them: `docker compose -f docker-compose.prod.yml run --rm -v "$(pwd)/data-collection:/data-collection" backend python -m app.repair_identities --apply` (stop the backend first to avoid a write-lock conflict; it rebuilds athletes + clears cache on start). Applied to production on 14 Aug 2026 (1,237 ID + 13,159 name fixes; Madison Lynch split; see BUGS.md). (The original per-event implementation trusted each source file 100% and could copy a single file's typo over a consistent DB ID — e.g. `Alexandra Boys` got a 7-digit `6511229` — which was caught by diffing against the source consensus and reverted; the script was rewritten to the consensus model.)
- **Athlete identity table (`athletes`)** — the stable identity layer decoupled from the dirty `gnz_id`. Each `LongScore` row carries `athlete_id` → `Athlete` (`slug` `a{sha1-hex10}`, `signature_hash`, `canonical_name`, `gnz_id`). Built by `rebuild_athletes()` in `app/athlete_identity.py` (union-find over `(normalized name, gnz_id)` signatures): within a name, signatures merge unless there's a same-event ID collision, a discipline (WAG/MAG) conflict, or disjoint club sets across different IDs (a person keeps their ID when changing clubs, so disjoint clubs ⇒ two people, e.g. the two Madison Lynches); across names, two athletes sharing a numeric gnz_id merge only when normalized names are similar (difflib ≥ 0.85) so spelling variants collapse while the 33 genuinely-different-people-shared-ID cases stay separate. Empty-ID rows join their name's dominant non-empty ID. `canonical_name`/`gnz_id` = most frequent values; the slug hashes the canonical `(name, id)` pair. `rebuild_athletes()` is **idempotent and signature-stable** (existing athlete rows reused by hash, orphans deleted) — runs after every ingest (upload/import-url, after `reconcile_athletes`), after inline gymnast edit, name merge, duplicate-fix apply, admin refresh-cache, and at startup when the table is empty; CLI: `python -m app.athlete_identity`. After re-clustering it **back-writes** every `long_scores` row to its cluster's canonical spelling (idempotent — matches zero rows once applied; live DB normalized ~3,000 rows across 304 athletes), so raw name-keyed queries, stats counts and per-event groupings stop seeing variants as separate people/marks. Orphan `Athlete` rows are deleted **after** the `athlete_id` reassignment — a rebuild that changes a cluster's identity must re-point rows first or the FK delete fails. Cache prefixes `gymnasts`/`medals`/`wide-all` cover the athlete-derived caches. **Query layers are re-keyed on `athlete_id`**: transformer pivot groups by athlete identity (canonical name + `slug` in every wide row), medals/gymnasts/wide-all accept `athlete_id`/`slug`, and rankings/apparatus/wellington group by athlete key so variant spellings rank as one gymnast. **Gymnast URLs** are `/gymnast/{slug}`; the route param can be a slug or a legacy `gnz_id` (the page sends slug-like values through the `slug` query param and everything else through `gnz_id`). Wellington intents are re-keyed on `athlete_id` (`UNIQUE(athlete_id, year)`, table rebuilt in `init_db()` with existing rows mapped via canonical gnz_id); `/api/wellington/intent` accepts `athlete_id`, `slug`, or legacy `gnz_id`. Gymnast counts (`/api/stats` `total_gymnasts`, event-list `gymnast_count`) count `distinct COALESCE(athlete_id, gymnast_name)` so variant spellings and same-name different-people each count once; `_compute_wide_all`'s "gymnast not found" fallback `name` uses `Athlete.canonical_name`.
- **Admin identity review + Merge/Split** — `GET /api/admin/identity-review` (admin, uncached) aggregates athlete-level conflicts: `similar_names` (fuzzy canonical-name pairs, difflib ≥ 0.85 via the token-prefilter, excluding shared-ID pairs), `name_conflicts` (same canonical name on 2+ athletes), `id_conflicts` (same gnz_id on 2+ athletes), and `multi_id_athletes` (one athlete with 2+ gnz_ids). Each `AthleteReviewInfo` carries evidence (slug, gnz_id, clubs, events + event_ids, years, disciplines, rows, wellington intent years). `POST /api/admin/athletes/merge` `{athlete_id, merge_id}` rewrites the merged athlete's rows to the survivor's canonical name + gnz_id (promoting the survivor's gnz_id when empty), clears `identity_override` on both sides, moves Wellington intents (UNIQUE(athlete_id, year), drops on conflict), then rebuilds — the survivor's Athlete row is reused, or re-created when its gnz_id was promoted (located afterwards by canonical name + gnz_id). `POST /api/admin/athletes/split` `{athlete_id, split_by ∈ {gnz_id, event_id, club_name}, value, new_gnz_id?}` assigns the chosen rows a fresh synthetic gnz_id (`S` + hex, or the admin-supplied real ID) **and** a unique `identity_override` token, then rebuilds; the response's two athlete ids are located by their rows after the rebuild (the pre-split id is not preserved when the split-off ID was the cluster's canonical ID). The `long_scores.identity_override` column (nullable, ALTER TABLE in `init_db()`) is the force-split boundary: `_cluster_name_signatures()` treats each distinct token as its own person and clusters unmarked rows with the normal rules, so a split survives rebuilds/re-uploads until a merge clears the token (a bare synthetic gnz_id cannot split same-club halves — e.g. `Te Ahorangi Milsted-Raika` 3 IDs at 1 club). Admin UI: the `/admin` Identity Review card replaced the old "Athlete ID Reconciliation" + "Suggested Merges" cards (the `duplicates*`/`suggested-merges`/`merge-names` endpoints remain in the API but are no longer called by the UI). Guards: self-merge 400, empty/all-row split 400, unknown split_by 400, missing athlete 404.
- **Region enrichment** — club→region lookup at pivot time via `clubs_and_regions.json`; changes require re-upload. The ACTIVE file is `data/clubs_and_regions.json` (inside the `backend_data` volume, via `app/clubdata.py`) so runtime alias saves survive redeploys; the committed `backend/clubs_and_regions.json` is the seed copied in on first run (`ensure_seed()` from `init_db()` and each reader/writer). To commit UI-saved aliases, copy the `data/` copy over the repo seed.
- **Unknown-club check** — `find_unknown_clubs()` in parser.py reads Scoreholder's real field names (`_id` on `eventOrganizations`, `_id`+`organizationId` on `eventParticipants`). A past bug used `orgId`/`participantId` which never match real files, silently letting variant club names through — fixed; uploads now 409 with a mapping dialog for genuinely unknown clubs. Variants that map to a canonical should be added as aliases in `clubs_and_regions.json`, then `python -m app.reconcile_clubs` normalizes existing rows. Regional-team rows (e.g. `Counties - Manukau`) are stored as club names and resolve via the lookup to themselves; `Gymsport Manukau` retargets to `Counties - Manukau`.
- **Club-mapping suggestions** — the 409 unknown-club response includes `suggestions` from `suggest_club_mapping()` in parser.py: exact normalized match (diacritic/whitespace-folded) against the alias table wins, otherwise a fuzzy `difflib.SequenceMatcher` ratio ≥ 0.9. The upload dialog defaults each club to "Keep original name" (`KEEP_ORIGINAL` sentinel in `upload/+page.svelte`) and pre-selects a confident suggestion when present. `saveAndRetry()` persists only mapped clubs via `save_aliases` then re-uploads with `allow_unknown` if any were kept.
- **DaisyUI z-index** — `.dropdown-content` sets `z-index: 1` overriding Tailwind classes; use inline `style="z-index: 50"`.
- **`$effect` reactivity** — tracks all dependencies read inside it; avoid reading state the effect itself modifies.
- **Production API proxy** — `hooks.server.ts` forwards `/api/*` from the frontend Node server to the backend container. `API_BASE` is always `""` (same-origin).
- **Body size limit** — SvelteKit adapter-node defaults to 512KB. JSON uploads can be ~3.5MB. Set `BODY_SIZE_LIMIT=52428800` (bytes) in the frontend service env vars.
- **Cache refresh** — `POST /api/admin/refresh-cache` clears the backend in-memory cache. Admin dashboard has a "Refresh Cache" button to ensure all pages show the latest data after uploads/edits.
- **Browser cache** — ranking endpoints (`/api/rankings/*`) are excluded from the `Cache-Control: public, max-age=300` middleware so intent/qualifier toggles reflect immediately; other endpoints keep browser caching. `stale-while-revalidate=60` (was 3600) so browsers/CDNs never serve public data more than ~1 minute past the fresh window while revalidating.
- **Apparatus Specialists** — Wellington ranking fallback path. Config-driven via `specialist_steps` (steps that check specialist qualification), `apparatus_qualifying_count` (how many competitions on the SAME apparatus must clear the mark — the count unit is distinct competitions, not distinct apparatus), and the threshold: a single float `apparatus_qualifying_score` (STEP 8–10 `wag_step_7_10`: 11.0 × 2 distinct competitions; MAG `mag_level_7_plus`: 11.5 × 1) or a per-apparatus dict `apparatus_qualifying_scores` (WAG `wag_junior_international` VT 12.2/UB 10.4/BB 10.5/FX 11.4 × 1; `wag_senior_international` VT 12.5/UB 11.3/BB 11.2/FX 11.4 × 1). Intent-submitted athletes NOT in the AA table are returned as `apparatus_specialists`; the backend tracks per-(gymnast, apparatus, event) best scores (`apparatus_events`, round-type-merged, vault per `_use_vault_average` rules). Each row is `qualified: True` (≥1 apparatus reached the mark in ≥ `apparatus_qualifying_count` competitions) or `qualified: False` (only 1..count-1 reach). The `apparatus` list mixes entries: a row's qualifying apparatus → solid colour-coded badges, plus any partial apparatus (reached once, count 1..count-1) → greyed-out `badge-outline` ghost badges, solid entries first. Badge entries carry `app`, `best`, `event`, `count`, and `competitions[]` (all qualifying comps, used in the tooltip); rows sort qualified-first then by count/name. The response exposes `apparatus_qualifying_score`/`apparatus_qualifying_count` for generic tooltip text; the frontend picks badge style per entry (`a.count >= apparatus_qualifying_count` → solid). Frontend renders them below the main table with badges (VT primary / UB secondary / BB accent / FX info) + DaisyUI tooltips listing the competitions (ghost badge tooltip: "Reached 11.000 once at X — needs N different competitions").
- **International Wellington configs** — WAG `wag_youth_international` / `wag_junior_international` / `wag_senior_international` (steps `Youth/Junior/Senior International`) use `selection: "international"` + `marks_required: 1`: ranked by the single highest AA mark (selector `_select_international` returns `[best, None, None]`), Gymnastics NZ qualifying 42.5/43.0/45.0 on one occasion, no Wellington qualifier, no competition-mix checks (`_selection_checks` returns `[]` for `marks_required == 1`). `marks_required` (default 3) drives the can't-form-selection check (`None in selected[:marks_required]`) and the `why` message; ranking `scores`/`competitions`/`categories` arrays only contain the filled slots (length 1 for International). The frontend step dropdown no longer filters out "international"; `INTERNATIONAL_CONFIGS` hides the Average column and "Regional events" for these configs. MAG International is just the existing `mag_level_7_plus` steps (U18, Senior Open) at 63.0 AA + 11.5 specialists.
- **Wellington intent tracking** — `WellingtonIntent` model (`wellington_intents` table, unique `(gnz_id, year)`), `GET /api/wellington/intents`, `POST /api/wellington/intent` (admin). Admin checkbox column + Intent filter toggle on the ranking page; toggling calls `invalidate()`.
- **Wellington not_ranked table** — `compute_wellington_rankings` returns a single `not_ranked` list of every Wellington athlete who isn't on the ranking, with a `why` (headline reason) and `checks` (✓/✗ requirements checklist). Two kinds of athlete are merged here: those who can't yet form the required 3-mark selection (`selector()` returned `None`; `why` from the count/mix check) and those who CAN form it but were dropped by the active toggles (`why` from `_dropped_reasons()`: "Hasn't submitted intent yet" when the intent filter is on + the qualifier `warnings`). Row shape: `name, gnz_id, club, region, scores[3] (None-padded), competition_names[3], categories[3], apparatus, competitions, regional_count, club_count, away_count, why, checks[list of {label, met, detail}], intent_submitted`. `checks` comes from `_selection_checks()` (per-config competition-mix items with "x of y" `detail`) + an `Intent submitted` item + `_qualifier_checks()` (GNZ/Wellington marks, always included when the config has a threshold) — computed with `_is_gnz_qualified`/`_is_wellington_qualified` for both kinds of athlete. It always renders (when non-empty) as "Not on the Ranking" — sorted alphabetically — with Name/GNZ ID/Club/Intent + 3 score tooltips + a trailing column with a secondary-themed info SVG whose tooltip renders the checklist (green `bg-success` circle with a check SVG for met / red `bg-error` circle with a cross SVG for missing + label + `(x of y)`, left-aligned, `sr-only` "Met:"/"Missing:" prefix for screen readers). The tooltip is checklist-only (no `why` headline; the `why` field is still returned by the API but unused by the UI). The score columns are **slot-aligned**: the 4 selector functions return a length-3 list with `None` for unfilled slots, and the can't-form-selection rows are built from those partial slots (not raw top-3 scores), so a regional event shows under "Regional Best", a club event under the named slot, an away under "Away Best", and empty slots render as dashes. The Wellington page has no filter toggles — the main table always shows only qualified + intended athletes, and `not_ranked` captures everyone else (the API endpoint's `gnz_qualifier`/`wellington_qualifier`/`intent_filter` params still exist and default to `true`). Ticking an athlete's Intent optimistically removes the row (`notRanked.filter`), then `loadRankings()` reconciles — selection-capable athletes move to `rankings`; in-progress athletes return (they still can't form a selection).
- **Gymnast page no-results** — `_compute_wide_all` adds a top-level `name` (latest `gymnast_name` across all years for that `gnz_id`) when the year query returns no rows. Frontend shows the name in the heading + a polite "no results for {year}" info alert; "Gymnast not found" only when no name exists at all.
- **Gymnast page Personal Bests card** — `SeasonBest.svelte` (rendered via `WideResultsTable`'s `afterHeader` snippet, shown only when a specific year is selected, not "All"). Client-side only: derives per-apparatus prefixes from the tab `columns` (regex `^([a-z]{2,3})(?:-\d+)?-total$`, preserving WAG/MAG column order), then for each apparatus takes the max `*-total` over the year's rows (skipping `null`/`"DNS"`), tracking the source row's `event_name` + `round-type` for a `dropdown-bottom dropdown-end` DaisyUI tooltip. Renders each best as a secondary-coloured box with the D-score of that best underneath. Also shows the gymnast's **best achieved AA** (`bestAA` — max `aa-score` across rows, excluding `round-type` containing "apparatus final" or "day 2" so a finals-day sum never masquerades as an AA; D-sum of the contributing row shown underneath) and the **Best Possible AA** (`aaText` = sum of all per-apparatus bests, primary-coloured box; `aaD` = sum of their D-scores). "Best Possible" is *not* an actually-achieved score — the AA tooltip explains this. A `divider divider-horizontal` separates the apparatus bits from the Best Possible AA. Card styled like the homepage cards (`card bg-base-200 border border-base-300`) and centered in the header's `grid-cols-[1fr_auto_1fr]` channel. **The gymnast page also defaults to the current year** (falls back to the most recent year with data) via `applyDefaultYear()` in `[gnz_id]/+page.svelte` — sets the global `selectedYear` store once when it's still `null`, so the layout year tabs stay consistent; a user picking "All" is never overridden.
- **Gymnast page meta under name** — when a year is selected, `nameBadge` (region `RegionBadge` beside the name) and `nameMeta` (GNZ ID / club link / each step on its own line, stacked) snippets render below/inline with the name. Values derive from the loaded wide rows: `gnzId` from `$page.params.gnz_id`, `club`/`region` via `mostCommon()` across rows (a gymnast can switch clubs mid-season), `steps` as the unique `step` values (a gymnast may compete two steps in one year).
- **`WideResultsTable` optional snippets/callback** — `onData?: (tabs) => void` fires after every successful load (used to mirror the loaded rows outside the table); `afterHeader` renders on the right of the name row (the Personal Bests card); `nameBadge`/`nameMeta` render beside/below the `<h1>`. All optional — other pages are unaffected. The pinned left-hand column is configurable via a `stickyCol` prop (default `"name"`; the gymnast page passes `stickyCol="event_name"` since `event_name` is already the first column and the gymnast's name is the same in every row).
- **Mobile responsiveness** — the app is mobile-tested at ~375px. Navigation: year filter is a native `<select>` below `md` (desktop keeps the tab radio group, which also lives in the drawer); the logo text/Beta badge hide below `sm`. Tables: low-value columns are hidden below `md` (`gnz-id`, sometimes `club`/`region`) via `hidden md:table-cell`; the rank+name pair (or a single `stickyCol`) is pinned with `sticky left-*` + zebra-aware backgrounds; `event_name` truncates tighter on mobile (`max-w-40 md:max-w-56`). Region cells swap to a compact checker square (`lib/RegionCheck.svelte`, tooltip + `aria-label`) below `md`, full `RegionBadge` above. `WideResultsTable`'s column-header filter and `FilterDropdown` (rankings Club/Region) open as a **full-width bottom sheet** on screens <768px (fixed-position panel, backdrop, bigger tap targets, sticky **Close (n selected)** button that only appears once something is selected); the sheet also closes via backdrop/Escape/outside-click. `FilterDropdown`'s menu is mounted only while `open` (`{#if open}`) so DaisyUI's `:focus-within` can't keep it visible after closing. Specialist ghost badges use `border-dashed`; `SeasonBest` card centers/wraps and separates "Best Possible AA" below `md`.
- **Step dropdown ordering** — backend `ORDER BY level_category` is alphabetical (`STEP 1, STEP 10, STEP 2, ...`). Frontend re-sorts with `sortSteps()` (STEP 1–10 numerically, then Youth/Junior/Senior) in `rankings/+page.svelte` and `WideResultsTable.svelte`. `wellington-ranking/+page.svelte` has its own `sortSteps()` (STEP 1–10, Level 1–10, Youth/Youth International, Junior/Junior International, Senior/Senior International, Senior Open, U18, U16).
- **SvelteKit CSRF disabled** — `csrf: { checkOrigin: false }` in `svelte.config.js`; all mutations go through the `/api` proxy to FastAPI which handles its own JWT auth. Still set `ORIGIN` env var in production for adapter-node URL generation.
- **`fetchToken` must NOT be `$state`** — the stale-response guard counter in `wellington-ranking/+page.svelte` is a plain `let`. If made `$state`, incrementing it inside `loadRankings()` re-triggers the `$effect` → infinite API request loop.
- **Inline edit** — `PATCH /api/admin/scores/gymnast` updates name/GNZ ID/club on all `long_scores` rows matching `(event_id, gymnast_name)`. Cache invalidation clears `wide-all`, `stats`, `gymnasts`, `clubs` prefixes. Frontend: Edit mode toggle makes name/GNZ ID/club cells editable inputs with per-row Save button. Known issue: table doesn't always feel reactive after save.
- **/clubs NZ map** — `NZRegionMap.svelte` renders the `@svg-maps/new-zealand` package (17 Stats NZ region paths, CC-BY-4.0) in a `viewBox="0 0 525 989"` (Chatham Islands cropped out). 15 gym regions map to stats paths: `gis`+`hkb` → Hawkes Bay / Poverty Bay, `tas`+`nsn`+`mbh` → Top of the South; Auckland is split into Harbour/Auckland/Counties-Manukau and Canterbury into Canterbury/Aorangi via SVG `<clipPath>` rects. No regional colouring — regions use theme colours (`--color-base-300` fill, `--color-primary` on hover/active). Layout: map left (sticky), selected region's box right; clicking a map region shows only that region's box (toggle to clear). **Mobile (`<lg`)** hides the map and renders a collapsible accordion of the region cards (`RegionCard` snippet, `mobileOpen` state, tap header to expand, one open at a time); regions listed north→south via `REGION_ORDER`.
- **NZ map checker animation** — each region's checker `<pattern>` is defined *inside* its region `<g>` (not `<defs>`) so CSS can reach it via `.nz-region:hover pattern` / `.nz-active pattern` (no parent selector otherwise). Animation is `translate(var(--scroll-x), var(--scroll-y))` where each region sets its own `--scroll-x/y/duration` vars (deterministic LCG `pick()` in the component); loop endpoints are always multiples of the 20px tile so the wrap is seamless. Wrapped in `prefers-reduced-motion: no-preference`. Fallback if a browser ignores CSS `transform` on `<pattern>`: drive `patternTransform` via `requestAnimationFrame`.
- **Svelte 5 snippet gotcha** — `{#snippet}` components must be invoked with `{@render RegionCard({...})}`, NOT `<RegionCard />` (throws `invalid_snippet_arguments`). Also avoid `class:ring-2` on snippet elements — Svelte parses the hyphen as an expression (`ring` undefined); use a plain `class` string instead.
- **Don't key `{#each}` on `gnz_id`** — GNZ IDs are not unique in the data (duplicate/blank IDs exist, e.g. twins sharing `822491`). A keyed each `(r.gnz_id)` throws `each_key_duplicate`, which aborts the render and can leave a page stuck on a spinner after data loads. The national/apparatus ranking tables use unkeyed `{#each}` (or an index key) for this reason.
- **SQLite read concurrency** — a 5000-row join/materializing SELECT degrades ~7–17x under concurrent connections (measured), which can cascade into `QueuePool` exhaustion (30s `pool.wait()` timeouts → hung requests → endless spinners). Mitigations in place: `PRAGMA busy_timeout=30000`, a passive `wal_checkpoint(PASSIVE)` at startup (keeps the WAL from growing large, which also stalls readers), the activity-log writer batched so per-request writes don't bloat the WAL, and `cached()` made **single-flight** so concurrent misses compute once.
- **Client-side exports** — all result/ranking pages use `ExportMenu.svelte` + `export.ts` for CSV/XLSX/PDF. SheetJS (`xlsx`) and jsPDF are lazy-loaded via dynamic `import()` so they don't bloat the entry bundle. XLSX honors a `colFormat` map (hidden columns + `wch` widths) computed in `WideResultsTable.svelte` — it hides `region`, per-pass vault columns (`vt-1-*`, `vt-2-*`), and all `*-bonus` columns, and widens name/club (30) and event_name (45). PDF exports render a condensed table (one column per apparatus showing `D / Total`, matching the frontend) with a title header and `Page X of Y` footer. CSV/XLSX keep every raw column (minus hidden ones); PDF uses `pdfColumns`. `slugifyFilename()` (in export.ts) kebab-cases download names.
- **SheetJS advisories** — `npm audit` flags prototype pollution/ReDoS in `xlsx` 0.18.5, but only for *parsing* untrusted files; the app only *writes* XLSX, so risk is negligible.
- **Activity tracking** — records page views + API requests across the whole site for admin review. Two capture paths: (1) FastAPI `log_activity` middleware (outermost, after `add_cache_control`) measures every `/api/*` request — authenticated requests also get a detail `activity_logs` row (username, role, method, path, query, status, duration), and **every** request is counted into the `traffic_daily` aggregate table (`kind` page/api, per local date + hour + normalized `path_group` + `anonymous` flag; counts, error counts, total duration) via `enqueue_traffic()`. (2) `POST /api/track/page` beacon from `+layout.svelte` (fires for all visitors when auth is configured; deduped with a plain `let lastTracked` keyed `username|path+search` for users, `anon|path` for guests) records page views for client-side navigations. The middleware skips `/api/track/page` (handled by the endpoint), `/api/admin/activity*` (so admin viewing/clearing doesn't self-log), `/api/health` (healthcheck polling noise) and **anonymous bot user-agents** (`app/traffic.py::is_bot` — UA only inspected, never stored). Anonymous requests are only aggregated (no detail row), so the audit table stays small. Both write through the **non-blocking batched background writer** (`app/activity_log.py`: bounded `queue.Queue` + a daemon thread draining up to 100 rows per transaction — batched `activity_logs` inserts plus `traffic_daily` `INSERT ... ON CONFLICT DO UPDATE` upserts keyed on `(date, hour, kind, path_group, anonymous)`; rows written synchronously when the writer isn't started, i.e. test contexts). The middleware never awaits a DB write, so a request's response can't stall on logging (a concurrent SQLite write/checkpoint used to hold responses for seconds under load). Path groups are normalized by `app/traffic.py::normalize_path` (query stripped, pure-numeric segments → `[id]`, 10-char hex slugs → `[slug]`). Date/hour buckets use server-local time — production sets `TZ=Pacific/Auckland` in both compose files. **No IP/user-agent stored.** Admin UI at `/admin?tab=activity`: `GET /api/admin/activity?user&type&limit&offset&days` returns the authenticated detail rows `{items, total}`; `GET /api/admin/activity/summary?days=7|30|90|0` (0 = all time) returns `totals` (page/API split by anonymous vs logged-in, errors, avg response ms, active days), `daily_series`, `auth_daily_series` (computed from `activity_logs` so logged-in history predates the dashboard), `hourly_series` (0–23), `top_pages`, `top_api`, `top_users`; `DELETE /api/admin/activity?user` clears detail rows. Anonymous traffic only accumulates from when the dashboard is deployed. Admin views/clears call `flush()` first so queued rows appear. Writes never break or delay a request. Charts use Chart.js lazy-loaded via `lib/charts/ChartJs.svelte` (canvas gets `role="img"` + `aria-label`; data also exposed as fallback text). Admin UI is the single `/admin` page — Activity lives in the right-hand column of the two-column dashboard (`/admin#activity`). Route guard covers `/admin` prefix, so `/admin/activity` needs no extra `requiresAuth` entry.

## Accessibility Conventions (STEP 24)

- All 6 public pages score **100/100** on Lighthouse accessibility (verified after a 3-tier pass; reports tracked in `a11y-reports/`, rerun with `./a11y-reports/run.sh before|after [pages...]` against the dev server — needs `CHROME_PATH` pointing at a Chrome/Chromium binary).
- **Dialogs** — use the shared `frontend/src/lib/Dialog.svelte` (`role="dialog"`, `aria-modal`, labelled `h3`, initial-focus move, Tab/Shift+Tab focus trap, Escape close, focus restore to opener, backdrop click). All 5 modals (upload club mapping, add/reset/delete user, edit/delete event) migrated to it.
- **Tabs** — year + WAG/MAG selectors are native `radio` inputs styled as `.tab` (NO `role="tab"` — native `checked` is announced and arrow-key navigation works). Two-button discipline toggles use `aria-pressed` buttons. Avoid the `role="tab"` on `<input>` anti-pattern (flagged by axe).
- **Tooltips** — `ScoreTooltip`/`AATooltip` and rankings/wellington score tooltips are DaisyUI `dropdown-hover` (opens on hover AND focus-within) with a `<button>` trigger, `aria-label` containing the visible score text (WCAG 2.5.3), `aria-describedby` → `role="tooltip"` panel. Never use hover-only CSS tooltips for information that isn't in the DOM elsewhere.
- **Focus** — SVG map regions keep a `focus-visible` outline + stroke; region selection moves focus to the desktop card and announces via an `aria-live` region. Drawer closes on Escape and restores focus to the hamburger button.
- **Buttons** — icon-only buttons need `aria-label` (not `title` alone). Table sort/filter buttons must clear the 24px min target size (WCAG 2.5.8) — the header filter buttons use `h-6 min-w-6`, sort labels `min-h-6`.
- **Live regions** — toasts (admin merge/cache, edit save, upload status) use `role="status"`; error cards `role="alert"`; "Showing X–Y of Z" uses `role="status"`.
- **Contrast** — `textColor()`/`gradientTextColor()` in `regions.ts` pick `#000` vs `#fff` via WCAG relative-luminance contrast (not the old >160 luminance heuristic; pure black matters for mid greens like `#008751`). Avoid `text-base-content/40–50` for real text (bump to `/60–70`).
- **Skip link + landmarks** — `+layout.svelte` has a skip-to-content link, `<main id="main">`, navbar/drawer as `<nav>`, and `aria-current="page"` on active nav links.
