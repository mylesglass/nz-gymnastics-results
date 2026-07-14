"""Simple in-memory cache with version-based invalidation."""

from typing import Any

_cache: dict[str, tuple[int, Any]] = {}
_version = 0


def cached(key_parts: tuple, fn):
    key = ":".join(str(k) for k in key_parts)
    entry = _cache.get(key)
    if entry is not None and entry[0] == _version:
        return entry[1]
    value = fn()
    _cache[key] = (_version, value)
    return value


def invalidate():
    global _version
    _version += 1


def cache_headers() -> dict[str, str]:
    return {
        "Cache-Control": "no-cache, must-revalidate",
        "ETag": str(_version),
    }
