import json
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, Header, UploadFile, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel
from sqlalchemy import func

from app.auth import (
    create_token,
    decode_token,
    get_current_user,
    hash_password,
    is_auth_configured,
    require_role,
    seed_admin_user,
    verify_password,
)
from app.cache import cache_headers, invalidate
from app.database import get_session, init_db
from app.models import Event, LongScore, User
from app.parser import ParseError, _NAME_TO_CANONICAL, find_unknown_clubs, parse_json, reload_club_maps, validate_upload_structure
from app.reconcile import reconcile_athletes
from app.schemas import (
    ClubItem,
    EventListItem,
    EventResponse,
    EventUpdate,
    GymnastItem,
    LoginRequest,
    RankingsResponse,
    RankingRow,
    ReconcileReport,
    ResultsResponse,
    StatsResponse,
    StepsResponse,
    TokenResponse,
    UploadValidationResponse,
    UserCreate,
    UserResponse,
    UserUpdate,
)
from app.transformer import export_csv, export_xlsx, pivot_to_wide, pivot_to_wide_dict


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    admin = seed_admin_user()
    if admin:
        print(f"  Admin user '{admin}' ready (set ADMIN_PASSWORD to disable auth)")
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
def get_stats(response: Response):
    response.headers.update(cache_headers())
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


@app.get("/api/clubs", response_model=list[ClubItem])
def list_clubs(response: Response):
    response.headers.update(cache_headers())
    session = get_session()
    try:
        rows = (
            session.query(
                LongScore.club_name,
                func.count(func.distinct(LongScore.gymnast_name)).label("gymnast_count"),
            )
            .filter(LongScore.club_name.isnot(None), LongScore.club_name != "")
            .group_by(LongScore.club_name)
            .order_by(LongScore.club_name)
            .all()
        )
        club_data_path = Path(__file__).resolve().parent.parent / "clubs_and_regions.json"
        if club_data_path.exists():
            with open(club_data_path) as f:
                club_data = json.load(f)

        def find_region(club_name: str) -> str | None:
            lower = club_name.lower().strip()
            # Direct region name match (e.g. Nationals where org is the region)
            for region_name in club_data.get("regions", {}):
                if lower == region_name.lower():
                    return region_name
            # Direct match against lookup (aliases cover most variants)
            v = club_data.get("lookup", {}).get(lower)
            if v:
                return v["region"] or _region_from_canonical(v["name"])
            # Prefix fallback: "Levin Gymnastics" → "Levin Gymnastics Club"
            return _region_from_prefix(lower)

        def _region_from_canonical(canonical: str) -> str | None:
            for region_name, clubs in club_data.get("regions", {}).items():
                for c in clubs:
                    if c["name"].lower() == canonical.lower():
                        return region_name
            return None

        def _region_from_prefix(lower: str) -> str | None:
            for region_name, clubs in club_data.get("regions", {}).items():
                for c in clubs:
                    for name in [c["name"]] + c.get("aliases", []):
                        ln = name.lower()
                        if lower.startswith(ln) or ln.startswith(lower):
                            return region_name
            return None

        items: list[ClubItem] = []
        for name, count in rows:
            region = find_region(name)
            items.append(ClubItem(
                name=name,
                gymnast_count=count,
                region=region,
                is_region=region is not None and name.lower() == region.lower(),
            ))
        return items
    finally:
        session.close()


@app.get("/api/gymnasts", response_model=list[GymnastItem])
def list_gymnasts(response: Response):
    response.headers.update(cache_headers())
    session = get_session()
    try:
        rows = (
            session.query(LongScore.gnz_id, LongScore.gymnast_name, LongScore.club_name)
            .filter(LongScore.gnz_id.isnot(None), LongScore.gnz_id != "")
            .group_by(LongScore.gnz_id, LongScore.gymnast_name)
            .order_by(LongScore.gymnast_name)
            .all()
        )
        return [GymnastItem(gnz_id=g, name=n, club=c) for g, n, c in rows]
    finally:
        session.close()


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

@app.get("/api/auth/status")
def auth_status(authorization: str | None = Header(None)):
    resp = {"configured": is_auth_configured()}
    if authorization:
        scheme, _, token = authorization.partition(" ")
        if scheme.lower() == "bearer":
            payload = decode_token(token)
            if payload:
                resp["user"] = {"username": payload["sub"], "role": payload["role"]}
    return resp


@app.post("/api/auth/login", response_model=TokenResponse)
def auth_login(body: LoginRequest):
    if not is_auth_configured():
        raise HTTPException(400, "Auth not configured")
    session = get_session()
    try:
        user = session.query(User).filter(User.username == body.username).first()
        if not user or not verify_password(body.password, user.hashed_password):
            raise HTTPException(401, "Invalid username or password")
        token = create_token(user.username, user.role)
        return TokenResponse(access_token=token, username=user.username, role=user.role)
    finally:
        session.close()


@app.post("/api/auth/register", response_model=UserResponse)
def auth_register(body: UserCreate, _auth=Depends(require_role("admin"))):
    session = get_session()
    try:
        existing = session.query(User).filter(User.username == body.username).first()
        if existing:
            raise HTTPException(409, "Username already exists")
        hashed = hash_password(body.password)
        user = User(username=body.username, hashed_password=hashed, role=body.role)
        session.add(user)
        session.commit()
        return UserResponse(id=user.id, username=user.username, role=user.role, created_at=user.created_at)
    finally:
        session.close()


@app.get("/api/auth/users", response_model=list[UserResponse])
def list_users(_auth=Depends(require_role("admin")), current_user: dict = Depends(get_current_user)):
    session = get_session()
    try:
        users = session.query(User).order_by(User.created_at).all()
        return [
            UserResponse(id=u.id, username=u.username, role=u.role, created_at=u.created_at)
            for u in users
        ]
    finally:
        session.close()


@app.post("/api/auth/users/{user_id}/reset-password")
def reset_password(user_id: int, body: UserUpdate, _auth=Depends(require_role("admin"))):
    session = get_session()
    try:
        user = session.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(404, "User not found")
        user.hashed_password = hash_password(body.password)
        session.commit()
        return {"ok": True}
    finally:
        session.close()


@app.delete("/api/auth/users/{user_id}")
def delete_user(user_id: int, _auth=Depends(require_role("admin")), current_user: dict = Depends(get_current_user)):
    session = get_session()
    try:
        user = session.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(404, "User not found")
        if user.username == current_user["username"]:
            raise HTTPException(400, "Cannot delete yourself")
        session.delete(user)
        session.commit()
        return {"ok": True}
    finally:
        session.close()


class AliasUpdate(BaseModel):
    aliases: dict[str, str]


@app.post("/api/clubs/aliases")
def save_aliases(body: AliasUpdate, _auth=Depends(require_role("admin"))):
    path = Path(__file__).resolve().parent.parent / "clubs_and_regions.json"
    with open(path) as f:
        data = json.load(f)
    for unknown, known in body.aliases.items():
        lower = unknown.lower().strip()
        if lower in data["lookup"]:
            continue
        region = ""
        for region_name, region_clubs in data.get("regions", {}).items():
            for c in region_clubs:
                if c["name"].lower() == known.lower():
                    region = region_name
                    existing = [a.lower() for a in c.get("aliases", [])]
                    if lower not in existing:
                        c.setdefault("aliases", []).append(unknown)
                    break
            if region:
                break
        data["lookup"][lower] = {"name": known, "region": region}
    with open(path, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    reload_club_maps()
    invalidate()
    return {"ok": True}


# ---------------------------------------------------------------------------
# Rankings (member+)
# ---------------------------------------------------------------------------

@app.get("/api/years")
def list_years(response: Response):
    response.headers.update(cache_headers())
    session = get_session()
    try:
        years = (
            session.query(Event.year)
            .filter(Event.year.isnot(None))
            .distinct()
            .order_by(Event.year.desc())
            .all()
        )
        return {"years": [y[0] for y in years]}
    finally:
        session.close()


@app.get("/api/rankings/steps", response_model=StepsResponse)
def list_ranking_steps(year: int, discipline: str, _auth=Depends(require_role("admin", "member"))):
    session = get_session()
    try:
        steps = (
            session.query(LongScore.level_category)
            .join(Event)
            .filter(
                Event.year == year,
                Event.is_national == False,
                LongScore.discipline == discipline,
                LongScore.level_category.isnot(None),
                LongScore.aa_score.isnot(None),
            )
            .distinct()
            .order_by(LongScore.level_category)
            .all()
        )
        return StepsResponse(steps=[s[0] for s in steps])
    finally:
        session.close()


@app.get("/api/rankings", response_model=RankingsResponse)
def get_rankings(
    year: int,
    step: str,
    discipline: str,
    _auth=Depends(require_role("admin", "member")),
):
    session = get_session()
    try:
        event_ids = [
            e.id
            for e in session.query(Event).filter(
                Event.year == year,
                Event.is_national == False,
            ).all()
        ]
        if not event_ids:
            return RankingsResponse(year=year, step=step, discipline=discipline, rankings=[])

        rows = (
            session.query(
                LongScore.gymnast_name,
                LongScore.gnz_id,
                LongScore.club_name,
                LongScore.event_id,
                LongScore.event_name,
                func.max(LongScore.aa_score),
            )
            .filter(
                LongScore.event_id.in_(event_ids),
                LongScore.level_category == step,
                LongScore.discipline == discipline,
                LongScore.aa_score.isnot(None),
            )
            .group_by(
                LongScore.gymnast_name,
                LongScore.gnz_id,
                LongScore.club_name,
                LongScore.event_id,
                LongScore.event_name,
            )
            .all()
        )

        from collections import defaultdict

        gymnast_data: dict[str, dict] = {}
        for name, gnz_id, club, eid, ename, aa_score in rows:
            key = name
            if key not in gymnast_data:
                gymnast_data[key] = {
                    "name": name,
                    "gnz_id": gnz_id or "",
                    "club": club,
                    "scores": [],
                    "competitions": [],
                }
            gymnast_data[key]["scores"].append(float(aa_score))
            gymnast_data[key]["competitions"].append(ename)

        ranking_list = []
        for data in gymnast_data.values():
            scores = data["scores"]
            comps = data["competitions"]
            paired = sorted(zip(scores, comps), key=lambda x: -x[0])
            top_two = paired[:2]
            data["scores"] = [s for s, _ in top_two]
            data["competitions"] = [c for _, c in top_two]
            data["total"] = sum(data["scores"])
            ranking_list.append(data)

        ranking_list.sort(key=lambda x: -x["total"])

        rank = 1
        prev_total = None
        for i, entry in enumerate(ranking_list):
            if prev_total is not None and entry["total"] < prev_total:
                rank = i + 1
            entry["rank"] = rank
            prev_total = entry["total"]

        for i, entry in enumerate(ranking_list):
            if i > 0 and entry["total"] == ranking_list[i - 1]["total"]:
                entry["rank_text"] = f"T{entry['rank']}"
            elif i < len(ranking_list) - 1 and entry["total"] == ranking_list[i + 1]["total"]:
                entry["rank_text"] = f"T{entry['rank']}"
            else:
                entry["rank_text"] = str(entry["rank"])

        rankings = [
            RankingRow(
                rank=r["rank_text"],
                name=r["name"],
                gnz_id=r["gnz_id"],
                club=r["club"],
                scores=r["scores"],
                competitions=r["competitions"],
                total=round(r["total"], 3),
            )
            for r in ranking_list
        ]

        return RankingsResponse(year=year, step=step, discipline=discipline, rankings=rankings)
    finally:
        session.close()


@app.post("/api/admin/reconcile-athletes", response_model=ReconcileReport)
def admin_reconcile(_auth=Depends(require_role("admin"))):
    report = reconcile_athletes()
    invalidate()
    return report


# ---------------------------------------------------------------------------
# Upload
# ---------------------------------------------------------------------------

@app.post("/api/upload", response_model=EventResponse)
def upload_file(file: UploadFile = File(...), allow_unknown: str = None, _auth=Depends(require_role("admin"))):
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

    unknown = find_unknown_clubs(data)
    if unknown and not allow_unknown:
        known = sorted(set(_NAME_TO_CANONICAL.values()))
        raise HTTPException(409, {
            "message": "Unknown club names found",
            "unknown_clubs": unknown,
            "known_clubs": known,
        })

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
        invalidate()

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
def list_events(response: Response):
    response.headers.update(cache_headers())
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
                    is_national=bool(ev.is_national),
                )
            )
        return result
    finally:
        session.close()


# ---------------------------------------------------------------------------
# Results (raw long-format)
# ---------------------------------------------------------------------------

@app.get("/api/events/{event_id}/results", response_model=ResultsResponse)
def get_results(event_id: int, response: Response):
    response.headers.update(cache_headers())
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
def get_results_wide(event_id: int, response: Response):
    response.headers.update(cache_headers())
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
def get_all_results_wide(response: Response, gnz_id: str = None, club: str = None, year: int = None):
    response.headers.update(cache_headers())
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
def export_event_csv(event_id: int, response: Response):
    response.headers.update(cache_headers())
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
def export_event_xlsx(event_id: int, response: Response):
    response.headers.update(cache_headers())
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
def delete_event(event_id: int, _auth=Depends(require_role("admin"))):
    session = get_session()
    try:
        event = session.query(Event).filter(Event.id == event_id).first()
        if not event:
            raise HTTPException(404, "Event not found")
        session.delete(event)
        session.commit()
        invalidate()
        return {"ok": True}
    finally:
        session.close()


# ---------------------------------------------------------------------------
# Update event
# ---------------------------------------------------------------------------

@app.patch("/api/events/{event_id}", response_model=EventListItem)
def update_event(event_id: int, body: EventUpdate, _auth=Depends(require_role("admin"))):
    session = get_session()
    try:
        event = session.query(Event).filter(Event.id == event_id).first()
        if not event:
            raise HTTPException(404, "Event not found")
        if body.name is not None:
            event.name = body.name
            session.query(LongScore).filter(LongScore.event_id == event_id).update(
                {"event_name": body.name}
            )
        if body.is_national is not None:
            event.is_national = body.is_national
        session.commit()
        invalidate()
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
            is_national=bool(event.is_national),
        )
    finally:
        session.close()