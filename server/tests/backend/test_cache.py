"""Tests for cache layer."""

import time

import fakeredis
import pytest

from apps.backend.app.services.cache.factory import get_rate_limit_cache, reset_rate_limit_cache
from apps.backend.app.services.cache.memory import MemoryCacheBackend
from apps.backend.app.services.cache.redis import RedisCacheBackend


@pytest.fixture
def redis_cache():
    """RedisCacheBackend backed by fakeredis (no real Redis required)."""
    backend = RedisCacheBackend.__new__(RedisCacheBackend)
    backend._client = fakeredis.FakeRedis(decode_responses=True)
    return backend


class TestMemoryCacheBackend:
    """Tests for MemoryCacheBackend."""

    def test_set_and_get(self):
        """Test basic set and get operations."""
        cache = MemoryCacheBackend()
        cache.set("key1", "value1")
        assert cache.get("key1") == "value1"

    def test_get_nonexistent_key(self):
        """Test getting a key that doesn't exist."""
        cache = MemoryCacheBackend()
        assert cache.get("nonexistent") is None

    def test_delete(self):
        """Test deleting a key."""
        cache = MemoryCacheBackend()
        cache.set("key1", "value1")
        cache.delete("key1")
        assert cache.get("key1") is None

    def test_clear(self):
        """Test clearing all keys."""
        cache = MemoryCacheBackend()
        cache.set("key1", "value1")
        cache.set("key2", "value2")
        cache.clear()
        assert cache.get("key1") is None
        assert cache.get("key2") is None

    def test_increment_new_key(self):
        """Test incrementing a new key."""
        cache = MemoryCacheBackend()
        result = cache.increment("counter")
        assert result == 1

    def test_increment_existing_key(self):
        """Test incrementing an existing key."""
        cache = MemoryCacheBackend()
        cache.set("counter", 5)
        result = cache.increment("counter")
        assert result == 6

    def test_increment_with_delta(self):
        """Test incrementing with custom delta."""
        cache = MemoryCacheBackend()
        cache.set("counter", 5)
        result = cache.increment("counter", delta=10)
        assert result == 15

    def test_ttl_expiration(self):
        """Test that keys expire after TTL."""
        cache = MemoryCacheBackend()
        cache.set("key_ttl", "value", ttl_seconds=1)
        assert cache.get("key_ttl") == "value"
        time.sleep(1.1)
        assert cache.get("key_ttl") is None

    def test_get_ttl(self):
        """Test getting remaining TTL."""
        cache = MemoryCacheBackend()
        cache.set("key1", "value", ttl_seconds=60)
        ttl = cache.get_ttl("key1")
        assert ttl is not None
        assert 58 <= ttl <= 60  # Allow some variance

    def test_get_ttl_no_ttl(self):
        """Test getting TTL for key without TTL."""
        cache = MemoryCacheBackend()
        cache.set("key1", "value")
        assert cache.get_ttl("key1") is None

    def test_get_ttl_nonexistent_key(self):
        """Test getting TTL for nonexistent key."""
        cache = MemoryCacheBackend()
        assert cache.get_ttl("nonexistent") is None

    def test_cleanup_expired(self):
        """Test cleanup of expired entries."""
        cache = MemoryCacheBackend()
        cache.set("key1", "value1", ttl_seconds=1)
        cache.set("key2", "value2", ttl_seconds=2)
        cache.set("key3", "value3")  # No TTL
        time.sleep(1.1)
        removed = cache.cleanup_expired()
        assert removed == 1
        assert cache.get("key1") is None
        assert cache.get("key2") == "value2"
        assert cache.get("key3") == "value3"

    def test_increment_preserves_ttl(self):
        """Test that increment preserves TTL."""
        cache = MemoryCacheBackend()
        cache.set("counter", 1, ttl_seconds=2)
        cache.increment("counter")
        ttl = cache.get_ttl("counter")
        assert ttl is not None
        assert 0 < ttl <= 2


class TestRedisCacheBackend:
    """Tests for RedisCacheBackend using fakeredis."""

    def test_set_and_get(self, redis_cache):
        redis_cache.set("key1", "value1")
        assert redis_cache.get("key1") == "value1"

    def test_get_nonexistent_key(self, redis_cache):
        assert redis_cache.get("nonexistent") is None

    def test_delete(self, redis_cache):
        redis_cache.set("key1", "value1")
        redis_cache.delete("key1")
        assert redis_cache.get("key1") is None

    def test_clear(self, redis_cache):
        redis_cache.set("key1", "value1")
        redis_cache.set("key2", "value2")
        redis_cache.clear()
        assert redis_cache.get("key1") is None
        assert redis_cache.get("key2") is None

    def test_increment_new_key(self, redis_cache):
        assert redis_cache.increment("counter") == 1

    def test_increment_existing_key(self, redis_cache):
        redis_cache.set("counter", 5)
        assert redis_cache.increment("counter") == 6

    def test_increment_with_delta(self, redis_cache):
        redis_cache.set("counter", 5)
        assert redis_cache.increment("counter", delta=10) == 15

    def test_ttl_expiration(self, redis_cache):
        redis_cache.set("key_ttl", "value", ttl_seconds=1)
        assert redis_cache.get("key_ttl") == "value"
        time.sleep(1.1)
        assert redis_cache.get("key_ttl") is None

    def test_get_ttl(self, redis_cache):
        redis_cache.set("key1", "value", ttl_seconds=60)
        ttl = redis_cache.get_ttl("key1")
        assert ttl is not None
        assert 58 <= ttl <= 60

    def test_get_ttl_no_ttl(self, redis_cache):
        redis_cache.set("key1", "value")
        assert redis_cache.get_ttl("key1") is None

    def test_get_ttl_nonexistent_key(self, redis_cache):
        assert redis_cache.get_ttl("nonexistent") is None

    def test_integer_values_roundtrip(self, redis_cache):
        redis_cache.set("n", 42)
        assert redis_cache.get("n") == 42

    def test_string_one_roundtrip(self, redis_cache):
        # captcha cache stores "1" as a sentinel
        redis_cache.set("altcha:used:abc", "1", ttl_seconds=3600)
        assert redis_cache.get("altcha:used:abc") == "1"


class TestCacheFactory:
    """Tests for cache factory."""

    def test_get_rate_limit_cache_returns_memory_by_default(self):
        reset_rate_limit_cache()
        cache = get_rate_limit_cache()
        assert isinstance(cache, MemoryCacheBackend)

    def test_get_rate_limit_cache_singleton(self):
        reset_rate_limit_cache()
        cache1 = get_rate_limit_cache()
        cache2 = get_rate_limit_cache()
        assert cache1 is cache2

    def test_reset_rate_limit_cache(self):
        cache1 = get_rate_limit_cache()
        cache1.set("key1", "value1")
        reset_rate_limit_cache()
        cache2 = get_rate_limit_cache()
        assert cache2.get("key1") is None

    def test_get_rate_limit_cache_returns_redis_when_configured(self, monkeypatch):
        import fakeredis

        from apps.backend.app.config import settings
        monkeypatch.setattr(settings, "CACHE_BACKEND", "redis")
        monkeypatch.setattr("apps.backend.app.services.cache.redis.redis_lib.from_url", lambda url, **kw: fakeredis.FakeRedis(decode_responses=True))
        reset_rate_limit_cache()
        cache = get_rate_limit_cache()
        assert isinstance(cache, RedisCacheBackend)
        reset_rate_limit_cache()  # cleanup