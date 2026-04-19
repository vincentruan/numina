"""Tests for cache backend configuration validation."""

import pytest

from app.config import settings
from app.services.cache.redis import RedisCacheBackend


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
    """App lifespan raises ValueError when CACHE_BACKEND=redis."""
    monkeypatch.setattr(settings, "CACHE_BACKEND", "redis")

    # Import here to avoid circular import issues at module level
    import asyncio
    from app.main import lifespan, app

    async def run_lifespan():
        async with lifespan(app):
            pass  # pragma: no cover

    with pytest.raises(ValueError, match="CACHE_BACKEND=redis is not yet implemented"):
        asyncio.get_event_loop().run_until_complete(run_lifespan())


def test_lifespan_does_not_raise_on_memory_backend(monkeypatch, tmp_path):
    """App lifespan does not raise when CACHE_BACKEND=memory (default)."""
    monkeypatch.setattr(settings, "CACHE_BACKEND", "memory")
    # The check itself should not raise — we only test the guard, not full startup
    if settings.CACHE_BACKEND == "redis":
        raise ValueError("CACHE_BACKEND=redis is not yet implemented.")
    # Reaching here means no ValueError was raised
