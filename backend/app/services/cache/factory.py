"""Cache factory for creating cache backends."""

from app.config import settings
from app.services.cache.base import CacheBackend
from app.services.cache.memory import MemoryCacheBackend
from app.services.cache.redis import RedisCacheBackend

# Global cache instance for rate limiting
_rate_limit_cache: CacheBackend | None = None

# Global cache instance for captcha payload registry
_captcha_payload_cache: CacheBackend | None = None


def get_rate_limit_cache() -> CacheBackend:
    """Get or create the rate limit cache backend.

    Uses singleton pattern to reuse cache instance.

    Returns:
        CacheBackend instance (MemoryCacheBackend by default)
    """
    global _rate_limit_cache
    if _rate_limit_cache is None:
        if settings.CACHE_BACKEND == "redis":
            _rate_limit_cache = RedisCacheBackend(settings.REDIS_URL)
        else:
            _rate_limit_cache = MemoryCacheBackend()
    return _rate_limit_cache


def get_captcha_payload_cache() -> CacheBackend:
    """Get or create the captcha payload registry cache backend.

    Uses singleton pattern to reuse cache instance.
    Separate from rate limit cache for isolation.

    Returns:
        CacheBackend instance (MemoryCacheBackend by default)
    """
    global _captcha_payload_cache
    if _captcha_payload_cache is None:
        if settings.CACHE_BACKEND == "redis":
            _captcha_payload_cache = RedisCacheBackend(settings.REDIS_URL)
        else:
            _captcha_payload_cache = MemoryCacheBackend()
    return _captcha_payload_cache


def reset_rate_limit_cache() -> None:
    """Reset cache for testing.

    Clears existing cache and resets to None so next call creates fresh instance.
    """
    global _rate_limit_cache
    if _rate_limit_cache is not None:
        _rate_limit_cache.clear()
    _rate_limit_cache = None


def reset_captcha_payload_cache() -> None:
    """Reset captcha payload cache for testing.

    Clears existing cache and resets to None so next call creates fresh instance.
    """
    global _captcha_payload_cache
    if _captcha_payload_cache is not None:
        _captcha_payload_cache.clear()
    _captcha_payload_cache = None