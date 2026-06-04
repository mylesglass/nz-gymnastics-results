# NZ Gymnastics Results

A web application for parsing, storing, and viewing gymnastics competition results from Scoreholder JSON exports.

## Features
- Upload Scoreholder JSON files and parse into a normalized database
- View results in a wide-format "All Around" table
- Export to CSV and XLSX
- Supports both WAG (Women's Artistic Gymnastics) and MAG (Men's Artistic Gymnastics)

## Tech Stack
- **Backend:** Python, FastAPI, SQLAlchemy, SQLite, Pandas
- **Frontend:** SvelteKit
- **Infrastructure:** Docker Compose

## Quick Start
```bash
docker compose up --build
```
Then open http://localhost:5173

## Development

### Backend
```bash
cd backend
pip install -e .
uvicorn app.main:app --reload
```

### Frontend
```bash
cd frontend
npm install
npm run dev
```

### Running Tests
```bash
cd backend
pytest
```
