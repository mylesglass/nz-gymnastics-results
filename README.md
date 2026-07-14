# NZ Gymnastics Results

A web application for parsing, storing, and viewing gymnastics competition results from Scoreholder JSON exports.

## Features
- Upload Scoreholder JSON files and parse into a normalized database
- View results in a wide-format table with WAG/MAG tabs
- Hover tooltips on apparatus scores showing full breakdown (D, E, N, Bonus, Rank)
- Filter, sort, and search results by name/ID, STEP/Level, Club, Division, Round — filters integrated into column headers
- View results for a single gymnast or club across all events (clickable table cells)
- Export to CSV and XLSX (all columns including per-pass vault data)
- Light/dark theme toggle
- Responsive column sizing with configurable per-column min-widths
- Sticky duplicate header with scroll-sync for long tables
- Supports both WAG (Women's Artistic Gymnastics) and MAG (Men's Artistic Gymnastics)
- Password-protected write operations (upload, delete, rename) via `ADMIN_PASSWORD` env var
- Footer with GitHub link and Ko-fi donation support

## Tech Stack
- **Backend:** Python, FastAPI, SQLAlchemy, SQLite, Pandas
- **Frontend:** SvelteKit 5, Tailwind CSS v4, DaisyUI v5 (dark theme)
- **Infrastructure:** Docker Compose

## Quick Start (no dependencies needed)

```bash
docker compose up --build
```

Then open http://localhost:5173

**Note:** The first `npm install` inside the frontend container takes ~7 minutes. Subsequent builds are instant due to Docker layer caching.

Once running, upload a JSON file via the web UI and view results.

### Dev Workflow (VS Code)

A convenience script and VS Code tasks are provided to start both services in separate terminal panels:

```bash
.dev.sh     # starts backend + frontend concurrently
```

In VS Code, press **Ctrl+Shift+B** to launch the "Dev Environment" task, which opens dedicated terminal panels for the backend and frontend (configured in `.vscode/tasks.json`).

## Development (faster iteration)

### Prerequisites
- Python 3.12+
- Node.js 20+
- npm (comes with Node)

### Backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
uvicorn app.main:app --reload --port 8000
```

The API is served at http://localhost:8000.

### Frontend

```bash
cd frontend
npm install
npm run dev
```

The UI is served at http://localhost:5173. In dev mode, Vite proxies `/api/*` requests to the backend.

## Testing

```bash
cd backend
source .venv/bin/activate
pytest
```

Runs 214 tests covering the decoder, resolver, parser, database models, transformer, and API endpoints.

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/health` | Health check |
| GET | `/api/stats` | Aggregate statistics (event/gymnast/score/club counts) |
| GET | `/api/clubs` | List all clubs with gymnast counts and region mapping |
| GET | `/api/gymnasts` | List all gymnasts with GNZ ID and club |
| GET | `/api/auth/status` | Check if admin password is configured |
| POST | `/api/auth` | Verify admin password |
| POST | `/api/upload` | Upload a Scoreholder JSON file (requires auth if configured) |
| GET | `/api/events` | List all uploaded events |
| GET | `/api/events/{id}/results` | Get results (long format) |
| GET | `/api/events/{id}/results/wide` | Get results (wide format, WAG/MAG split) |
| GET | `/api/results/wide-all` | Get results across all events (filters: `?gnz_id=`, `?club=`, `?year=`) |
| GET | `/api/events/{id}/export/csv` | Download results as CSV |
| GET | `/api/events/{id}/export/xlsx` | Download results as XLSX |
| PATCH | `/api/events/{id}` | Rename an event (requires auth if configured) |
| DELETE | `/api/events/{id}` | Delete an event and its scores (requires auth if configured) |

## Project Structure

```
backend/                  # Python FastAPI backend
├── app/
│   ├── main.py           # FastAPI app + endpoints
│   ├── models.py         # SQLAlchemy ORM models
│   ├── database.py       # SQLite engine + session
│   ├── schemas.py        # Pydantic models
│   ├── auth.py           # Password-based auth (ADMIN_PASSWORD env var)
│   ├── parser.py         # Scoreholder JSON parser
│   ├── decoder.py        # Node-tree score field decoder
│   ├── resolver.py       # ID chain resolver
│   ├── transformer.py    # Pandas long→wide pivot + export
│   └── validate_json.py  # Batch validation CLI
└── tests/                # pytest suite (214 tests)

frontend/                 # SvelteKit + Tailwind CSS v4 + DaisyUI v5
├── src/
│   ├── lib/
│   │   ├── api.ts              # Typed API client
│   │   ├── auth.ts             # Auth stores (isLoggedIn, authConfigured)
│   │   ├── ScoreTooltip.svelte # Apparatus score tooltip
│   │   ├── AATooltip.svelte    # All-Around score tooltip (D/E/N sum)
│   │   ├── MultiSelect.svelte  # Multi-select dropdown
│   │   └── WideResultsTable.svelte # Shared results table (filters, sort, export, sticky header)
│   ├── app.css              # @import "tailwindcss"; @plugin "daisyui";
│   ├── app.html             # Inline theme script (flash prevention)
│   └── routes/
│       ├── +layout.svelte       # Nav bar, footer, theme toggle
│       ├── +page.svelte         # Landing page (stats / upload / login prompt)
│       ├── upload/+page.svelte  # JSON upload drop-zone
│       ├── login/+page.svelte   # Password login form
│       ├── events/+page.svelte  # Event list (search, year filter, rename/delete)
│       ├── events/[id]/+page.svelte  # Per-event results
│       ├── results/+page.svelte      # All-events results
│       ├── clubs/+page.svelte        # Club list (region-grouped)
│       ├── club/[club]/+page.svelte  # Club results across all events
│       ├── gymnasts/+page.svelte     # Gymnast list (A-Z grouped)
│       └── gymnast/[gnz_id]/+page.svelte  # Gymnast results across all events
├── svelte.config.js
├── vite.config.ts        # tailwindcss() + sveltekit() plugins
├── package.json
└── Dockerfile
```