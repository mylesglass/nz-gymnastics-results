import json
import time
from collections import defaultdict
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone

from fastapi import FastAPI, File, HTTPException, Header, Request, UploadFile, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel
from sqlalchemy import case, func

from app.activity_log import enqueue as enqueue_activity, flush as flush_activity, start as start_activity_writer, stop as stop_activity_writer, enqueue_traffic as enqueue_traffic_activity
from app.athlete_identity import rebuild_athletes, resolve_identity, _signature_hash, _slug_from_hash

from app.auth import (
    ALL_PERMISSIONS,
    DEFAULT_MEMBER_PERMISSIONS,
    PERMISSION_NATIONAL,
    PERMISSION_WELLINGTON,
    create_token,
    decode_token,
    effective_permissions,
    get_current_user,
    get_optional_user,
    get_user_permissions,
    hash_password,
    is_auth_configured,
    require_permission,
    require_role,
    seed_admin_user,
    verify_password,
)
from app.cache import cache, cache_headers, cached, invalidate
from app.clubdata import active_path, ensure_seed
from app.cloudflare import CloudflareFetchError, fetch_zone_summary, is_configured as cloudflare_is_configured
from app.database import get_session, init_db
from app.models import ACTIVITY_TYPE_API, ACTIVITY_TYPE_PAGE, ActivityLog, Athlete, Event, LongScore, SlugRedirect, TrafficDaily, User, WellingtonIntent
from app.parser import ParseError, _NAME_TO_CANONICAL, detect_participant_collisions, find_unknown_clubs, parse_json, reload_club_maps, suggest_club_mapping, validate_upload_structure
from app.reconcile import reconcile_athletes
from app.scoreholder import ScoreholderFetchError, fetch_event_json
from app.schemas import (
    ApparatusLeaderboard,
    ApparatusRankingRow,
    ApparatusRankingsResponse,
    ApparatusSpecialistRow,
    ApplyFixItem,
    ActivityLogItem,
    ActivityLogResponse,
    ActivitySummaryResponse,
    ActivityTotals,
    ClubMedals,
    CloudflareSummaryResponse,
    ClubItem,
    ConflictItem,
    DuplicateGroup,
    DuplicateInstance,
    EventListItem,
    EventResponse,
    EventUpdate,
    FixDuplicatesResponse,
    GymnastEditRequest,
    GymnastEditResponse,
    GymnastItem,
    GymnastMedals,
    HourPoint,
    IdConflict,
    IdentityReviewResponse,
    ImportUrlRequest,
    IntentToggle,
    KnownClubItem,
    LoginRequest,
    MedalCounts,
    MedalsResponse,
    MergeAthletesRequest,
    MergeAthletesResponse,
    MergeChangeRow,
    MergeNamesRequest,
    MergePairPreview,
    MergePreviewRequest,
    MergePreviewResponse,
    MultiIdAthlete,
    NameConflict,
    RankingsResponse,
    RankingRow,
    ResultsResponse,
    SimilarAthletes,
    SplitAthleteRequest,
    SplitAthleteResponse,
    StatsResponse,
    StepsResponse,
    SuggestedMerge,
    TokenResponse,
    TopPath,
    TopUser,
    TrackPageRequest,
    TrafficPoint,
    UploadValidationResponse,
    UserCreate,
    UserPermissionsUpdate,
    UserResponse,
    UserUpdate,
    WellingtonNotRankedRow,
    WellingtonRankingRow,
    WellingtonRankingResponse,
)
from app.traffic import is_bot, normalize_path
from app.transformer import _find_region, _guess_host_club, _use_vault_average, export_csv, export_xlsx, pivot_to_wide, pivot_to_wide_dict, pivot_to_wide_dict_multi
from app.wellington_ranking import compute_wellington_rankings


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    admin = seed_admin_user()
    if admin:
        print(f"  Admin user '{admin}' ready (set ADMIN_PASSWORD to disable auth)")
    start_activity_writer()
    yield
    stop_activity_writer()


app = FastAPI(title="NZ Gymnastics Results API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def add_cache_control(request: Request, call_next):
    response: Response = await call_next(request)
    path = request.url.path

    if request.method == "GET" and (
        path.startswith("/api/events")
        or path.startswith("/api/results")
        or path == "/api/stats"
        or path == "/api/medals"
        or path == "/api/clubs"
        or path == "/api/gymnasts"
        or path == "/api/years"
    ):
        if not response.headers.get("Cache-Control"):
            response.headers["Cache-Control"] = "public, max-age=300, stale-while-revalidate=60"
    elif (
        path.startswith("/api/admin")
        or request.method in ("POST", "PUT", "DELETE", "PATCH")
    ):
        response.headers["Cache-Control"] = "no-store, no-cache, private"

    return response


def _log_activity(
    username: str,
    role: str,
    type_: str,
    method: str | None,
    path: str,
    query: str | None,
    status_code: int | None,
    duration_ms: float | None,
) -> None:
    """Queue one activity log row (written in the background)."""
    enqueue_activity(
        username=username,
        role=role,
        type_=type_,
        method=method,
        path=path,
        query=query,
        status_code=status_code,
        duration_ms=duration_ms,
    )


@app.middleware("http")
async def log_activity(request: Request, call_next):
    """Record API traffic for admin review.

    Authenticated requests are written as detail rows to ``activity_logs`` (who
    did what when) and every request is counted into the ``traffic_daily``
    aggregates (page vs API, anonymous vs logged-in) so usage of the whole site
    is visible. Anonymous bot user-agents are excluded. The page-tracking
    beacon and admin activity views are handled separately and never
    self-log. Failures never affect the request itself.
    """
    start = time.perf_counter()
    response = await call_next(request)
    duration_ms = (time.perf_counter() - start) * 1000.0

    path = request.url.path
    if (
        path == "/api/track/page"
        or path.startswith("/api/admin/activity")
        or path == "/api/health"
        or not path.startswith("/api")
    ):
        return response

    authorization = request.headers.get("authorization")
    payload = None
    if authorization:
        scheme, _, token = authorization.partition(" ")
        if scheme.lower() == "bearer":
            payload = decode_token(token)

    if payload is None:
        if is_bot(request.headers.get("user-agent")):
            return response
        enqueue_traffic_activity(
            ACTIVITY_TYPE_API,
            normalize_path(path),
            anonymous=True,
            status_code=response.status_code,
            duration_ms=round(duration_ms, 2),
        )
        return response

    query = request.url.query or None
    _log_activity(
        payload["sub"],
        payload.get("role", "member"),
        ACTIVITY_TYPE_API,
        request.method,
        path[:500],
        (query or "")[:1000],
        response.status_code,
        round(duration_ms, 2),
    )
    enqueue_traffic_activity(
        ACTIVITY_TYPE_API,
        normalize_path(path),
        anonymous=False,
        status_code=response.status_code,
        duration_ms=round(duration_ms, 2),
    )
    return response


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/stats")
def get_stats(response: Response):
    response.headers.update(cache_headers())
    data = cached(("stats",), lambda: _compute_stats(), ttl=300)
    return data


def _compute_stats() -> StatsResponse:
    session = get_session()
    try:
        return StatsResponse(
            total_events=session.query(func.count(Event.id)).scalar() or 0,
            total_gymnasts=session.query(func.count(func.distinct(func.coalesce(LongScore.athlete_id, LongScore.gymnast_name)))).scalar() or 0,
            total_scores=session.query(func.count(LongScore.id)).scalar() or 0,
            total_clubs=session.query(func.count(func.distinct(LongScore.club_name))).scalar() or 0,
        )
    finally:
        session.close()


# Round types where an all-around ranking is a real award. "Apparatus Finals"
# and "Day 2" rounds never carry an AA medal.
_AA_MEDAL_ROUND_TYPES = ("All Around", "All Around - Final", "All Around - Day 2", "All Around, Teams", "Team")


@app.get("/api/medals", response_model=MedalsResponse)
def get_medals(response: Response, year: int = None, gnz_id: str = None, club: str = None, athlete_id: int = None, slug: str = None):
    response.headers.update(cache_headers())
    return cached(
        ("medals", year or "", gnz_id or "", club or "", athlete_id or "", slug or ""),
        lambda: _compute_medals(year, gnz_id, club, athlete_id, slug),
        ttl=300,
    )


def _compute_medals(year: int | None, gnz_id: str | None, club: str | None, athlete_id: int | None = None, slug: str | None = None) -> MedalsResponse:
    """Aggregate gold/silver/bronze tallies per gymnast and club.

    Medals are counted by rank value (1 = gold, 2 = silver, 3 = bronze) from
    the stored apparatus/AA ranks, deduped so multi-pass vaults and the AA
    rank duplicated across a gymnast's apparatus rows count once. Every
    competition (including National Championships) and every team entry is
    treated the same. Gymnasts are keyed on ``athlete_id`` (falling back to a
    name key for rows with no identity assigned).
    """
    from collections import defaultdict

    session = get_session()
    try:
        query = (
            session.query(
                LongScore.event_id,
                LongScore.athlete_id,
                LongScore.gnz_id,
                LongScore.gymnast_name,
                LongScore.club_name,
                LongScore.apparatus,
                LongScore.round_type,
                LongScore.apparatus_rank,
                LongScore.aa_rank,
            )
            .join(Event, Event.id == LongScore.event_id)
        )
        if year:
            query = query.filter(Event.year == year)
        if athlete_id:
            query = query.filter(LongScore.athlete_id == athlete_id)
        elif slug:
            resolved = resolve_identity(session, slug=slug)
            if resolved is None:
                return MedalsResponse(year=year, gymnasts=[], clubs=[])
            query = query.filter(LongScore.athlete_id == resolved)
        elif gnz_id:
            resolved = resolve_identity(session, gnz_id=gnz_id)
            if resolved is None:
                query = query.filter(LongScore.gnz_id == gnz_id)
            else:
                query = query.filter(LongScore.athlete_id == resolved)
        if club:
            query = query.filter(LongScore.club_name == club)
        rows = query.all()

        slug_by_id = {a.id: a.slug for a in session.query(Athlete).all()}
        awards: list[tuple[str, int, str | None]] = []
        app_seen: set[tuple] = set()
        aa_seen: set[tuple] = set()
        entity_meta: dict[str, tuple[str, str | None, str | None, str]] = {}

        for (event_id, aid, gid, name, club_name, apparatus, round_type,
             app_rank, aa_rank) in rows:
            if aid:
                entity_key = f"id:{aid}"
            else:
                entity_key = f"name:{name.strip().lower()}"
            if entity_key not in entity_meta:
                entity_meta[entity_key] = (name, gid, club_name, slug_by_id.get(aid) or "")
            if app_rank in (1, 2, 3):
                unit = (event_id, entity_key, apparatus, round_type or "")
                if unit not in app_seen:
                    app_seen.add(unit)
                    awards.append((entity_key, app_rank, club_name))
            if aa_rank in (1, 2, 3) and round_type in _AA_MEDAL_ROUND_TYPES:
                unit = (event_id, entity_key, round_type or "")
                if unit not in aa_seen:
                    aa_seen.add(unit)
                    awards.append((entity_key, aa_rank, club_name))

        def _init_counts() -> dict:
            return {"g": 0, "s": 0, "b": 0, "total": 0}

        def _add(totals: dict, rank: int) -> None:
            key = {1: "g", 2: "s", 3: "b"}[rank]
            totals[key] += 1
            totals["total"] += 1

        gymnast = defaultdict(_init_counts)
        club_counts = defaultdict(_init_counts)

        for entity_key, rank, club_name in awards:
            _add(gymnast[entity_key], rank)
            if club_name:
                _add(club_counts[club_name], rank)

        gymnasts = [
            GymnastMedals(
                slug=meta[3],
                gnz_id=meta[1] or "",
                name=meta[0],
                club=meta[2],
                medals=MedalCounts(**gymnast[k]),
            )
            for k, meta in entity_meta.items()
            if k in gymnast and gymnast[k]["total"] > 0
        ]
        clubs = [
            ClubMedals(
                name=name,
                medals=MedalCounts(**club_counts[name]),
            )
            for name in club_counts
            if club_counts[name]["total"] > 0
        ]
        gymnasts.sort(key=lambda x: x.name.lower())
        clubs.sort(key=lambda x: x.name.lower())
        return MedalsResponse(year=year, gymnasts=gymnasts, clubs=clubs)
    finally:
        session.close()


@app.get("/api/clubs", response_model=list[ClubItem])
def list_clubs(response: Response):
    response.headers.update(cache_headers())
    data = cached(("clubs",), lambda: _compute_clubs(), ttl=300)
    return data


@app.get("/api/clubs/known", response_model=list[KnownClubItem])
def list_known_clubs(response: Response):
    """Return the canonical club list (with regions) from clubs_and_regions.json.

    Used by the host-club picker on the upload and events pages.
    """
    response.headers.update(cache_headers())
    data = cached(("clubs-known",), lambda: _compute_known_clubs(), ttl=300)
    return data


def _compute_known_clubs() -> list[KnownClubItem]:
    with open(active_path()) as f:
        club_data = json.load(f)
    items: list[KnownClubItem] = []
    for region_name, clubs in club_data.get("regions", {}).items():
        for c in clubs:
            items.append(KnownClubItem(name=c["name"], region=region_name))
    items.sort(key=lambda x: (x.region, x.name))
    return items


def _compute_clubs() -> list[ClubItem]:
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
        if active_path().exists():
            with open(active_path()) as f:
                club_data = json.load(f)

        def find_region(club_name: str) -> str | None:
            lower = club_name.lower().strip()
            for region_name in club_data.get("regions", {}):
                if lower == region_name.lower():
                    return region_name
            v = club_data.get("lookup", {}).get(lower)
            if v:
                return v["region"] or _region_from_canonical(v["name"])
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
def list_gymnasts(response: Response, year: int = None):
    response.headers.update(cache_headers())
    data = cached(("gymnasts", year or ""), lambda: _compute_gymnasts(year), ttl=300)
    return data


def _compute_gymnasts(year: int | None) -> list[GymnastItem]:
    from collections import defaultdict

    session = get_session()
    try:
        query = (
            session.query(LongScore.gymnast_name, LongScore.gnz_id, LongScore.club_name, LongScore.athlete_id)
            .join(Event, Event.id == LongScore.event_id)
            .filter(LongScore.gnz_id.isnot(None), LongScore.gnz_id != "")
            .distinct()
        )
        if year:
            query = query.filter(Event.year == year)
        rows = query.all()

        name_groups: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
        club_groups: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
        name_casing: dict[str, str] = {}
        athletes = {a.id: a for a in session.query(Athlete).all()}

        for name, gnz_id, club, athlete_id in rows:
            if athlete_id and athlete_id in athletes:
                key = f"id:{athlete_id}"
                canonical = athletes[athlete_id].canonical_name or name.strip()
            else:
                key = name.strip().lower()
                canonical = name.strip()
            name_casing[key] = name_casing.get(key, canonical)
            name_groups[key][gnz_id or ""] += 1
            club_groups[key][club or ""] += 1

        result = []
        for key in sorted(name_groups):
            ids = name_groups[key]
            clubs = club_groups[key]
            sorted_ids = sorted(ids.items(), key=lambda x: (-x[1], x[0].isdigit(), x[0]))
            best_id = sorted_ids[0][0]
            alt_ids = [gid for gid, _ in sorted_ids[1:]]

            sorted_clubs = sorted(clubs.items(), key=lambda x: (-x[1], x[0]))
            best_club = sorted_clubs[0][0] or None
            alt_clubs = [c for c, _ in sorted_clubs[1:]]

            slug = ""
            if key.startswith("id:"):
                athlete = athletes.get(int(key.split(":")[1]))
                slug = athlete.slug if athlete else ""

            result.append(GymnastItem(
                slug=slug,
                gnz_id=best_id,
                name=name_casing[key],
                club=best_club,
                alt_ids=alt_ids,
                alt_clubs=alt_clubs,
            ))

        result.sort(key=lambda x: x.name.lower())
        return result
    finally:
        session.close()


@app.get("/api/gymnast", response_model=GymnastItem | None)
def get_gymnast(response: Response, gnz_id: str = None, slug: str = None):
    """Return a single gymnast's identity record (name, slug, club) by slug or gnz_id."""
    response.headers.update(cache_headers())
    if not slug and not gnz_id:
        return None
    return cached(
        ("gymnast", slug or "", gnz_id or ""),
        lambda: _compute_gymnast(slug, gnz_id),
        ttl=300,
    )


def _compute_gymnast(slug: str | None, gnz_id: str | None) -> GymnastItem | None:
    session = get_session()
    try:
        if slug:
            athlete = session.query(Athlete).filter(Athlete.slug == slug).first()
            if athlete is None:
                # Old slug from a merged-away (or re-keyed) identity: redirect
                # to the athlete that absorbed it, so the frontend 301s to the
                # survivor's canonical URL instead of 404ing.
                redirect = (
                    session.query(SlugRedirect)
                    .filter(SlugRedirect.old_slug == slug)
                    .first()
                )
                if redirect is not None:
                    athlete = session.get(Athlete, redirect.athlete_id)
        elif gnz_id:
            matches = session.query(Athlete).filter(Athlete.gnz_id == gnz_id).all()
            athlete = matches[0] if len(matches) == 1 else None
        else:
            return None

        if athlete is None and gnz_id:
            # No athlete cluster — fall back to the raw name row(s) for a gnz_id.
            rows = (
                session.query(LongScore.gymnast_name, LongScore.club_name)
                .filter(LongScore.gnz_id == gnz_id)
                .order_by(LongScore.gymnast_name)
                .all()
            )
            if not rows:
                return None
            name = rows[0][0].strip()
            clubs = {c for _, c in rows if c}
            club = sorted(clubs)[0] if clubs else None
            return GymnastItem(slug="", gnz_id=gnz_id or "", name=name, club=club)

        if athlete is None:
            return None

        club = (
            session.query(LongScore.club_name)
            .filter(LongScore.athlete_id == athlete.id, LongScore.club_name.isnot(None))
            .first()
        )
        return GymnastItem(
            slug=athlete.slug,
            gnz_id=athlete.gnz_id or "",
            name=athlete.canonical_name,
            club=club[0] if club else None,
        )
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
                resp["user"] = {
                    "username": payload["sub"],
                    "role": payload["role"],
                    "permissions": get_user_permissions(payload["sub"]),
                }
    return resp


@app.get("/api/auth/me")
def auth_me(_auth=Depends(get_current_user)):
    session = get_session()
    try:
        user = session.query(User).filter(User.username == _auth["username"]).first()
    finally:
        session.close()
    if not user:
        raise HTTPException(404, "User not found")
    return {
        "username": user.username,
        "role": user.role,
        "permissions": effective_permissions(user.role, user.permissions),
    }


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
        permissions = effective_permissions(user.role, user.permissions)
        return TokenResponse(
            access_token=token,
            username=user.username,
            role=user.role,
            permissions=permissions,
        )
    finally:
        session.close()


@app.post("/api/auth/register", response_model=UserResponse)
def auth_register(body: UserCreate, _auth=Depends(require_role("admin"))):
    session = get_session()
    try:
        existing = session.query(User).filter(User.username == body.username).first()
        if existing:
            raise HTTPException(409, "Username already exists")
        role = body.role or "member"
        if role == "admin":
            permissions = ALL_PERMISSIONS
        elif body.permissions:
            permissions = [p for p in body.permissions if p in ALL_PERMISSIONS]
        else:
            permissions = DEFAULT_MEMBER_PERMISSIONS
        hashed = hash_password(body.password)
        user = User(
            username=body.username,
            hashed_password=hashed,
            role=role,
            permissions=",".join(permissions),
        )
        session.add(user)
        session.commit()
        return UserResponse(
            id=user.id,
            username=user.username,
            role=user.role,
            permissions=permissions,
            created_at=user.created_at,
        )
    finally:
        session.close()


@app.get("/api/auth/users", response_model=list[UserResponse])
def list_users(_auth=Depends(require_role("admin")), current_user: dict = Depends(get_current_user)):
    session = get_session()
    try:
        users = session.query(User).order_by(User.created_at).all()
        return [
            UserResponse(
                id=u.id,
                username=u.username,
                role=u.role,
                permissions=effective_permissions(u.role, u.permissions),
                created_at=u.created_at,
            )
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


@app.patch("/api/auth/users/{user_id}/permissions")
def update_permissions(user_id: int, body: UserPermissionsUpdate, _auth=Depends(require_role("admin"))):
    session = get_session()
    try:
        user = session.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(404, "User not found")
        if user.role == "admin":
            permissions = ALL_PERMISSIONS
        else:
            permissions = [p for p in body.permissions if p in ALL_PERMISSIONS]
        user.permissions = ",".join(permissions)
        session.commit()
        return {
            "ok": True,
            "permissions": permissions,
        }
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
    path = ensure_seed()
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
def list_ranking_steps(year: int, discipline: str, _auth=Depends(require_permission(PERMISSION_NATIONAL, PERMISSION_WELLINGTON))):
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
                LongScore.pass_final_score.isnot(None),
            )
            .distinct()
            .order_by(LongScore.level_category)
            .all()
        )
        return StepsResponse(steps=[s[0] for s in steps])
    finally:
        session.close()


# Gymnastics NZ qualifying marks for the national rankings qualifier filter.
# ``count`` marks at or above ``mark`` are required, each from a distinct
# competition (per-event marks are distinct by construction). ``away`` rules
# additionally need one qualifying mark from an event whose host club's region
# differs from the athlete's home province (region of their club).
_QUALIFIER_CONFIG: dict[str, dict] = {
    "STEP 5": {"mark": 50.0, "count": 2, "away": True},
    "STEP 6": {"mark": 50.0, "count": 2, "away": True},
    "STEP 7": {"mark": 43.0, "count": 2},
    "STEP 8": {"mark": 43.0, "count": 2},
    "STEP 9": {"mark": 43.0, "count": 2},
    "STEP 10": {"mark": 43.0, "count": 2},
    "Youth International": {"mark": 42.5, "count": 1},
    "Junior International": {"mark": 43.0, "count": 1},
    "Senior International": {"mark": 45.0, "count": 1},
    "Level 7": {"mark": 63.0, "count": 1},
    "Level 8": {"mark": 63.0, "count": 1},
    "Level 9": {"mark": 63.0, "count": 1},
    "U18": {"mark": 63.0, "count": 1},
    "Senior Open": {"mark": 63.0, "count": 1},
}


# Number of marks used for the national ranking per step. STEP 5/6 rank on the
# AVERAGE of their top 3 competition scores; all other steps use the top 2.
_RANKING_MARKS: dict[str, int] = {
    "STEP 5": 3,
    "STEP 6": 3,
}

# Apparatus-qualifier section thresholds per step, mirroring the Wellington
# rankings. ``mark`` is a single threshold across all apparatus; ``marks`` is a
# per-apparatus dict. A gymnast qualifies as a specialist when they reach the
# threshold on ``count`` DISTINCT COMPETITIONS on the same apparatus (per-event
# apparatus scores are round-type-merged, vault per ``_use_vault_average``).
# The section lists gymnasts who aren't already in the (filtered) AA table.
_APPARATUS_QUALIFIER_CONFIG: dict[str, dict] = {
    "STEP 8": {"mark": 11.0, "count": 2},
    "STEP 9": {"mark": 11.0, "count": 2},
    "STEP 10": {"mark": 11.0, "count": 2},
    "Level 7": {"mark": 11.5, "count": 1},
    "Level 8": {"mark": 11.5, "count": 1},
    "Level 9": {"mark": 11.5, "count": 1},
    "U18": {"mark": 11.5, "count": 1},
    "Senior Open": {"mark": 11.5, "count": 1},
    "Junior International": {
        "marks": {"VT": 12.2, "UB": 10.4, "BB": 10.5, "FX": 11.4},
        "count": 1,
    },
    "Senior International": {
        "marks": {"VT": 12.5, "UB": 11.3, "BB": 11.2, "FX": 11.4},
        "count": 1,
    },
}

# Display-only season-mark indicator for low WAG steps: a ✓ is shown when the
# gymnast reached ``mark`` on ``count`` distinct competitions that season.
# Kept separate from ``_QUALIFIER_CONFIG`` so it never filters the ranking.
_MARK_INDICATOR: dict[str, dict] = {
    "STEP 1": {"mark": 52.0, "count": 2},
    "STEP 2": {"mark": 52.0, "count": 2},
    "STEP 3": {"mark": 52.0, "count": 2},
    "STEP 4": {"mark": 52.0, "count": 2},
}


def _reached_mark_twice(all_events: list[dict], step: str) -> bool:
    """Whether a gymnast reached the season-mark threshold ``count`` times.

    Each entry in ``all_events`` is a distinct competition, so reaching the
    mark on two entries means two different competitions.
    """
    cfg = _MARK_INDICATOR.get(step)
    if cfg is None:
        return False
    qualifying = [e for e in all_events if e["score"] >= cfg["mark"]]
    return len(qualifying) >= cfg["count"]


def _is_qualifier(all_events: list[dict], club: str, step: str) -> bool:
    """Check the GNZ qualifying-mark rules against all per-competition marks."""
    cfg = _QUALIFIER_CONFIG.get(step)
    if cfg is None:
        return True
    qualifying = [e for e in all_events if e["score"] >= cfg["mark"]]
    if len(qualifying) < cfg["count"]:
        return False
    if cfg.get("away"):
        home = _find_region(club or "")
        if not home:
            return False
        for e in qualifying:
            host_region = _find_region(e["host_club"] or "")
            if host_region and host_region != home:
                return True
        return False
    return True


def _build_event_marks(rows, step: str, athletes: dict[int, Athlete] | None = None):
    """Aggregate raw LongScore rows into per-competition and per-apparatus marks.

    Rows are grouped by (gymnast, event, round_type). Each group collapses to
    one competition score (best All Around mark, else the apparatus sum with
    vault per ``_use_vault_average``) and one score per apparatus, then round
    types merge so each (gymnast, event) contributes at most one mark.  Gymnast
    identity uses ``athlete_id`` (falling back to the name for unassigned
    rows), so spelling variants of one person rank as a single gymnast.

    Returns ``(per_event, apparatus_events, meta_by_key)`` where
    ``per_event`` maps ``(athlete_key, event_id)`` -> competition dict,
    ``apparatus_events`` maps athlete_key -> apparatus -> event_id ->
    ``{"score", "event_name", "d"}`` (``d`` is the D-score of the best pass,
    averaged when the vault is averaged) and ``meta_by_key`` holds the best
    display name/gnz_id/club.
    """
    athletes = athletes or {}
    event_groups: dict[tuple, list] = defaultdict(list)
    for r in rows:
        key = (
            r.athlete_id or r.gymnast_name, r.gymnast_name, r.gnz_id,
            r.club_name, r.event_id, r.event_name, r.round_type,
        )
        event_groups[key].append(r)

    per_event: dict[tuple, dict] = {}
    apparatus_events: dict[str, dict[str, dict[int, dict]]] = defaultdict(
        lambda: defaultdict(dict),
    )
    meta_by_key: dict[str, dict[str, str]] = {}
    for (a_key, name, gnz_id, club, eid, ename, rt), scores in event_groups.items():
        aa_values = [s.aa_score for s in scores if s.aa_score is not None]
        if aa_values:
            comp_score = float(max(aa_values))
        else:
            apparatus_scores: dict[str, list[float]] = defaultdict(list)
            for s in scores:
                if s.pass_final_score is not None:
                    apparatus_scores[s.apparatus or ""].append(float(s.pass_final_score))
            comp_score = 0.0
            for app, app_scores in apparatus_scores.items():
                if app == "VT" and len(app_scores) > 1:
                    if _use_vault_average(step, rt or ""):
                        comp_score += sum(app_scores) / len(app_scores)
                    else:
                        comp_score += max(app_scores)
                else:
                    comp_score += sum(app_scores)

        key2 = (a_key, eid)
        prev = per_event.get(key2)
        if prev is None or comp_score > prev["score"]:
            per_event[key2] = {
                "score": comp_score,
                "event_name": ename,
                "gnz_id": gnz_id or "",
                "club": club or "",
                "host_club": scores[0].host_club or "",
            }

        # Event-level apparatus score. Vault aggregates multiple passes per the
        # AA rules (average or best); ``d`` tracks the best pass (averaged when
        # the vault is averaged), matching ``_build_wide_row``.
        event_app_scores: dict[str, float] = {}
        event_app_ds: dict[str, float | None] = {}
        vt_totals: list[float] = []
        vt_ds: list[float | None] = []
        for s in scores:
            if s.pass_final_score is None:
                continue
            if s.apparatus == "VT":
                vt_totals.append(float(s.pass_final_score))
                vt_ds.append(s.d_score)
            else:
                score = float(s.pass_final_score)
                prev_app = event_app_scores.get(s.apparatus or "")
                if prev_app is None or score > prev_app:
                    event_app_scores[s.apparatus or ""] = score
                    event_app_ds[s.apparatus or ""] = s.d_score
        if vt_totals:
            if _use_vault_average(step, rt or ""):
                event_app_scores["VT"] = sum(vt_totals) / len(vt_totals)
                event_app_ds["VT"] = (
                    sum(d for d in vt_ds if d is not None) / len(vt_ds)
                    if all(d is not None for d in vt_ds) and vt_ds
                    else None
                )
            else:
                best_idx = max(range(len(vt_totals)), key=lambda i: vt_totals[i])
                event_app_scores["VT"] = vt_totals[best_idx]
                event_app_ds["VT"] = vt_ds[best_idx]
        for app, score in event_app_scores.items():
            prev_app = apparatus_events[a_key][app].get(eid)
            if prev_app is None or score > prev_app["score"]:
                apparatus_events[a_key][app][eid] = {
                    "score": score,
                    "event_name": ename,
                    "d": event_app_ds.get(app),
                }

        if a_key not in meta_by_key:
            meta_by_key[a_key] = {"name": name, "gnz_id": gnz_id or "", "club": club or ""}
        else:
            if not meta_by_key[a_key]["gnz_id"] and gnz_id:
                meta_by_key[a_key]["gnz_id"] = gnz_id
            if not meta_by_key[a_key]["club"] and club:
                meta_by_key[a_key]["club"] = club

    for a_key, meta in meta_by_key.items():
        if isinstance(a_key, int) and a_key in athletes:
            meta["name"] = athletes[a_key].canonical_name or meta["name"]

    return per_event, apparatus_events, meta_by_key


def _compute_apparatus_specialists(
    apparatus_events: dict[str, dict[str, dict[int, dict]]],
    step: str,
    meta_by_key: dict[str, dict[str, str]],
    exclude_names: set[str] | None = None,
    athletes: dict[int, Athlete] | None = None,
) -> tuple[list[dict], float | None, int]:
    """Build the national apparatus-qualifier section for a step.

    Every gymnast who reached the step's apparatus threshold on ``count``
    distinct competitions on the same apparatus, unless their key is in
    ``exclude_names`` (the qualifier-filtered All Around table, when the
    ``qualifier`` filter is on). Returns ``(specialists, single-float mark,
    count)`` where the single-float mark is ``None`` for per-apparatus-threshold
    steps.
    """
    athletes = athletes or {}
    cfg = _APPARATUS_QUALIFIER_CONFIG.get(step)
    if cfg is None:
        return [], None, 2
    app_threshold = cfg.get("mark")
    app_scores_by_app = cfg.get("marks")
    app_count = cfg.get("count", 2)

    specialists = []
    for key, app_events in apparatus_events.items():
        if exclude_names and key in exclude_names:
            continue
        meta = meta_by_key.get(key, {"name": str(key), "gnz_id": "", "club": ""})
        club = meta["club"]
        slug = ""
        if isinstance(key, int):
            slug = athletes[key].slug if key in athletes else ""
        qualifying: list[dict] = []
        partial: list[dict] = []
        for app, events in app_events.items():
            threshold = (
                app_scores_by_app.get(app, float("inf"))
                if app_scores_by_app is not None
                else app_threshold
            )
            hits = sorted(
                (e for e in events.values() if e["score"] >= threshold),
                key=lambda x: -x["score"],
            )
            if not hits:
                continue
            best = hits[0]
            entry = {
                "app": app,
                "best": round(best["score"], 3),
                "event": best["event_name"],
                "count": len(hits),
                "competitions": sorted({h["event_name"] for h in hits}),
            }
            if len(hits) >= app_count:
                qualifying.append(entry)
            else:
                partial.append(entry)

        if qualifying:
            qualifying.sort(key=lambda x: (-x["best"], x["app"]))
            partial.sort(key=lambda x: (-x["best"], x["app"]))
            specialists.append({
                "name": meta["name"],
                "slug": slug,
                "gnz_id": meta["gnz_id"],
                "club": club,
                "region": _find_region(club or ""),
                "apparatus": qualifying + partial,
                "count": len(qualifying) + len(partial),
                "qualified": True,
            })
        elif partial:
            partial.sort(key=lambda x: (-x["best"], x["app"]))
            specialists.append({
                "name": meta["name"],
                "slug": slug,
                "gnz_id": meta["gnz_id"],
                "club": club,
                "region": _find_region(club or ""),
                "apparatus": partial,
                "count": len(partial),
                "qualified": False,
            })

    specialists.sort(key=lambda x: (-x["qualified"], -x["count"], x["name"]))
    return specialists, app_threshold, app_count


@app.get("/api/rankings", response_model=RankingsResponse)
def get_rankings(
    year: int,
    step: str,
    discipline: str,
    quota: bool = False,
    qualifier: bool = False,
    division: str = "",
    _auth=Depends(require_permission(PERMISSION_NATIONAL)),
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
                LongScore.athlete_id,
                LongScore.gnz_id,
                LongScore.club_name,
                LongScore.event_id,
                LongScore.event_name,
                LongScore.apparatus,
                LongScore.pass_number,
                LongScore.pass_final_score,
                LongScore.d_score,
                LongScore.aa_score,
                LongScore.round_type,
                Event.host_club,
            )
            .join(Event, LongScore.event_id == Event.id)
            .filter(
                LongScore.event_id.in_(event_ids),
                LongScore.level_category == step,
                LongScore.discipline == discipline,
                LongScore.pass_final_score.isnot(None),
                *([LongScore.division == division] if division else []),
            )
            .all()
        )

        athletes = {a.id: a for a in session.query(Athlete).all()}

        # One competition score per (gymnast, event, round_type), collapsed to
        # ONE mark per (gymnast, event) so the top-2 total never uses two marks
        # from the same competition (e.g. the two days of a two-day meet). Also
        # accumulates per-apparatus bests for the specialist/leaderboard views.
        per_event, apparatus_events, meta_by_key = _build_event_marks(rows, step, athletes)

        # Build gymnast_data: aggregate competitions per gymnast, keep the best
        # gnz_id and club, and retain ALL per-event marks for the qualifier check.
        by_key: dict[str, list[dict]] = defaultdict(list)
        for (key, _eid), entry in per_event.items():
            by_key[key].append(entry)

        gymnast_data: dict[str, dict] = {}
        for key, entries in by_key.items():
            paired = sorted(entries, key=lambda x: -x["score"])
            meta = meta_by_key.get(key, {"name": str(key), "gnz_id": "", "club": ""})
            best_gnz_id = next((e["gnz_id"] for e in paired if e["gnz_id"]), "")
            best_club = next((e["club"] for e in paired if e["club"]), "")
            slug = athletes[key].slug if isinstance(key, int) and key in athletes else ""
            gymnast_data[key] = {
                "name": meta["name"],
                "slug": slug,
                "gnz_id": best_gnz_id,
                "club": best_club,
                "all_events": paired,
                "scores": [e["score"] for e in paired[:2]],
                "competitions": [e["event_name"] for e in paired[:2]],
            }

        # Qualifier filter: check the GNZ qualifying-mark rules against all
        # per-competition marks (each already a distinct competition).
        if qualifier:
            gymnast_data = {
                k: v for k, v in gymnast_data.items()
                if _is_qualifier(v["all_events"], v["club"], step)
            }

        mark_count = _RANKING_MARKS.get(step, 2)
        rank_by_average = step in _RANKING_MARKS

        ranking_list = []
        for data in gymnast_data.values():
            top = data["all_events"][:mark_count]
            data["scores"] = [s["score"] for s in top]
            data["competitions"] = [s["event_name"] for s in top]
            data["total"] = sum(data["scores"])
            data["average"] = data["total"] / len(data["scores"]) if data["scores"] else 0.0
            data["reached_mark"] = _reached_mark_twice(data["all_events"], step)
            ranking_list.append(data)

        rank_key = "average" if rank_by_average else "total"
        ranking_list.sort(key=lambda x: -x[rank_key])

        # Quota mode: cap each region at 4 for the first pass, then fill remaining
        if quota:
            region_count: dict[str, int] = {}
            quota_entries = []
            remaining = []
            for entry in ranking_list:
                region = _find_region(entry["club"] or "")
                if not region:
                    continue
                entry["region"] = region
                cnt = region_count.get(region, 0)
                if cnt < 4:
                    region_count[region] = cnt + 1
                    quota_entries.append(entry)
                else:
                    remaining.append(entry)
            ranking_list = quota_entries + remaining
        else:
            for entry in ranking_list:
                entry["region"] = _find_region(entry["club"] or "")

        rank = 1
        prev_val = None
        for i, entry in enumerate(ranking_list):
            val = entry[rank_key]
            if prev_val is not None and val < prev_val:
                rank = i + 1
            entry["rank"] = rank
            prev_val = val

        for i, entry in enumerate(ranking_list):
            if i > 0 and entry[rank_key] == ranking_list[i - 1][rank_key]:
                entry["rank_text"] = f"T{entry['rank']}"
            elif i < len(ranking_list) - 1 and entry[rank_key] == ranking_list[i + 1][rank_key]:
                entry["rank_text"] = f"T{entry['rank']}"
            else:
                entry["rank_text"] = str(entry["rank"])

        rankings = [
            RankingRow(
                rank=r["rank_text"],
                name=r["name"],
                slug=r["slug"],
                gnz_id=r["gnz_id"],
                club=r["club"],
                region=r["region"],
                scores=r["scores"],
                competitions=r["competitions"],
                total=round(r["total"], 3),
                reached_mark=r.get("reached_mark", False),
            )
            for r in ranking_list
        ]

        # Apparatus-qualifier section: shown alongside the qualifier view. It
        # lists gymnasts who reached the step's apparatus threshold, excluding
        # gymnasts who qualified for All Around (already in the filtered table),
        # so the two tables never overlap. With the qualifier filter off the
        # section is empty.
        specialists_list, app_qual_score, app_qual_count = _compute_apparatus_specialists(
            apparatus_events, step, meta_by_key,
            exclude_names=set(gymnast_data) if qualifier else None,
            athletes=athletes,
        )
        if not qualifier:
            specialists_list = []
        specialists_rows = [
            ApparatusSpecialistRow(
                name=r["name"],
                slug=r["slug"],
                gnz_id=r["gnz_id"],
                club=r["club"],
                region=r["region"],
                apparatus=r.get("apparatus", []),
                count=r.get("count", 0),
                qualified=r.get("qualified", True),
            )
            for r in specialists_list
        ]

        return RankingsResponse(
            year=year, step=step, discipline=discipline, rankings=rankings,
            apparatus_specialists=specialists_rows,
            apparatus_qualifying_score=app_qual_score,
            apparatus_qualifying_count=app_qual_count,
        )
    finally:
        session.close()


# Standard apparatus order per discipline; leaderboards follow this order and
# only include apparatus with at least one recorded mark.
_APPARATUS_ORDER: dict[str, list[str]] = {
    "WAG": ["VT", "UB", "BB", "FX"],
    "MAG": ["FX", "PH", "SR", "VT", "PB", "HB"],
}


@app.get("/api/rankings/apparatus", response_model=ApparatusRankingsResponse)
def get_apparatus_rankings(
    response: Response,
    year: int,
    step: str,
    discipline: str,
    division: str = "",
    _auth=Depends(require_permission(PERMISSION_NATIONAL)),
):
    """Per-apparatus national leaderboards for a step/level.

    Ranks gymnasts by their best single mark on each apparatus in the season.
    Per-event apparatus scores are round-type-merged and vault follows
    ``_use_vault_average``, matching the All Around rankings. Only non-national
    events of the requested year are considered. Cached per selection for 5
    minutes (no qualifier/intent toggles, so a short TTL is safe).
    """
    response.headers.update(cache_headers())
    return cached(
        ("apparatus-rankings", year, step, discipline, division),
        lambda: _compute_apparatus_rankings(year, step, discipline, division),
        ttl=300,
    )


def _compute_apparatus_rankings(year: int, step: str, discipline: str, division: str) -> ApparatusRankingsResponse:
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
            return ApparatusRankingsResponse(year=year, step=step, discipline=discipline, apparatus=[])

        rows = (
            session.query(
                LongScore.gymnast_name,
                LongScore.athlete_id,
                LongScore.gnz_id,
                LongScore.club_name,
                LongScore.event_id,
                LongScore.event_name,
                LongScore.apparatus,
                LongScore.pass_number,
                LongScore.pass_final_score,
                LongScore.d_score,
                LongScore.aa_score,
                LongScore.round_type,
                Event.host_club,
            )
            .join(Event, LongScore.event_id == Event.id)
            .filter(
                LongScore.event_id.in_(event_ids),
                LongScore.level_category == step,
                LongScore.discipline == discipline,
                LongScore.pass_final_score.isnot(None),
                *([LongScore.division == division] if division else []),
            )
            .all()
        )

        athletes = {a.id: a for a in session.query(Athlete).all()}
        _, apparatus_events, meta_by_key = _build_event_marks(rows, step, athletes)

        # Best season mark per (gymnast, apparatus), plus where it was set.
        by_app: dict[str, list[dict]] = defaultdict(list)
        for key, app_events in apparatus_events.items():
            meta = meta_by_key.get(key, {"name": str(key), "gnz_id": "", "club": ""})
            slug = athletes[key].slug if isinstance(key, int) and key in athletes else ""
            for app, events in app_events.items():
                best = max(events.values(), key=lambda e: e["score"])
                by_app[app].append({
                    "name": meta["name"],
                    "slug": slug,
                    "gnz_id": meta["gnz_id"],
                    "club": meta["club"],
                    "region": _find_region(meta["club"] or ""),
                    "best": best["score"],
                    "d": best.get("d"),
                    "event": best["event_name"],
                    "count": len(events),
                })

        order = _APPARATUS_ORDER.get(discipline, [])
        remaining = sorted(set(by_app) - set(order))
        leaderboards = []
        for app in order + remaining:
            if app not in by_app:
                continue
            entries = sorted(by_app[app], key=lambda x: -x["best"])

            rank = 1
            prev_val = None
            for i, entry in enumerate(entries):
                if prev_val is not None and entry["best"] < prev_val:
                    rank = i + 1
                entry["rank"] = rank
                prev_val = entry["best"]

            for i, entry in enumerate(entries):
                if i > 0 and entry["best"] == entries[i - 1]["best"]:
                    entry["rank_text"] = f"T{entry['rank']}"
                elif i < len(entries) - 1 and entry["best"] == entries[i + 1]["best"]:
                    entry["rank_text"] = f"T{entry['rank']}"
                else:
                    entry["rank_text"] = str(entry["rank"])

            leaderboards.append(ApparatusLeaderboard(
                app=app,
                rankings=[
                    ApparatusRankingRow(
                        rank=e["rank_text"],
                        name=e["name"],
                        slug=e["slug"],
                        gnz_id=e["gnz_id"],
                        club=e["club"],
                        region=e["region"],
                        best=round(e["best"], 3),
                        d=round(e["d"], 1) if e["d"] is not None else None,
                        event=e["event"],
                        count=e["count"],
                    )
                    for e in entries
                ],
            ))

        return ApparatusRankingsResponse(year=year, step=step, discipline=discipline, apparatus=leaderboards)
    finally:
        session.close()


@app.get("/api/rankings/wellington", response_model=WellingtonRankingResponse)
def get_wellington_rankings(
    year: int,
    step: str,
    discipline: str,
    gnz_qualifier: bool = True,
    wellington_qualifier: bool = True,
    intent_filter: bool = True,
    _auth=Depends(require_permission(PERMISSION_WELLINGTON)),
):
    session = get_session()
    try:
        intents = {
            row.athlete_id or row.gnz_id
            for row in session.query(
                WellingtonIntent.athlete_id,
                WellingtonIntent.gnz_id,
            ).filter(
                WellingtonIntent.year == year,
            ).all()
        }
    finally:
        session.close()

    result = compute_wellington_rankings(
        year, discipline, step,
        gnz_qualifier=gnz_qualifier, wellington_qualifier=wellington_qualifier,
        intents=intents, intent_filter=intent_filter,
    )
    rankings = [
        WellingtonRankingRow(
            rank=r["rank_text"],
            name=r["name"],
            slug=r.get("slug", ""),
            gnz_id=r["gnz_id"],
            club=r["club"],
            region=r["region"],
            scores=r["scores"],
            competitions=r["competitions"],
            categories=r["categories"],
            apparatus=r.get("apparatus", []),
            total=r["total"],
            average=r["average"],
            warnings=r["warnings"],
            intent_submitted=r["intent_submitted"],
        )
        for r in result["rankings"]
    ]
    specialists = [
        ApparatusSpecialistRow(
            name=r["name"],
            slug=r.get("slug", ""),
            gnz_id=r["gnz_id"],
            club=r["club"],
            region=r["region"],
            apparatus=r.get("apparatus", []),
            count=r.get("count", 0),
            qualified=r.get("qualified", True),
        )
        for r in result.get("apparatus_specialists", [])
    ]
    not_ranked = [
        WellingtonNotRankedRow(
            name=r["name"],
            slug=r.get("slug", ""),
            gnz_id=r["gnz_id"],
            club=r["club"],
            region=r["region"],
            scores=r["scores"],
            competition_names=r["competition_names"],
            categories=r.get("categories", []),
            apparatus=r.get("apparatus", []),
            competitions=r["competitions"],
            regional_count=r.get("regional_count", 0),
            club_count=r.get("club_count", 0),
            away_count=r.get("away_count", 0),
            why=r.get("why", ""),
            checks=r.get("checks", []),
            intent_submitted=r["intent_submitted"],
        )
        for r in result.get("not_ranked", [])
    ]
    return WellingtonRankingResponse(
        year=result["year"],
        step=result["step"],
        discipline=result["discipline"],
        rankings=rankings,
        not_ranked=not_ranked,
        config_key=result.get("config_key", ""),
        qualifying_score=result.get("gnz_qualifying_score"),
        wellington_qualifying_score=result.get("wellington_qualifying_score"),
        apparatus_specialists=specialists,
        apparatus_qualifying_score=result.get("apparatus_qualifying_score"),
        apparatus_qualifying_count=result.get("apparatus_qualifying_count", 2),
    )


@app.get("/api/wellington/intents")
def get_intents(
    year: int,
    _auth=Depends(require_permission(PERMISSION_WELLINGTON)),
):
    session = get_session()
    try:
        rows = session.query(WellingtonIntent.athlete_id, WellingtonIntent.gnz_id).filter(
            WellingtonIntent.year == year,
        ).all()
        athlete_ids = sorted({r.athlete_id for r in rows if r.athlete_id is not None})
        slugs = [
            a.slug
            for a in session.query(Athlete).filter(Athlete.id.in_(athlete_ids)).all()
        ] if athlete_ids else []
        return {"athlete_ids": athlete_ids, "slugs": slugs, "gnz_ids": [r.gnz_id for r in rows if r.gnz_id]}
    finally:
        session.close()


@app.post("/api/wellington/intent")
def toggle_intent(
    body: IntentToggle,
    _auth=Depends(require_role("admin")),
):
    session = get_session()
    try:
        athlete_id = body.athlete_id
        if athlete_id is None and body.slug:
            athlete_id = resolve_identity(session, slug=body.slug)
        if athlete_id is None and body.gnz_id:
            athlete_id = resolve_identity(session, gnz_id=body.gnz_id)
        if athlete_id is None:
            raise HTTPException(400, "athlete_id is required")
        existing = session.query(WellingtonIntent).filter(
            WellingtonIntent.athlete_id == athlete_id,
            WellingtonIntent.year == body.year,
        ).first()
        if body.submitted and not existing:
            session.add(WellingtonIntent(
                athlete_id=athlete_id,
                gnz_id=body.gnz_id or None,
                year=body.year,
            ))
            session.commit()
        elif not body.submitted and existing:
            session.delete(existing)
            session.commit()
        invalidate()
        return {"ok": True}
    finally:
        session.close()


def _build_duplicate_groups(session) -> list[tuple[dict, list[dict]]]:
    """Query all (name, gnz_id, club, level) combos with counts,
    group by name, and return list of (group_info, instances).

    Each group_info has name, name_lower.
    Each instance has club, level, id_counts, total_rows.
    """
    from sqlalchemy import func as sa_func

    rows = (
        session.query(
            LongScore.gymnast_name,
            LongScore.gnz_id,
            LongScore.club_name,
            LongScore.level_category,
            sa_func.count(LongScore.id),
        )
        .filter(
            LongScore.gnz_id.isnot(None),
            LongScore.gnz_id != "",
        )
        .group_by(
            LongScore.gymnast_name,
            LongScore.gnz_id,
            LongScore.club_name,
            LongScore.level_category,
        )
        .all()
    )

    # Build all raw groups keyed by (name_lower, club_lower, level)
    raw: dict[tuple[str, str, str], dict[str, int]] = {}
    name_map: dict[tuple[str, str, str], str] = {}
    for name, gnz_id, club, level, cnt in rows:
        key = (name.strip().lower(), (club or "").strip().lower(), level or "")
        if key not in raw:
            raw[key] = {}
            name_map[key] = name.strip()
        raw[key][gnz_id or ""] = raw[key].get(gnz_id or "", 0) + cnt

    # Group instances by name_lower
    name_instances: dict[str, list[dict]] = {}
    for (name_lower, club_lower, level), id_counts in raw.items():
        total = sum(id_counts.values())
        inst = {
            "club": club_lower,
            "level": level,
            "id_counts": id_counts,
            "total_rows": total,
            "name": name_map[(name_lower, club_lower, level)],
        }
        if name_lower not in name_instances:
            name_instances[name_lower] = []
        name_instances[name_lower].append(inst)

    # Build groups: include if across all instances there are >= 2 distinct IDs
    result = []
    for name_lower, instances in name_instances.items():
        all_ids = set()
        for inst in instances:
            all_ids.update(inst["id_counts"].keys())
        if len(all_ids) < 2:
            continue
        total = sum(i["total_rows"] for i in instances)
        result.append(({
            "name": instances[0]["name"],
            "name_lower": name_lower,
            "total_rows": total,
        }, instances))

    result.sort(key=lambda x: -x[0]["total_rows"])
    return result


@app.get("/api/admin/duplicates", response_model=list[DuplicateGroup])
def list_duplicates(_auth=Depends(require_role("admin"))):
    session = get_session()
    try:
        groups = _build_duplicate_groups(session)
        return [
            DuplicateGroup(
                name=g["name"],
                instances=[
                    DuplicateInstance(
                        club=i["club"],
                        level_category=i["level"],
                        id_counts=i["id_counts"],
                        total_rows=i["total_rows"],
                    )
                    for i in instances
                ],
                total_rows=g["total_rows"],
            )
            for g, instances in groups
        ]
    finally:
        session.close()


@app.post("/api/admin/duplicates/fix", response_model=FixDuplicatesResponse)
def fix_duplicates(_auth=Depends(require_role("admin"))):
    session = get_session()
    try:
        groups = _build_duplicate_groups(session)
        fixed = 0
        low_confidence: list[DuplicateGroup] = []

        for g, instances in groups:
            # Collect all IDs across instances with total counts
            all_id_counts: dict[str, int] = {}
            for inst in instances:
                for gid, cnt in inst["id_counts"].items():
                    all_id_counts[gid] = all_id_counts.get(gid, 0) + cnt

            if len(all_id_counts) < 2:
                continue

            sorted_ids = sorted(all_id_counts.items(), key=lambda x: (-x[1], x[0].isdigit(), x[0]))
            top_id, top_count = sorted_ids[0]
            runner_up_count = sorted_ids[1][1] if len(sorted_ids) > 1 else 0

            # High confidence: top ID count > 2x runner-up
            if top_count > runner_up_count * 2:
                for inst in instances:
                    for old_id in inst["id_counts"]:
                        if old_id == top_id:
                            continue
                        updated = (
                            session.query(LongScore)
                            .filter(
                                LongScore.gymnast_name.ilike(g["name_lower"]),
                                LongScore.club_name.ilike(inst["club"]),
                                LongScore.level_category == inst["level"],
                                LongScore.gnz_id == old_id,
                            )
                            .update({LongScore.gnz_id: top_id}, synchronize_session=False)
                        )
                        fixed += updated
            else:
                low_confidence.append(DuplicateGroup(
                    name=g["name"],
                    instances=[
                        DuplicateInstance(
                            club=i["club"],
                            level_category=i["level"],
                            id_counts=i["id_counts"],
                            total_rows=i["total_rows"],
                        )
                        for i in instances
                    ],
                    total_rows=g["total_rows"],
                ))

        if fixed:
            session.commit()
            rebuild_athletes(session)
            invalidate()

        return FixDuplicatesResponse(fixed=fixed, low_confidence=low_confidence)
    finally:
        session.close()


@app.post("/api/admin/duplicates/apply", response_model=dict)
def apply_duplicate_fixes(
    fixes: list[ApplyFixItem],
    _auth=Depends(require_role("admin")),
):
    session = get_session()
    try:
        total = 0
        for fix in fixes:
            ids_to_replace = (
                session.query(LongScore.gnz_id)
                .filter(
                    LongScore.gymnast_name.ilike(fix.name),
                    LongScore.club_name.ilike(fix.club),
                    LongScore.level_category == fix.level_category,
                    LongScore.gnz_id != fix.chosen_id,
                    LongScore.gnz_id.isnot(None),
                    LongScore.gnz_id != "",
                )
                .distinct()
                .all()
            )

            for (old_id,) in ids_to_replace:
                updated = (
                    session.query(LongScore)
                    .filter(
                        LongScore.gymnast_name.ilike(fix.name),
                        LongScore.club_name.ilike(fix.club),
                        LongScore.level_category == fix.level_category,
                        LongScore.gnz_id == old_id,
                    )
                    .update({LongScore.gnz_id: fix.chosen_id}, synchronize_session=False)
                )
                total += updated

        if total:
            session.commit()
            rebuild_athletes(session)
            invalidate()

        return {"applied": total}
    finally:
        session.close()


@app.post("/api/admin/refresh-cache")
def refresh_cache(_auth=Depends(require_role("admin"))):
    session = get_session()
    try:
        rebuild_athletes(session)
    finally:
        session.close()
    invalidate()
    return {"ok": True}


# ---------------------------------------------------------------------------
# Activity tracking (admin)
# ---------------------------------------------------------------------------

@app.post("/api/track/page")
def track_page(body: TrackPageRequest, user: dict | None = Depends(get_optional_user)):
    path = (body.path or "/")[:500]
    if user is None:
        enqueue_traffic_activity(
            ACTIVITY_TYPE_PAGE,
            normalize_path(path),
            anonymous=True,
            status_code=200,
            duration_ms=None,
        )
        return {"ok": True}
    _log_activity(
        user["username"],
        user["role"],
        ACTIVITY_TYPE_PAGE,
        "GET",
        path,
        None,
        200,
        None,
    )
    enqueue_traffic_activity(
        ACTIVITY_TYPE_PAGE,
        normalize_path(path),
        anonymous=False,
        status_code=200,
        duration_ms=None,
    )
    return {"ok": True}


@app.get("/api/admin/activity", response_model=ActivityLogResponse)
def list_activity(
    user: str = None,
    type: str = None,
    limit: int = 100,
    offset: int = 0,
    days: int = None,
    _auth=Depends(require_role("admin")),
):
    flush_activity()
    limit = max(1, min(limit, 500))
    offset = max(0, offset)
    session = get_session()
    try:
        query = session.query(ActivityLog)
        if user:
            query = query.filter(ActivityLog.username == user)
        if type:
            query = query.filter(ActivityLog.type == type)
        if days:
            days = max(1, min(days, 3650))
            cutoff = datetime.now(timezone.utc) - timedelta(days=days)
            query = query.filter(ActivityLog.created_at >= cutoff)
        total = query.count()
        rows = (
            query.order_by(ActivityLog.created_at.desc(), ActivityLog.id.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )
        return ActivityLogResponse(
            items=[
                ActivityLogItem(
                    id=r.id,
                    username=r.username,
                    role=r.role,
                    type=r.type,
                    method=r.method,
                    path=r.path,
                    query=r.query,
                    status_code=r.status_code,
                    duration_ms=r.duration_ms,
                    created_at=r.created_at,
                )
                for r in rows
            ],
            total=total,
        )
    finally:
        session.close()


@app.get("/api/admin/activity/summary", response_model=ActivitySummaryResponse)
def activity_summary(
    days: int = 30,
    _auth=Depends(require_role("admin")),
):
    """Aggregate traffic analytics for the admin usage dashboard.

    ``days`` of 7/30/90 select a trailing window (0 = all time). Totals, daily
    and hourly series, top pages/API paths and top users are computed from the
    ``traffic_daily`` counters (all traffic) plus the ``activity_logs`` table
    (authenticated history, so logged-in trends are visible immediately).
    """
    flush_activity()
    if days not in (0, 7, 30, 90):
        days = 30
    session = get_session()
    try:
        today = datetime.now().date()
        start = today - timedelta(days=days - 1) if days else None

        def _series_query():
            q = session.query(
                TrafficDaily.date,
                TrafficDaily.kind,
                func.coalesce(func.sum(TrafficDaily.count), 0),
                func.coalesce(func.sum(TrafficDaily.error_count), 0),
                TrafficDaily.anonymous,
            )
            if start:
                q = q.filter(TrafficDaily.date >= start)
            return q.group_by(TrafficDaily.date, TrafficDaily.kind, TrafficDaily.anonymous).all()

        rows = _series_query()
        daily: dict[str, dict] = {}
        hourly: dict[str, dict] = {}
        totals = {
            "page_views": 0, "api_requests": 0, "errors": 0,
            "anon_page_views": 0, "auth_page_views": 0,
            "anon_api_requests": 0, "auth_api_requests": 0,
        }
        active_days: set[str] = set()
        for date, kind, count, errors, anonymous in rows:
            date_s = date.isoformat()
            active_days.add(date_s)
            bucket = daily.setdefault(date_s, {"page_views": 0, "api_requests": 0, "errors": 0})
            bucket["errors"] += errors or 0
            totals["errors"] += errors or 0
            if kind == "page":
                bucket["page_views"] += count
                totals["page_views"] += count
                if anonymous:
                    totals["anon_page_views"] += count
                else:
                    totals["auth_page_views"] += count
            else:
                bucket["api_requests"] += count
                totals["api_requests"] += count
                if anonymous:
                    totals["anon_api_requests"] += count
                else:
                    totals["auth_api_requests"] += count

        # Per-hour volume over the selected window.
        hour_q = session.query(
            TrafficDaily.hour,
            TrafficDaily.kind,
            func.coalesce(func.sum(TrafficDaily.count), 0),
        )
        if start:
            hour_q = hour_q.filter(TrafficDaily.date >= start)
        for hour, kind, count in hour_q.group_by(TrafficDaily.hour, TrafficDaily.kind).all():
            slot = hourly.setdefault(hour, {"page_views": 0, "api_requests": 0})
            slot["page_views" if kind == "page" else "api_requests"] += count

        # Average response time over the window (api rows carry durations).
        dur_q = session.query(
            func.coalesce(func.sum(TrafficDaily.count), 0),
            func.coalesce(func.sum(TrafficDaily.total_duration_ms), 0.0),
        )
        if start:
            dur_q = dur_q.filter(TrafficDaily.date >= start)
        api_count, api_ms = dur_q.first()
        avg_duration_ms = round(api_ms / api_count, 2) if api_count else None

        # Top paths from the aggregate counters.
        def _top(kind: str) -> list[TopPath]:
            q = session.query(
                TrafficDaily.path_group,
                func.coalesce(func.sum(TrafficDaily.count), 0),
                func.coalesce(func.sum(TrafficDaily.error_count), 0),
            ).filter(TrafficDaily.kind == kind)
            if start:
                q = q.filter(TrafficDaily.date >= start)
            return [
                TopPath(path=path, count=count, errors=errors)
                for path, count, errors in q.group_by(TrafficDaily.path_group)
                .order_by(func.sum(TrafficDaily.count).desc())
                .limit(15)
                .all()
            ]

        top_pages = _top(ACTIVITY_TYPE_PAGE)
        top_api = _top(ACTIVITY_TYPE_API)

        # Authenticated history from the detail log (backfills pre-dashboard
        # dates for logged-in traffic).
        auth_q = session.query(
            func.date(ActivityLog.created_at),
            ActivityLog.type,
            func.count(ActivityLog.id),
        )
        if start:
            auth_q = auth_q.filter(ActivityLog.created_at >= datetime.combine(start, datetime.min.time()))
        auth_rows = auth_q.group_by(func.date(ActivityLog.created_at), ActivityLog.type).all()
        auth_daily: dict[str, dict] = {}
        for date_s, kind, count in auth_rows:
            bucket = auth_daily.setdefault(date_s, {"page_views": 0, "api_requests": 0, "errors": 0})
            if kind == ACTIVITY_TYPE_PAGE:
                bucket["page_views"] += count
            else:
                bucket["api_requests"] += count

        # Top users from the detail log.
        user_q = session.query(
            ActivityLog.username,
            ActivityLog.role,
            func.sum(case((ActivityLog.type == ACTIVITY_TYPE_PAGE, 1), else_=0)),
            func.sum(case((ActivityLog.type == ACTIVITY_TYPE_API, 1), else_=0)),
        )
        if start:
            user_q = user_q.filter(ActivityLog.created_at >= datetime.combine(start, datetime.min.time()))
        user_rows = user_q.group_by(ActivityLog.username, ActivityLog.role).all()
        top_users = [
            TopUser(username=username, role=role, page_views=page_views, api_requests=api_requests)
            for username, role, page_views, api_requests in user_rows
        ]
        top_users.sort(key=lambda u: u.page_views + u.api_requests, reverse=True)
        top_users = top_users[:10]

        def _fill_daily(dates: dict) -> list[TrafficPoint]:
            return [
                TrafficPoint(
                    date=d,
                    page_views=dates[d]["page_views"],
                    api_requests=dates[d]["api_requests"],
                    errors=dates[d]["errors"],
                )
                for d in sorted(dates)
            ]

        return ActivitySummaryResponse(
            range_days=days,
            totals=ActivityTotals(
                page_views=totals["page_views"],
                api_requests=totals["api_requests"],
                errors=totals["errors"],
                avg_duration_ms=avg_duration_ms,
                active_days=len(active_days),
                anon_page_views=totals["anon_page_views"],
                auth_page_views=totals["auth_page_views"],
                anon_api_requests=totals["anon_api_requests"],
                auth_api_requests=totals["auth_api_requests"],
            ),
            daily_series=_fill_daily(daily),
            auth_daily_series=_fill_daily(auth_daily),
            hourly_series=[
                HourPoint(hour=h, **hourly[h])
                for h in sorted(hourly)
            ],
            top_pages=top_pages,
            top_api=top_api,
            top_users=top_users,
        )
    finally:
        session.close()


@app.delete("/api/admin/activity")
def clear_activity(user: str = None, _auth=Depends(require_role("admin"))):
    flush_activity()
    session = get_session()
    try:
        query = session.query(ActivityLog)
        if user:
            query = query.filter(ActivityLog.username == user)
        deleted = query.delete(synchronize_session=False)
        session.commit()
        return {"deleted": deleted}
    finally:
        session.close()


@app.get("/api/admin/cloudflare/summary", response_model=CloudflareSummaryResponse)
def cloudflare_summary(
    days: int = 30,
    _auth=Depends(require_role("admin")),
):
    """Cloudflare edge HTTP traffic analytics for the admin dashboard.

    Pulls per-day rollups (requests, bytes, threats, cached bytes, unique
    visitors) from the Cloudflare GraphQL Analytics API, plus top-country and
    status-code breakdowns from the adaptive dataset (clamped to the last 7
    days, matching its retention). Returns ``configured: False`` when the
    ``CLOUDFLARE_ZONE_ID``/``CLOUDFLARE_API_TOKEN`` env vars are missing, and
    a ``configured: True`` payload with an ``error`` field on fetch failures.
    """
    if days not in (7, 30):
        days = 30
    if not cloudflare_is_configured():
        return CloudflareSummaryResponse(configured=False, days=days)
    try:
        return cached(
            ("cloudflare", days),
            lambda: fetch_zone_summary(days),
            ttl=300,
        )
    except CloudflareFetchError as e:
        return CloudflareSummaryResponse(configured=True, days=days, error=str(e))


def _find_similar_names(session, threshold: float = 0.85) -> list[dict]:
    import difflib

    rows = (
        session.query(LongScore.gymnast_name)
        .distinct()
        .all()
    )
    names = sorted({r[0] for r in rows if r[0]})

    count_rows = (
        session.query(LongScore.gymnast_name, func.count(LongScore.id))
        .group_by(LongScore.gymnast_name)
        .all()
    )
    name_to_count = {r[0]: r[1] for r in count_rows}

    gnz_id_rows = (
        session.query(LongScore.gymnast_name, LongScore.gnz_id)
        .filter(LongScore.gnz_id.isnot(None), LongScore.gnz_id != "")
        .distinct()
        .all()
    )
    name_to_gnz_ids: dict[str, list[str]] = {}
    for name, gnz_id in gnz_id_rows:
        name_to_gnz_ids.setdefault(name, []).append(gnz_id)

    token_groups: dict[str, list[str]] = {}
    for name in names:
        lower = name.lower().strip()
        tokens = lower.split()
        for t in tokens:
            if len(t) < 3:
                continue
            if t not in token_groups:
                token_groups[t] = []
            token_groups[t].append(name)

    seen = set()
    result = []
    for token, group in token_groups.items():
        if len(group) < 2:
            continue
        for i in range(len(group)):
            for j in range(i + 1, len(group)):
                a, b = group[i], group[j]
                key = (a, b) if a < b else (b, a)
                if key in seen:
                    continue
                seen.add(key)
                matcher = difflib.SequenceMatcher(None, a.lower(), b.lower())
                if matcher.quick_ratio() < threshold:
                    continue
                ratio = matcher.ratio()
                if ratio >= threshold and a.lower().strip() != b.lower().strip():
                    rows_a = name_to_count.get(a, 0)
                    rows_b = name_to_count.get(b, 0)
                    if rows_b < rows_a:
                        a, b = b, a
                        rows_a, rows_b = rows_b, rows_a
                    ids_a_vals = name_to_gnz_ids.get(a, [])
                    ids_b_vals = name_to_gnz_ids.get(b, [])
                    result.append({
                        "name_a": a, "name_b": b, "score": round(ratio, 4),
                        "gnz_ids_a": ids_a_vals, "gnz_ids_b": ids_b_vals,
                        "rows_a": rows_a, "rows_b": rows_b,
                    })
    result.sort(key=lambda x: -x["score"])
    return result


@app.get("/api/admin/suggested-merges", response_model=list[SuggestedMerge])
def list_suggested_merges(_auth=Depends(require_role("admin"))):
    session = get_session()
    try:
        return [SuggestedMerge(**m) for m in _find_similar_names(session)]
    finally:
        session.close()


@app.post("/api/admin/merge-names", response_model=dict)
def merge_names(
    req: MergeNamesRequest,
    _auth=Depends(require_role("admin")),
):
    session = get_session()
    try:
        updated = (
            session.query(LongScore)
            .filter(
                func.trim(func.lower(LongScore.gymnast_name))
                == func.trim(func.lower(req.from_name))
            )
            .update({LongScore.gymnast_name: req.to_name}, synchronize_session=False)
        )

        # Normalize survivor name to its most common form
        canonical = (
            session.query(LongScore.gymnast_name, func.count(LongScore.id).label("cnt"))
            .filter(
                func.trim(func.lower(LongScore.gymnast_name))
                == func.trim(func.lower(req.to_name))
            )
            .group_by(LongScore.gymnast_name)
            .order_by(func.count(LongScore.id).desc())
            .first()
        )
        if canonical and canonical[0] != req.to_name:
            session.query(LongScore).filter(
                func.trim(func.lower(LongScore.gymnast_name))
                == func.trim(func.lower(req.to_name)),
                LongScore.gymnast_name != canonical[0],
            ).update({LongScore.gymnast_name: canonical[0]}, synchronize_session=False)

        if updated:
            session.commit()
            invalidate()
        report = reconcile_athletes()
        rebuild_athletes(session)
        return {
            "merged": updated,
            "names_unified": report["names_unified"],
            "ids_corrected": report["ids_corrected"],
            "conflicts": report.get("conflicts", []),
        }
    finally:
        session.close()


@app.patch("/api/admin/scores/gymnast", response_model=GymnastEditResponse)
def edit_gymnast_scores(
    req: GymnastEditRequest,
    _auth=Depends(require_role("admin")),
):
    if not any([req.new_name, req.new_gnz_id, req.new_club]):
        raise HTTPException(400, "At least one field to update must be provided")

    session = get_session()
    try:
        updates: dict = {}
        if req.new_name is not None:
            updates[LongScore.gymnast_name] = req.new_name
        if req.new_gnz_id is not None:
            updates[LongScore.gnz_id] = req.new_gnz_id
        if req.new_club is not None:
            updates[LongScore.club_name] = req.new_club

        updated = (
            session.query(LongScore)
            .filter(
                LongScore.event_id == req.event_id,
                func.trim(func.lower(LongScore.gymnast_name))
                == func.trim(func.lower(req.current_name)),
            )
            .update(updates, synchronize_session=False)
        )

        if updated:
            session.commit()
            rebuild_athletes(session)
            cache.invalidate_prefix("wide-all")
            cache.invalidate_prefix("apparatus-rankings")
            cache.invalidate_prefix("stats")
            cache.invalidate_prefix("gymnasts")
            cache.invalidate_prefix("clubs")
            cache.invalidate_prefix("medals")
            invalidate(req.event_id)

        return GymnastEditResponse(updated=updated)
    finally:
        session.close()


def _split_csv(value) -> list[str]:
    """Split a SQLite group_concat string into a non-empty list."""
    if not value:
        return []
    return [v for v in str(value).split(",") if v]


def _fresh_synthetic_id(session) -> str:
    """Return a unique admin-generated gnz_id for split-off athletes."""
    import uuid

    while True:
        gid = "S" + uuid.uuid4().hex[:8]
        taken = (
            session.query(LongScore)
            .filter(LongScore.gnz_id == gid)
            .first()
        )
        if taken is None:
            return gid


def _fresh_override_token() -> str:
    """Return a unique identity_override token marking an admin force-split."""
    import uuid

    return "split-" + uuid.uuid4().hex[:12]


def _build_identity_review(session) -> dict:
    """Aggregate athlete-level identity conflicts for admin review.

    Returns ``{similar_names, name_conflicts, id_conflicts, multi_id_athletes}``
    where each athlete entry carries the evidence an admin needs to judge
    whether two records are the same person.
    """
    from collections import defaultdict

    agg_rows = (
        session.query(
            LongScore.athlete_id,
            func.count(LongScore.id).label("row_count"),
            func.count(func.distinct(LongScore.event_id)).label("event_count"),
            func.group_concat(func.distinct(LongScore.event_id)).label("event_ids"),
            func.group_concat(func.distinct(LongScore.club_name)).label("clubs"),
            func.group_concat(func.distinct(LongScore.discipline)).label("discs"),
            func.group_concat(func.distinct(Event.year)).label("years"),
        )
        .join(Event, Event.id == LongScore.event_id)
        .filter(LongScore.athlete_id.isnot(None))
        .group_by(LongScore.athlete_id)
        .all()
    )
    agg_by_id = {aid: {
        "rows": row_count,
        "events": event_count,
        "event_ids": event_ids,
        "clubs": clubs,
        "discs": discs,
        "years": years,
    } for aid, row_count, event_count, event_ids, clubs, discs, years in agg_rows}

    id_rows = (
        session.query(
            LongScore.athlete_id,
            LongScore.gnz_id,
            func.count(LongScore.id),
        )
        .filter(
            LongScore.athlete_id.isnot(None),
            LongScore.gnz_id.isnot(None),
            LongScore.gnz_id != "",
        )
        .group_by(LongScore.athlete_id, LongScore.gnz_id)
        .all()
    )

    intent_rows = (
        session.query(WellingtonIntent.athlete_id, WellingtonIntent.year)
        .filter(WellingtonIntent.athlete_id.isnot(None))
        .all()
    )

    athletes = {a.id: a for a in session.query(Athlete).all()}
    intents: dict[int, list[int]] = defaultdict(list)
    for aid, year in intent_rows:
        intents[aid].append(year)

    def _info(aid: int) -> dict:
        a = athletes.get(aid)
        agg = agg_by_id.get(aid, {})
        return {
            "athlete_id": aid,
            "slug": a.slug if a else "",
            "name": (a.canonical_name if a else "") or "",
            "gnz_id": (a.gnz_id if a else None),
            "clubs": sorted(set(_split_csv(agg.get("clubs")))),
            "events": agg.get("events", 0),
            "event_ids": [int(e) for e in sorted(set(_split_csv(agg.get("event_ids"))))],
            "years": [int(y) for y in sorted(set(_split_csv(agg.get("years"))))],
            "disciplines": sorted(set(_split_csv(agg.get("discs")))),
            "rows": agg.get("rows", 0),
            "intent_years": sorted(intents.get(aid, [])),
        }

    info_by_id = {aid: _info(aid) for aid in athletes}

    # --- Name conflicts: same canonical name, multiple athletes ----------
    by_name: dict[str, list[dict]] = defaultdict(list)
    for info in info_by_id.values():
        if info["name"]:
            by_name[info["name"]].append(info)
    name_conflicts = [
        {"name": name, "athletes": infos}
        for name, infos in by_name.items()
        if len(infos) > 1
    ]
    name_conflicts.sort(key=lambda g: -sum(x["rows"] for x in g["athletes"]))

    # --- ID conflicts: same gnz_id, multiple athletes --------------------
    by_gid: dict[str, list[dict]] = defaultdict(list)
    for info in info_by_id.values():
        if info["gnz_id"]:
            by_gid[info["gnz_id"]].append(info)
    id_conflicts = [
        {"gnz_id": gid, "athletes": infos}
        for gid, infos in by_gid.items()
        if len(infos) > 1
    ]
    id_conflicts.sort(key=lambda g: -sum(x["rows"] for x in g["athletes"]))

    # --- Multi-ID athletes: one athlete carrying 2+ gnz_ids (Split review)
    gid_counts: dict[int, dict[str, int]] = defaultdict(dict)
    for aid, gid, cnt in id_rows:
        gid_counts[aid][gid] = gid_counts[aid].get(gid, 0) + cnt
    multi_id = []
    for aid, gids in gid_counts.items():
        if len(gids) > 1:
            info = info_by_id[aid]
            multi_id.append({
                "athlete_id": aid,
                "slug": info["slug"],
                "name": info["name"],
                "gnz_ids": dict(sorted(gids.items(), key=lambda kv: -kv[1])),
                "clubs": info["clubs"],
                "events": info["events"],
                "event_ids": info["event_ids"],
                "years": info["years"],
                "disciplines": info["disciplines"],
                "rows": info["rows"],
            })
    multi_id.sort(key=lambda m: -m["rows"])

    # --- Similar names: fuzzy canonical-name pairs (single-athlete names) -
    import difflib

    name_to_athletes: dict[str, list[int]] = defaultdict(list)
    for aid, a in athletes.items():
        if a.canonical_name:
            name_to_athletes[a.canonical_name].append(aid)
    single = {name: aids[0] for name, aids in name_to_athletes.items() if len(aids) == 1}
    names = sorted(single.keys())

    token_groups: dict[str, list[str]] = defaultdict(list)
    for name in names:
        for t in name.lower().split():
            if len(t) >= 3:
                token_groups[t].append(name)

    similar = []
    seen: set[tuple[str, str]] = set()
    for token, group in token_groups.items():
        if len(group) < 2:
            continue
        for i in range(len(group)):
            for j in range(i + 1, len(group)):
                a, b = group[i], group[j]
                key = (a, b) if a < b else (b, a)
                if key in seen:
                    continue
                seen.add(key)
                matcher = difflib.SequenceMatcher(None, a.lower(), b.lower())
                if matcher.quick_ratio() < 0.85:
                    continue
                ratio = matcher.ratio()
                if ratio < 0.85:
                    continue
                info_a, info_b = info_by_id[single[a]], info_by_id[single[b]]
                if info_a["gnz_id"] and info_a["gnz_id"] == info_b["gnz_id"]:
                    continue
                similar.append({
                    "name_a": a,
                    "name_b": b,
                    "score": round(ratio, 4),
                    "athlete_a": info_a,
                    "athlete_b": info_b,
                })
    similar.sort(key=lambda s: -s["score"])

    return {
        "similar_names": similar[:200],
        "name_conflicts": name_conflicts,
        "id_conflicts": id_conflicts,
        "multi_id_athletes": multi_id,
    }


@app.get("/api/admin/identity-review", response_model=IdentityReviewResponse)
def get_identity_review(_auth=Depends(require_role("admin"))):
    session = get_session()
    try:
        return _build_identity_review(session)
    finally:
        session.close()


@app.post("/api/admin/athletes/merge-preview", response_model=MergePreviewResponse)
def preview_merge(
    req: MergePreviewRequest,
    _auth=Depends(require_role("admin")),
):
    """Return the exact changes a merge would apply, without writing anything.

    Used by the identity review's confirm dialog so an admin sees every row
    that will be rewritten (name/GNZ ID before -> after, highlighted) plus the
    resulting URL before committing a merge.
    """
    if not req.merge_ids:
        raise HTTPException(400, "No athletes to merge")
    if req.athlete_id in req.merge_ids:
        raise HTTPException(400, "Cannot merge an athlete into itself")

    session = get_session()
    try:
        survivor = session.get(Athlete, req.athlete_id)
        if survivor is None:
            raise HTTPException(404, "Survivor athlete not found")

        def _summary(a: Athlete) -> dict:
            agg = (
                session.query(
                    func.count(LongScore.id),
                    func.count(func.distinct(LongScore.event_id)),
                    func.group_concat(func.distinct(LongScore.club_name)),
                    func.group_concat(func.distinct(Event.year)),
                )
                .join(Event, Event.id == LongScore.event_id)
                .filter(LongScore.athlete_id == a.id)
                .group_by(LongScore.athlete_id)
                .first()
            )
            rows, event_count, clubs, years = agg or (0, 0, None, None)
            intents = [
                y for (y,) in session.query(WellingtonIntent.year)
                .filter(WellingtonIntent.athlete_id == a.id)
                .all()
            ]
            return {
                "athlete_id": a.id,
                "slug": a.slug,
                "name": a.canonical_name,
                "gnz_id": a.gnz_id,
                "clubs": sorted(set(_split_csv(clubs))),
                "events": event_count,
                "event_ids": [],
                "years": [int(y) for y in sorted(set(_split_csv(years)))],
                "disciplines": [],
                "rows": rows,
                "intent_years": sorted(intents),
            }

        survivor_summary = _summary(survivor)
        pairs = []
        for mid in req.merge_ids:
            merged = session.get(Athlete, mid)
            if merged is None:
                raise HTTPException(404, f"Athlete {mid} not found")
            if merged.id == survivor.id:
                raise HTTPException(400, "Cannot merge an athlete into itself")

            name = survivor.canonical_name
            gid = survivor.gnz_id
            if not gid:
                gid = merged.gnz_id

            change_rows = (
                session.query(
                    LongScore.event_id,
                    func.min(Event.name),
                    LongScore.gymnast_name,
                    LongScore.gnz_id,
                    func.count(LongScore.id),
                )
                .join(Event, Event.id == LongScore.event_id)
                .filter(LongScore.athlete_id == merged.id)
                .group_by(LongScore.event_id, LongScore.gymnast_name, LongScore.gnz_id)
                .order_by(func.min(Event.name))
                .all()
            )
            changes = [
                MergeChangeRow(
                    event_id=eid,
                    event_name=ename,
                    rows=cnt,
                    old_name=old_name,
                    old_gnz_id=old_gid or "",
                    new_name=name,
                    new_gnz_id=gid or "",
                )
                for eid, ename, old_name, old_gid, cnt in change_rows
            ]
            intent_moves = [
                y for (y,) in session.query(WellingtonIntent.year)
                .filter(WellingtonIntent.athlete_id == merged.id)
                .all()
            ]
            new_survivor_slug = _slug_from_hash(
                _signature_hash(survivor.canonical_name.strip().lower(), gid or "")
            )
            pairs.append(MergePairPreview(
                survivor=survivor_summary,
                merged=_summary(merged),
                target_name=name,
                target_gnz_id=gid or "",
                changes=changes,
                intent_moves=sorted(intent_moves),
                survivor_slug=new_survivor_slug,
                merged_slug=merged.slug,
            ))
        return MergePreviewResponse(pairs=pairs)
    finally:
        session.close()


@app.post("/api/admin/athletes/merge", response_model=MergeAthletesResponse)
def merge_athletes(
    req: MergeAthletesRequest,
    _auth=Depends(require_role("admin")),
):
    if req.athlete_id == req.merge_id:
        raise HTTPException(400, "Cannot merge an athlete into itself")

    session = get_session()
    try:
        survivor = session.get(Athlete, req.athlete_id)
        merged = session.get(Athlete, req.merge_id)
        if survivor is None or merged is None:
            raise HTTPException(404, "Athlete not found")

        name = survivor.canonical_name
        gid = survivor.gnz_id
        if not gid:
            gid = merged.gnz_id
            survivor.gnz_id = gid

        updated = (
            session.query(LongScore)
            .filter(LongScore.athlete_id == merged.id)
            .update(
                {
                    LongScore.gymnast_name: name,
                    LongScore.gnz_id: gid,
                    LongScore.identity_override: None,
                },
                synchronize_session=False,
            )
        )
        # The survivor's rows are unmarked too, so the merge fully commits
        # (an override would otherwise keep the two athletes hard-separated).
        session.query(LongScore).filter(
            LongScore.athlete_id == survivor.id,
        ).update(
            {LongScore.identity_override: None},
            synchronize_session=False,
        )

        # Move Wellington intents from merged -> survivor (unique per year).
        existing_years = {
            i.year
            for i in session.query(WellingtonIntent)
            .filter(WellingtonIntent.athlete_id == survivor.id)
            .all()
        }
        for intent in (
            session.query(WellingtonIntent)
            .filter(WellingtonIntent.athlete_id == merged.id)
            .all()
        ):
            if intent.year in existing_years:
                session.delete(intent)
            else:
                intent.athlete_id = survivor.id
                intent.gnz_id = gid
                existing_years.add(intent.year)

        session.commit()
        rebuild_athletes(session)
        invalidate()

        # The survivor's Athlete row may be re-created (new signature) when its
        # gnz_id was empty and got promoted; locate it by the merged identity.
        result = (
            session.query(Athlete)
            .filter(
                Athlete.canonical_name == name,
                Athlete.gnz_id == gid,
            )
            .first()
        )
        if result is None:
            raise HTTPException(500, "Merge did not produce a surviving athlete")

        return MergeAthletesResponse(
            merged_rows=updated,
            survivor_id=result.id,
            survivor_slug=result.slug,
        )
    finally:
        session.close()


@app.post("/api/admin/athletes/split", response_model=SplitAthleteResponse)
def split_athlete(
    req: SplitAthleteRequest,
    _auth=Depends(require_role("admin")),
):
    session = get_session()
    try:
        athlete = session.get(Athlete, req.athlete_id)
        if athlete is None:
            raise HTTPException(404, "Athlete not found")

        base = session.query(LongScore).filter(LongScore.athlete_id == athlete.id)
        total = base.count()
        if total == 0:
            raise HTTPException(400, "Athlete has no rows")

        if req.split_by == "gnz_id":
            subset = base.filter(LongScore.gnz_id == req.value)
        elif req.split_by == "event_id":
            try:
                event_id = int(req.value)
            except ValueError:
                raise HTTPException(400, "event_id must be a number")
            subset = base.filter(LongScore.event_id == event_id)
        elif req.split_by == "club_name":
            subset = base.filter(LongScore.club_name == req.value)
        else:
            raise HTTPException(
                400,
                f"Unknown split_by {req.split_by!r} (use gnz_id, event_id or club_name)",
            )

        count = subset.count()
        if count == 0:
            raise HTTPException(400, "No rows match that value")
        if count == total:
            raise HTTPException(400, "Cannot split off every row of the athlete")

        # Identify rows by id so the two athletes can be found after the
        # rebuild re-keyed them (the original athlete row is recreated when
        # the split-off ID was the cluster's canonical ID).
        subset_ids = {r[0] for r in subset.with_entities(LongScore.id).all()}
        all_ids = {r[0] for r in base.with_entities(LongScore.id).all()}
        remainder_ids = all_ids - subset_ids

        new_gid = req.new_gnz_id or _fresh_synthetic_id(session)
        override = _fresh_override_token()
        subset.update(
            {
                LongScore.gnz_id: new_gid,
                LongScore.identity_override: override,
            },
            synchronize_session=False,
        )
        session.commit()
        rebuild_athletes(session)
        invalidate()

        created_id = session.get(LongScore, next(iter(subset_ids))).athlete_id
        original_id = session.get(LongScore, next(iter(remainder_ids))).athlete_id
        created = session.get(Athlete, created_id)
        original = session.get(Athlete, original_id)
        if original is None or created is None:
            raise HTTPException(500, "Split did not produce two athletes")

        return SplitAthleteResponse(
            split_rows=count,
            original_id=original.id,
            original_slug=original.slug,
            created_id=created.id,
            created_slug=created.slug,
        )
    finally:
        session.close()


# ---------------------------------------------------------------------------
# Upload
# ---------------------------------------------------------------------------

@app.post("/api/upload", response_model=EventResponse)
def upload_file(file: UploadFile = File(...), allow_unknown: str = None, host_club: str = None, _auth=Depends(require_role("admin"))):
    if not file.filename or not file.filename.endswith(".json"):
        raise HTTPException(400, "Only .json files are accepted")

    raw = file.file.read()
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        raise HTTPException(400, f"Invalid JSON: {e}")

    return _ingest_event(data, allow_unknown, host_club)


def _resolve_host_club(event_name: str, host_club: str | None = None) -> str | None:
    """Pick an event's host club: explicit value wins, else a name-based guess.

    National events default to ``"Gymnastics NZ"`` (they aren't hosted by a
    member club). Returns ``None`` when nothing resolves.
    """
    explicit = (host_club or "").strip()
    if explicit:
        return explicit
    guess = _guess_host_club(event_name)
    if guess:
        return guess
    if "national" in event_name.lower():
        return "Gymnastics NZ"
    return None


def _ingest_event(data: dict, allow_unknown: str | None, host_club: str | None = None) -> EventResponse:
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
            "suggestions": suggest_club_mapping(unknown),
        })

    try:
        event_info, rows = parse_json(data)
    except ParseError as e:
        raise HTTPException(422, f"Parse error: {e}")

    collision_warnings = detect_participant_collisions(data)

    session = get_session()
    try:
        # Re-upload: replace every existing copy of the same competition
        # (name + start date + discipline) so re-imports never accumulate
        # duplicates, and a same-named event from another year is left alone.
        existing = (
            session.query(Event)
            .filter(
                Event.name == event_info["name"],
                Event.start_date == event_info["start_date"],
                Event.discipline == event_info["discipline"],
            )
            .all()
        )
        for event in existing:
            session.delete(event)
        if existing:
            session.flush()

        event = Event(
            name=event_info["name"],
            start_date=event_info["start_date"],
            end_date=event_info["end_date"],
            discipline=event_info["discipline"],
            year=event_info.get("year"),
            host_club=_resolve_host_club(event_info["name"], host_club),
        )
        session.add(event)
        session.flush()

        # Backfill missing GNZ IDs from existing database records
        rows_without = [r for r in rows if not r.get("gnz_id")]
        if rows_without:
            names = {r["gymnast_name"].strip().lower() for r in rows_without}
            existing = (
                session.query(func.lower(func.trim(LongScore.gymnast_name)), LongScore.gnz_id)
                .filter(
                    func.lower(func.trim(LongScore.gymnast_name)).in_(names),
                    LongScore.gnz_id.isnot(None),
                    LongScore.gnz_id != "",
                )
                .distinct()
                .all()
            )
            name_to_id: dict[str, str] = {}
            for name, gid in existing:
                # Guard: only backfill when the name maps to exactly one distinct
                # numeric ID — ambiguous names must stay blank for manual review
                # rather than risk attaching the wrong person's ID.
                if not gid.isdigit():
                    continue
                if name in name_to_id and name_to_id[name] != gid:
                    name_to_id.pop(name)
                    continue
                name_to_id[name] = gid
            for row in rows:
                if not row.get("gnz_id"):
                    key = row["gymnast_name"].strip().lower()
                    if key in name_to_id:
                        row["gnz_id"] = name_to_id[key]

        for row in rows:
            score = LongScore(event_id=event.id, **row)
            session.add(score)
        session.commit()
        cache.invalidate_prefix("medals")
        invalidate(event.id)

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

        report = reconcile_athletes()
        rebuild_athletes(session)

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
            ids_corrected=report["ids_corrected"],
            names_unified=report["names_unified"],
            conflicts=report.get("conflicts", []),
            host_club=event.host_club,
            warnings=collision_warnings,
        )
    finally:
        session.close()


@app.post("/api/import-url", response_model=EventResponse)
def import_from_url(req: ImportUrlRequest, _auth=Depends(require_role("admin"))):
    if not req.url.strip():
        raise HTTPException(400, "URL is required")
    try:
        data = fetch_event_json(req.url.strip())
    except ScoreholderFetchError as e:
        raise HTTPException(502, str(e))
    return _ingest_event(data, "1" if req.allow_unknown else None, req.host_club)


# ---------------------------------------------------------------------------
# List events
# ---------------------------------------------------------------------------

@app.get("/api/events", response_model=list[EventListItem])
def list_events(response: Response):
    response.headers.update(cache_headers())
    session = get_session()
    try:
        stmt = (
            session.query(
                Event,
                func.count(func.distinct(func.coalesce(LongScore.athlete_id, LongScore.gymnast_name))).label("gymnast_count"),
            )
            .outerjoin(LongScore, Event.id == LongScore.event_id)
            .group_by(Event.id)
            .order_by(Event.start_date.desc())
        )
        results = stmt.all()
        return [
            EventListItem(
                id=ev.id,
                name=ev.name,
                start_date=ev.start_date,
                end_date=ev.end_date,
                discipline=ev.discipline,
                year=ev.year,
                gymnast_count=gymnast_count or 0,
                is_national=bool(ev.is_national),
                host_club=ev.host_club,
            )
            for ev, gymnast_count in results
        ]
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
def get_all_results_wide(response: Response, gnz_id: str = None, club: str = None, year: int = None, athlete_id: int = None, slug: str = None):
    response.headers.update(cache_headers())
    return cached(
        ("wide-all", year or "", gnz_id or "", club or "", athlete_id or "", slug or ""),
        lambda: _compute_wide_all(year, gnz_id, club, athlete_id, slug),
        ttl=300,
    )


def _compute_wide_all(year: int | None, gnz_id: str | None, club: str | None, athlete_id: int | None = None, slug: str | None = None) -> dict:
    session = get_session()
    try:
        resolved_id = athlete_id
        if not resolved_id and slug:
            resolved_id = resolve_identity(session, slug=slug)
        if not resolved_id and gnz_id:
            resolved_id = resolve_identity(session, gnz_id=gnz_id)
        query = session.query(Event.id).order_by(Event.created_at.desc())
        if year:
            query = query.filter(Event.year == year)
        event_ids = [r[0] for r in query.all()]
        result = {}
        if event_ids:
            result = pivot_to_wide_dict_multi(event_ids, session, gnz_id, club, resolved_id)
        if (resolved_id or gnz_id) and not result:
            name_row = None
            if resolved_id:
                athlete = session.get(Athlete, resolved_id)
                if athlete and athlete.canonical_name:
                    name_row = (athlete.canonical_name,)
                else:
                    name_row = (
                        session.query(LongScore.gymnast_name)
                        .filter(
                            LongScore.athlete_id == resolved_id,
                            LongScore.gymnast_name.isnot(None),
                            LongScore.gymnast_name != "",
                        )
                        .order_by(LongScore.id.desc())
                        .first()
                    )
                if name_row:
                    result["name"] = name_row[0]
            else:
                athlete_id = resolve_identity(session, gnz_id=gnz_id)
                if athlete_id is not None:
                    athlete = session.get(Athlete, athlete_id)
                    if athlete and athlete.canonical_name:
                        result["name"] = athlete.canonical_name
                if "name" not in result:
                    name_row = (
                        session.query(LongScore.gymnast_name)
                        .filter(
                            LongScore.gnz_id == gnz_id,
                            LongScore.gymnast_name.isnot(None),
                            LongScore.gymnast_name != "",
                        )
                        .order_by(LongScore.id.desc())
                        .first()
                    )
                    if name_row:
                        result["name"] = name_row[0]
        return result
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
        cache.invalidate_prefix("medals")
        invalidate(event_id)
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
        if body.host_club is not None:
            event.host_club = body.host_club or None
        session.commit()
        cache.invalidate_prefix("medals")
        invalidate(event_id)
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
            host_club=event.host_club,
        )
    finally:
        session.close()