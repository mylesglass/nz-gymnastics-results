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
│   │   ├── models.py        # SQLAlchemy models (is_national, etc.)
│   │   ├── database.py      # SQLite engine + session + migration
│   │   ├── schemas.py       # Pydantic models (RankingRow, etc.)
│   │   ├── auth.py          # JWT auth (bcrypt, HS256, role-based, seed_admin_user)
│   │   ├── cache.py         # GranularTTLCache with per-key TTL + per-event prefix invalidation, admin refresh-cache endpoint
│   │   ├── parser.py        # Scoreholder JSON parser (~630 lines)
│   │   ├── decoder.py       # Node-tree score field decoder
│   │   ├── resolver.py      # ID chain resolver
│   │   ├── transformer.py   # Pandas long→wide pivot + CSV/XLSX export + region enrichment
│   │   ├── reconcile.py     # Athlete ID reconciliation
│   │   ├── reconcile_clubs.py # Club name normalization script
│   │   ├── scoreholder.py   # Fetch Scoreholder event JSON exports from public URLs
│   │   ├── validate_json.py # Batch validation CLI
│   │   └── wellington_ranking.py # Wellington regional ranking computation
│   ├── tests/               # pytest suite (130 pass, 87 skip)
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
│   │   │   └── export.ts                # Export builders (CSV, XLSX, PDF) + slugifyFilename + ColFormat/PdfColumn types
│   │   ├── routes/
│   │   │   ├── +layout.svelte          # Nav, footer, theme toggle, year tabs via goto()
│   │   │   ├── +page.svelte            # Landing page (info items above nav cards w/ stat badges, What's new from patch_notes.json)
│   │   │   ├── upload/+page.svelte     # JSON upload (file drag-drop + import-from-URL)
│   │   │   ├── login/+page.svelte      # Username+password login
│   │   │   ├── admin/+page.svelte      # Admin dashboard
│   │   │   ├── admin/users/+page.svelte # User management
│   │   │   ├── rankings/+page.svelte   # National Rankings (member+)
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
│   │   ├── app.css              # @import "tailwindcss"; @plugin "daisyui";
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
- **Stats:** 156 pass, 87 skip (skipped tests rely on data-collection JSON files not always present)
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

## Key Architectural Decisions & Gotchas

- **SQLite** — single file, no PostgreSQL needed
- **Scoreholder JSON parsing** — flat reference-based model with 22 top-level arrays. IDs resolved via resolver chains, scores decoded via node-tree output maps.
- **Vault aggregation** — level-dependent: STEP 6/7 always average; high-level AA best-mark, high-level Apps average. Logic in `transformer._use_vault_average()`.
- **National rankings — one mark per competition** — `/api/rankings` groups rows by `(gymnast, event, round_type)`, computes a competition score per group (max AA else apparatus sum with vault rules), then collapses to the **max score per `(gymnast, event)`** so a two-day meet (AA + Apparatus Finals) contributes only one mark; the total is always made of distinct competitions. **STEP 5/6 rank on the AVERAGE of their top 3 marks** (`_RANKING_MARKS`); all other steps use the top 2 summed (`total`). Sort/rank/ties use the average for STEP 5/6 and the total otherwise. All per-event marks (`all_events`) are kept for the qualifier check, not just the selected top marks. STEP 1–4 return a display-only `reached_mark` flag — the rankings table's rightmost **Q** column (✓ vs —) — set when a gymnast reached 52.000 on 2 distinct competitions that season (`_MARK_INDICATOR`). The endpoint accepts an optional `division` query param (`OVER`/`UNDER`) that filters rows in SQL, so qualifier marks, the Q column and quota mode all operate on division-only data. Frontend: the quota/qualifier toggles are hidden for STEP 1–4 and MAG Level 1–3 (`showRankingToggles`), the Total column is hidden (bolded Average shown), a "Can't find someone?" alert appears under the table when `qualifier` is on, a WAG-only Division `<select>` (`divisionFilter`, shown next to the step selector) triggers a server reload and is reset on step/discipline change, and the Club/Region headers have funnel-icon dropdowns that filter the already-loaded rows client-side (`filteredRankings`, exports follow the filter).
- **GNZ qualifying marks (national `qualifier` filter)** — `_QUALIFIER_CONFIG` in `main.py`: STEP 5/6 = 2 marks ≥ 50.000 with one from an event whose host club's region ≠ the athlete's home region; STEP 7–10 = 2 marks ≥ 43.000; Youth/Junior/Senior International = 1 mark ≥ 42.5/43.0/45.0; MAG Level 7–9, U18, Senior Open = 1 mark ≥ 63.0; everything else always qualifies. Marks are distinct competitions by construction. A blank/unknown host club never counts as "outside" (conservative).
- **Event `host_club`** — nullable column on `events` (ALTER TABLE in `init_db()`, which also drops the superseded `host_province` column), set at upload from the `host_club` form field / `ImportUrlRequest` field, otherwise a best-effort name-based guess via `transformer._guess_host_club()` (canonical club names + aliases as substrings, longest match wins). National events default to `"Gymnastics NZ"`. Editable via `PATCH /api/events/{id}` (admin events edit dialog, searchable datalist fed by `GET /api/clubs/known`). The national STEP 5/6 away rule derives the event's province from the host club via `_find_region(host_club)`. Existing events can be filled without re-upload using `python -m app.backfill_host_club` (dry-run by default, `--apply` to write; review wrong guesses on the events page). Reference worksheet: `data-collection/event_names.txt` (`YYYY<TAB>name<TAB>host`).
- **Event re-upload dedup** — `_ingest_event` replaces **all** existing events matching `(name, start_date, discipline)` (previously only the `.first()` match by name alone, which left stale copies and could delete a same-named event from a different year — e.g. re-uploading 2025 `MAG Wellington Champs` deleted the 2023 one). Re-importing a competition now never accumulates duplicates. Already-duplicated rows (same export imported repeatedly, e.g. 4× identical `Auckland Champs` 2025-03-01) are cleaned with `python -m app.dedupe_events` (dry-run by default, `--apply` to write; keeps the copy with the most `long_scores`, tie-break lowest id; ORM cascades the deleted copies' scores).
- **Bonus propagation** — apparatus-level modifier stored on one pass, propagated to all passes in same `(entityId, unitEventId)` group at parse time.
- **Floating point** — `_fmt3` in transformer.py: rounds to 6 decimals then floors to 3 to handle IEEE 754 noise.
- **WAG/MAG split** — tab assignment uses `discipline` field from data, not apparatus heuristic.
- **Division extraction** — heuristic text matching (UNDER/OVER/A/B) from competition node names.
- **Numpy types in JSON** — pandas/numpy produce `numpy.int64`/`numpy.float64` that FastAPI's `jsonable_encoder` can't serialize; must convert in transformer.py.
- **Auth** — JWT-based (bcrypt, HS256, 7-day expiry), role-based (admin/member). Admin seeded from env vars (`ADMIN_USERNAME`, `ADMIN_PASSWORD`, `ADMIN_ROLE`). JWT_SECRET auto-generated and persisted to `data/jwt_secret.txt`. When `ADMIN_PASSWORD` is unset, all endpoints are public.
- **Page permissions** — per-user ranking-page access. `User.permissions` is a comma-separated string of keys (`rankings.national`, `rankings.wellington`), migrated in `init_db()` (ALTER TABLE ADD COLUMN). Backend enforces via `require_permission(*keys)` in `auth.py` (DB lookup; admins bypass; dev fallback admin bypasses). New members default to `rankings.national` only; admins are always full (login/me/status/users report effective permissions via `effective_permissions`). Ranking endpoints: `/api/rankings`→national, `/api/rankings/wellington` + `GET /api/wellington/intents`→wellington, `/api/rankings/steps`→either. `PATCH /api/auth/users/{id}/permissions` (admin) updates them; `GET /api/auth/me` returns DB-fresh permissions. Frontend: `lib/auth.ts` stores permissions in localStorage (`nzgr_permissions`), `hasPermission()` (admins pass), `+layout.svelte` refreshes via `me()` on mount and gates nav links; signed-out users and members without the permission are redirected away from ranking pages by the route guard.
- **Client-side route guard** — auth lives in localStorage (no SSR cookies), so protected routes are guarded in `+layout.svelte`. `requiresAuth` (currently `/admin` prefix plus `/rankings` and `/wellington-ranking`) waits for `checkAuthStatus()` to resolve (`authResolved`/`authActive`), renders nothing until then (no flash), then `goto("/")` via `$effect` when the user has no access. Signed-out users and logged-in members lacking the required role/permission are both redirected: `/admin` requires `admin`, `/rankings` requires `rankings.national`, `/wellington-ranking` requires `rankings.wellington` (`routeAllowed`). Auth-disabled servers stay public. Add new prefixes to `requiresAuth` for other logged-in-only pages.
- **Import from URL** — `POST /api/import-url` (admin) takes `{url, allow_unknown}` and fetches the Scoreholder public export via `app/scoreholder.py`. The API form is `https://scoreholder.com/api/events/{id}?context=public` (NOT the old `?scope=PUBLIC`, which now 400s). It 307-redirects to a CloudFront cache URL. The response is always Brotli-compressed (`Content-Encoding: br`) regardless of `Accept-Encoding`, so httpx needs the `brotli` package installed. No Cloudflare challenge for plain browser-UA requests. Event ID extracted via `r"/events/([0-9a-f]{24})"`; fetch errors → 502; shares `_ingest_event()` with `POST /api/upload`.
- **DB schema** — `events` table + `long_scores` table (one row per apparatus pass per gymnast) + `users` table (username, hashed_password, role).
- **`new URL()` breaks** on relative paths in dev mode — use string concatenation in api.ts.
- **Two JSON formats exist** — only the new format (`eventOrganizations`, `performanceRules`, etc.) is supported.
- **Name cleaning** — `_NAME_LEVEL_SUFFIX` regex strips `(L#)`, `(STEP 10)`, `(YI)` from gymnast names at parse time.
- **Region enrichment** — club→region lookup at pivot time via `clubs_and_regions.json`; changes require re-upload.
- **Unknown-club check** — `find_unknown_clubs()` in parser.py reads Scoreholder's real field names (`_id` on `eventOrganizations`, `_id`+`organizationId` on `eventParticipants`). A past bug used `orgId`/`participantId` which never match real files, silently letting variant club names through — fixed; uploads now 409 with a mapping dialog for genuinely unknown clubs. Variants that map to a canonical should be added as aliases in `clubs_and_regions.json`, then `python -m app.reconcile_clubs` normalizes existing rows. Regional-team rows (e.g. `Counties - Manukau`) are stored as club names and resolve via the lookup to themselves; `Gymsport Manukau` retargets to `Counties - Manukau`.
- **Club-mapping suggestions** — the 409 unknown-club response includes `suggestions` from `suggest_club_mapping()` in parser.py: exact normalized match (diacritic/whitespace-folded) against the alias table wins, otherwise a fuzzy `difflib.SequenceMatcher` ratio ≥ 0.9. The upload dialog defaults each club to "Keep original name" (`KEEP_ORIGINAL` sentinel in `upload/+page.svelte`) and pre-selects a confident suggestion when present. `saveAndRetry()` persists only mapped clubs via `save_aliases` then re-uploads with `allow_unknown` if any were kept.
- **DaisyUI z-index** — `.dropdown-content` sets `z-index: 1` overriding Tailwind classes; use inline `style="z-index: 50"`.
- **`$effect` reactivity** — tracks all dependencies read inside it; avoid reading state the effect itself modifies.
- **Production API proxy** — `hooks.server.ts` forwards `/api/*` from the frontend Node server to the backend container. `API_BASE` is always `""` (same-origin).
- **Body size limit** — SvelteKit adapter-node defaults to 512KB. JSON uploads can be ~3.5MB. Set `BODY_SIZE_LIMIT=52428800` (bytes) in the frontend service env vars.
- **Cache refresh** — `POST /api/admin/refresh-cache` clears the backend in-memory cache. Admin dashboard has a "Refresh Cache" button to ensure all pages show the latest data after uploads/edits.
- **Browser cache** — ranking endpoints (`/api/rankings/*`) are excluded from the `Cache-Control: public, max-age=300` middleware so intent/qualifier toggles reflect immediately; other endpoints keep browser caching.
- **Apparatus Specialists** — Wellington ranking fallback path. Config-driven via `specialist_steps` (steps that check specialist qualification), `apparatus_qualifying_count` (how many competitions on the SAME apparatus must clear the mark — the count unit is distinct competitions, not distinct apparatus), and the threshold: a single float `apparatus_qualifying_score` (STEP 8–10 `wag_step_7_10`: 11.0 × 2 distinct competitions; MAG `mag_level_7_plus`: 11.5 × 1) or a per-apparatus dict `apparatus_qualifying_scores` (WAG `wag_junior_international` VT 12.2/UB 10.4/BB 10.5/FX 11.4 × 1; `wag_senior_international` VT 12.5/UB 11.3/BB 11.2/FX 11.4 × 1). Intent-submitted athletes NOT in the AA table are returned as `apparatus_specialists`; the backend tracks per-(gymnast, apparatus, event) best scores (`apparatus_events`, round-type-merged, vault per `_use_vault_average` rules). Each row is `qualified: True` (≥1 apparatus reached the mark in ≥ `apparatus_qualifying_count` competitions) or `qualified: False` (only 1..count-1 reach). The `apparatus` list mixes entries: a row's qualifying apparatus → solid colour-coded badges, plus any partial apparatus (reached once, count 1..count-1) → greyed-out `badge-outline` ghost badges, solid entries first. Badge entries carry `app`, `best`, `event`, `count`, and `competitions[]` (all qualifying comps, used in the tooltip); rows sort qualified-first then by count/name. The response exposes `apparatus_qualifying_score`/`apparatus_qualifying_count` for generic tooltip text; the frontend picks badge style per entry (`a.count >= apparatus_qualifying_count` → solid). Frontend renders them below the main table with badges (VT primary / UB secondary / BB accent / FX info) + DaisyUI tooltips listing the competitions (ghost badge tooltip: "Reached 11.000 once at X — needs N different competitions").
- **International Wellington configs** — WAG `wag_youth_international` / `wag_junior_international` / `wag_senior_international` (steps `Youth/Junior/Senior International`) use `selection: "international"` + `marks_required: 1`: ranked by the single highest AA mark (selector `_select_international` returns `[best, None, None]`), Gymnastics NZ qualifying 42.5/43.0/45.0 on one occasion, no Wellington qualifier, no competition-mix checks (`_selection_checks` returns `[]` for `marks_required == 1`). `marks_required` (default 3) drives the can't-form-selection check (`None in selected[:marks_required]`) and the `why` message; ranking `scores`/`competitions`/`categories` arrays only contain the filled slots (length 1 for International). The frontend step dropdown no longer filters out "international"; `INTERNATIONAL_CONFIGS` hides the Average column and "Regional events" for these configs. MAG International is just the existing `mag_level_7_plus` steps (U18, Senior Open) at 63.0 AA + 11.5 specialists.
- **Wellington intent tracking** — `WellingtonIntent` model (`wellington_intents` table, unique `(gnz_id, year)`), `GET /api/wellington/intents`, `POST /api/wellington/intent` (admin). Admin checkbox column + Intent filter toggle on the ranking page; toggling calls `invalidate()`.
- **Wellington not_ranked table** — `compute_wellington_rankings` returns a single `not_ranked` list of every Wellington athlete who isn't on the ranking, with a `why` (headline reason) and `checks` (✓/✗ requirements checklist). Two kinds of athlete are merged here: those who can't yet form the required 3-mark selection (`selector()` returned `None`; `why` from the count/mix check) and those who CAN form it but were dropped by the active toggles (`why` from `_dropped_reasons()`: "Hasn't submitted intent yet" when the intent filter is on + the qualifier `warnings`). Row shape: `name, gnz_id, club, region, scores[3] (None-padded), competition_names[3], categories[3], apparatus, competitions, regional_count, club_count, away_count, why, checks[list of {label, met, detail}], intent_submitted`. `checks` comes from `_selection_checks()` (per-config competition-mix items with "x of y" `detail`) + an `Intent submitted` item + `_qualifier_checks()` (GNZ/Wellington marks, always included when the config has a threshold) — computed with `_is_gnz_qualified`/`_is_wellington_qualified` for both kinds of athlete. It always renders (when non-empty) as "Not on the Ranking" — sorted alphabetically — with Name/GNZ ID/Club/Intent + 3 score tooltips + a trailing column with a secondary-themed info SVG whose tooltip renders the checklist (green `bg-success` circle with a check SVG for met / red `bg-error` circle with a cross SVG for missing + label + `(x of y)`, left-aligned, `sr-only` "Met:"/"Missing:" prefix for screen readers). The tooltip is checklist-only (no `why` headline; the `why` field is still returned by the API but unused by the UI). The score columns are **slot-aligned**: the 4 selector functions return a length-3 list with `None` for unfilled slots, and the can't-form-selection rows are built from those partial slots (not raw top-3 scores), so a regional event shows under "Regional Best", a club event under the named slot, an away under "Away Best", and empty slots render as dashes. The Wellington page has no filter toggles — the main table always shows only qualified + intended athletes, and `not_ranked` captures everyone else (the API endpoint's `gnz_qualifier`/`wellington_qualifier`/`intent_filter` params still exist and default to `true`). Ticking an athlete's Intent optimistically removes the row (`notRanked.filter`), then `loadRankings()` reconciles — selection-capable athletes move to `rankings`; in-progress athletes return (they still can't form a selection).
- **Gymnast page no-results** — `_compute_wide_all` adds a top-level `name` (latest `gymnast_name` across all years for that `gnz_id`) when the year query returns no rows. Frontend shows the name in the heading + a polite "no results for {year}" info alert; "Gymnast not found" only when no name exists at all.
- **Gymnast page Personal Bests card** — `SeasonBest.svelte` (rendered via `WideResultsTable`'s `afterHeader` snippet, shown only when a specific year is selected, not "All"). Client-side only: derives per-apparatus prefixes from the tab `columns` (regex `^([a-z]{2,3})(?:-\d+)?-total$`, preserving WAG/MAG column order), then for each apparatus takes the max `*-total` over the year's rows (skipping `null`/`"DNS"`), tracking the source row's `event_name` + `round-type` for a `dropdown-bottom dropdown-end` DaisyUI tooltip. Renders each best as a secondary-coloured box with the D-score of that best underneath. Also shows the gymnast's **best achieved AA** (`bestAA` — max `aa-score` across rows, excluding `round-type` containing "apparatus final" or "day 2" so a finals-day sum never masquerades as an AA; D-sum of the contributing row shown underneath) and the **Best Possible AA** (`aaText` = sum of all per-apparatus bests, primary-coloured box; `aaD` = sum of their D-scores). "Best Possible" is *not* an actually-achieved score — the AA tooltip explains this. A `divider divider-horizontal` separates the apparatus bits from the Best Possible AA. Card styled like the homepage cards (`card bg-base-200 border border-base-300`) and centered in the header's `grid-cols-[1fr_auto_1fr]` channel. **The gymnast page also defaults to the current year** (falls back to the most recent year with data) via `applyDefaultYear()` in `[gnz_id]/+page.svelte` — sets the global `selectedYear` store once when it's still `null`, so the layout year tabs stay consistent; a user picking "All" is never overridden.
- **Gymnast page meta under name** — when a year is selected, `nameBadge` (region `RegionBadge` beside the name) and `nameMeta` (GNZ ID / club link / each step on its own line, stacked) snippets render below/inline with the name. Values derive from the loaded wide rows: `gnzId` from `$page.params.gnz_id`, `club`/`region` via `mostCommon()` across rows (a gymnast can switch clubs mid-season), `steps` as the unique `step` values (a gymnast may compete two steps in one year).
- **`WideResultsTable` optional snippets/callback** — `onData?: (tabs) => void` fires after every successful load (used to mirror the loaded rows outside the table); `afterHeader` renders on the right of the name row (the Personal Bests card); `nameBadge`/`nameMeta` render beside/below the `<h1>`. All optional — other pages are unaffected.
- **Step dropdown ordering** — backend `ORDER BY level_category` is alphabetical (`STEP 1, STEP 10, STEP 2, ...`). Frontend re-sorts with `sortSteps()` (STEP 1–10 numerically, then Youth/Junior/Senior) in `rankings/+page.svelte` and `WideResultsTable.svelte`. `wellington-ranking/+page.svelte` has its own `sortSteps()` (STEP 1–10, Level 1–10, Youth/Youth International, Junior/Junior International, Senior/Senior International, Senior Open, U18, U16).
- **SvelteKit CSRF disabled** — `csrf: { checkOrigin: false }` in `svelte.config.js`; all mutations go through the `/api` proxy to FastAPI which handles its own JWT auth. Still set `ORIGIN` env var in production for adapter-node URL generation.
- **`fetchToken` must NOT be `$state`** — the stale-response guard counter in `wellington-ranking/+page.svelte` is a plain `let`. If made `$state`, incrementing it inside `loadRankings()` re-triggers the `$effect` → infinite API request loop.
- **Inline edit** — `PATCH /api/admin/scores/gymnast` updates name/GNZ ID/club on all `long_scores` rows matching `(event_id, gymnast_name)`. Cache invalidation clears `wide-all`, `stats`, `gymnasts`, `clubs` prefixes. Frontend: Edit mode toggle makes name/GNZ ID/club cells editable inputs with per-row Save button. Known issue: table doesn't always feel reactive after save.
- **/clubs NZ map** — `NZRegionMap.svelte` renders the `@svg-maps/new-zealand` package (17 Stats NZ region paths, CC-BY-4.0) in a `viewBox="0 0 525 989"` (Chatham Islands cropped out). 15 gym regions map to stats paths: `gis`+`hkb` → Hawkes Bay / Poverty Bay, `tas`+`nsn`+`mbh` → Top of the South; Auckland is split into Harbour/Auckland/Counties-Manukau and Canterbury into Canterbury/Aorangi via SVG `<clipPath>` rects. No regional colouring — regions use theme colours (`--color-base-300` fill, `--color-primary` on hover/active). Layout: map left (sticky), selected region's box right; clicking a map region shows only that region's box (toggle to clear). **Mobile (`<lg`)** hides the map and renders a collapsible accordion of the region cards (`RegionCard` snippet, `mobileOpen` state, tap header to expand, one open at a time); regions listed north→south via `REGION_ORDER`.
- **NZ map checker animation** — each region's checker `<pattern>` is defined *inside* its region `<g>` (not `<defs>`) so CSS can reach it via `.nz-region:hover pattern` / `.nz-active pattern` (no parent selector otherwise). Animation is `translate(var(--scroll-x), var(--scroll-y))` where each region sets its own `--scroll-x/y/duration` vars (deterministic LCG `pick()` in the component); loop endpoints are always multiples of the 20px tile so the wrap is seamless. Wrapped in `prefers-reduced-motion: no-preference`. Fallback if a browser ignores CSS `transform` on `<pattern>`: drive `patternTransform` via `requestAnimationFrame`.
- **Svelte 5 snippet gotcha** — `{#snippet}` components must be invoked with `{@render RegionCard({...})}`, NOT `<RegionCard />` (throws `invalid_snippet_arguments`). Also avoid `class:ring-2` on snippet elements — Svelte parses the hyphen as an expression (`ring` undefined); use a plain `class` string instead.
- **Client-side exports** — all result/ranking pages use `ExportMenu.svelte` + `export.ts` for CSV/XLSX/PDF. SheetJS (`xlsx`) and jsPDF are lazy-loaded via dynamic `import()` so they don't bloat the entry bundle. XLSX honors a `colFormat` map (hidden columns + `wch` widths) computed in `WideResultsTable.svelte` — it hides `region`, per-pass vault columns (`vt-1-*`, `vt-2-*`), and all `*-bonus` columns, and widens name/club (30) and event_name (45). PDF exports render a condensed table (one column per apparatus showing `D / Total`, matching the frontend) with a title header and `Page X of Y` footer. CSV/XLSX keep every raw column (minus hidden ones); PDF uses `pdfColumns`. `slugifyFilename()` (in export.ts) kebab-cases download names.
- **SheetJS advisories** — `npm audit` flags prototype pollution/ReDoS in `xlsx` 0.18.5, but only for *parsing* untrusted files; the app only *writes* XLSX, so risk is negligible.
- **Activity tracking** — records pages + API requests made by logged-in users for admin review. Two capture paths: (1) FastAPI `log_activity` middleware (outermost, after `add_cache_control`) decodes the Bearer token and writes one `activity_logs` row per authenticated `/api/*` request — method, path, query, status, duration; (2) `POST /api/track/page` beacon from `+layout.svelte` (a `$effect` watching `user` + `$page.url.pathname`, deduped with a plain `let lastTracked` keyed `username|path+search`) records page views for client-side navigations. The middleware skips `/api/track/page` and `/api/admin/activity*` (so admin viewing/clearing doesn't self-log) and skips anonymous traffic. Writes go through `run_in_threadpool` with exceptions swallowed — logging never breaks a request. **No IP/user-agent stored.** Admin UI at `/admin/activity` (`GET /api/admin/activity?user&type&limit&offset` returns `{items, total}`, `DELETE /api/admin/activity?user` clears; both admin-only). Route guard covers `/admin` prefix, so `/admin/activity` needs no extra `requiresAuth` entry.

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
