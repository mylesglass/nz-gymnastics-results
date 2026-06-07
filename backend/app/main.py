import json
from contextlib import asynccontextmanager

from fastapi import FastAPI, File, Header, HTTPException, UploadFile, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy import func

from app.auth import is_auth_configured, check_password
from app.database import get_session, init_db
from app.models import Event, LongScore
from app.parser import ParseError, parse_json, validate_upload_structure
from app.schemas import EventListItem, EventResponse, EventUpdate, ResultsResponse, StatsResponse
from app.transformer import export_csv, export_xlsx, pivot_to_wide, pivot_to_wide_dict


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


@app.get("/api/stats")
def get_stats():
    session = get_session()
    try:
        total_events = session.query(func.count(Event.id)).scalar() or 0
        total_gymnasts = (
            session.query(func.count(func.distinct(LongScore.gymnast_name))).scalar() or 0
        )
        total_scores = session.query(func.count(LongScore.id)).scalar() or 0
        total_clubs = (
            session.query(func.count(func.distinct(LongScore.club_name))).scalar() or 0
        )
        return StatsResponse(
            total_events=total_events,
            total_gymnasts=total_gymnasts,
            total_scores=total_scores,
            total_clubs=total_clubs,
        )
    finally:
        session.close()


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

class LoginRequest(BaseModel):
    password: str


async def require_auth(x_admin_password: str | None = Header(None)):
    if not is_auth_configured():
        return
    if not x_admin_password or not check_password(x_admin_password):
        raise HTTPException(401, "Unauthorized")


@app.get("/api/auth/status")
def auth_status():
    return {"configured": is_auth_configured()}


@app.post("/api/auth")
def auth_login(body: LoginRequest):
    if not is_auth_configured():
        return {"ok": True}
    if not check_password(body.password):
        raise HTTPException(401, "Unauthorized")
    return {"ok": True}


# ---------------------------------------------------------------------------
# Upload
# ---------------------------------------------------------------------------

@app.post("/api/upload", response_model=EventResponse)
def upload_file(file: UploadFile = File(...), _auth=Depends(require_auth)):
    if not file.filename or not file.filename.endswith(".json"):
        raise HTTPException(400, "Only .json files are accepted")

    raw = file.file.read()
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        raise HTTPException(400, f"Invalid JSON: {e}")

    errors = validate_upload_structure(data)
    if errors:
        raise HTTPException(422, {"message": "Invalid upload structure", "errors": errors})

    try:
        event_info, rows = parse_json(data)
    except ParseError as e:
        raise HTTPException(422, f"Parse error: {e}")

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
            year=event_info.get("year"),
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
        club_count = (
            session.query(func.count(func.distinct(LongScore.club_name)))
            .filter(LongScore.event_id == event.id)
            .scalar()
        )

        return EventResponse(
            id=event.id,
            name=event.name,
            start_date=event.start_date,
            end_date=event.end_date,
            discipline=event.discipline,
            year=event.year,
            gymnast_count=gymnast_count,
            score_count=score_count,
            club_count=club_count,
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
        events = session.query(Event).order_by(Event.start_date.desc()).all()
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
                    year=ev.year,
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
                year=event.year,
                gymnast_count=gymnast_count or 0,
            ),
            columns=columns,
            rows=rows,
        )
    finally:
        session.close()


# ---------------------------------------------------------------------------
# Results (wide format per discipline)
# ---------------------------------------------------------------------------

@app.get("/api/events/{event_id}/results/wide")
def get_results_wide(event_id: int):
    session = get_session()
    try:
        event = session.query(Event).filter(Event.id == event_id).first()
        if not event:
            raise HTTPException(404, "Event not found")

        data = pivot_to_wide_dict(event_id, session)
        return {"event": {"id": event.id, "name": event.name, "discipline": event.discipline}, **data}
    finally:
        session.close()


# ---------------------------------------------------------------------------
# All results (across all events, wide format)
# ---------------------------------------------------------------------------


@app.get("/api/results/wide-all")
def get_all_results_wide(gnz_id: str = None, club: str = None, year: int = None):
    session = get_session()
    try:
        query = session.query(Event).order_by(Event.created_at.desc())
        if year:
            query = query.filter(Event.year == year)
        events = query.all()
        combined: dict[str, dict] = {}

        for ev in events:
            data = pivot_to_wide_dict(ev.id, session, gnz_id, club)
            if not data:
                continue
            for disc_key in ("wag", "mag"):
                if disc_key not in data:
                    continue
                if disc_key not in combined:
                    combined[disc_key] = {"columns": [], "rows": []}
                disc = data[disc_key]
                for row in disc["rows"]:
                    row["event_name"] = ev.name
                    row["event_id"] = ev.id
                combined[disc_key]["rows"].extend(disc["rows"])
                if not combined[disc_key]["columns"]:
                    combined[disc_key]["columns"] = list(disc["columns"])
                else:
                    for c in disc["columns"]:
                        if c not in combined[disc_key]["columns"]:
                            combined[disc_key]["columns"].append(c)

        for disc_key in combined:
            if "event_name" in combined[disc_key]["columns"]:
                combined[disc_key]["columns"].remove("event_name")
            combined[disc_key]["columns"].insert(0, "event_name")

        return combined
    finally:
        session.close()


# ---------------------------------------------------------------------------
# Export CSV
# ---------------------------------------------------------------------------

@app.get("/api/events/{event_id}/export/csv")
def export_event_csv(event_id: int):
    session = get_session()
    try:
        event = session.query(Event).filter(Event.id == event_id).first()
        if not event:
            raise HTTPException(404, "Event not found")
        df = pivot_to_wide(event_id, session, event.name, event.start_date)
        data = export_csv(df)
        return Response(
            content=data,
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="{event.name}.csv"'},
        )
    finally:
        session.close()


# ---------------------------------------------------------------------------
# Export XLSX
# ---------------------------------------------------------------------------

@app.get("/api/events/{event_id}/export/xlsx")
def export_event_xlsx(event_id: int):
    session = get_session()
    try:
        event = session.query(Event).filter(Event.id == event_id).first()
        if not event:
            raise HTTPException(404, "Event not found")
        df = pivot_to_wide(event_id, session, event.name, event.start_date)
        data = export_xlsx(df)
        return Response(
            content=data,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f'attachment; filename="{event.name}.xlsx"'},
        )
    finally:
        session.close()


# ---------------------------------------------------------------------------
# Delete event
# ---------------------------------------------------------------------------

@app.delete("/api/events/{event_id}")
def delete_event(event_id: int, _auth=Depends(require_auth)):
    session = get_session()
    try:
        event = session.query(Event).filter(Event.id == event_id).first()
        if not event:
            raise HTTPException(404, "Event not found")
        session.delete(event)
        session.commit()
        return {"ok": True}
    finally:
        session.close()


# ---------------------------------------------------------------------------
# Rename event
# ---------------------------------------------------------------------------

@app.patch("/api/events/{event_id}", response_model=EventListItem)
def rename_event(event_id: int, body: EventUpdate, _auth=Depends(require_auth)):
    session = get_session()
    try:
        event = session.query(Event).filter(Event.id == event_id).first()
        if not event:
            raise HTTPException(404, "Event not found")
        event.name = body.name
        session.query(LongScore).filter(LongScore.event_id == event_id).update(
            {"event_name": body.name}
        )
        session.commit()
        gymnast_count = (
            session.query(func.count(func.distinct(LongScore.gymnast_name)))
            .filter(LongScore.event_id == event.id)
            .scalar()
        )
        return EventListItem(
            id=event.id,
            name=event.name,
            start_date=event.start_date,
            end_date=event.end_date,
            discipline=event.discipline,
            year=event.year,
            gymnast_count=gymnast_count,
        )
    finally:
        session.close()