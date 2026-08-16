"""Benchmark materialized-data feasibility against the live database.

Phase 0 diagnostic (STEP 30 in PLAN.md). Times the current per-request compute
costs, then builds a prototype materialized store (wide rows + ranking marks)
in a scratch SQLite file and reports rebuild wall time, store size, and
equivalence spot-checks. Read-only against the source DB — the store is written
to ``/tmp`` (or ``--store``) and removed afterwards unless ``--keep`` is given.

Usage:
    python -m app.bench_materialize
    python -m app.bench_materialize --max-events 20 --max-marks 10   # bounded smoke run
    python -m app.bench_materialize --store /tmp/bench.db --keep
"""

import argparse
import json
import sqlite3
import sys
import time
from collections import defaultdict
from pathlib import Path

from sqlalchemy import text

from app.database import get_session
from app.models import Athlete, Event, LongScore
from app.transformer import _compute_pivot, _wide_column_list_for_prefixes

# Importing app.main pulls in the FastAPI app definition, but lifespan never runs
# on import, so the only effect is module-level constants + route registration.
from app.main import _build_event_marks, _compute_wide_all

WAG_PREFIXES = ["vt", "ub", "bb", "fx"]
MAG_PREFIXES = ["fx", "ph", "sr", "vt", "pb", "hb"]

GO_NO_GO = {
    "full_rebuild_ms": 60_000,
    "per_event_ms": 1_000,
    "store_bytes": 100 * 1024 * 1024,
}


def _time(label: str, fn):
    t0 = time.perf_counter()
    result = fn()
    ms = (time.perf_counter() - t0) * 1000.0
    print(f"    {label:<58} {ms:>10.1f} ms")
    return result, ms


def _serialized(obj) -> str:
    return json.dumps(obj, sort_keys=True, ensure_ascii=False)


def _per_event_nested(per_event: dict) -> list:
    """Serialize the tuple-keyed per_event dict as [[key, eid, entry], ...]."""
    return [[k, e, v] for (k, e), v in per_event.items()]


def _per_event_flat(lst: list) -> dict:
    """Inverse of _per_event_nested — reconstruct tuple keys on load."""
    return {(k, e): v for k, e, v in lst}


def _apparatus_events_to_list(d: dict) -> list:
    return [[k, app, eid, entry]
            for k, apps in d.items()
            for app, evs in apps.items()
            for eid, entry in evs.items()]


def _meta_to_list(d: dict) -> list:
    return [[k, v] for k, v in d.items()]


# ---------------------------------------------------------------------------
# Baseline — today's per-request costs (uncached)
# ---------------------------------------------------------------------------

def _ranking_rows(session, year: int, discipline: str, step: str, division: str):
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


def _run_baseline(session) -> None:
    print("\n== Baseline (live DB, uncached per-request cost) ==")

    largest = session.execute(text(
        "SELECT event_id, count(*) c FROM long_scores GROUP BY event_id ORDER BY c DESC LIMIT 1"
    )).first()
    event_id, cnt = largest[0], largest[1]
    print(f"  largest event: id={event_id} ({cnt} long rows)")
    pivot, ms = _time(
        f"pivot_to_wide_dict (single event {event_id})",
        lambda: _compute_pivot(event_id, session),
    )
    n_rows = sum(len(v["rows"]) for v in pivot.values())
    print(f"      -> {n_rows} wide rows across {list(pivot)}")

    heaviest = session.execute(text(
        "SELECT athlete_id, count(*) c FROM long_scores "
        "WHERE athlete_id IS NOT NULL GROUP BY athlete_id ORDER BY c DESC LIMIT 1"
    )).first()
    data, ms = _time(
        f"wide-all for heaviest gymnast (athlete {heaviest[0]}, {heaviest[1]} long rows)",
        lambda: _compute_wide_all(None, None, None, heaviest[0]),
    )
    print(f"      -> {sum(len(v['rows']) for v in data.values() if isinstance(v, dict))} wide rows")

    # National rankings: heaviest step by row count for the most recent year.
    step_row = session.execute(text(
        "SELECT e.year, s.discipline, s.level_category, count(*) c "
        "FROM long_scores s JOIN events e ON s.event_id = e.id "
        "WHERE e.is_national = 0 AND s.pass_final_score IS NOT NULL "
        "GROUP BY 1, 2, 3 ORDER BY c DESC LIMIT 1"
    )).first()
    year, disc, step, cnt = step_row[0], step_row[1], step_row[2], step_row[3]
    print(f"  heaviest ranking step: {disc} {year} {step} ({cnt} rows)")
    athletes = {a.id: a for a in session.query(Athlete).all()}
    rows, _ = _time(
        "rankings SQL rows",
        lambda: _ranking_rows(session, year, disc, step, ""),
    )
    _, ms = _time(
        f"_build_event_marks ({len(rows)} rows)",
        lambda: _build_event_marks(rows, step, athletes),
    )


# ---------------------------------------------------------------------------
# Rebuild prototype — Phase A (wide rows) + Phase B (ranking marks)
# ---------------------------------------------------------------------------

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


def _build_prototype(session, store_path: Path, max_events: int, max_marks: int) -> dict:
    """Build wide_rows + ranking_marks into a scratch SQLite file. Returns stats."""
    print("\n== Rebuild prototype ==")
    if store_path.exists():
        store_path.unlink()
    conn = sqlite3.connect(str(store_path))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript(
        """
        CREATE TABLE wide_rows (
            id INTEGER PRIMARY KEY, event_id INTEGER NOT NULL, year INTEGER,
            event_sort REAL, discipline TEXT, athlete_id INTEGER,
            club TEXT, gnz_id TEXT, name TEXT, payload TEXT
        );
        CREATE TABLE ranking_marks (key TEXT PRIMARY KEY, payload TEXT);
        """
    )
    try:
        # --- Phase A: one pivot per event -> wide_rows ---
        t0 = time.perf_counter()
        events = session.query(Event).order_by(Event.created_at.desc()).all()
        if max_events:
            events = events[:max_events]
        wide_count = 0
        payload_bytes = 0
        rows_buffer = []
        for ev in events:
            data = _compute_pivot(ev.id, session)
            sort_ts = ev.created_at.timestamp() if ev.created_at else 0.0
            for disc_key in ("wag", "mag"):
                disc = data.get(disc_key)
                if not disc:
                    continue
                for row in disc["rows"]:
                    payload = _serialized(row)
                    payload_bytes += len(payload)
                    rows_buffer.append((
                        ev.id, ev.year, sort_ts, disc_key.upper(),
                        row.get("athlete_id"), row.get("club"), row.get("gnz-id"),
                        row.get("name"), payload,
                    ))
                    wide_count += 1
        conn.executemany(
            "INSERT INTO wide_rows (event_id, year, event_sort, discipline, "
            "athlete_id, club, gnz_id, name, payload) VALUES (?,?,?,?,?,?,?,?,?)",
            rows_buffer,
        )
        conn.execute("CREATE INDEX idx_wide_event ON wide_rows(event_id)")
        conn.execute("CREATE INDEX idx_wide_athlete_year ON wide_rows(athlete_id, year)")
        conn.execute("CREATE INDEX idx_wide_club_year ON wide_rows(club, year)")
        phase_a_ms = (time.perf_counter() - t0) * 1000.0
        print(f"    Phase A (wide_rows): {wide_count} rows, "
              f"{payload_bytes / 1024 / 1024:.2f} MB serialized — {phase_a_ms:.1f} ms")
        per_event_ms = phase_a_ms / len(events)
        print(f"      per-event avg: {per_event_ms:.1f} ms")

        # --- Phase B: one _build_event_marks pass per (year, disc, step, division) ---
        t0 = time.perf_counter()
        athletes = {a.id: a for a in session.query(Athlete).all()}
        keys = _discover_mark_keys(session)
        if max_marks:
            keys = keys[:max_marks]
        marks_bytes = 0
        for key in keys:
            year, disc, step, division = key
            rows = _ranking_rows(session, year, disc, step, division)
            per_event, apparatus_events, meta_by_key = _build_event_marks(
                rows, step, athletes
            )
            for a_key, meta in meta_by_key.items():
                if isinstance(a_key, int) and a_key in athletes:
                    meta["slug"] = athletes[a_key].slug
            payload = _serialized({
                "per_event": _per_event_nested(per_event),
                "apparatus_events": _apparatus_events_to_list(apparatus_events),
                "meta_by_key": _meta_to_list(meta_by_key),
            })
            marks_bytes += len(payload)
            conn.execute("INSERT INTO ranking_marks (key, payload) VALUES (?, ?)",
                         ("|".join(map(str, key)), payload))
        conn.commit()
        phase_b_ms = (time.perf_counter() - t0) * 1000.0
        print(f"    Phase B (ranking_marks): {len(keys)} keys, "
              f"{marks_bytes / 1024 / 1024:.2f} MB serialized — {phase_b_ms:.1f} ms")
        per_mark_ms = phase_b_ms / len(keys)
        print(f"      per-key avg: {per_mark_ms:.1f} ms")

        # --- overall ---
        conn.execute("PRAGMA wal_checkpoint(PASSIVE)")
        conn.close()
        store_bytes = store_path.stat().st_size
        total_ms = phase_a_ms + phase_b_ms
        print(f"    Total rebuild: {total_ms:.1f} ms; store size: "
              f"{store_bytes / 1024 / 1024:.2f} MB")
        return {
            "events": len(events),
            "wide_count": wide_count,
            "wide_bytes": payload_bytes,
            "marks_keys": len(keys),
            "marks_bytes": marks_bytes,
            "phase_a_ms": phase_a_ms,
            "phase_b_ms": phase_b_ms,
            "total_ms": total_ms,
            "per_event_ms": per_event_ms,
            "store_bytes": store_bytes,
        }
    except Exception:
        conn.close()
        raise


# ---------------------------------------------------------------------------
# Equivalence spot-checks against freshly recomputed values
# ---------------------------------------------------------------------------

def _check_equivalence(session, store_path: Path) -> None:
    print("\n== Equivalence spot-checks ==")
    conn = sqlite3.connect(str(store_path))
    failures = []

    # Phase A: stored wide payloads == fresh pivot for a sample of built events.
    built = [r[0] for r in conn.execute(
        "SELECT DISTINCT event_id FROM wide_rows ORDER BY event_id"
    ).fetchall()]
    if not built:
        print("    (no wide_rows built — nothing to check)")
        return
    sizes = {eid: cnt for eid, cnt in session.execute(text(
        "SELECT event_id, count(*) FROM long_scores GROUP BY event_id"
    )).fetchall()}
    largest = max(built, key=lambda e: sizes.get(e, 0))
    sample = list(dict.fromkeys([largest] + built[:1]))
    for eid in sample:
        fresh = {}
        data = _compute_pivot(eid, session)
        for disc_key in ("wag", "mag"):
            disc = data.get(disc_key)
            if not disc:
                continue
            fresh[disc_key] = {_serialized(r) for r in disc["rows"]}
        stored = {}
        for disc_key, disc in fresh.items():
            rows = conn.execute(
                "SELECT payload FROM wide_rows WHERE event_id=? AND discipline=?",
                (eid, disc_key.upper()),
            ).fetchall()
            stored[disc_key] = {r[0] for r in rows}
        ok = fresh == stored
        print(f"    wide_rows event {eid}: match -> {'PASS' if ok else 'FAIL'}")
        if not ok:
            failures.append(f"wide_rows event {eid}")

    # Phase B: stored marks blob == fresh _build_event_marks for a few keys.
    athletes = {a.id: a for a in session.query(Athlete).all()}
    stored_keys = [r[0] for r in conn.execute(
        "SELECT key FROM ranking_marks ORDER BY key"
    ).fetchall()]
    sample = [k for k in stored_keys if k.endswith("|")][:2] + \
             [k for k in stored_keys if not k.endswith("|")][:1]
    for key in sample:
        year, disc, step, division = key.split("|", 3)
        rows = _ranking_rows(session, int(year), disc, step, division)
        per_event, apparatus_events, meta_by_key = _build_event_marks(rows, step, athletes)
        for a_key, meta in meta_by_key.items():
            if isinstance(a_key, int) and a_key in athletes:
                meta["slug"] = athletes[a_key].slug
        fresh = _serialized({
            "per_event": _per_event_nested(per_event),
            "apparatus_events": _apparatus_events_to_list(apparatus_events),
            "meta_by_key": _meta_to_list(meta_by_key),
        })
        stored = conn.execute(
            "SELECT payload FROM ranking_marks WHERE key=?",
            (key,),
        ).fetchone()
        ok = stored is not None and stored[0] == fresh
        print(f"    ranking_marks {key}: match -> {'PASS' if ok else 'FAIL'}")
        if not ok:
            failures.append(key)

    conn.close()
    if failures:
        print(f"\n  EQUIVALENCE FAILURES: {failures}")
        sys.exit(1)
    print("    all checks passed")


# ---------------------------------------------------------------------------
# Go/no-go summary
# ---------------------------------------------------------------------------

def _summary(stats: dict) -> None:
    print("\n== Go / no-go ==")
    checks = [
        ("full rebuild ≤ 60s", stats["total_ms"] <= GO_NO_GO["full_rebuild_ms"], stats["total_ms"] / 1000.0),
        ("per-event insert ≤ 1s", stats["per_event_ms"] <= GO_NO_GO["per_event_ms"], stats["per_event_ms"] / 1000.0),
        ("store ≤ 100 MB", stats["store_bytes"] <= GO_NO_GO["store_bytes"], f"{stats['store_bytes'] / 1024 / 1024:.1f} MB"),
    ]
    for label, ok, val in checks:
        print(f"    [{'x' if ok else ' '}] {label}: {val}")
    if all(ok for _, ok, _ in checks):
        print("  -> design feasible; proceed to Phase 1 (materialize.py)")
    else:
        print("  -> REBUILD TOO COSTLY at current granularity; fall back to "
              "hot-key warming + lazy backfill (see PLAN.md STEP 30)")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--store", default="/tmp/nzgr_materialized_bench.db")
    parser.add_argument("--max-events", type=int, default=0, help="limit Phase A events (0 = all)")
    parser.add_argument("--max-marks", type=int, default=0, help="limit Phase B keys (0 = all)")
    parser.add_argument("--skip-baseline", action="store_true")
    parser.add_argument("--keep", action="store_true", help="keep the scratch store file")
    args = parser.parse_args()

    print(f"source DB: {Path(__import__('app.database', fromlist=['SQLITE_PATH']).SQLITE_PATH)}")
    session = get_session()
    store_path = Path(args.store)
    try:
        if not args.skip_baseline:
            _run_baseline(session)
        stats = _build_prototype(session, store_path, args.max_events, args.max_marks)
        _check_equivalence(session, store_path)
        _summary(stats)
    finally:
        session.close()
        if not args.keep and store_path.exists():
            store_path.unlink()
            for suffix in ("-wal", "-shm"):
                p = Path(str(store_path) + suffix)
                if p.exists():
                    p.unlink()


if __name__ == "__main__":
    main()
