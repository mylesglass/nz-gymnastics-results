"""In-memory cache with granular per-event invalidation and optional TTL."""

import threading
import time
from typing import Any, Optional

_etag_version = 0

_compute_guard = threading.Lock()
_compute_locks: dict[str, threading.Lock] = {}


class GranularTTLCache:
    def __init__(self, default_ttl: int = 300):
        self.default_ttl = default_ttl
        self._store: dict[str, Any] = {}

    def get(self, key: str) -> Optional[Any]:
        if key not in self._store:
            return None
        entry = self._store[key]
        if isinstance(entry, tuple) and len(entry) == 2:
            expires_at, data = entry
            if time.time() > expires_at:
                del self._store[key]
                return None
            return data
        return entry

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        if ttl is None:
            self._store[key] = value
        else:
            expiry = time.time() + ttl
            self._store[key] = (expiry, value)

    def invalidate_prefix(self, prefix: str) -> None:
        keys_to_del = [k for k in self._store if k.startswith(prefix)]
        for k in keys_to_del:
            self._store.pop(k, None)

    def clear(self) -> None:
        self._store.clear()


cache = GranularTTLCache(default_ttl=300)


def cached(key_parts: tuple, fn, ttl: Optional[int] = None):
    key = ":".join(str(k) for k in key_parts)
    value = cache.get(key)
    if value is not None:
        return value

    # Single-flight: when many requests miss the same key at once, only one
    # computes and the rest reuse the result. Prevents a burst of concurrent
    # requests (e.g. a page firing several requests) from all running the same
    # heavy query and stalling the SQLite connection pool.
    with _compute_guard:
        lock = _compute_locks.get(key)
        if lock is None:
            lock = threading.Lock()
            _compute_locks[key] = lock
    with lock:
        try:
            value = cache.get(key)
            if value is None:
                value = fn()
                cache.set(key, value, ttl)
            return value
        finally:
            with _compute_guard:
                _compute_locks.pop(key, None)


def invalidate(event_id: Optional[int] = None):
    global _etag_version
    _etag_version += 1
    if event_id is not None:
        cache.invalidate_prefix(f"event:{event_id}:")
    else:
        cache.clear()


def cache_headers() -> dict[str, str]:
    return {
        "ETag": str(_etag_version),
    }
