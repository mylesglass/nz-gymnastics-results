# NZ Gymnastics Results

A web application for parsing, storing, and viewing gymnastics competition results from Scoreholder JSON exports.

## Features
- Upload Scoreholder JSON files and parse into a normalized database
- View results in a wide-format "All Around" table
- Export to CSV and XLSX
- Supports both WAG (Women's Artistic Gymnastics) and MAG (Men's Artistic Gymnastics)

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

Runs 191 tests covering the decoder, resolver, parser, database models, and API endpoints.

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/health` | Health check |
| POST | `/api/upload` | Upload a Scoreholder JSON file |
| GET | `/api/events` | List all uploaded events |
| GET | `/api/events/{id}/results` | Get results (long format) |
| GET | `/api/events/{id}/results/wide` | Get results (wide format, WAG/MAG split) |
| GET | `/api/events/{id}/export/csv` | Download results as CSV |
| GET | `/api/events/{id}/export/xlsx` | Download results as XLSX |

## Project Structure

```
backend/                  # Python FastAPI backend
├── app/
│   ├── main.py           # FastAPI app + endpoints
│   ├── models.py         # SQLAlchemy ORM models
│   ├── database.py       # SQLite engine + session
│   ├── schemas.py        # Pydantic models
│   ├── parser.py         # Scoreholder JSON parser
│   ├── decoder.py        # Node-tree score field decoder
│   ├── resolver.py       # ID chain resolver
│   └── transformer.py    # Pandas long→wide pivot + export
└── tests/                # pytest suite (191 tests)

frontend/                 # SvelteKit + Tailwind CSS v4 + DaisyUI v5
├── src/
│   ├── lib/api.ts        # API client
│   ├── app.css           # Tailwind + DaisyUI imports
│   ├── app.html          # data-theme="dark"
│   └── routes/
│       ├── +layout.svelte    # Nav bar wrapper
│       ├── +page.svelte      # Upload (DaisyUI card/drop-zone)
│       ├── events/+page.svelte       # Event list table
│       └── events/[id]/+page.svelte  # Results (grouped apparatus cells, tooltips)
├── svelte.config.js
├── vite.config.ts        # tailwindcss() + sveltekit() plugins
├── package.json
└── Dockerfile
```