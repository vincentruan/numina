"""Unified cache abstraction — memory/redis dual implementation."""

from packages.core.cache.base import Cache
from packages.core.cache.factory import (
    _check_redis_connection,
    get_cache,
    init_cache,
    reset_cache,
)
from packages.core.cache.memory import MemoryCache
from packages.core.cache.redis import RedisCache
from packages.core.cache.sync_bridge import SyncCacheBridge

__all__ = [
    "Cache",
    "MemoryCache",
    "RedisCache",
    "SyncCacheBridge",
    "init_cache",
    "get_cache",
    "reset_cache",
    "_check_redis_connection",
]
