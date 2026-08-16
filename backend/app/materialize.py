"""Persistent materialized stores for precomputed results and rankings.

Every data mutation (upload, edit, merge/split, intent toggle, …) invalidates the
in-memory cache via :func:`app.cache.invalidate`, which bumps a persisted
``epoch`` in the materialized store and — when running inside the live app —
kicks a background rebuild. The rebuild recomputes the two derived stores once:

* ``wide_rows`` — the output of ``transformer._pivot_long_rows`` flattened to one
  row per (event, discipline, athlete, round_type). Request pages and wide-all
  reads become indexed ``SELECT``s instead of per-request Pandas pivots.
* ``ranking_marks`` — the output of ``main._build_event_marks`` per
  ``(year, discipline, step, division)`` stored as a JSON blob, so leaderboards,
  qualifier filters, quota and specialists derive in-memory at request time.

The store lives in a separate SQLite file (``<source>.materialized.db``) derived
from the *current* source engine so tests isolate automatically. Rebuilds write
in a single transaction, so WAL readers always see the previous or the new
complete version — never a partial one. Wellington rankings deliberately stay
out of the store (``/api/rankings/wellington`` is always live-computed): the
page is low traffic and an intent toggle must reflect on the very next read.
See STEP 30 in PLAN.md.
"""

import json
import logging
import os
import threading
import time
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import Session, sessionmaker

from app import database as db_mod
from app.models import Athlete, Event, LongScore
from app.transformer import (
    _athlete_maps,
    _compute_pivot,
    _pivot_long_rows,
    _wide_column_list_for_prefixes,
)

logger = logging.getLogger("materialize")

_SCHEMA_VERSION = "1"
_META_DEFAULTS = {
    "schema_version": _SCHEMA_VERSION,
    "ready": "0",
    "building": "0",
    "epoch": "0",
    "built_epoch": "0",
    "last_rebuild_at": "",
    "last_rebuild_ms": "0",
    "last_rebuild_size_bytes": "0",
}

WAG_PREFIXES = ["vt", "ub", "bb", "fx"]
MAG_PREFIXES = ["fx", "ph", "sr", "vt", "pb", "hb"]

# Module-level store state. The engine is created lazily from the *current*
# source engine URL so tests (which patch app.database.engine per test) get an
# isolated store next to their temp DB. reset() clears it between tests.
_engine = None
_SessionLocal = None
_store_path = None
_init_lock = threading.Lock()
# Events whose wide_rows may be stale. A mutation marks its event dirty; the
# read paths refresh it on demand (or live-pivot if a full rebuild holds the
# lock), and a completed fresh full rebuild clears the set.
_dirty_events: set[int] = set()
_dirty_lock = threading.Lock()
_rebuild_lock = threading.Lock()
_rebuild_thread: "threading.Thread | None" = None
_thread_lock = threading.Lock()
_auto_rebuild = False


# ---------------------------------------------------------------------------
# Store lifecycle
# ---------------------------------------------------------------------------

def _derive_store_path() -> str | None:
    url = db_mod.engine.url
    db = url.database
    if not db or db == ":memory:":
        return None
    p = Path(db)
    return str(p.with_name(p.stem + ".materialized.db"))


def _set_pragmas(engine):
    @event.listens_for(engine, "connect")
    def _set_sqlite_pragmas(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA busy_timeout=30000")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


def _create_tables(engine):
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT)"))
        conn.execute(text(
            """
            CREATE TABLE IF NOT EXISTS wide_rows (
                id INTEGER PRIMARY KEY,
                event_id INTEGER NOT NULL,
                year INTEGER,
                event_sort REAL,
                event_name TEXT,
                discipline TEXT,
                athlete_id INTEGER,
                club TEXT,
                gnz_id TEXT,
                name TEXT,
                payload TEXT
            )
            """
        ))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_wide_event ON wide_rows(event_id)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_wide_athlete_year ON wide_rows(athlete_id, year)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_wide_club_year ON wide_rows(club, year)"))
        conn.execute(text("CREATE TABLE IF NOT EXISTS ranking_marks (key TEXT PRIMARY KEY, payload TEXT)"))
        # The Wellington store was removed (the endpoint is always live-computed);
        # drop the table so pre-existing store files don't carry stale blobs.
        conn.execute(text("DROP TABLE IF EXISTS wellington_cache"))
        for key, value in _META_DEFAULTS.items():
            conn.execute(text("INSERT OR IGNORE INTO meta (key, value) VALUES (:k, :v)"),
                         {"k": key, "v": value})


def init_materialized():
    """Ensure the materialized store exists and return its engine (None for
    in-memory source databases). Idempotent; the engine is cached for the
    process lifetime but re-created when the source engine's path changes
    (test isolation)."""
    global _engine, _SessionLocal, _store_path
    path = _derive_store_path()
    if path is None:
        return None
    with _init_lock:
        if _engine is not None and _store_path == path:
            return _engine
        if _engine is not None:
            _engine.dispose()
        _store_path = path
        engine = create_engine(f"sqlite:///{path}", connect_args={"check_same_thread": False})
        _set_pragmas(engine)
        _create_tables(engine)
        _SessionLocal = sessionmaker(bind=engine, class_=Session)
        _engine = engine
        return engine


def reset() -> None:
    """Clear cached store state (test isolation only)."""
    global _engine, _SessionLocal, _store_path, _rebuild_thread
    with _init_lock:
        _engine = None
        _SessionLocal = None
        _store_path = None
    with _thread_lock:
        _rebuild_thread = None
    with _dirty_lock:
        _dirty_events.clear()


def mark_event_dirty(event_id: int) -> None:
    """Record an event whose wide_rows may be stale (a mutation that couldn't
    refresh the store synchronously, e.g. while a full rebuild held the lock).
    The read paths refresh it on demand; a completed fresh rebuild clears it."""
    with _dirty_lock:
        _dirty_events.add(event_id)


def dirty_events() -> set[int]:
    """Snapshot of events whose store rows may be stale."""
    with _dirty_lock:
        return set(_dirty_events)


def _dirty_remove(event_id: int) -> None:
    with _dirty_lock:
        _dirty_events.discard(event_id)


def _dirty_clear_all() -> None:
    with _dirty_lock:
        _dirty_events.clear()


def enable_auto_rebuild() -> None:
    """Turn on background rebuilds (called from the app lifespan)."""
    global _auto_rebuild
    _auto_rebuild = True


# ---------------------------------------------------------------------------
# meta helpers
# ---------------------------------------------------------------------------

def _meta_get(key: str) -> str | None:
    engine = init_materialized()
    if engine is None:
        return None
    with engine.connect() as conn:
        row = conn.execute(text("SELECT value FROM meta WHERE key = :k"), {"k": key}).fetchone()
    return row[0] if row else None


def _meta_set(key: str, value) -> None:
    engine = init_materialized()
    if engine is None:
        return
    with engine.begin() as conn:
        conn.execute(
            text("INSERT INTO meta (key, value) VALUES (:k, :v) "
                 "ON CONFLICT(key) DO UPDATE SET value = excluded.value"),
            {"k": key, "v": str(value)},
        )


def mark_needs_rebuild() -> None:
    """Bump the persisted mutation epoch (called from cache.invalidate)."""
    engine = init_materialized()
    if engine is None:
        return
    with engine.begin() as conn:
        conn.execute(text("UPDATE meta SET value = CAST(value AS INTEGER) + 1 WHERE key = 'epoch'"))


def maybe_kick_rebuild() -> None:
    """Start a background rebuild when the app is running (no-op for CLIs/tests)."""
    if _auto_rebuild:
        rebuild_async()


def needs_rebuild() -> bool:
    """True when the store is empty or a mutation happened since the last build."""
    if not is_ready():
        return True
    epoch = _meta_get("epoch")
    built = _meta_get("built_epoch")
    if epoch is None or built is None:
        return True
    return str(epoch) != str(built)


def is_ready() -> bool:
    return _meta_get("ready") == "1"


def status() -> dict:
    return {
        "ready": is_ready(),
        "building": _meta_get("building") == "1",
        "needs_rebuild": needs_rebuild(),
        "last_rebuild_at": _meta_get("last_rebuild_at") or "",
        "last_rebuild_ms": float(_meta_get("last_rebuild_ms") or 0),
        "last_rebuild_size_bytes": int(_meta_get("last_rebuild_size_bytes") or 0),
    }


# ---------------------------------------------------------------------------
# Serialization helpers
# ---------------------------------------------------------------------------

def _serialized(obj) -> str:
    return json.dumps(obj, sort_keys=True, ensure_ascii=False)


# The marks blob stores the _build_event_marks output as JSON arrays of
# [key, ...] tuples rather than object keys, so integer athlete/event IDs keep
# their type through the round-trip (JSON object keys would stringify them).

def _per_event_nested(per_event: dict) -> list:
    """Serialize the tuple-keyed per_event dict as [[key, eid, entry], ...]."""
    return [[k, e, v] for (k, e), v in per_event.items()]


def _per_event_flat(lst: list) -> dict:
    """Inverse of _per_event_nested — reconstruct tuple keys on load."""
    return {(k, e): v for k, e, v in lst}


def _apparatus_events_to_list(d: dict) -> list:
    """Serialize {key: {app: {eid: entry}}} as [[key, app, eid, entry], ...]."""
    return [[k, app, eid, entry]
            for k, apps in d.items()
            for app, evs in apps.items()
            for eid, entry in evs.items()]


def _apparatus_events_from_list(lst: list) -> dict:
    out: dict = defaultdict(lambda: defaultdict(dict))
    for k, app, eid, entry in lst:
        out[k][app][eid] = entry
    return out


def _meta_to_list(d: dict) -> list:
    return [[k, v] for k, v in d.items()]


def _meta_from_list(lst: list) -> dict:
    return {k: v for k, v in lst}


def _to_long_dict(s: LongScore) -> dict:
    return {
        "gymnast_name": s.gymnast_name,
        "gnz_id": s.gnz_id or "",
        "club_name": s.club_name or "",
        "discipline": s.discipline,
        "level_category": s.level_category or "",
        "division": s.division or "",
        "round_type": s.round_type or "",
        "apparatus": s.apparatus,
        "d_score": s.d_score,
        "e_score": s.e_score,
        "n_score": s.neutral_deductions,
        "total_score": s.pass_final_score,
        "apparatus_rank": s.apparatus_rank,
        "aa_score": s.aa_score,
        "aa_rank": s.aa_rank,
        "bonus": s.bonus,
        "athlete_id": s.athlete_id,
    }


# ---------------------------------------------------------------------------
# Rebuild
# ---------------------------------------------------------------------------

def _pivot_worker(job):
    """Process-pool worker: pivot a chunk of (event_id, long dicts) groups.

    Pure pandas over the passed data — never touches the DB, so forking is safe.
    Returns ``[(event_id, discipline, row_dict), ...]``."""
    chunk, slug_by_id, name_by_id = job
    out = []
    for eid, longs in chunk:
        data = _pivot_long_rows(longs, slug_by_id, name_by_id)
        for disc_key in ("wag", "mag"):
            disc = data.get(disc_key)
            if not disc:
                continue
            for row in disc["rows"]:
                out.append((eid, disc_key.upper(), row))
    return out


def _compute_wide_rows_all(session) -> list[tuple]:
    """Rebuild the full wide_rows store. Loads all long scores once, pivots
    per event in a process pool (events are independent), returns insert tuples."""
    rows = session.query(LongScore).all()
    slug_by_id, name_by_id = _athlete_maps(session)
    id_by_slug = {slug: aid for aid, slug in slug_by_id.items()}
    events = {
        ev.id: (ev.year, ev.created_at.timestamp() if ev.created_at else 0.0, ev.name)
        for ev in session.query(Event).all()
    }
    by_event: dict[int, list[dict]] = defaultdict(list)
    for obj in rows:
        by_event[obj.event_id].append(_to_long_dict(obj))
    items = list(by_event.items())
    # MATERIALIZE_WORKERS overrides the worker count (production can lower it to
    # bound rebuild memory/CPU on a memory-constrained host).
    workers = int(os.environ.get("MATERIALIZE_WORKERS", "0") or 0) or min(6, os.cpu_count() or 1)
    if len(items) < 20 or workers <= 1:
        parts = [_pivot_worker((items, slug_by_id, name_by_id))]
    else:
        chunks = [items[i::workers] for i in range(workers)]
        with ProcessPoolExecutor(max_workers=workers) as pool:
            parts = list(pool.map(
                _pivot_worker,
                [(chunk, slug_by_id, name_by_id) for chunk in chunks],
            ))
    wide: list[tuple] = []
    for part in parts:
        wide.extend(part)
    out: list[tuple] = []
    for eid, disc, row in wide:
        year, sort_ts, ename = events.get(eid, (None, 0.0, ""))
        # The pivot emits a slug but not the athlete_id itself, so recover the
        # athlete id from the slug for the indexed filter column.
        athlete_id = id_by_slug.get(row.get("slug"))
        out.append((
            eid, year, sort_ts, ename, disc,
            athlete_id, row.get("club"), row.get("gnz-id"),
            row.get("name"), _serialized(row),
        ))
    return out


def _ranking_rows(session, year: int, discipline: str, step: str, division: str):
    """Mirror of the /api/rankings source query (main.py:1173-1208)."""
    event_ids = [
        e.id
        for e in session.query(Event).filter(
            Event.year == year,
            Event.is_national == False,  # noqa: E712
        ).all()
    ]
    if not event_ids:
        return []
    return (
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


def _discover_mark_keys(session) -> list[tuple]:
    """Return [(year, discipline, step, division)] where division is "" or a
    distinct non-empty division present for that (year, discipline, step)."""
    rows = session.execute(text(
        "SELECT e.year, s.discipline, s.level_category, coalesce(s.division, '') "
        "FROM long_scores s JOIN events e ON s.event_id = e.id "
        "WHERE e.is_national = 0 AND s.pass_final_score IS NOT NULL "
        "GROUP BY 1, 2, 3, 4"
    )).fetchall()
    by_step: dict[tuple, set[str]] = defaultdict(set)
    for year, disc, step, division in rows:
        by_step[(year, disc, step)].add(division)
    keys = []
    for (year, disc, step), divisions in by_step.items():
        keys.append((year, disc, step, ""))
        keys.extend((year, disc, step, d) for d in sorted(divisions) if d)
    return keys


def _compute_marks_all(session) -> dict[str, str]:
    """Rebuild the ranking_marks store: one _build_event_marks blob per key."""
    from app.main import _build_event_marks  # lazy: avoids a top-level app.main import
    athletes = {a.id: a for a in session.query(Athlete).all()}
    marks: dict[str, str] = {}
    for key in _discover_mark_keys(session):
        year, discipline, step, division = key
        rows = _ranking_rows(session, year, discipline, step, division)
        per_event, apparatus_events, meta_by_key = _build_event_marks(rows, step, athletes)
        for a_key, meta in meta_by_key.items():
            if isinstance(a_key, int) and a_key in athletes:
                meta["slug"] = athletes[a_key].slug
        marks["|".join(map(str, key))] = _serialized({
            "per_event": _per_event_nested(per_event),
            "apparatus_events": _apparatus_events_to_list(apparatus_events),
            "meta_by_key": _meta_to_list(meta_by_key),
        })
    return marks


def _replace_store(engine, wide_tuples: list[tuple], marks: dict[str, str],
                   built_epoch: str, start: float) -> None:
    """Atomically swap all stores in one transaction (readers keep the old
    committed version until commit)."""
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM wide_rows"))
        if wide_tuples:
            conn.exec_driver_sql(
                "INSERT INTO wide_rows (event_id, year, event_sort, event_name, discipline, "
                "athlete_id, club, gnz_id, name, payload) VALUES (?,?,?,?,?,?,?,?,?,?)",
                wide_tuples,
            )
        conn.execute(text("DELETE FROM ranking_marks"))
        if marks:
            conn.exec_driver_sql(
                "INSERT INTO ranking_marks (key, payload) VALUES (?, ?)",
                list(marks.items()),
            )
        ms = (time.time() - start) * 1000.0
        conn.execute(text("UPDATE meta SET value = '1' WHERE key = 'ready'"))
        conn.execute(text("UPDATE meta SET value = '0' WHERE key = 'building'"))
        conn.execute(text("UPDATE meta SET value = :v WHERE key = 'built_epoch'"), {"v": built_epoch})
        conn.execute(text("UPDATE meta SET value = :v WHERE key = 'last_rebuild_ms'"),
                     {"v": str(round(ms, 1))})
        conn.execute(text("UPDATE meta SET value = :v WHERE key = 'last_rebuild_at'"),
                     {"v": time.strftime("%Y-%m-%d %H:%M:%S")})
    if _store_path:
        try:
            _meta_set("last_rebuild_size_bytes", Path(_store_path).stat().st_size)
        except OSError:
            pass


def rebuild_all() -> dict:
    """Full synchronous rebuild of wide_rows + ranking_marks. Returns status."""
    engine = init_materialized()
    if engine is None:
        return {"skipped": True}
    with _rebuild_lock:
        _meta_set("building", "1")
        try:
            start = time.time()
            built_epoch = _meta_get("epoch") or "0"
            session = db_mod.get_session()
            try:
                wide_tuples = _compute_wide_rows_all(session)
                marks = _compute_marks_all(session)
            finally:
                session.close()
            _replace_store(engine, wide_tuples, marks, built_epoch, start)
        finally:
            _meta_set("building", "0")
    # A mutation during the rebuild left the epoch ahead of built_epoch — re-kick.
    if needs_rebuild():
        rebuild_async()
    else:
        # The store now reflects every committed mutation; nothing is dirty.
        _dirty_clear_all()
    return status()


def rebuild_async() -> None:
    """Start a background rebuild thread unless a different one is running.

    The re-kick at the end of ``rebuild_all`` runs *inside* the rebuild thread
    itself, so the liveness check must exclude the current thread — otherwise a
    mutation landing mid-rebuild would never spawn the follow-up rebuild and the
    store would stay stale until the next mutation or boot."""
    global _rebuild_thread
    if init_materialized() is None:
        return
    with _thread_lock:
        t = _rebuild_thread
        if t is not None and t.is_alive() and t is not threading.current_thread():
            return
        _rebuild_thread = threading.Thread(
            target=_rebuild_worker, name="materialize-rebuild", daemon=True
        )
        _rebuild_thread.start()


def _rebuild_worker() -> None:
    try:
        rebuild_all()
    except Exception:
        logger.exception("materialized rebuild failed")


def rebuild_event(event_id: int) -> bool:
    """Synchronously refresh one event's wide_rows.

    Returns ``True`` when the event's rows were refreshed (and its dirty flag
    cleared), ``False`` when skipped — an in-memory source DB, or a full rebuild
    currently holds the lock and will cover this event, so the caller falls back
    to live-computing rather than serving stale rows.
    """
    engine = init_materialized()
    if engine is None:
        return False
    if not _rebuild_lock.acquire(blocking=False):
        return False
    try:
        session = db_mod.get_session()
        try:
            ev = session.get(Event, event_id)
            if ev is None:
                return False
            slug_by_id, _ = _athlete_maps(session)
            id_by_slug = {slug: aid for aid, slug in slug_by_id.items()}
            data = _compute_pivot(event_id, session)
            sort_ts = ev.created_at.timestamp() if ev.created_at else 0.0
            rows = []
            for disc_key in ("wag", "mag"):
                disc = data.get(disc_key)
                if not disc:
                    continue
                for row in disc["rows"]:
                    athlete_id = id_by_slug.get(row.get("slug"))
                    rows.append((
                        event_id, ev.year, sort_ts, ev.name, disc_key.upper(),
                        athlete_id, row.get("club"), row.get("gnz-id"),
                        row.get("name"), _serialized(row),
                    ))
        finally:
            session.close()
        if not rows:
            with engine.begin() as conn:
                conn.execute(text("DELETE FROM wide_rows WHERE event_id = :e"), {"e": event_id})
        else:
            with engine.begin() as conn:
                conn.execute(text("DELETE FROM wide_rows WHERE event_id = :e"), {"e": event_id})
                conn.exec_driver_sql(
                    "INSERT INTO wide_rows (event_id, year, event_sort, event_name, discipline, "
                    "athlete_id, club, gnz_id, name, payload) VALUES (?,?,?,?,?,?,?,?,?,?)",
                    rows,
                )
    finally:
        _rebuild_lock.release()
    _dirty_remove(event_id)
    return True


# ---------------------------------------------------------------------------
# Reads (used by Phase 2 endpoint rewiring)
# ---------------------------------------------------------------------------

def reads_enabled() -> bool:
    """Env flag MATERIALIZED_READS=0 forces all endpoints back to live compute."""
    return os.environ.get("MATERIALIZED_READS", "1") != "0"


def get_wide_rows(event_id: int | None = None, athlete_id: int | None = None,
                  club: str | None = None, gnz_id: str | None = None,
                  year: int | None = None, include_event: bool = False) -> dict:
    """Return the {wag:{columns,rows}, mag:{columns,rows}} shape.

    With ``include_event`` (wide-all), columns start with ``event_name`` and rows
    carry ``event_name``/``event_id``; the single-event endpoint omits both."""
    engine = init_materialized()
    if engine is None:
        return {}
    sql = ("SELECT event_id, event_name, discipline, payload FROM wide_rows WHERE 1=1")
    params = []
    if event_id is not None:
        sql += " AND event_id = ?"
        params.append(event_id)
    if athlete_id is not None:
        sql += " AND athlete_id = ?"
        params.append(athlete_id)
    if club:
        sql += " AND club = ?"
        params.append(club)
    if gnz_id:
        sql += " AND gnz_id = ?"
        params.append(gnz_id)
    if year:
        sql += " AND year = ?"
        params.append(year)
    sql += " ORDER BY event_sort DESC, id"
    with engine.connect() as conn:
        rows = conn.exec_driver_sql(sql, tuple(params)).fetchall()
    if not rows:
        return {}
    by_disc: dict[str, list[dict]] = defaultdict(list)
    for eid, ename, disc, payload in rows:
        row = json.loads(payload)
        if include_event:
            row["event_name"] = ename
            row["event_id"] = eid
        by_disc[disc].append(row)
    result: dict[str, dict] = {}
    for disc in ("WAG", "MAG"):
        if disc not in by_disc:
            continue
        prefixes = WAG_PREFIXES if disc == "WAG" else MAG_PREFIXES
        columns = _wide_column_list_for_prefixes(prefixes, set())
        if include_event:
            columns = ["event_name"] + columns
        result[disc.lower()] = {"columns": columns, "rows": by_disc[disc]}
    return result


def get_ranking_marks(year: int, discipline: str, step: str, division: str = ""):
    """Return the per-event marks blob for a ranking selection (None if absent)."""
    engine = init_materialized()
    if engine is None:
        return None
    key = "|".join(str(x) for x in (year, discipline, step, division))
    with engine.connect() as conn:
        row = conn.exec_driver_sql(
            "SELECT payload FROM ranking_marks WHERE key = ?", (key,)
        ).fetchone()
    if not row:
        return None
    data = json.loads(row[0])
    data["per_event"] = _per_event_flat(data["per_event"])
    data["apparatus_events"] = _apparatus_events_from_list(data["apparatus_events"])
    data["meta_by_key"] = _meta_from_list(data["meta_by_key"])
    return data
