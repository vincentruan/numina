"""Abstract cache backend interface for rate limiting and other caching needs."""

from abc import ABC, abstractmethod
from typing import Any


class CacheBackend(ABC):
    """Abstract cache backend interface.

    Supports basic cache operations with optional TTL (time-to-live).
    Implementations can be in-memory, Redis, or other storage backends.
    """

    @abstractmethod
    def get(self, key: str) -> Any | None:
        """Retrieve value by key.

        Args:
            key: Cache key

        Returns:
            Cached value or None if not found or expired
        """
        pass

    @abstractmethod
    def set(self, key: str, value: Any, ttl_seconds: int | None = None) -> None:
        """Store value with optional TTL.

        Args:
            key: Cache key
            value: Value to cache
            ttl_seconds: Time-to-live in seconds, None for no expiration
        """
        pass

    @abstractmethod
    def delete(self, key: str) -> None:
        """Remove key from cache.

        Args:
            key: Cache key to delete
        """
        pass

    @abstractmethod
    def increment(self, key: str, delta: int = 1) -> int:
        """Increment counter, returns new value.

        Creates key with value 0 if not exists, then increments.

        Args:
            key: Cache key
            delta: Increment amount (default 1)

        Returns:
            New value after increment
        """
        pass

    @abstractmethod
    def get_ttl(self, key: str) -> int | None:
        """Get remaining TTL in seconds.

        Args:
            key: Cache key

        Returns:
            Remaining TTL in seconds, None if no TTL or key not found
        """
        pass

    @abstractmethod
    def clear(self) -> None:
        """Clear all cache entries."""
        pass