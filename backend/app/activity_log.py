"""Batched background writer for activity logging and traffic aggregation.

The middleware enqueues rows via :func:`enqueue` (authenticated detail rows for
``activity_logs``) and :func:`enqueue_traffic` (per-day/hour counters for
``traffic_daily``) so a request's response never waits on a database write.
When the writer has been started (in the FastAPI lifespan) rows are written in
the background, batched into single transactions under bursts; otherwise they
are written synchronously (test contexts that don't run the lifespan, or after
shutdown).
"""

import queue
import threading
from collections import defaultdict
from datetime import datetime

from sqlalchemy import text

from app.database import get_session
from app.models import ActivityLog

_BATCH_MAX = 100
_queue: "queue.Queue[dict | None]" = queue.Queue(maxsize=5000)

_lock = threading.Lock()
_started = False
_writer: threading.Thread | None = None


def _insert_activity(session, rows: list[dict]) -> None:
    """Write a batch of ActivityLog rows in one transaction."""
    for r in rows:
        session.add(ActivityLog(
            username=r["username"],
            role=r["role"],
            type=r["type"],
            method=r["method"],
            path=r["path"],
            query=r["query"],
            status_code=r["status_code"],
            duration_ms=r["duration_ms"],
        ))


def _insert_traffic(session, rows: list[dict]) -> None:
    """Upsert a batch of traffic counters into ``traffic_daily``.

    Rows are aggregated in Python per ``(date, hour, kind, path_group,
    anonymous)`` then written with one ``INSERT ... ON CONFLICT DO UPDATE``
    per key so repeated requests in a burst increment existing buckets instead
    of inserting duplicates.
    """
    totals: dict[tuple, dict] = defaultdict(
        lambda: {"count": 0, "error_count": 0, "total_duration_ms": 0.0},
    )
    for r in rows:
        key = (
            r["date"], r["hour"], r["kind"], r["path_group"], r["anonymous"],
        )
        totals[key]["count"] += 1
        if r["status_code"] is not None and r["status_code"] >= 400:
            totals[key]["error_count"] += 1
        totals[key]["total_duration_ms"] += r["duration_ms"] or 0.0

    sql = text("""
        INSERT INTO traffic_daily
            (date, hour, kind, path_group, anonymous,
             count, error_count, total_duration_ms, created_at)
        VALUES
            (:date, :hour, :kind, :path_group, :anonymous,
             :count, :error_count, :total_duration_ms, :created_at)
        ON CONFLICT(date, hour, kind, path_group, anonymous)
        DO UPDATE SET
            count = count + :count,
            error_count = error_count + :error_count,
            total_duration_ms = total_duration_ms + :total_duration_ms
    """)
    now = datetime.now()
    for (date, hour, kind, path_group, anonymous), agg in totals.items():
        session.execute(sql, {
            "date": date,
            "hour": hour,
            "kind": kind,
            "path_group": path_group,
            "anonymous": anonymous,
            "count": agg["count"],
            "error_count": agg["error_count"],
            "total_duration_ms": round(agg["total_duration_ms"], 3),
            "created_at": now,
        })


def _insert(rows: list[dict]) -> None:
    """Write a batch of rows in one transaction."""
    session = get_session()
    try:
        activity = [r for r in rows if r["_target"] == "activity"]
        traffic = [r for r in rows if r["_target"] == "traffic"]
        if activity:
            _insert_activity(session, activity)
        if traffic:
            _insert_traffic(session, traffic)
        session.commit()
    except Exception:
        session.rollback()
    finally:
        session.close()


def _run() -> None:
    """Writer loop: block for an item, drain whatever else is queued, write."""
    while True:
        item = _queue.get()
        if item is None:
            return
        batch = [item]
        try:
            while len(batch) < _BATCH_MAX:
                batch.append(_queue.get_nowait())
        except queue.Empty:
            pass
        _insert(batch)


def start() -> None:
    """Start the background writer thread (idempotent)."""
    global _started, _writer
    with _lock:
        if _started:
            return
        _started = True
        _writer = threading.Thread(target=_run, name="activity-log-writer", daemon=True)
        _writer.start()


def stop() -> None:
    """Stop the writer and flush any remaining queued rows."""
    global _started, _writer
    with _lock:
        if not _started:
            return
        _started = False
        _queue.put(None)
        writer = _writer
        _writer = None
    if writer is not None:
        writer.join(timeout=5)
    flush()


def enqueue(
    username: str,
    role: str,
    type_: str,
    method: str | None,
    path: str,
    query: str | None,
    status_code: int | None,
    duration_ms: float | None,
) -> None:
    """Queue one activity row. Never blocks on the request path."""
    row = {
        "_target": "activity",
        "username": username,
        "role": role,
        "type": type_,
        "method": method,
        "path": path,
        "query": query,
        "status_code": status_code,
        "duration_ms": duration_ms,
    }
    if not _started:
        _insert([row])
        return
    try:
        _queue.put_nowait(row)
    except queue.Full:
        pass


def enqueue_traffic(
    kind: str,
    path_group: str,
    anonymous: bool,
    status_code: int | None,
    duration_ms: float | None,
) -> None:
    """Queue one aggregated traffic counter (never blocks the request path).

    ``kind`` is ``"page"`` or ``"api"`` and ``path_group`` a normalized path.
    Date/hour buckets use the server's local time.
    """
    now = datetime.now()
    row = {
        "_target": "traffic",
        "date": now.date(),
        "hour": now.hour,
        "kind": kind,
        "path_group": path_group,
        "anonymous": anonymous,
        "status_code": status_code,
        "duration_ms": duration_ms,
    }
    if not _started:
        _insert([row])
        return
    try:
        _queue.put_nowait(row)
    except queue.Full:
        pass


def flush() -> None:
    """Synchronously drain queued rows (admin views and shutdown)."""
    while not _queue.empty():
        batch = []
        try:
            while len(batch) < _BATCH_MAX:
                batch.append(_queue.get_nowait())
        except queue.Empty:
            pass
        if batch:
            _insert(batch)
