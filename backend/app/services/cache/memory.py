"""In-memory cache backend implementation."""

import time
from typing import Any

from app.services.cache.base import CacheBackend


class MemoryCacheBackend(CacheBackend):
    """In-memory cache backend using dictionary with TTL support.

    Suitable for single-instance deployments. Thread-safe for basic operations.
    """

    def __init__(self):
        # Structure: {key: (value, expire_at_timestamp)}
        # expire_at is None for no TTL
        self._store: dict[str, tuple[Any, float | None]] = {}

    def get(self, key: str) -> Any | None:
        entry = self._store.get(key)
        if entry is None:
            return None
        value, expire_at = entry
        # Check if expired
        if expire_at is not None and time.time() > expire_at:
            del self._store[key]
            return None
        return value

    def set(self, key: str, value: Any, ttl_seconds: int | None = None) -> None:
        expire_at = None
        if ttl_seconds is not None:
            expire_at = time.time() + ttl_seconds
        self._store[key] = (value, expire_at)

    def delete(self, key: str) -> None:
        self._store.pop(key, None)

    def increment(self, key: str, delta: int = 1) -> int:
        current = self.get(key)
        # Treat None as 0
        current_value = current if current is not None else 0
        new_value = current_value + delta
        # Preserve TTL if exists
        entry = self._store.get(key)
        expire_at = entry[1] if entry else None
        self._store[key] = (new_value, expire_at)
        return new_value

    def get_ttl(self, key: str) -> int | None:
        entry = self._store.get(key)
        if entry is None:
            return None
        expire_at = entry[1]
        if expire_at is None:
            return None
        remaining = int(expire_at - time.time())
        return max(0, remaining)

    def clear(self) -> None:
        self._store.clear()

    def cleanup_expired(self) -> int:
        """Remove all expired entries.

        Returns:
            Count of removed entries
        """
        now = time.time()
        expired_keys = [
            k for k, (_, expire_at) in self._store.items()
            if expire_at is not None and now > expire_at
        ]
        for k in expired_keys:
            del self._store[k]
        return len(expired_keys)