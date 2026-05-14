"""Redis cache backend implementation."""

import json
from typing import Any, cast

import redis as redis_lib

from apps.backend.app.services.cache.base import CacheBackend


class RedisCacheBackend(CacheBackend):
    """Redis cache backend for distributed deployments.

    Suitable for multi-worker deployments where shared rate-limit state is required.
    Configure via CACHE_BACKEND=redis and REDIS_URL in settings.
    """

    def __init__(self, redis_url: str):
        self._client: redis_lib.Redis = cast(
            redis_lib.Redis,
            redis_lib.from_url(redis_url, decode_responses=True),
        )

    def get(self, key: str) -> Any | None:
        val = cast(str | None, self._client.get(key))
        return json.loads(val) if val is not None else None

    def set(self, key: str, value: Any, ttl_seconds: int | None = None) -> None:
        serialized = json.dumps(value)
        if ttl_seconds is not None:
            self._client.setex(key, ttl_seconds, serialized)
        else:
            self._client.set(key, serialized)

    def delete(self, key: str) -> None:
        self._client.delete(key)

    def increment(self, key: str, delta: int = 1) -> int:
        # Callers follow the pattern: increment(), then set(..., ttl) if count==1
        # so TTL is managed by the caller via set(); no need to handle it here.
        return cast(int, self._client.incrby(key, delta))

    def get_ttl(self, key: str) -> int | None:
        ttl = cast(int, self._client.ttl(key))
        # ttl() returns -1 (no TTL) or -2 (key missing) — both map to None
        if ttl < 0:
            return None
        return ttl

    def clear(self) -> None:
        self._client.flushdb()
