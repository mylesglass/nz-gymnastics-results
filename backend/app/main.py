import json
from contextlib import asynccontextmanager

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func

from app.database import get_session, init_db
from app.models import Event, LongScore
from app.parser import parse_json
from app.schemas import EventListItem, EventResponse, ResultsResponse


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="NZ Gymnastics Results API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health():
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Upload
# ---------------------------------------------------------------------------

@app.post("/api/upload", response_model=EventResponse)
def upload_file(file: UploadFile = File(...)):
    if not file.filename or not file.filename.endswith(".json"):
        raise HTTPException(400, "Only .json files are accepted")

    raw = file.file.read()
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        raise HTTPException(400, f"Invalid JSON: {e}")

    event_info, rows = parse_json(data)

    session = get_session()
    try:
        # Re-upload: delete existing data for same event name
        existing = session.query(Event).filter(Event.name == event_info["name"]).first()
        if existing:
            session.delete(existing)
            session.flush()

        event = Event(
            name=event_info["name"],
            start_date=event_info["start_date"],
            end_date=event_info["end_date"],
            discipline=event_info["discipline"],
        )
        session.add(event)
        session.flush()

        for row in rows:
            score = LongScore(event_id=event.id, **row)
            session.add(score)
        session.commit()

        gymnast_count = (
            session.query(func.count(func.distinct(LongScore.gymnast_name)))
            .filter(LongScore.event_id == event.id)
            .scalar()
        )
        score_count = (
            session.query(func.count(LongScore.id))
            .filter(LongScore.event_id == event.id)
            .scalar()
        )

        return EventResponse(
            id=event.id,
            name=event.name,
            start_date=event.start_date,
            end_date=event.end_date,
            discipline=event.discipline,
            gymnast_count=gymnast_count,
            score_count=score_count,
        )
    finally:
        session.close()


# ---------------------------------------------------------------------------
# List events
# ---------------------------------------------------------------------------

@app.get("/api/events", response_model=list[EventListItem])
def list_events():
    session = get_session()
    try:
        events = session.query(Event).order_by(Event.created_at.desc()).all()
        result = []
        for ev in events:
            gymnast_count = (
                session.query(func.count(func.distinct(LongScore.gymnast_name)))
                .filter(LongScore.event_id == ev.id)
                .scalar()
            )
            result.append(
                EventListItem(
                    id=ev.id,
                    name=ev.name,
                    start_date=ev.start_date,
                    end_date=ev.end_date,
                    discipline=ev.discipline,
                    gymnast_count=gymnast_count or 0,
                )
            )
        return result
    finally:
        session.close()


# ---------------------------------------------------------------------------
# Results (raw long-format)
# ---------------------------------------------------------------------------

@app.get("/api/events/{event_id}/results", response_model=ResultsResponse)
def get_results(event_id: int):
    session = get_session()
    try:
        event = session.query(Event).filter(Event.id == event_id).first()
        if not event:
            raise HTTPException(404, "Event not found")

        gymnast_count = (
            session.query(func.count(func.distinct(LongScore.gymnast_name)))
            .filter(LongScore.event_id == event.id)
            .scalar()
        )

        scores = (
            session.query(LongScore)
            .filter(LongScore.event_id == event.id)
            .order_by(LongScore.gymnast_name, LongScore.apparatus, LongScore.pass_number)
            .all()
        )

        columns = [
            "gymnast_name", "gnz_id", "club_name", "discipline",
            "level_category", "division", "apparatus", "pass_number",
            "d_score", "e_score", "neutral_deductions", "pass_final_score",
            "apparatus_rank", "aa_score", "aa_rank", "round_type",
        ]
        rows = [
            {col: getattr(s, col) for col in columns}
            for s in scores
        ]

        return ResultsResponse(
            event=EventListItem(
                id=event.id,
                name=event.name,
                start_date=event.start_date,
                end_date=event.end_date,
                discipline=event.discipline,
                gymnast_count=gymnast_count or 0,
            ),
            columns=columns,
            rows=rows,
        )
    finally:
        session.close()