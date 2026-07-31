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
│   │   │   ├── regions.ts          # Region color palettes + gradient/text helpers
│   │   │   ├── RegionBadge.svelte  # Region color badge component
│   │   │   ├── NZRegionMap.svelte  # Interactive NZ SVG map (15 gym regions, theme-coloured)
│   │   │   ├── WideResultsTable.svelte  # Shared results table (paginated, virtualized)
│   │   │   ├── ScoreTooltip.svelte      # Apparatus score tooltip
│   │   │   └── AATooltip.svelte         # AA score tooltip
│   │   ├── routes/
│   │   │   ├── +layout.svelte          # Nav, footer, theme toggle, year tabs via goto()
│   │   │   ├── +page.svelte            # Landing page with stat cards
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
│   │   │   ├── clubs/+page.svelte  # Interactive NZ map (map left, region box right)
│   │   │   ├── club/[club]/+page.server.ts # SSR load for club results
│   │   │   ├── club/[club]/+page.svelte # Club results
│   │   │   ├── gymnasts/+page.server.ts # SSR load for gymnast list
│   │   │   ├── gymnasts/+page.svelte   # Gymnast list with A-Z letter jump
│   │   │   ├── gymnast/[gnz_id]/+page.svelte # Gymnast results (client-only, no server load)
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
- **Bonus propagation** — apparatus-level modifier stored on one pass, propagated to all passes in same `(entityId, unitEventId)` group at parse time.
- **Floating point** — `_fmt3` in transformer.py: rounds to 6 decimals then floors to 3 to handle IEEE 754 noise.
- **WAG/MAG split** — tab assignment uses `discipline` field from data, not apparatus heuristic.
- **Division extraction** — heuristic text matching (UNDER/OVER/A/B) from competition node names.
- **Numpy types in JSON** — pandas/numpy produce `numpy.int64`/`numpy.float64` that FastAPI's `jsonable_encoder` can't serialize; must convert in transformer.py.
- **Auth** — JWT-based (bcrypt, HS256, 7-day expiry), role-based (admin/uploader). Admin seeded from env vars (`ADMIN_USERNAME`, `ADMIN_PASSWORD`, `ADMIN_ROLE`). JWT_SECRET auto-generated and persisted to `data/jwt_secret.txt`. When `ADMIN_PASSWORD` is unset, all endpoints are public.
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
- **Apparatus Specialists** — Wellington ranking fallback path for WAG STEP 8–10 (`wag_step_7_10` config: `specialist_steps`, `apparatus_qualifying_score: 11.0`, `apparatus_qualifying_count: 2`). Intent-submitted athletes NOT in the AA table who reach ≥11.000 on two distinct apparatus (best per apparatus across all eligible events, competition name tracked). Returned as `apparatus_specialists` in the ranking response; frontend renders below the main table with color-coded badges (VT primary / UB secondary / BB accent / FX info) + DaisyUI tooltips showing the competition.
- **Wellington intent tracking** — `WellingtonIntent` model (`wellington_intents` table, unique `(gnz_id, year)`), `GET /api/wellington/intents`, `POST /api/wellington/intent` (admin). Admin checkbox column + Intent filter toggle on the ranking page; toggling calls `invalidate()`.
- **Gymnast page no-results** — `_compute_wide_all` adds a top-level `name` (latest `gymnast_name` across all years for that `gnz_id`) when the year query returns no rows. Frontend shows the name in the heading + a polite "no results for {year}" info alert; "Gymnast not found" only when no name exists at all.
- **Step dropdown ordering** — backend `ORDER BY level_category` is alphabetical (`STEP 1, STEP 10, STEP 2, ...`). Frontend re-sorts with `sortSteps()` (STEP 1–10 numerically, then Youth/Junior/Senior) in `rankings/+page.svelte` and `WideResultsTable.svelte`.
- **SvelteKit CSRF disabled** — `csrf: { checkOrigin: false }` in `svelte.config.js`; all mutations go through the `/api` proxy to FastAPI which handles its own JWT auth. Still set `ORIGIN` env var in production for adapter-node URL generation.
- **`fetchToken` must NOT be `$state`** — the stale-response guard counter in `wellington-ranking/+page.svelte` is a plain `let`. If made `$state`, incrementing it inside `loadRankings()` re-triggers the `$effect` → infinite API request loop.
- **Inline edit** — `PATCH /api/admin/scores/gymnast` updates name/GNZ ID/club on all `long_scores` rows matching `(event_id, gymnast_name)`. Cache invalidation clears `wide-all`, `stats`, `gymnasts`, `clubs` prefixes. Frontend: Edit mode toggle makes name/GNZ ID/club cells editable inputs with per-row Save button. Known issue: table doesn't always feel reactive after save.
- **/clubs NZ map** — `NZRegionMap.svelte` renders the `@svg-maps/new-zealand` package (17 Stats NZ region paths, CC-BY-4.0) in a `viewBox="0 0 525 989"` (Chatham Islands cropped out). 15 gym regions map to stats paths: `gis`+`hkb` → Hawkes Bay / Poverty Bay, `tas`+`nsn`+`mbh` → Top of the South; Auckland is split into Harbour/Auckland/Counties-Manukau and Canterbury into Canterbury/Aorangi via SVG `<clipPath>` rects. No regional colouring — regions use theme colours (`--color-base-300` fill, `--color-primary` on hover/active). Layout: map left (sticky), selected region's box right; clicking a map region shows only that region's box (toggle to clear).
- **Svelte 5 snippet gotcha** — `{#snippet}` components must be invoked with `{@render RegionBox({...})}`, NOT `<RegionBox />` (throws `invalid_snippet_arguments`). Also avoid `class:ring-2` on snippet elements — Svelte parses the hyphen as an expression (`ring` undefined); use a plain `class` string instead.
