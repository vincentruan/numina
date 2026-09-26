"""Redis Cache implementation using redis.asyncio."""

from __future__ import annotations

import json
from typing import Any

import redis.asyncio as aioredis

from packages.core.cache.base import Cache


class RedisCache(Cache):
    """Redis-backed cache for cross-process shared state.

    Uses ``redis.asyncio.Redis`` for non-blocking IO.
    ``clear()`` is prefix-scoped (SCAN + DEL) — never calls ``flushdb()``
    when a prefix is configured, so multiple services can safely share
    the same Redis instance.
    """

    def __init__(self, client: aioredis.Redis, *, prefix: str = "") -> None:
        self._client = client
        self._prefix = prefix

    def _key(self, key: str) -> str:
        """Apply the namespace prefix to a user-supplied key."""
        return f"{self._prefix}{key}" if self._prefix else key

    # --- Value ---

    async def get(self, key: str) -> Any | None:
        val = await self._client.get(self._key(key))
        if val is None:
            return None
        return json.loads(val)

    async def set(self, key: str, value: Any, *, ttl: int | None = None) -> None:
        serialized = json.dumps(value)
        rk = self._key(key)
        if ttl is not None:
            await self._client.setex(rk, ttl, serialized)
        else:
            await self._client.set(rk, serialized)

    async def delete(self, key: str) -> None:
        await self._client.delete(self._key(key))

    async def get_ttl(self, key: str) -> int | None:
        ttl = await self._client.ttl(self._key(key))
        if ttl < 0:  # -1 = no TTL, -2 = key missing
            return None
        return ttl

    # --- Counter ---

    async def increment(self, key: str, amount: int = 1, *, ttl: int | None = None) -> int:
        rk = self._key(key)
        if ttl is not None:
            # SET NX initializes the counter to 0 with TTL only on first creation.
            # INCRBY then atomically increments. If the key already exists, SET NX
            # is a no-op and the existing TTL is preserved (not reset).
            await self._client.set(rk, 0, ex=ttl, nx=True)
        return await self._client.incrby(rk, amount)

    # --- Set ---

    async def sadd(self, key: str, *members: str, ttl: int | None = None) -> int:
        rk = self._key(key)
        added = await self._client.sadd(rk, *members)
        if ttl is not None:
            await self._client.expire(rk, ttl)
        return added

    async def sismember(self, key: str, member: str) -> bool:
        return bool(await self._client.sismember(self._key(key), member))

    async def smembers(self, key: str) -> set[str]:
        result = await self._client.smembers(self._key(key))
        return set(result) if result else set()

    async def srem(self, key: str, *members: str) -> int:
        return await self._client.srem(self._key(key), *members)

    # --- List ---

    async def lpush(self, key: str, value: Any, *, ttl: int | None = None) -> int:
        rk = self._key(key)
        serialized = json.dumps(value)
        length = await self._client.lpush(rk, serialized)
        if ttl is not None:
            await self._client.expire(rk, ttl)
        return length

    async def lrange(self, key: str, start: int, stop: int) -> list:
        rk = self._key(key)
        raw = await self._client.lrange(rk, start, stop)
        result = []
        for item in raw:
            try:
                result.append(json.loads(item))
            except (json.JSONDecodeError, TypeError):
                result.append(item)
        return result

    async def ltrim(self, key: str, start: int, stop: int) -> None:
        await self._client.ltrim(self._key(key), start, stop)

    # --- Lifecycle ---

    async def clear(self) -> None:
        """Delete all keys with this cache's prefix.

        When a prefix is set, uses SCAN + DEL to avoid touching other
        services' data. Without a prefix, falls back to ``flushdb()``
        (single-app Redis, backward compatible).
        """
        if not self._prefix:
            await self._client.flushdb()
            return
        cursor = 0
        pattern = f"{self._prefix}*"
        while True:
            cursor, batch = await self._client.scan(cursor, match=pattern, count=100)
            if batch:
                await self._client.delete(*batch)
            if cursor == 0:
                break
