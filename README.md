# 🏅 NZ Gymnastics Results

A web application for parsing, storing, and viewing gymnastics competition results from
[Scoreholder](https://scoreholder.com) JSON exports. Built for the New Zealand gymnastics
community but designed to be adaptable for any gymnastics organisation. 🥇

## ✨ Features

### 📥 Data ingestion
- **Upload** Scoreholder event JSON files via drag-and-drop from the web UI
- **Import from URL** — paste one or many Scoreholder public event links to import directly without downloading files
- **Automatic club normalisation** — resolves name variants to canonical clubs via a configurable alias table (`clubs_and_regions.json`)

### 📊 Results & browsing
- **Wide-format results table** with WAG (Women's Artistic Gymnastics) and MAG (Men's Artistic Gymnastics) tabs
- **Rich score tooltips** on apparatus scores showing full breakdown (D‑score, E‑score, neutral deductions, bonus, rank)
- **Interactive NZ map** on the Clubs page — click any of the 15 gymnastics regions to see its clubs (hover/select animates a scrolling checker), with a collapsible north‑to‑south region accordion on mobile 🗺️
- **Club & gymnast profiles** — view all results for a single club or gymnast across all events (clickable table cells), with Personal Bests and season-meta cards on gymnast pages
- **All-events results** view, grouped by gymnast, with configurable year filter
- **SEO‑friendly pages** — public pages are server-rendered with real headings and counts, gymnasts have readable URLs (`/gymnast/{slug}-{name}`), plus a dynamic sitemap and `robots.txt`

### 🏆 Rankings & exports
- **National, Apparatus, and Wellington Regional Rankings** (member login) by discipline and level category
- **Wellington intent tracking** with qualifier toggles, a "not on the ranking" checklist, and apparatus specialist detection (WAG steps 8–10, MAG Level 7+, Junior/Senior International)
- **Rankings remember your place** — leaving to view a gymnast and coming back keeps your discipline and step
- **Export** to CSV, XLSX, or PDF from a single dropdown — full detail in CSV/XLSX (with configurable hidden columns and widths), table-friendly layout in PDF with a header and page numbers

### 🎨 UI
- Light / dark **theme toggle** with 30+ themes, persisted in `localStorage`
- **Responsive design** — works on desktop, tablet, and mobile
- **Year filter** in the nav bar that applies across all data pages
- **"What's new"** section on the landing page showing the full update history
- Sticky column headers, scroll-sync for long tables, and a season **timeline** on the events page

### ⚡ Performance
- **Precomputed data stores** — results and ranking marks are rebuilt in the background after every upload, so pages load near-instantly instead of pivoting on every request
- **Granular caching** with per-key TTLs, single-flight loads, and ETags; browser caching capped at 5 minutes

### 🔐 Authentication & admin
- **JWT-based authentication** with bcrypt-hashed passwords and HS256 tokens (7-day expiry) and per-user **permission gating** (`rankings.national`, `rankings.wellington`)
- **Admin dashboard** — site statistics, cache refresh, upload, user management, identity review, usage analytics, and Cloudflare edge analytics, all on one page
- **Inline editing** of gymnast name / GNZ ID / club / division / round-type directly on event and all‑results tables (changes reflect immediately and keep your place)
- **Athlete identity layer** — variant name spellings and duplicate IDs are clustered into stable athlete identities; an Identity Review tool lets admins merge/split profiles with a preview
- **Usage analytics** — anonymous traffic and logged-in activity tracked (no IPs or user agents stored) with optional **Cloudflare edge analytics**

## 🧰 Tech Stack

| Layer      | Technology                                              |
|------------|---------------------------------------------------------|
| **Backend**  | Python 3.12+, [FastAPI](https://fastapi.tiangolo.com), SQLAlchemy, SQLite, Pandas |
| **Frontend** | [SvelteKit 5](https://svelte.dev), Tailwind CSS v4, [DaisyUI v5](https://daisyui.com) |
| **Infra**    | [Docker Compose](https://docs.docker.com/compose/) for both dev and production |

## 🚀 Quick Start (Docker)

The fastest way to get running — works immediately, no Python or Node.js required.

```bash
# Clone the repository
git clone https://github.com/mylesglass/nz-gymnastics-results.git
cd nz-gymnastics-results

# Start both services (backend API + frontend)
docker compose up --build
```

Open **http://localhost:5173** in your browser. 🎉

The first frontend build takes ~7 minutes; subsequent builds are instant thanks to Docker
layer caching.

### 🔑 Authentication (optional)

By default, the API runs with authentication disabled — all endpoints are public.
To enable login protection, set these environment variables for the backend service:

| Variable         | Purpose                         |
|------------------|---------------------------------|
| `JWT_SECRET`     | Signing key for JWT tokens      |
| `ADMIN_USERNAME` | Initial admin account username  |
| `ADMIN_PASSWORD` | Initial admin account password  |

If `JWT_SECRET` is unset it will be auto-generated and persisted to `data/jwt_secret.txt`.
When `ADMIN_PASSWORD` is unset, **all API endpoints are public** (ideal for local or trusted deployments).

## 🛠️ Development (faster iteration)

### 🐍 Backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
uvicorn app.main:app --reload --port 8000
```

The API is served at **http://localhost:8000**.

### ⚡ Frontend

```bash
cd frontend
npm install
npm run dev
```

The UI is served at **http://localhost:5173**. The Vite dev server proxies `/api/*`
requests to `http://localhost:8000`.

A convenience script launches both in one command:

```bash
./.dev.sh
```

## 🌍 Production Deployment

A production‑ready Docker Compose file is provided (`docker-compose.prod.yml`).
It uses a multi‑stage frontend build (`Dockerfile.prod`, adapter‑node) and expects to
connect to an external Docker network named `yams_default` (shared with an Nginx Proxy
Manager container).

```bash
# Example command — adjust env vars as needed
ORIGIN=https://results.coach.tools ADMIN_PASSWORD=*** \
  docker compose -f docker-compose.prod.yml up --build -d
```

| Variable           | Purpose                                                        |
|--------------------|----------------------------------------------------------------|
| `ORIGIN`           | Public URL of the frontend (required for adapter‑node CSRF)    |
| `ADMIN_PASSWORD`   | Password for the seeded admin user                             |
| `BODY_SIZE_LIMIT`  | Max upload size in bytes (default `52428800` = 50MB)           |

The production setup proxies `/api` requests from the frontend Node server to the
backend container via `hooks.server.ts` — no direct public access to the API.

## 🗄️ The data model

Scoreholder JSON exports flatten everything into reference‑based arrays.
The backend normalises this into SQLite tables:

- **`events`** — one row per uploaded event (name, discipline, date, `is_national`, `host_club`)
- **`long_scores`** — one row per apparatus pass per gymnast (D score, E score, neutral deductions, rank, vault start value, bonus, round type, `athlete_id`)
- **`athletes`** — the stable identity layer: variant spellings / duplicate IDs clustered into one athlete per person (canonical name + GNZ ID, content-addressed slug)
- **`users`** — admin/member accounts with ranking permissions
- **`wellington_intents`** — intent-submitted gymnasts per year
- **`slug_redirects`** — keeps old gymnast URLs working after identity merges/splits
- **`activity_logs`** + **`traffic_daily`** — usage analytics (no IPs or user agents stored)

From there, the `transformer.py` pivots the long format into a wide table (one row per
gymnast, one column per apparatus) and enriches each row with the gymnast's region via
club lookup. A **materialized store** (`data/results.materialized.db`) precomputes the
wide rows and ranking marks after every upload so read paths are cheap lookups.

### 🏛️ Club & region lookup

Every club name that appears in uploaded data is resolved to a canonical name and a
region through `clubs_and_regions.json` in the backend directory. The file defines:

- **canonical clubs** grouped by gymnastics region
- **aliases** for each club (so variants like "Counties", "Counties Manukau", and
  "Counties Manukau Gymnastics Club" all map to the same canonical)
- **region colour palettes** used on the frontend NZ map and club listings

To add or correct a mapping, edit `clubs_and_regions.json` and then run:

```bash
cd backend
source .venv/bin/activate
python -m app.reconcile_clubs
```

This re‑normalises all existing database rows to the updated aliases.

## 🌐 API endpoints

All routes live under `/api`. Write endpoints are admin‑only (JWT); ranking endpoints require a member login with the matching permission.

### 👀 Public

| Method | Path                              | Description                                        |
|--------|-----------------------------------|----------------------------------------------------|
| GET    | `/api/health`                     | Health check                                       |
| GET    | `/api/stats`                      | Aggregate statistics (event / gymnast / club counts) |
| GET    | `/api/years`                      | List all years with events                         |
| GET    | `/api/clubs`                      | List all clubs with gymnast counts and region       |
| GET    | `/api/clubs/known`                | List known club names (searchable, for event editing) |
| GET    | `/api/gymnasts`                   | List all gymnasts with GNZ ID and club              |
| GET    | `/api/gymnast`                    | Single gymnast identity lookup (by slug or GNZ ID)  |
| GET    | `/api/medals`                     | Medal tallies per gymnast and club   |
| GET    | `/api/events`                     | List all uploaded events                           |
| GET    | `/api/events/{id}/results`        | Single event results (long format)                 |
| GET    | `/api/events/{id}/results/wide`   | Single event results (wide format, WAG / MAG split) |
| GET    | `/api/results/wide-all`           | All‑events results (filters: `gnz_id`, `club`, `year`, `region`) |
| GET    | `/api/events/{id}/export/csv`     | Download event results as CSV                      |
| GET    | `/api/events/{id}/export/xlsx`    | Download event results as XLSX                     |
| POST   | `/api/track/page`                 | Page-view beacon (anonymous, used for usage stats)  |

### 🏆 Rankings (member+)

| Method | Path                              | Description                                        |
|--------|-----------------------------------|----------------------------------------------------|
| GET    | `/api/rankings/steps`             | Available step/level categories for a year + discipline |
| GET    | `/api/rankings`                   | National rankings (qualifier/quota/division toggles) |
| GET    | `/api/rankings/apparatus`         | National apparatus leaderboards per step            |
| GET    | `/api/rankings/wellington`        | Wellington regional rankings                        |

### 🔒 Auth

| Method | Path                                       | Description                |
|--------|--------------------------------------------|----------------------------|
| GET    | `/api/auth/status`                         | Whether auth is configured |
| GET    | `/api/auth/me`                             | Current user + effective permissions |
| POST   | `/api/auth/login`                          | Log in (returns JWT)       |
| POST   | `/api/auth/register`                       | Create a user (admin)      |
| GET    | `/api/auth/users`                          | List users (admin)         |
| PATCH  | `/api/auth/users/{id}/permissions`         | Update a user's ranking access (admin) |
| POST   | `/api/auth/users/{id}/reset-password`      | Reset a user's password (admin) |
| DELETE | `/api/auth/users/{id}`                     | Delete a user (admin)      |

### ✏️ Write / admin

| Method  | Path                                | Description                                      |
|---------|-------------------------------------|--------------------------------------------------|
| POST    | `/api/upload`                       | Upload a Scoreholder JSON file                   |
| POST    | `/api/import-url`                   | Import from a Scoreholder public URL             |
| POST    | `/api/clubs/aliases`                | Save new club aliases (from the mapping dialog)  |
| PATCH   | `/api/events/{id}`                  | Rename an event / set `is_national` / `host_club` |
| DELETE  | `/api/events/{id}`                  | Delete an event and its scores                   |
| PATCH   | `/api/admin/scores/gymnast`         | Inline-edit name / GNZ ID / club / division / round-type |
| POST    | `/api/admin/refresh-cache`          | Clear the in‑memory cache + trigger store rebuild |
| GET     | `/api/admin/rebuild/status`         | Materialized-store build status                  |
| GET     | `/api/admin/identity-review`        | Athlete-level name/ID conflicts                  |
| POST    | `/api/admin/athletes/merge-preview` | Preview a merge before committing                |
| POST    | `/api/admin/athletes/merge`         | Merge two athlete profiles                       |
| POST    | `/api/admin/athletes/split`         | Split one athlete into two                       |
| GET     | `/api/admin/activity`               | Logged-in activity log (detail)                  |
| GET     | `/api/admin/activity/summary`       | Usage summaries + charts data (7/30/90/all days) |
| DELETE  | `/api/admin/activity`               | Clear activity log rows                          |
| GET     | `/api/admin/cloudflare/summary`     | Cloudflare edge analytics (7/30 days)            |

### 🎯 Wellington intents

| Method  | Path                         | Description                           |
|---------|------------------------------|---------------------------------------|
| GET     | `/api/wellington/intents`    | List intent‑submitted gymnasts        |
| POST    | `/api/wellington/intent`     | Set intent for a gymnast (admin)      |

## 🧪 Testing

```bash
cd backend
source .venv/bin/activate
pytest
```

Runs 424 tests covering the decoder, resolver, parser, database models (incl. migrations),
transformer, reconciliation, athlete identity (clustering, back-write, admin review/merge/split),
rankings (national/apparatus/Wellington), materialized stores, activity tracking, Cloudflare
analytics, inline editing, medals, club aliases, and API endpoints. 87 further tests are
conditionally skipped when the reference data‑collection JSON files are not present.

## 📁 Project structure

```
.
├── .dev.sh                       # Start backend + frontend concurrently
├── docker-compose.yml            # Dev Docker Compose
├── docker-compose.prod.yml       # Production Docker Compose (external network)
│
├── data-collection/               # Reference Scoreholder JSON exports (for testing)
│
├── backend/
│   ├── Dockerfile
│   ├── pyproject.toml
│   ├── clubs_and_regions.json     # Canonical club names, aliases, regions, colours (seed)
│   ├── app/
│   │   ├── main.py                # FastAPI routes + all endpoint logic
│   │   ├── models.py              # SQLAlchemy models (Event, LongScore, User, Athlete, ...)
│   │   ├── database.py            # SQLite engine, session, migrations
│   │   ├── schemas.py             # Pydantic models
│   │   ├── auth.py                # JWT auth (bcrypt, HS256, roles, permissions)
│   │   ├── cache.py               # Granular TTL cache, per-event invalidation, single-flight
│   │   ├── activity_log.py        # Batched background writer for activity + traffic
│   │   ├── traffic.py             # Path normalisation + bot detection
│   │   ├── cloudflare.py          # Cloudflare GraphQL edge analytics
│   │   ├── parser.py              # Scoreholder JSON parser
│   │   ├── decoder.py             # Node‑tree score field decoder
│   │   ├── resolver.py            # ID‑chain resolver
│   │   ├── transformer.py         # Pandas long→wide pivot + CSV / XLSX export + region lookup
│   │   ├── materialize.py         # Precomputed wide_rows + ranking_marks stores
│   │   ├── athlete_identity.py    # Athlete clustering + rebuild_athletes
│   │   ├── reconcile.py           # Evidence-based ID reconciliation
│   │   ├── reconcile_clubs.py     # Club name normalisation script
│   │   ├── scoreholder.py         # Fetch Scoreholder public exports
│   │   ├── clubdata.py            # Active clubs_and_regions.json management
│   │   ├── wellington_ranking.py  # Wellington regional ranking computation
│   │   ├── validate_json.py       # Batch validation CLI
│   │   ├── repair_identities.py   # Consensus-driven identity repair CLI
│   │   ├── repair_merges.py       # Wrong-merge repair CLI
│   │   ├── reverse_merges.py      # Merge-reversal CLI
│   │   ├── dedupe_events.py       # Duplicate-event cleanup CLI
│   │   ├── backfill_host_club.py  # Host-club backfill CLI
│   │   ├── fix_apparatus.py       # Normalise un-resolvable All-around apparatus CLI
│   │   └── bench_materialize.py   # Store benchmark CLI
│   └── tests/
│
├── frontend/
│   ├── Dockerfile
│   ├── Dockerfile.prod            # Multi‑stage production build (adapter‑node)
│   ├── package.json
│   ├── svelte.config.js
│   ├── vite.config.ts
│   ├── src/
│   │   ├── hooks.server.ts        # /api proxy → backend in production
│   │   ├── app.css                # @import "tailwindcss"; @plugin "daisyui"
│   │   ├── app.html
│   │   ├── lib/
│   │   │   ├── api.ts                       # Typed fetch wrappers for every endpoint
│   │   │   ├── auth.ts                      # JWT auth store (currentUser, permissions, logout)
│   │   │   ├── year.ts                      # Global year filter store
│   │   │   ├── rankingState.svelte.ts       # Shared discipline/step for ranking pages
│   │   │   ├── seo.ts + Seo.svelte          # page titles + shared <svelte:head> / JSON-LD
│   │   │   ├── backend.ts                   # Backend URL + backendFetch for SSR loads
│   │   │   ├── export.ts + ExportMenu.svelte # CSV / XLSX / PDF export dropdown
│   │   │   ├── regions.ts + RegionBadge.svelte + RegionCheck.svelte
│   │   │   ├── NZRegionMap.svelte           # Interactive SVG map of NZ
│   │   │   ├── WideResultsTable.svelte      # Shared results table (paginated, editable)
│   │   │   ├── ScoreTooltip.svelte + AATooltip.svelte  # Score breakdown tooltips
│   │   │   ├── Tooltip.svelte               # Shared accessible tooltip
│   │   │   ├── Dialog.svelte                # A11y dialog (focus trap, Escape)
│   │   │   ├── FilterDropdown.svelte        # Multi-select club/region funnel filters
│   │   │   ├── SeasonBest.svelte            # Gymnast Personal Bests card
│   │   │   ├── Timeline.svelte              # Season timeline on the events page
│   │   │   ├── charts/ChartJs.svelte        # Lazy-loaded Chart.js wrapper
│   │   │   ├── admin/                       # Admin dashboard components
│   │   │   │   ├── Overview.svelte, Activity.svelte, ActivityCharts.svelte,
│   │   │   │   ├── CloudflareOverview.svelte, ActivityLog.svelte, Upload.svelte,
│   │   │   │   ├── Users.svelte, IdentityReview.svelte, StatTile.svelte
│   │   │   └── utils/
│   │   └── routes/
│   │       ├── +layout.server.ts            # SEO verification meta hook
│   │       ├── +layout.svelte               # Nav, footer, theme, year tabs, route guard
│   │       ├── +page.server.ts + +page.svelte  # Landing page (stats + What's new)
│   │       ├── robots.txt/ + sitemap.xml/   # Dynamic robots + sitemap
│   │       ├── login/+page.svelte           # Username + password login
│   │       ├── admin/+page.svelte           # Single admin dashboard page
│   │       ├── rankings/+page.svelte        # National rankings (member+)
│   │       ├── rankings/apparatus/+page.svelte  # Apparatus rankings (member+)
│   │       ├── wellington-ranking/+page.svelte  # Wellington rankings (member+)
│   │       ├── events/ + events/[id]/       # Event list + per-event results
│   │       ├── results/                     # All-events results
│   │       ├── clubs/ + club/[club]/        # Club list (NZ map) + club results
│   │       ├── gymnasts/                    # Gymnast list (A–Z, sticky search)
│   │       └── gymnast/[slug]/              # Gymnast results (readable URL)
│   └── static/
│       └── patch_notes.json                 # Full update history (What's new section)
```

## 🧭 Guidance for adapting the system

If you want to repurpose this application for your own gymnastics organisation, the
key files to customise are:

| File                              | What to change                                                  |
|-----------------------------------|-----------------------------------------------------------------|
| `backend/clubs_and_regions.json`  | Your region names, canonical clubs, aliases, and colour palettes |
| `frontend/src/lib/regions.ts`     | Same colour palettes and region config (must match the JSON)     |
| `frontend/src/lib/NZRegionMap.svelte` | Replace the SVG map source with your own geography           |
| `docker-compose.yml` / `.prod.yml`   | Container names, ports, environment variables               |
| `backend/app/wellington_ranking.py`  | Replace or remove with your own ranking logic               |

The parser expects Scoreholder's current JSON format — if Scoreholder changes its
export schema you would need to update `backend/app/parser.py`.

## 📜 License

This project is open‑source. See individual files for third‑party license details
(the NZ map SVG is CC‑BY‑4.0, DaisyUI is MIT, etc.).

---

<p align="center">
  Made with ❤️ for the NZ gymnastics community · <a href="https://github.com/mylesglass/nz-gymnastics-results">GitHub</a> · <a href="https://ko-fi.com/mylesglass">Ko‑fi</a>
</p>
