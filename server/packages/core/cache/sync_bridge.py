"""Synchronous bridge for the async Cache interface.

Allows sync code (scheduler jobs, sync service functions) to use the unified
Cache without requiring ``async def`` callers.

Optimization: For ``MemoryCache``, operations are direct dict accesses (no
background thread needed — async methods are lightweight wrappers). For
``RedisCache``, a dedicated background event loop thread handles async Redis
commands, avoiding deadlocks when called from sync code running inside
FastAPI's event loop.
"""

from __future__ import annotations

import asyncio
import threading
from typing import Any

from packages.core.cache.base import Cache


class SyncCacheBridge:
    """Sync wrapper over an async ``Cache`` instance.

    Thread-safe. Safe to call from sync code running inside or outside an
    event loop (e.g., FastAPI sync route handlers, scheduler jobs).
    """

    def __init__(self, cache: Cache) -> None:
        self._cache = cache
        self._loop: asyncio.AbstractEventLoop | None = None
        self._loop_thread: threading.Thread | None = None
        self._is_memory = False

        from packages.core.cache.memory import MemoryCache

        if isinstance(cache, MemoryCache):
            self._is_memory = True
        else:
            self._loop = asyncio.new_event_loop()
            self._loop_thread = threading.Thread(
                target=self._run_forever, daemon=True, name="sync-cache-bridge"
            )
            self._loop_thread.start()

    def _run_forever(self) -> None:
        """Target for the background event loop thread."""
        assert self._loop is not None
        asyncio.set_event_loop(self._loop)
        self._loop.run_forever()

    def _submit(self, coro: Any) -> Any:
        """Run an async coroutine and return the result synchronously."""
        if self._is_memory:
            # MemoryCache: run coroutine directly in a short-lived loop.
            # This is safe because MemoryCache has no real I/O.
            loop = asyncio.new_event_loop()
            try:
                return loop.run_until_complete(coro)
            finally:
                loop.close()
        assert self._loop is not None
        future = asyncio.run_coroutine_threadsafe(coro, self._loop)
        return future.result()

    def get(self, key: str) -> Any | None:
        return self._submit(self._cache.get(key))

    def set(self, key: str, value: Any, *, ttl: int | None = None) -> None:
        self._submit(self._cache.set(key, value, ttl=ttl))

    def delete(self, key: str) -> None:
        self._submit(self._cache.delete(key))

    def close(self) -> None:
        """Stop the background event loop thread (if any)."""
        if self._loop is not None:
            self._loop.call_soon_threadsafe(self._loop.stop)
            if self._loop_thread is not None:
                self._loop_thread.join(timeout=5)
            self._loop.close()
            self._loop = None
            self._loop_thread = None

    @classmethod
    def from_cache(cls) -> SyncCacheBridge:
        """Create a bridge wrapping the global Cache singleton.

        Raises:
            RuntimeError: If ``init_cache()`` has not been called.
        """
        from packages.core.cache.factory import get_cache

        return cls(get_cache())
