import time
from typing import Any

from fastapi import Response

from app.core.config import CACHE_TTL_SECONDS

_cache: dict[str, tuple[float, Any]] = {}


def get_cached(cache_key: str):
    cached = _cache.get(cache_key)
    if cached is None:
        return None

    expires_at, value = cached
    if expires_at <= time.monotonic():
        _cache.pop(cache_key, None)
        return None

    return value


def set_cached(cache_key: str, value: Any):
    _cache[cache_key] = (time.monotonic() + CACHE_TTL_SECONDS, value)
    return value


def set_cache_headers(response: Response, hit: bool):
    response.headers["Cache-Control"] = f"public, max-age={CACHE_TTL_SECONDS}"
    response.headers["X-Cache"] = "HIT" if hit else "MISS"
