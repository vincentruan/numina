"""In-memory Cache implementation."""

from __future__ import annotations

import time
from typing import Any

from packages.core.cache.base import Cache


class MemoryCache(Cache):
    """Process-local in-memory cache.

    All key types (Value / Set / List) share a unified expiry tracking
    mechanism via ``_expire_at``.
    """

    def __init__(self) -> None:
        self._store: dict[str, Any] = {}
        self._sets: dict[str, set[str]] = {}
        self._lists: dict[str, list[Any]] = {}
        self._expire_at: dict[str, float] = {}

    def _is_expired(self, key: str) -> bool:
        exp = self._expire_at.get(key)
        if exp is not None and time.time() > exp:
            self._remove_key(key)
            return True
        return False

    def _remove_key(self, key: str) -> None:
        self._store.pop(key, None)
        self._sets.pop(key, None)
        self._lists.pop(key, None)
        self._expire_at.pop(key, None)

    # --- Value ---

    async def get(self, key: str) -> Any | None:
        if self._is_expired(key):
            return None
        return self._store.get(key)

    async def set(self, key: str, value: Any, *, ttl: int | None = None) -> None:
        # Clear any set/list data for this key (type collision guard)
        self._sets.pop(key, None)
        self._lists.pop(key, None)
        self._store[key] = value
        if ttl is not None:
            self._expire_at[key] = time.time() + ttl
        else:
            self._expire_at.pop(key, None)

    async def delete(self, key: str) -> None:
        self._remove_key(key)

    async def get_ttl(self, key: str) -> int | None:
        if self._is_expired(key):
            return None
        exp = self._expire_at.get(key)
        if exp is None:
            return None
        remaining = int(exp - time.time())
        return max(0, remaining)

    # --- Counter ---

    async def increment(self, key: str, amount: int = 1) -> int:
        current = 0 if self._is_expired(key) else self._store.get(key, 0)
        new_value = current + amount
        self._store[key] = new_value
        # Preserve existing TTL (don't touch _expire_at)
        return new_value

    # --- Set ---

    async def sadd(self, key: str, *members: str, ttl: int | None = None) -> int:
        if self._is_expired(key):
            self._sets[key] = set()
        s = self._sets.setdefault(key, set())
        before = len(s)
        s.update(members)
        added = len(s) - before
        if ttl is not None:
            self._expire_at[key] = time.time() + ttl
        return added

    async def sismember(self, key: str, member: str) -> bool:
        if self._is_expired(key):
            return False
        s = self._sets.get(key)
        if s is None:
            return False
        return member in s

    async def smembers(self, key: str) -> set[str]:
        if self._is_expired(key):
            return set()
        s = self._sets.get(key)
        if s is None:
            return set()
        return set(s)

    async def srem(self, key: str, *members: str) -> int:
        if self._is_expired(key):
            return 0
        s = self._sets.get(key)
        if s is None:
            return 0
        before = len(s)
        s.difference_update(members)
        return before - len(s)

    # --- List ---

    async def lpush(self, key: str, value: Any, *, ttl: int | None = None) -> int:
        if self._is_expired(key):
            self._lists[key] = []
        lst = self._lists.setdefault(key, [])
        lst.insert(0, value)
        if ttl is not None:
            self._expire_at[key] = time.time() + ttl
        return len(lst)

    async def lrange(self, key: str, start: int, stop: int) -> list:
        if self._is_expired(key):
            return []
        lst = self._lists.get(key)
        if lst is None:
            return []
        if stop == -1:
            return list(lst[start:])
        return list(lst[start : stop + 1])

    async def ltrim(self, key: str, start: int, stop: int) -> None:
        if self._is_expired(key):
            return
        lst = self._lists.get(key)
        if lst is None:
            return
        if stop == -1:
            self._lists[key] = lst[start:]
        else:
            self._lists[key] = lst[start : stop + 1]

    # --- Lifecycle ---

    async def clear(self) -> None:
        self._store.clear()
        self._sets.clear()
        self._lists.clear()
        self._expire_at.clear()

    def cleanup_expired(self) -> int:
        """Remove all expired entries. Returns count of removed keys."""
        now = time.time()
        expired = [k for k, exp in self._expire_at.items() if now > exp]
        for k in expired:
            self._remove_key(k)
        return len(expired)
