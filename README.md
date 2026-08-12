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
- **Club & gymnast profiles** — view all results for a single club or gymnast across all events (clickable table cells)
- **All-events results** view, grouped by gymnast, with configurable year filter

### 🏆 Rankings & exports
- **National Rankings** by discipline and level category
- **Wellington Regional Rankings** with intent tracking, qualifier toggles, and apparatus specialist detection for WAG steps 8–10
- **Export** to CSV, XLSX, or PDF from a single dropdown — full detail in CSV/XLSX (with configurable hidden columns and widths), table-friendly layout in PDF with a header and page numbers

### 🎨 UI
- Light / dark **theme toggle** with 30+ themes, persisted in `localStorage`
- **Responsive design** — works on desktop, tablet, and mobile
- **Year filter** in the nav bar that applies across all data pages
- Sticky column headers and scroll-sync for long tables

### 🔐 Authentication & admin
- **JWT-based authentication** with bcrypt-hashed passwords and HS256 tokens (7-day expiry)
- **Admin dashboard** with statistics, cache refresh, and user management
- **Inline editing** of gymnast name / GNZ ID / club directly on event and all‑results tables
- **Athlete ID reconciliation** to unify duplicate GNZ IDs across events

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
ORIGIN=https://scores.mylessglass.com ADMIN_PASSWORD=*** \
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
The backend normalises this into two database tables:

- **`events`** — one row per uploaded event (name, discipline, date)
- **`long_scores`** — one row per apparatus pass per gymnast (D score, E score, neutral deductions, rank, etc.)

From there, the `transformer.py` pivots the long format into a wide table (one row per
gymnast, one column per apparatus) and enriches each row with the gymnast's region via
club lookup.

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

All routes live under `/api`. Role requirements are checked via JWT (write endpoints
are admin‑only unless configured otherwise).

### 👀 Public

| Method | Path                              | Description                                        |
|--------|-----------------------------------|----------------------------------------------------|
| GET    | `/api/health`                     | Health check                                       |
| GET    | `/api/stats`                      | Aggregate statistics (event / gymnast / club counts) |
| GET    | `/api/years`                      | List all years with events                         |
| GET    | `/api/clubs`                      | List all clubs with gymnast counts and region       |
| GET    | `/api/gymnasts`                   | List all gymnasts with GNZ ID and club              |
| GET    | `/api/rankings`                   | National rankings (WAG / MAG, all levels)          |
| GET    | `/api/rankings/wellington`        | Wellington regional rankings                       |
| GET    | `/api/events`                     | List all uploaded events                           |
| GET    | `/api/events/{id}/results`        | Single event results (long format)                 |
| GET    | `/api/events/{id}/results/wide`   | Single event results (wide format, WAG / MAG split) |
| GET    | `/api/results/wide-all`           | All‑events results (filters: `gnz_id`, `club`, `year`, `region`) |
| GET    | `/api/events/{id}/export/csv`     | Download event results as CSV                      |
| GET    | `/api/events/{id}/export/xlsx`    | Download event results as XLSX                     |

### 🔒 Auth

| Method | Path                                       | Description                |
|--------|--------------------------------------------|----------------------------|
| POST   | `/api/auth/login`                          | Log in (returns JWT)       |
| POST   | `/api/auth/register`                       | Register a new user (admin) |
| GET    | `/api/auth/users`                          | List users (admin)         |
| POST   | `/api/auth/users/{id}/reset-password`      | Reset a user's password (admin) |
| DELETE | `/api/auth/users/{id}`                     | Delete a user (admin)      |

### ✏️ Write / admin

| Method  | Path                                | Description                                      |
|---------|-------------------------------------|--------------------------------------------------|
| POST    | `/api/upload`                       | Upload a Scoreholder JSON file                   |
| POST    | `/api/import-url`                   | Import from a Scoreholder public URL             |
| PATCH   | `/api/events/{id}`                  | Rename an event                                  |
| DELETE  | `/api/events/{id}`                  | Delete an event and its scores                   |
| PATCH   | `/api/admin/scores/gymnast`         | Update name / GNZ ID / club on scores            |
| POST    | `/api/admin/reconcile-athletes`     | Reconcile duplicate GNZ IDs                      |
| POST    | `/api/admin/refresh-cache`          | Clear the in‑memory cache                        |

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

Runs 332 tests covering the decoder, resolver, parser, database models (incl. migrations),
transformer, reconciliation, athlete identity (clustering, back-write, admin review/merge/split),
club aliases, and API endpoints. 87 further tests are conditionally
skipped when the reference data‑collection JSON files are not present.

## 📁 Project structure

```
.
├── .dev.sh                       # Start backend + frontend concurrently
├── docker-compose.yml            # Dev Docker Compose
├── docker-compose.prod.yml       # Production Docker Compose
│
├── data-collection/               # Reference Scoreholder JSON exports (for testing)
│
├── backend/
│   ├── Dockerfile
│   ├── pyproject.toml
│   ├── clubs_and_regions.json     # Canonical club names, aliases, regions, colours
│   ├── app/
│   │   ├── main.py                # FastAPI routes + all endpoint logic
│   │   ├── models.py              # SQLAlchemy models (Event, LongScore, User)
│   │   ├── database.py            # SQLite engine, session, migration
│   │   ├── schemas.py             # Pydantic models
│   │   ├── auth.py                # JWT auth (bcrypt, HS256, admin seeding)
│   │   ├── cache.py               # Granular TTL cache with per‑event prefix invalidation
│   │   ├── parser.py              # Scoreholder JSON parser (~630 lines)
│   │   ├── decoder.py             # Node‑tree score field decoder
│   │   ├── resolver.py            # ID‑chain resolver for the flat Scoreholder model
│   │   ├── transformer.py         # Pandas long→wide pivot + CSV / XLSX export + region enrichment
│   │   ├── reconcile.py           # Athlete GNZ ID reconciliation
│   │   ├── reconcile_clubs.py     # Club name normalisation script
│   │   ├── scoreholder.py         # Fetch Scoreholder public export JSON from URLs
│   │   ├── validate_json.py       # Batch validation CLI
│   │   └── wellington_ranking.py  # Wellington regional ranking computation
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
│   │   │   ├── auth.ts                      # JWT auth store (currentUser, setToken, logout)
│   │   │   ├── year.ts                      # Global year filter store
│   │   │   ├── regions.ts                   # Region colour palettes + REGION_ORDER + gradient helpers
│   │   │   ├── RegionBadge.svelte           # Inline region colour chip
│   │   │   ├── NZRegionMap.svelte           # Interactive SVG map of NZ (animated checker on hover/select)
│   │   │   ├── WideResultsTable.svelte      # Shared results table (paginated, virtualised)
│   │   │   ├── MultiSelect.svelte           # Multi‑select dropdown
│   │   │   ├── ScoreTooltip.svelte          # Apparatus score breakdown tooltip
│   │   │   └── AATooltip.svelte             # All‑around score tooltip
│   │   └── routes/
│   │       ├── +layout.svelte               # Nav bar, theme toggle, year tabs
│   │       ├── +page.svelte                 # Landing page: info items above nav cards w/ stat badges, member-only Rankings card, What's new
│   │       ├── upload/+page.svelte          # JSON upload + import‑from‑URL
│   │       ├── login/+page.svelte           # Username + password login
│   │       ├── admin/+page.svelte           # Admin dashboard
│   │       ├── admin/users/+page.svelte     # User management
│   │       ├── rankings/+page.svelte        # National rankings (member+)
│   │       ├── wellington-ranking/+page.svelte  # Wellington rankings
│   │       ├── events/+page.svelte          # Event list (search / rename / delete)
│   │       ├── events/[id]/+page.svelte     # Per‑event results
│   │       ├── results/+page.svelte         # All‑events results
│   │       ├── clubs/+page.svelte           # Interactive NZ map (desktop) / region accordion (mobile)
│   │       ├── club/[club]/+page.svelte     # Club results
│   │       ├── gymnasts/+page.svelte        # Gymnast list (A‑Z grouped, sticky header)
│   │       └── gymnast/[gnz_id]/+page.svelte # Gymnast results
│   └── static/
│       └── patch_notes.json                 # Full update history (scrollable What's new section)
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
