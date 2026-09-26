"""Tests for SyncCacheBridge — sync wrapper over async Cache."""

import time

import pytest

from packages.core.cache import MemoryCache, init_cache, reset_cache
from packages.core.cache.sync_bridge import SyncCacheBridge


class TestSyncBridgeMemory:
    """MemoryCache path — direct dict access, no background thread."""

    def setup_method(self):
        self.cache = MemoryCache()
        self.bridge = SyncCacheBridge(self.cache)

    def test_get_miss_returns_none(self):
        assert self.bridge.get("nope") is None

    def test_set_and_get(self):
        self.bridge.set("k1", "v1", ttl=60)
        assert self.bridge.get("k1") == "v1"

    def test_set_with_ttl_expires(self):
        self.bridge.set("k1", "v1", ttl=1)
        assert self.bridge.get("k1") == "v1"
        time.sleep(1.1)
        assert self.bridge.get("k1") is None

    def test_delete(self):
        self.bridge.set("k1", "v1")
        self.bridge.delete("k1")
        assert self.bridge.get("k1") is None

    def test_delete_nonexistent_no_error(self):
        self.bridge.delete("nope")  # should not raise

    def test_no_background_thread_for_memory(self):
        """MemoryCache path must NOT start a background event loop."""
        assert self.bridge._loop_thread is None


class TestSyncBridgeRedis:
    """RedisCache path — background event loop thread."""

    def setup_method(self):
        import fakeredis.aioredis
        from packages.core.cache import RedisCache

        cache = RedisCache.__new__(RedisCache)
        cache._client = fakeredis.aioredis.FakeRedis(decode_responses=True)
        cache._prefix = ""
        self.cache = cache
        self.bridge = SyncCacheBridge(cache)

    def teardown_method(self):
        self.bridge.close()

    def test_set_and_get(self):
        self.bridge.set("k1", "v1", ttl=60)
        assert self.bridge.get("k1") == "v1"

    def test_delete(self):
        self.bridge.set("k1", "v1")
        self.bridge.delete("k1")
        assert self.bridge.get("k1") is None

    def test_ttl_expires(self):
        self.bridge.set("k1", "v1", ttl=1)
        assert self.bridge.get("k1") == "v1"
        time.sleep(1.1)
        assert self.bridge.get("k1") is None


class TestSyncBridgeFactory:
    """from_cache() returns a bridge wrapping get_cache()."""

    def setup_method(self):
        reset_cache()

    def teardown_method(self):
        reset_cache()

    def test_from_cache_returns_bridge(self):
        init_cache(backend="memory")
        bridge = SyncCacheBridge.from_cache()
        assert isinstance(bridge, SyncCacheBridge)

    def test_from_cache_raises_if_not_initialized(self):
        with pytest.raises(RuntimeError, match="not initialized"):
            SyncCacheBridge.from_cache()
