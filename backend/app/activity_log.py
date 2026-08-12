"""Batched background writer for activity logging.

The middleware enqueues rows via :func:`enqueue` so a request's response never
waits on a database write. When the writer has been started (in the FastAPI
lifespan) rows are written in the background, batched into single transactions
under bursts; otherwise they are written synchronously (test contexts that
don't run the lifespan, or after shutdown).
"""

import queue
import threading

from app.database import get_session
from app.models import ActivityLog

_BATCH_MAX = 100
_queue: "queue.Queue[dict | None]" = queue.Queue(maxsize=5000)

_lock = threading.Lock()
_started = False
_writer: threading.Thread | None = None


def _insert(rows: list[dict]) -> None:
    """Write a batch of rows in one transaction."""
    session = get_session()
    try:
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
