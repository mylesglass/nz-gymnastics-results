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
├── .vscode/tasks.json       # VS Code tasks (Ctrl+Shift-B) — gitignored
├── AGENTS.md                # This file
├── docker-compose.yml
│
├── backend/
│   ├── app/
│   │   ├── main.py          # FastAPI routes
│   │   ├── models.py        # SQLAlchemy models (Base from DeclarativeBase)
│   │   ├── database.py      # SQLite engine + session
│   │   ├── schemas.py       # Pydantic models
│   │   ├── auth.py          # JWT auth (bcrypt, HS256, role-based, seed_admin_user)
│   │   ├── parser.py        # Scoreholder JSON parser (~630 lines)
│   │   ├── decoder.py       # Node-tree score field decoder
│   │   ├── resolver.py      # ID chain resolver
│   │   ├── transformer.py   # Pandas long→wide pivot + CSV/XLSX export + region enrichment
│   │   ├── reconcile.py     # Athlete ID reconciliation
│   │   └── validate_json.py # Batch validation CLI
│   ├── tests/               # pytest suite (251 tests)
│   └── pyproject.toml
│
├── frontend/
│   ├── src/
│   │   ├── lib/
│   │   │   ├── api.ts              # Typed fetch wrappers
│   │   │   ├── auth.ts             # JWT auth stores (currentUser, setToken, logout)
│   │   │   ├── year.ts             # Shared year toggle store
│   │   │   ├── WideResultsTable.svelte  # Shared results table
│   │   │   ├── ScoreTooltip.svelte      # Apparatus score tooltip
│   │   │   ├── AATooltip.svelte         # AA score tooltip
│   │   │   └── MultiSelect.svelte       # Multi-select dropdown
│   │   ├── routes/
│   │   │   ├── +layout.svelte          # Nav, footer, theme toggle
│   │   │   ├── +page.svelte            # Landing page
│   │   │   ├── upload/+page.svelte     # JSON upload
│   │   │   ├── login/+page.svelte      # Username+password login
│   │   │   ├── admin/+page.svelte      # Admin dashboard
│   │   │   ├── admin/users/+page.svelte # User management
│   │   │   ├── rankings/+page.svelte   # Rankings (member+)
│   │   │   ├── events/+page.svelte     # Event list
│   │   │   ├── events/[id]/+page.svelte # Event results
│   │   │   ├── results/+page.svelte    # All-events results
│   │   │   ├── clubs/+page.svelte      # Club list
│   │   │   ├── club/[club]/+page.svelte # Club results
│   │   │   ├── gymnasts/+page.svelte   # Gymnast list
│   │   │   └── gymnast/[gnz_id]/+page.svelte # Gymnast results
│   │   ├── app.css              # @import "tailwindcss"; @plugin "daisyui";
│   │   └── app.html
│   ├── svelte.config.js
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
- `API_BASE = ""` in dev (Vite proxy), `"http://backend:8000"` in production
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
- Data fetching client-side in `onMount` (no load functions)
- `goto()` from `$app/navigation` for programmatic navigation

## Testing Conventions

### Backend (pytest)
- All tests in `backend/tests/`, one file per module
- **Run:** `cd backend && source .venv/bin/activate && pytest`
- **Run single:** `pytest tests/test_parser.py -v`
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

# Docker
docker compose up --build
```

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
- **DB schema** — `events` table + `long_scores` table (one row per apparatus pass per gymnast) + `users` table (username, hashed_password, role).
- **`new URL()` breaks** on relative paths in dev mode — use string concatenation in api.ts.
- **Two JSON formats exist** — only the new format (`eventOrganizations`, `performanceRules`, etc.) is supported.
- **Name cleaning** — `_NAME_LEVEL_SUFFIX` regex strips `(L#)`, `(STEP 10)`, `(YI)` from gymnast names at parse time.
- **Region enrichment** — club→region lookup at pivot time via `clubs_and_regions.json`; changes require re-upload.
- **DaisyUI z-index** — `.dropdown-content` sets `z-index: 1` overriding Tailwind classes; use inline `style="z-index: 50"`.
- **`$effect` reactivity** — tracks all dependencies read inside it; avoid reading state the effect itself modifies.
