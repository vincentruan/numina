"""Redis cache backend implementation (placeholder for future use)."""

from typing import Any, Optional

from app.services.cache.base import CacheBackend


class RedisCacheBackend(CacheBackend):
    """Redis cache backend for distributed deployments.

    TODO: Implement when Redis is needed. Requires redis-py dependency.
    """

    def __init__(self, redis_url: str):
        """Initialize Redis backend.

        Args:
            redis_url: Redis connection URL (e.g., redis://localhost:6379/0)

        Raises:
            NotImplementedError: Redis backend is not yet implemented.
                Factory will catch this and fall back to memory cache.
        """
        # Placeholder: self._client = redis.from_url(redis_url)
        self._redis_url = redis_url
        raise NotImplementedError("Redis backend not yet implemented")

    def get(self, key: str) -> Optional[Any]:
        raise NotImplementedError("Redis backend not yet implemented")

    def set(self, key: str, value: Any, ttl_seconds: Optional[int] = None) -> None:
        raise NotImplementedError("Redis backend not yet implemented")

    def delete(self, key: str) -> None:
        raise NotImplementedError("Redis backend not yet implemented")

    def increment(self, key: str, delta: int = 1) -> int:
        raise NotImplementedError("Redis backend not yet implemented")

    def get_ttl(self, key: str) -> Optional[int]:
        raise NotImplementedError("Redis backend not yet implemented")

    def clear(self) -> None:
        raise NotImplementedError("Redis backend not yet implemented")