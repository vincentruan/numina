"""Tests for cache backend configuration validation."""

import asyncio

import pytest

from app.config import settings
from app.services.cache.redis import RedisCacheBackend


def _run_in_new_loop(coro):
    """Run a coroutine in a fresh event loop without closing the global loop.

    asyncio.run() closes the running loop, which breaks tests that use
    asyncio.get_event_loop() afterwards (e.g. storage backend tests).
    """
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def test_redis_backend_constructor_does_not_raise():
    """RedisCacheBackend can be instantiated without raising."""
    backend = RedisCacheBackend("redis://localhost:6379/0")
    assert backend._redis_url == "redis://localhost:6379/0"


def test_redis_backend_operations_raise():
    """All RedisCacheBackend operations raise NotImplementedError."""
    backend = RedisCacheBackend("redis://localhost:6379/0")
    with pytest.raises(NotImplementedError):
        backend.get("key")
    with pytest.raises(NotImplementedError):
        backend.set("key", "value")
    with pytest.raises(NotImplementedError):
        backend.delete("key")
    with pytest.raises(NotImplementedError):
        backend.increment("key")
    with pytest.raises(NotImplementedError):
        backend.get_ttl("key")
    with pytest.raises(NotImplementedError):
        backend.clear()


def test_cache_backend_memory_is_default():
    """Default CACHE_BACKEND is 'memory'."""
    assert settings.CACHE_BACKEND == "memory"


def test_lifespan_raises_on_redis_backend(monkeypatch):
    """App lifespan raises RuntimeError when CACHE_BACKEND=redis."""
    monkeypatch.setattr(settings, "CACHE_BACKEND", "redis")

    from app.main import lifespan, app

    async def run_lifespan():
        async with lifespan(app):
            pass  # pragma: no cover

    with pytest.raises(RuntimeError, match="Unsupported CACHE_BACKEND="):
        _run_in_new_loop(run_lifespan())


def test_lifespan_raises_on_unknown_backend(monkeypatch):
    """App lifespan raises RuntimeError for any unrecognized CACHE_BACKEND value."""
    monkeypatch.setattr(settings, "CACHE_BACKEND", "memcached")

    from app.main import lifespan, app

    async def run_lifespan():
        async with lifespan(app):
            pass  # pragma: no cover

    with pytest.raises(RuntimeError, match="Unsupported CACHE_BACKEND="):
        _run_in_new_loop(run_lifespan())
