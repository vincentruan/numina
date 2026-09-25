"""Cache factory — singleton lifecycle management."""

import redis.asyncio as aioredis

from packages.core.cache.base import Cache
from packages.core.cache.memory import MemoryCache
from packages.core.cache.redis import RedisCache
from packages.core.logging import get_logger

logger = get_logger(__name__)

_instance: Cache | None = None


def init_cache(
    backend: str = "memory",
    *,
    redis_url: str = "",
    prefix: str = "",
) -> Cache:
    """Create the global Cache singleton.

    Args:
        backend: ``"memory"`` or ``"redis"``.
        redis_url: Redis connection URL (required when ``backend="redis"``).
        prefix: Key prefix for namespace isolation in shared Redis.

    Returns:
        The newly created Cache instance.

    Raises:
        RuntimeError: If ``backend="redis"`` but *redis_url* is empty.
    """
    global _instance

    if backend == "redis":
        if not redis_url:
            raise RuntimeError("CACHE_BACKEND=redis requires REDIS_URL")
        client = aioredis.from_url(redis_url, decode_responses=True, max_connections=10)
        _instance = RedisCache(client, prefix=prefix)
        logger.info("Cache initialized: redis (prefix=%r)", prefix)
    else:
        _instance = MemoryCache()
        logger.info("Cache initialized: memory")

    return _instance


def get_cache() -> Cache:
    """Return the global Cache singleton.

    Raises:
        RuntimeError: If ``init_cache()`` has not been called.
    """
    if _instance is None:
        raise RuntimeError("Cache not initialized — call init_cache() first")
    return _instance


def reset_cache() -> None:
    """Reset the singleton (for testing)."""
    global _instance
    _instance = None


async def _check_redis_connection(redis_url: str) -> None:
    """Verify Redis connectivity at startup.

    Only called when ``CACHE_BACKEND=redis``. Raises ``RuntimeError``
    so the service fails fast rather than silently degrading.
    """
    try:
        r = aioredis.from_url(redis_url)
        await r.ping()
        await r.aclose()
    except Exception as e:
        raise RuntimeError(f"Redis connection failed: {e}") from e
