"""Unified cache abstraction — memory/redis dual implementation."""

from __future__ import annotations

from packages.core.cache.base import Cache
from packages.core.cache.factory import (
    get_cache,
    init_cache,
    reset_cache,
)
from packages.core.cache.memory import MemoryCache
from packages.core.cache.sync_bridge import SyncCacheBridge


def __getattr__(name: str):
    """Lazy import RedisCache — redis may not be installed in all environments."""
    if name == "RedisCache":
        from packages.core.cache.redis import RedisCache
        return RedisCache
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "Cache",
    "MemoryCache",
    "RedisCache",
    "SyncCacheBridge",
    "init_cache",
    "get_cache",
    "reset_cache",
]
