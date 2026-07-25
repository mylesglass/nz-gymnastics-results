"""In-memory cache with granular per-event invalidation."""

import re
from typing import Any

_cache: dict[str, Any] = {}
_etag_version = 0


def cached(key_parts: tuple, fn):
    key = ":".join(str(k) for k in key_parts)
    value = _cache.get(key)
    if value is not None:
        return value
    value = fn()
    _cache[key] = value
    return value


def invalidate(event_id: int | None = None):
    global _etag_version
    _etag_version += 1
    if event_id is not None:
        pattern = re.compile(f"^event:{event_id}:")
        keys_to_delete = [k for k in _cache if pattern.match(k)]
        for k in keys_to_delete:
            _cache.pop(k, None)
    else:
        _cache.clear()


def cache_headers() -> dict[str, str]:
    return {
        "Cache-Control": "no-cache, must-revalidate",
        "ETag": str(_etag_version),
    }
