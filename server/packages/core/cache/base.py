"""Cache abstract base class — unified interface for memory/redis backends."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class Cache(ABC):
    """Unified cache abstraction.

    Provides user-selectable flexibility: memory mode (process-local) or
    redis mode (cross-process shared). Used for shared state, config hot-paths,
    data acceleration, and security monitoring.

    Operations grouped by data structure (inspired by Spring Data Redis):
    - Value: KV read/write + TTL
    - Counter: atomic counter
    - Set: set operations (dedup, membership test)
    - List: list operations (event logs, time-range queries)
    """

    # --- Value ---

    @abstractmethod
    async def get(self, key: str) -> Any | None:
        """Retrieve value by key. Returns None if not found or expired."""
        ...

    @abstractmethod
    async def set(self, key: str, value: Any, *, ttl: int | None = None) -> None:
        """Store value with optional TTL (seconds)."""
        ...

    @abstractmethod
    async def delete(self, key: str) -> None:
        """Remove key from cache. No-op if key does not exist."""
        ...

    @abstractmethod
    async def get_ttl(self, key: str) -> int | None:
        """Get remaining TTL in seconds. None if no TTL or key not found."""
        ...

    # --- Counter ---

    @abstractmethod
    async def increment(self, key: str, amount: int = 1) -> int:
        """Atomically increment counter. Creates key at 0 if not exists. Returns new value."""
        ...

    # --- Set ---

    @abstractmethod
    async def sadd(self, key: str, *members: str, ttl: int | None = None) -> int:
        """Add members to set. Returns count of members actually added.

        When *ttl* is provided the key's expiry is (re)set — useful on the
        first call to bound the set's lifetime.
        """
        ...

    @abstractmethod
    async def sismember(self, key: str, member: str) -> bool:
        """Check if *member* is in the set at *key*."""
        ...

    @abstractmethod
    async def smembers(self, key: str) -> set[str]:
        """Return all members of the set at *key*."""
        ...

    @abstractmethod
    async def srem(self, key: str, *members: str) -> int:
        """Remove members from set. Returns count actually removed."""
        ...

    # --- List ---

    @abstractmethod
    async def lpush(self, key: str, value: Any, *, ttl: int | None = None) -> int:
        """Push *value* to the left of the list. Returns current list length.

        Values are JSON-serialized for Redis compatibility.
        """
        ...

    @abstractmethod
    async def lrange(self, key: str, start: int, stop: int) -> list:
        """Return list elements from *start* to *stop* (inclusive, -1 = end)."""
        ...

    @abstractmethod
    async def ltrim(self, key: str, start: int, stop: int) -> None:
        """Trim list to the specified range."""
        ...

    # --- Lifecycle ---

    @abstractmethod
    async def clear(self) -> None:
        """Remove all entries managed by this cache instance.

        In prefix mode (RedisCache with a prefix), only keys matching the
        prefix are deleted — other services' data is never touched.
        """
        ...
