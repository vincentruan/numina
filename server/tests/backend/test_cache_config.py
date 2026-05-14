"""Tests for cache backend configuration."""

from apps.backend.app.config import settings


def test_cache_backend_memory_is_default():
    """Default CACHE_BACKEND is 'memory'."""
    assert settings.CACHE_BACKEND == "memory"
