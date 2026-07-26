import json
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, Header, Request, UploadFile, Depends
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
from app.cache import cache_headers, cached, invalidate
from app.database import get_session, init_db
from app.models import Event, LongScore, User
from app.parser import ParseError, _NAME_TO_CANONICAL, find_unknown_clubs, parse_json, reload_club_maps, validate_upload_structure
from app.reconcile import reconcile_athletes
from app.schemas import (
    ApplyFixItem,
    ClubItem,
    ConflictItem,
    DuplicateGroup,
    DuplicateInstance,
    EventListItem,
    EventResponse,
    EventUpdate,
    FixDuplicatesResponse,
    GymnastItem,
    LoginRequest,
    MergeNamesRequest,
    RankingsResponse,
    RankingRow,
    ResultsResponse,
    StatsResponse,
    StepsResponse,
    SuggestedMerge,
    TokenResponse,
    UploadValidationResponse,
    UserCreate,
    UserResponse,
    UserUpdate,
)
from app.transformer import _find_region, _use_vault_average, export_csv, export_xlsx, pivot_to_wide, pivot_to_wide_dict, pivot_to_wide_dict_multi


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


@app.middleware("http")
async def add_cache_control(request: Request, call_next):
    response: Response = await call_next(request)
    path = request.url.path

    if request.method == "GET" and (
        path.startswith("/api/events")
        or path.startswith("/api/results")
        or path == "/api/stats"
        or path == "/api/clubs"
        or path == "/api/gymnasts"
        or path == "/api/years"
    ):
        if not response.headers.get("Cache-Control"):
            response.headers["Cache-Control"] = "public, max-age=300, stale-while-revalidate=3600"
    elif (
        path.startswith("/api/admin")
        or request.method in ("POST", "PUT", "DELETE", "PATCH")
    ):
        response.headers["Cache-Control"] = "no-store, no-cache, private"

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
            total_gymnasts=session.query(func.count(func.distinct(LongScore.gymnast_name))).scalar() or 0,
            total_scores=session.query(func.count(LongScore.id)).scalar() or 0,
            total_clubs=session.query(func.count(func.distinct(LongScore.club_name))).scalar() or 0,
        )
    finally:
        session.close()


@app.get("/api/clubs", response_model=list[ClubItem])
def list_clubs(response: Response):
    response.headers.update(cache_headers())
    data = cached(("clubs",), lambda: _compute_clubs(), ttl=300)
    return data


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
        club_data_path = Path(__file__).resolve().parent.parent / "clubs_and_regions.json"
        if club_data_path.exists():
            with open(club_data_path) as f:
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
def list_gymnasts(response: Response):
    response.headers.update(cache_headers())
    data = cached(("gymnasts",), lambda: _compute_gymnasts(), ttl=300)
    return data


def _compute_gymnasts() -> list[GymnastItem]:
    from collections import defaultdict

    session = get_session()
    try:
        rows = (
            session.query(LongScore.gymnast_name, LongScore.gnz_id, LongScore.club_name)
            .filter(LongScore.gnz_id.isnot(None), LongScore.gnz_id != "")
            .distinct()
            .all()
        )

        name_groups: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
        club_groups: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
        name_casing: dict[str, str] = {}

        for name, gnz_id, club in rows:
            key = name.strip().lower()
            name_casing[key] = name_casing.get(key, name.strip())
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

            result.append(GymnastItem(
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
                LongScore.pass_final_score.isnot(None),
            )
            .distinct()
            .order_by(LongScore.level_category)
            .all()
        )
        return StepsResponse(steps=[s[0] for s in steps])
    finally:
        session.close()


_QUALIFIER_THRESHOLDS = {
    "STEP 5": 52.0,
    "STEP 6": 52.0,
    "STEP 7": 43.0,
    "STEP 8": 43.0,
}


def _is_qualifier(data: dict, step: str) -> bool:
    threshold = _QUALIFIER_THRESHOLDS.get(step)
    if threshold is None:
        return True
    return any(s >= threshold for s in data["scores"])


@app.get("/api/rankings", response_model=RankingsResponse)
def get_rankings(
    year: int,
    step: str,
    discipline: str,
    quota: bool = False,
    qualifier: bool = False,
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
                LongScore.apparatus,
                LongScore.pass_number,
                LongScore.pass_final_score,
                LongScore.aa_score,
                LongScore.round_type,
            )
            .filter(
                LongScore.event_id.in_(event_ids),
                LongScore.level_category == step,
                LongScore.discipline == discipline,
                LongScore.pass_final_score.isnot(None),
            )
            .all()
        )

        from collections import defaultdict

        # Group rows by (gymnast, event, round_type)
        event_groups: dict[tuple, list] = defaultdict(list)
        for r in rows:
            key = (r.gymnast_name, r.gnz_id, r.club_name, r.event_id, r.event_name, r.round_type)
            event_groups[key].append(r)

        # Compute a single competition score per (gymnast, event, round_type)
        # then pick top 2 competitions per gymnast (same as before)
        comp_scores: dict[str, list[tuple[float, str, str, str]]] = defaultdict(list)
        for (name, gnz_id, club, eid, ename, rt), scores in event_groups.items():
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

            comp_scores[name].append((comp_score, ename, gnz_id or "", club or ""))

        # Build gymnast_data: aggregate competitions per gymnast,
        # take top 2 by score, keep the best gnz_id and club per gymnast
        gymnast_data: dict[str, dict] = {}
        for name, entries in comp_scores.items():
            paired = sorted(entries, key=lambda x: -x[0])
            top_two = paired[:2]
            best_gnz_id = next((e[2] for e in paired if e[2]), "")
            best_club = next((e[3] for e in paired if e[3]), "")
            gymnast_data[name] = {
                "name": name,
                "gnz_id": best_gnz_id,
                "club": best_club,
                "scores": [s[0] for s in top_two],
                "competitions": [s[1] for s in top_two],
            }

        # Qualifier filter: check all per-competition max scores against threshold
        if qualifier:
            gymnast_data = {
                k: v for k, v in gymnast_data.items()
                if _is_qualifier(v, step)
            }

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
                region=r["region"],
                scores=r["scores"],
                competitions=r["competitions"],
                total=round(r["total"], 3),
            )
            for r in ranking_list
        ]

        return RankingsResponse(year=year, step=step, discipline=discipline, rankings=rankings)
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
            invalidate()

        return {"applied": total}
    finally:
        session.close()


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
        return {
            "merged": updated,
            "names_unified": report["names_unified"],
            "ids_corrected": report["ids_corrected"],
            "conflicts": report.get("conflicts", []),
        }
    finally:
        session.close()


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
                if gid.isdigit() and (name not in name_to_id or len(gid) > len(name_to_id[name])):
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
        stmt = (
            session.query(
                Event,
                func.count(func.distinct(LongScore.gymnast_name)).label("gymnast_count"),
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
def get_all_results_wide(response: Response, gnz_id: str = None, club: str = None, year: int = None):
    response.headers.update(cache_headers())
    return cached(
        ("wide-all", year or "", gnz_id or "", club or ""),
        lambda: _compute_wide_all(year, gnz_id, club),
        ttl=300,
    )


def _compute_wide_all(year: int | None, gnz_id: str | None, club: str | None) -> dict:
    session = get_session()
    try:
        query = session.query(Event.id).order_by(Event.created_at.desc())
        if year:
            query = query.filter(Event.year == year)
        event_ids = [r[0] for r in query.all()]
        if not event_ids:
            return {}
        return pivot_to_wide_dict_multi(event_ids, session, gnz_id, club)
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
        session.commit()
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
        )
    finally:
        session.close()