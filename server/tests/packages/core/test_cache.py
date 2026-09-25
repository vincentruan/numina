"""Tests for unified Cache abstraction (MemoryCache + RedisCache)."""

import time

import fakeredis.aioredis
import pytest

from packages.core.cache import keys
from packages.core.cache.base import Cache
from packages.core.cache.factory import get_cache, init_cache, reset_cache
from packages.core.cache.memory import MemoryCache
from packages.core.cache.redis import RedisCache


# =============================================================================
# MemoryCache — Value operations
# =============================================================================


class TestMemoryCacheValue:
    async def test_set_and_get(self):
        cache = MemoryCache()
        await cache.set("k1", "v1")
        assert await cache.get("k1") == "v1"

    async def test_get_nonexistent(self):
        cache = MemoryCache()
        assert await cache.get("nope") is None

    async def test_delete(self):
        cache = MemoryCache()
        await cache.set("k1", "v1")
        await cache.delete("k1")
        assert await cache.get("k1") is None

    async def test_delete_nonexistent(self):
        cache = MemoryCache()
        await cache.delete("nope")  # should not raise

    async def test_ttl_expiration(self):
        cache = MemoryCache()
        await cache.set("k1", "v1", ttl=1)
        assert await cache.get("k1") == "v1"
        time.sleep(1.1)
        assert await cache.get("k1") is None

    async def test_get_ttl(self):
        cache = MemoryCache()
        await cache.set("k1", "v1", ttl=60)
        ttl = await cache.get_ttl("k1")
        assert ttl is not None
        assert 58 <= ttl <= 60

    async def test_get_ttl_no_ttl(self):
        cache = MemoryCache()
        await cache.set("k1", "v1")
        assert await cache.get_ttl("k1") is None

    async def test_get_ttl_nonexistent(self):
        cache = MemoryCache()
        assert await cache.get_ttl("nope") is None

    async def test_overwrite_preserves_value(self):
        cache = MemoryCache()
        await cache.set("k1", "v1")
        await cache.set("k1", "v2")
        assert await cache.get("k1") == "v2"

    async def test_overwrite_clears_ttl_when_none(self):
        cache = MemoryCache()
        await cache.set("k1", "v1", ttl=60)
        await cache.set("k1", "v2")  # no ttl → clears previous TTL
        assert await cache.get_ttl("k1") is None


# =============================================================================
# MemoryCache — Counter operations
# =============================================================================


class TestMemoryCacheCounter:
    async def test_increment_new_key(self):
        cache = MemoryCache()
        assert await cache.increment("counter") == 1

    async def test_increment_existing(self):
        cache = MemoryCache()
        await cache.set("counter", 5)
        assert await cache.increment("counter") == 6

    async def test_increment_with_delta(self):
        cache = MemoryCache()
        await cache.set("counter", 5)
        assert await cache.increment("counter", 10) == 15

    async def test_increment_preserves_ttl(self):
        cache = MemoryCache()
        await cache.set("counter", 1, ttl=2)
        await cache.increment("counter")
        ttl = await cache.get_ttl("counter")
        assert ttl is not None
        assert 0 < ttl <= 2


# =============================================================================
# MemoryCache — Set operations
# =============================================================================


class TestMemoryCacheSet:
    async def test_sadd_and_sismember(self):
        cache = MemoryCache()
        await cache.sadd("ips", "1.2.3.4")
        assert await cache.sismember("ips", "1.2.3.4") is True
        assert await cache.sismember("ips", "5.6.7.8") is False

    async def test_smembers(self):
        cache = MemoryCache()
        await cache.sadd("ips", "1.1.1.1", "2.2.2.2")
        members = await cache.smembers("ips")
        assert members == {"1.1.1.1", "2.2.2.2"}

    async def test_smembers_nonexistent(self):
        cache = MemoryCache()
        assert await cache.smembers("nope") == set()

    async def test_srem(self):
        cache = MemoryCache()
        await cache.sadd("ips", "1.1.1.1", "2.2.2.2")
        removed = await cache.srem("ips", "1.1.1.1")
        assert removed == 1
        assert await cache.sismember("ips", "1.1.1.1") is False

    async def test_srem_nonexistent_member(self):
        cache = MemoryCache()
        await cache.sadd("ips", "1.1.1.1")
        removed = await cache.srem("ips", "9.9.9.9")
        assert removed == 0

    async def test_set_ttl_expiration(self):
        """Set entries expire after TTL — critical for suspicious IP sets."""
        cache = MemoryCache()
        await cache.sadd("ips", "1.1.1.1", ttl=1)
        assert await cache.sismember("ips", "1.1.1.1") is True
        time.sleep(1.1)
        assert await cache.sismember("ips", "1.1.1.1") is False
        assert await cache.smembers("ips") == set()


# =============================================================================
# MemoryCache — List operations
# =============================================================================


class TestMemoryCacheList:
    async def test_lpush_and_lrange(self):
        cache = MemoryCache()
        await cache.lpush("events", {"type": "login", "ip": "1.2.3.4"})
        await cache.lpush("events", {"type": "logout", "ip": "1.2.3.4"})
        items = await cache.lrange("events", 0, -1)
        assert len(items) == 2
        assert items[0]["type"] == "logout"  # most recent first

    async def test_lpush_returns_length(self):
        cache = MemoryCache()
        length = await cache.lpush("events", "e1")
        assert length == 1
        length = await cache.lpush("events", "e2")
        assert length == 2

    async def test_ltrim(self):
        cache = MemoryCache()
        for i in range(5):
            await cache.lpush("events", f"event-{i}")
        await cache.ltrim("events", 0, 2)
        items = await cache.lrange("events", 0, -1)
        assert len(items) == 3

    async def test_lrange_nonexistent(self):
        cache = MemoryCache()
        assert await cache.lrange("nope", 0, -1) == []

    async def test_list_ttl_expiration(self):
        cache = MemoryCache()
        await cache.lpush("events", "e1", ttl=1)
        items = await cache.lrange("events", 0, -1)
        assert len(items) == 1
        time.sleep(1.1)
        items = await cache.lrange("events", 0, -1)
        assert len(items) == 0


# =============================================================================
# MemoryCache — clear
# =============================================================================


class TestMemoryCacheClear:
    async def test_clear(self):
        cache = MemoryCache()
        await cache.set("k1", "v1")
        await cache.set("k2", "v2")
        await cache.sadd("ips", "1.1.1.1")
        await cache.lpush("events", "e1")
        await cache.clear()
        assert await cache.get("k1") is None
        assert await cache.smembers("ips") == set()
        assert await cache.lrange("events", 0, -1) == []


# =============================================================================
# MemoryCache — cleanup_expired
# =============================================================================


class TestMemoryCacheCleanup:
    async def test_cleanup_expired(self):
        cache = MemoryCache()
        await cache.set("k1", "v1", ttl=1)
        await cache.set("k2", "v2", ttl=2)
        await cache.set("k3", "v3")  # No TTL
        time.sleep(1.1)
        removed = cache.cleanup_expired()
        assert removed == 1
        assert await cache.get("k1") is None
        assert await cache.get("k2") == "v2"
        assert await cache.get("k3") == "v3"


# =============================================================================
# RedisCache — Value operations (using fakeredis)
# =============================================================================


@pytest.fixture
def redis_cache():
    """RedisCache backed by fakeredis (no real Redis required)."""
    cache = RedisCache.__new__(RedisCache)
    cache._client = fakeredis.aioredis.FakeRedis(decode_responses=True)
    cache._prefix = ""
    yield cache


class TestRedisCacheValue:
    async def test_set_and_get(self, redis_cache):
        await redis_cache.set("k1", "v1")
        assert await redis_cache.get("k1") == "v1"

    async def test_get_nonexistent(self, redis_cache):
        assert await redis_cache.get("nope") is None

    async def test_delete(self, redis_cache):
        await redis_cache.set("k1", "v1")
        await redis_cache.delete("k1")
        assert await redis_cache.get("k1") is None

    async def test_ttl_expiration(self, redis_cache):
        await redis_cache.set("k1", "v1", ttl=1)
        assert await redis_cache.get("k1") == "v1"
        time.sleep(1.1)
        assert await redis_cache.get("k1") is None

    async def test_get_ttl(self, redis_cache):
        await redis_cache.set("k1", "v1", ttl=60)
        ttl = await redis_cache.get_ttl("k1")
        assert ttl is not None
        assert 58 <= ttl <= 60

    async def test_get_ttl_no_ttl(self, redis_cache):
        await redis_cache.set("k1", "v1")
        assert await redis_cache.get_ttl("k1") is None

    async def test_integer_roundtrip(self, redis_cache):
        await redis_cache.set("n", 42)
        assert await redis_cache.get("n") == 42

    async def test_string_one_roundtrip(self, redis_cache):
        """Captcha cache stores "1" as sentinel."""
        await redis_cache.set("altcha:used:abc", "1", ttl=3600)
        assert await redis_cache.get("altcha:used:abc") == "1"

    async def test_dict_roundtrip(self, redis_cache):
        """Complex values are JSON-serialized."""
        data = {"type": "login", "ip": "1.2.3.4", "count": 42}
        await redis_cache.set("event", data)
        result = await redis_cache.get("event")
        assert result == data


# =============================================================================
# RedisCache — Counter operations
# =============================================================================


class TestRedisCacheCounter:
    async def test_increment_new_key(self, redis_cache):
        assert await redis_cache.increment("counter") == 1

    async def test_increment_existing(self, redis_cache):
        await redis_cache.set("counter", 5)
        assert await redis_cache.increment("counter") == 6

    async def test_increment_with_delta(self, redis_cache):
        await redis_cache.set("counter", 5)
        assert await redis_cache.increment("counter", 10) == 15


# =============================================================================
# RedisCache — Set operations
# =============================================================================


class TestRedisCacheSet:
    async def test_sadd_and_sismember(self, redis_cache):
        await redis_cache.sadd("ips", "1.2.3.4")
        assert await redis_cache.sismember("ips", "1.2.3.4") is True
        assert await redis_cache.sismember("ips", "5.6.7.8") is False

    async def test_smembers(self, redis_cache):
        await redis_cache.sadd("ips", "1.1.1.1", "2.2.2.2")
        members = await redis_cache.smembers("ips")
        assert members == {"1.1.1.1", "2.2.2.2"}

    async def test_srem(self, redis_cache):
        await redis_cache.sadd("ips", "1.1.1.1", "2.2.2.2")
        removed = await redis_cache.srem("ips", "1.1.1.1")
        assert removed == 1
        assert await redis_cache.sismember("ips", "1.1.1.1") is False


# =============================================================================
# RedisCache — List operations
# =============================================================================


class TestRedisCacheList:
    async def test_lpush_and_lrange(self, redis_cache):
        await redis_cache.lpush("events", {"type": "login"})
        await redis_cache.lpush("events", {"type": "logout"})
        items = await redis_cache.lrange("events", 0, -1)
        assert len(items) == 2
        assert items[0]["type"] == "logout"

    async def test_ltrim(self, redis_cache):
        for i in range(5):
            await redis_cache.lpush("events", f"event-{i}")
        await redis_cache.ltrim("events", 0, 2)
        items = await redis_cache.lrange("events", 0, -1)
        assert len(items) == 3


# =============================================================================
# RedisCache — clear safety (prefix-scoped)
# =============================================================================


class TestRedisCacheClearSafety:
    async def test_clear_only_deletes_own_prefix(self):
        """clear() must NOT call flushdb() when prefix is set."""
        cache = RedisCache.__new__(RedisCache)
        fake = fakeredis.aioredis.FakeRedis(decode_responses=True)
        cache._client = fake
        cache._prefix = "myapp:"

        await cache.set("k1", "v1")
        await cache.set("k2", "v2")
        await fake.set("otherservice:key", "foreign-data")

        await cache.clear()

        assert await cache.get("k1") is None
        assert await cache.get("k2") is None
        assert await fake.get("otherservice:key") == "foreign-data"

    async def test_clear_without_prefix_flushes(self):
        """Without a prefix, clear() falls back to flushdb (single-app Redis)."""
        cache = RedisCache.__new__(RedisCache)
        fake = fakeredis.aioredis.FakeRedis(decode_responses=True)
        cache._client = fake
        cache._prefix = ""

        await cache.set("k1", "v1")
        await cache.clear()
        assert await cache.get("k1") is None

    async def test_prefix_isolation(self):
        """Two caches with different prefixes don't see each other's keys."""
        fake = fakeredis.aioredis.FakeRedis(decode_responses=True)

        cache_a = RedisCache.__new__(RedisCache)
        cache_a._client = fake
        cache_a._prefix = "a:"

        cache_b = RedisCache.__new__(RedisCache)
        cache_b._client = fake
        cache_b._prefix = "b:"

        await cache_a.set("key", "from-a")
        await cache_b.set("key", "from-b")

        assert await cache_a.get("key") == "from-a"
        assert await cache_b.get("key") == "from-b"


# =============================================================================
# Factory
# =============================================================================


class TestFactory:
    def setup_method(self):
        reset_cache()

    def teardown_method(self):
        reset_cache()

    def test_init_memory_default(self):
        cache = init_cache(backend="memory")
        assert isinstance(cache, MemoryCache)
        assert get_cache() is cache

    def test_get_cache_before_init_raises(self):
        with pytest.raises(RuntimeError, match="not initialized"):
            get_cache()

    def test_singleton(self):
        init_cache(backend="memory")
        c1 = get_cache()
        c2 = get_cache()
        assert c1 is c2

    def test_init_redis_without_url_raises(self):
        with pytest.raises(RuntimeError, match="REDIS_URL"):
            init_cache(backend="redis")

    def test_init_redis_with_fakeredis(self, monkeypatch):
        """Redis backend creation with fakeredis injection."""
        import redis.asyncio as aioredis

        def fake_from_url(url, **kwargs):
            return fakeredis.aioredis.FakeRedis(decode_responses=True)

        monkeypatch.setattr(aioredis, "from_url", fake_from_url)
        cache = init_cache(backend="redis", redis_url="redis://fake:6379/0")
        assert isinstance(cache, RedisCache)


# =============================================================================
# Key constants
# =============================================================================


class TestKeys:
    def test_prefix_constants_exist(self):
        assert keys.RATE_LIMIT == "ratelimit"
        assert keys.CAPTCHA == "captcha"
        assert keys.FAM_SETTING == "famsetting"
        assert keys.AGENT_REG == "agentreg"
        assert keys.FX_RATE == "fxrate"
        assert keys.SEC_EVENT == "secevent"
        assert keys.SEC_SUSPECT == "secsuspect"
        assert keys.SEC_COUNTER == "seccounter"
