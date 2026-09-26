# Unified Redis Shared Cache Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move all "cache layer" data (shared state, config hot-path, data acceleration, security monitoring) behind a single `Cache` abstraction in `packages/core/cache/`, with memory/redis dual implementation, replacing the current fragmented pattern of inline dicts and per-purpose factory functions.

**Architecture:** Create `Cache` abstract base class in `packages/core/cache/` with Value/Counter/Set/List operation groups (inspired by Spring Data Redis). Single global instance via `init_cache()`/`get_cache()` factory. `MemoryCache` and `RedisCache` (async, via `redis.asyncio`) implement the interface. Key prefixes in `keys.py` prevent collisions. All existing inline dicts (`_rate_store`, `_family_setting_cache`, `InMemorySecurityStore`, `agent_registry._cache`, `exchange_rate_adapter._cache`) are migrated to use `get_cache()`. The old `server/apps/backend/app/services/cache/` directory is deleted.

**Tech Stack:** Python 3.12+, `redis.asyncio` (async Redis client), `fakeredis` (test fake), FastAPI lifespan, `asyncio`

**Spec:** [`docs/superpowers/specs/2026-09-25-unified-redis-shared-cache-design.md`](../specs/2026-09-25-unified-redis-shared-cache-design.md)

## Global Constraints

- Python 3.12+ union syntax: `str | None`, `list[str]` (not `Optional`, not `List`)
- Import direction: `apps/` → `packages/`, never reverse; `packages/` never import `apps/`
- `packages/core` never imports from `apps/`
- Async interface: all `Cache` methods are `async def`; callers use `await`
- Key prefix convention via `keys.py` constants — no hardcoded prefixes in consumer code
- `RedisCache.clear()` must use SCAN+DEL by prefix, NOT `flushdb()` (multi-service shared Redis)
- `redis.asyncio.Redis` connection pool: `max_connections=10`
- No speculative operations (Hash, Sorted Set) — only Value/Counter/Set/List

## Review Focus

1. **`RedisCache.clear()` safety** — must only delete keys matching the app's prefix, never call `flushdb()`. Test: write keys with different prefixes, call `clear()`, verify foreign keys survive. → Pinned to Task 1 (Step: `test_clear_only_deletes_own_prefix`).

2. **`MemoryCache` Set/List TTL expiry** — sets and lists must expire correctly via the shared `_expire_at` dict, not just values. Test: `sadd` with TTL, sleep past TTL, verify `smembers` returns empty. → Pinned to Task 1 (Step: `test_set_ttl_expiration`).

3. **Sync→async cascade in `config_service.get_family_setting_cached`** — this function is currently sync, called from both async routers and sync job functions. Converting to async must not break the scheduler_worker's `fetch_rates_job` call path. → Pinned to Task 2 (Step: `test_family_setting_cached_async`).

4. **Rate limit middleware async conversion** — `RateLimitMiddleware.dispatch()` is already async, but `_check_rate_limit()` is sync using a class-level dict. Converting to `await cache.increment()` + TTL must not break the 429 response path. → Pinned to Task 2 (Step: `test_rate_limit_uses_cache`).

5. **Test fixture `reset_cache()` in conftest** — the old conftest calls `reset_rate_limit_cache()` and `reset_captcha_payload_cache()` per-test. The new fixture must call `reset_cache()` and ensure `RateLimitMiddleware._rate_store` is no longer referenced. → Pinned to Task 3 (Step: `test_conftest_reset`).

---

### Task 1: Core Cache Module (`packages/core/cache/`)

**Files:**
- Create: `server/packages/core/cache/__init__.py`
- Create: `server/packages/core/cache/base.py`
- Create: `server/packages/core/cache/memory.py`
- Create: `server/packages/core/cache/redis.py`
- Create: `server/packages/core/cache/factory.py`
- Create: `server/packages/core/cache/keys.py`
- Test: `server/tests/packages/core/test_cache.py`

**Interfaces:**
- Consumes: `packages.core.settings.settings` (for `CACHE_BACKEND`, `REDIS_URL`)
- Produces: `Cache` (ABC), `MemoryCache`, `RedisCache`, `init_cache()`, `get_cache()`, `reset_cache()`, key prefix constants

- [ ] **Step 1: Write the failing test for `Cache` base class**

```python
# server/tests/packages/core/test_cache.py
"""Tests for unified Cache abstraction (MemoryCache + RedisCache)."""

import time

import fakeredis
import pytest

from packages.core.cache.base import Cache
from packages.core.cache.memory import MemoryCache
from packages.core.cache.redis import RedisCache
from packages.core.cache.factory import init_cache, get_cache, reset_cache
from packages.core.cache import keys


# --- MemoryCache Value operations ---

class TestMemoryCacheValue:
    def test_set_and_get(self):
        cache = MemoryCache()
        import asyncio
        asyncio.get_event_loop().run_until_complete(cache.set("k1", "v1"))
        result = asyncio.get_event_loop().run_until_complete(cache.get("k1"))
        assert result == "v1"

    def test_get_nonexistent(self):
        cache = MemoryCache()
        import asyncio
        result = asyncio.get_event_loop().run_until_complete(cache.get("nope"))
        assert result is None

    def test_delete(self):
        cache = MemoryCache()
        import asyncio
        loop = asyncio.get_event_loop()
        loop.run_until_complete(cache.set("k1", "v1"))
        loop.run_until_complete(cache.delete("k1"))
        assert loop.run_until_complete(cache.get("k1")) is None

    def test_ttl_expiration(self):
        cache = MemoryCache()
        import asyncio
        loop = asyncio.get_event_loop()
        loop.run_until_complete(cache.set("k1", "v1", ttl=1))
        assert loop.run_until_complete(cache.get("k1")) == "v1"
        time.sleep(1.1)
        assert loop.run_until_complete(cache.get("k1")) is None

    def test_get_ttl(self):
        cache = MemoryCache()
        import asyncio
        loop = asyncio.get_event_loop()
        loop.run_until_complete(cache.set("k1", "v1", ttl=60))
        ttl = loop.run_until_complete(cache.get_ttl("k1"))
        assert ttl is not None
        assert 58 <= ttl <= 60

    def test_get_ttl_no_ttl(self):
        cache = MemoryCache()
        import asyncio
        loop = asyncio.get_event_loop()
        loop.run_until_complete(cache.set("k1", "v1"))
        assert loop.run_until_complete(cache.get_ttl("k1")) is None
```

Note: The above uses `run_until_complete` for simplicity. Since `pytest` is configured with `asyncio_mode = "auto"` for agent tests and the core tests also support async, the actual tests should use `async def test_*` with `await`. Rewrite as:

```python
# server/tests/packages/core/test_cache.py
"""Tests for unified Cache abstraction (MemoryCache + RedisCache)."""

import asyncio
import time

import fakeredis
import pytest

from packages.core.cache.base import Cache
from packages.core.cache.memory import MemoryCache
from packages.core.cache.redis import RedisCache
from packages.core.cache.factory import init_cache, get_cache, reset_cache
from packages.core.cache import keys


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

    async def test_srem(self):
        cache = MemoryCache()
        await cache.sadd("ips", "1.1.1.1", "2.2.2.2")
        removed = await cache.srem("ips", "1.1.1.1")
        assert removed == 1
        assert await cache.sismember("ips", "1.1.1.1") is False

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

    async def test_ltrim(self):
        cache = MemoryCache()
        for i in range(5):
            await cache.lpush("events", f"event-{i}")
        await cache.ltrim("events", 0, 2)
        items = await cache.lrange("events", 0, -1)
        assert len(items) == 3

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
        await cache.clear()
        assert await cache.get("k1") is None
        assert await cache.smembers("ips") == set()


# =============================================================================
# RedisCache — Value operations (using fakeredis)
# =============================================================================

@pytest.fixture
def redis_cache():
    """RedisCache backed by fakeredis (no real Redis required)."""
    cache = RedisCache.__new__(RedisCache)
    cache._client = fakeredis.FakeRedis(decode_responses=True)
    cache._prefix = ""  # no prefix for tests
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

    async def test_integer_roundtrip(self, redis_cache):
        await redis_cache.set("n", 42)
        assert await redis_cache.get("n") == 42

    async def test_string_one_roundtrip(self, redis_cache):
        """Captcha cache stores "1" as sentinel."""
        await redis_cache.set("altcha:used:abc", "1", ttl=3600)
        assert await redis_cache.get("altcha:used:abc") == "1"


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
        """clear() must NOT call flushdb(). It must only delete keys with matching prefix."""
        cache = RedisCache.__new__(RedisCache)
        fake = fakeredis.FakeRedis(decode_responses=True)
        cache._client = fake
        cache._prefix = "myapp:"

        # Write keys with our prefix
        await cache.set("k1", "v1")
        await cache.set("k2", "v2")

        # Write a key with a different prefix (simulating another service)
        fake.set("otherservice:key", "foreign-data")

        await cache.clear()

        # Our keys are gone
        assert await cache.get("k1") is None
        assert await cache.get("k2") is None

        # Foreign key survives
        assert fake.get("otherservice:key") == "foreign-data"


# =============================================================================
# Factory
# =============================================================================

class TestFactory:
    async def test_init_memory_default(self):
        reset_cache()
        cache = init_cache(backend="memory")
        assert isinstance(cache, MemoryCache)
        assert get_cache() is cache
        reset_cache()

    async def test_get_cache_before_init_raises(self):
        reset_cache()
        with pytest.raises(RuntimeError, match="not initialized"):
            get_cache()

    async def test_singleton(self):
        reset_cache()
        init_cache(backend="memory")
        c1 = get_cache()
        c2 = get_cache()
        assert c1 is c2
        reset_cache()


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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd server && uv run pytest tests/packages/core/test_cache.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'packages.core.cache'`

- [ ] **Step 3: Create `base.py` — Cache abstract base class**

```python
# server/packages/core/cache/base.py
"""Cache abstract base class — unified interface for memory/redis backends."""

from abc import ABC, abstractmethod
from typing import Any


class Cache(ABC):
    """Unified cache abstraction.

    Provides user-selectable flexibility: memory mode (process-local) or
    redis mode (cross-process shared). Used for shared state, config hot-paths,
    data acceleration, and security monitoring.

    Operations grouped by data structure (inspired by Spring Data Redis):
    - Value: KV read/write + TTL
    - Counter: atomic counter
    - Set: set operations (dedup, membership test)
    - List: list operations (event logs, time-range queries)
    """

    # --- Value ---

    @abstractmethod
    async def get(self, key: str) -> Any | None: ...

    @abstractmethod
    async def set(self, key: str, value: Any, *, ttl: int | None = None) -> None: ...

    @abstractmethod
    async def delete(self, key: str) -> None: ...

    @abstractmethod
    async def get_ttl(self, key: str) -> int | None: ...

    # --- Counter ---

    @abstractmethod
    async def increment(self, key: str, amount: int = 1) -> int: ...

    # --- Set ---

    @abstractmethod
    async def sadd(self, key: str, *members: str, ttl: int | None = None) -> int:
        """Add members to set. Optionally set TTL on first call."""
        ...

    @abstractmethod
    async def sismember(self, key: str, member: str) -> bool: ...

    @abstractmethod
    async def smembers(self, key: str) -> set[str]: ...

    @abstractmethod
    async def srem(self, key: str, *members: str) -> int: ...

    # --- List ---

    @abstractmethod
    async def lpush(self, key: str, value: Any, *, ttl: int | None = None) -> int:
        """Push value to left of list. Returns current list length."""
        ...

    @abstractmethod
    async def lrange(self, key: str, start: int, stop: int) -> list: ...

    @abstractmethod
    async def ltrim(self, key: str, start: int, stop: int) -> None: ...

    # --- Lifecycle ---

    @abstractmethod
    async def clear(self) -> None: ...
```

- [ ] **Step 4: Create `memory.py` — MemoryCache implementation**

```python
# server/packages/core/cache/memory.py
"""In-memory Cache implementation."""

import json
import time
from typing import Any

from packages.core.cache.base import Cache


class MemoryCache(Cache):
    """Process-local in-memory cache.

    All key types (Value / Set / List) share a unified expiry tracking
    mechanism via ``_expire_at``.
    """

    def __init__(self) -> None:
        # Value store: {key: (value, )}
        self._store: dict[str, tuple[Any, float | None]] = {}
        # Set store: {key: set[str]}
        self._sets: dict[str, set[str]] = {}
        # List store: {key: list[Any]}  (values are JSON-serialized)
        self._lists: dict[str, list[Any]] = {}
        # Unified expiry: {key: expire_at_timestamp}
        # Covers all stores (_store, _sets, _lists).
        self._expire_at: dict[str, float] = {}

    def _is_expired(self, key: str) -> bool:
        exp = self._expire_at.get(key)
        if exp is not None and time.time() > exp:
            self._remove_key(key)
            return True
        return False

    def _remove_key(self, key: str) -> None:
        self._store.pop(key, None)
        self._sets.pop(key, None)
        self._lists.pop(key, None)
        self._expire_at.pop(key, None)

    def _set_ttl(self, key: str, ttl: int | None) -> None:
        if ttl is not None:
            self._expire_at[key] = time.time() + ttl

    # --- Value ---

    async def get(self, key: str) -> Any | None:
        if self._is_expired(key):
            return None
        entry = self._store.get(key)
        if entry is None:
            return None
        return entry[0]

    async def set(self, key: str, value: Any, *, ttl: int | None = None) -> None:
        # Clear any set/list data for this key (type collision)
        self._sets.pop(key, None)
        self._lists.pop(key, None)
        self._store[key] = (value, None)
        if ttl is not None:
            self._expire_at[key] = time.time() + ttl
        else:
            self._expire_at.pop(key, None)

    async def delete(self, key: str) -> None:
        self._remove_key(key)

    async def get_ttl(self, key: str) -> int | None:
        if self._is_expired(key):
            return None
        exp = self._expire_at.get(key)
        if exp is None:
            return None
        remaining = int(exp - time.time())
        return max(0, remaining)

    # --- Counter ---

    async def increment(self, key: str, amount: int = 1) -> int:
        if self._is_expired(key):
            current = 0
        else:
            entry = self._store.get(key)
            current = entry[0] if entry is not None else 0
        new_value = current + amount
        # Preserve TTL
        exp = self._expire_at.get(key)
        self._store[key] = (new_value, None)
        if exp is not None:
            self._expire_at[key] = exp
        return new_value

    # --- Set ---

    async def sadd(self, key: str, *members: str, ttl: int | None = None) -> int:
        if self._is_expired(key):
            self._sets[key] = set()
        s = self._sets.setdefault(key, set())
        before = len(s)
        s.update(members)
        added = len(s) - before
        if ttl is not None:
            self._expire_at[key] = time.time() + ttl
        return added

    async def sismember(self, key: str, member: str) -> bool:
        if self._is_expired(key):
            return False
        s = self._sets.get(key)
        if s is None:
            return False
        return member in s

    async def smembers(self, key: str) -> set[str]:
        if self._is_expired(key):
            return set()
        s = self._sets.get(key)
        if s is None:
            return set()
        return set(s)

    async def srem(self, key: str, *members: str) -> int:
        if self._is_expired(key):
            return 0
        s = self._sets.get(key)
        if s is None:
            return 0
        before = len(s)
        s.difference_update(members)
        return before - len(s)

    # --- List ---

    async def lpush(self, key: str, value: Any, *, ttl: int | None = None) -> int:
        if self._is_expired(key):
            self._lists[key] = []
        lst = self._lists.setdefault(key, [])
        lst.insert(0, value)
        if ttl is not None:
            self._expire_at[key] = time.time() + ttl
        return len(lst)

    async def lrange(self, key: str, start: int, stop: int) -> list:
        if self._is_expired(key):
            return []
        lst = self._lists.get(key)
        if lst is None:
            return []
        if stop == -1:
            return list(lst[start:])
        return list(lst[start:stop + 1])

    async def ltrim(self, key: str, start: int, stop: int) -> None:
        if self._is_expired(key):
            return
        lst = self._lists.get(key)
        if lst is None:
            return
        if stop == -1:
            self._lists[key] = lst[start:]
        else:
            self._lists[key] = lst[start:stop + 1]

    # --- Lifecycle ---

    async def clear(self) -> None:
        self._store.clear()
        self._sets.clear()
        self._lists.clear()
        self._expire_at.clear()

    def cleanup_expired(self) -> int:
        """Remove all expired entries. Returns count of removed keys."""
        now = time.time()
        expired = [k for k, exp in self._expire_at.items() if now > exp]
        for k in expired:
            self._remove_key(k)
        return len(expired)
```

- [ ] **Step 5: Create `redis.py` — RedisCache implementation**

```python
# server/packages/core/cache/redis.py
"""Redis Cache implementation using redis.asyncio."""

import json
from typing import Any

import redis.asyncio as aioredis

from packages.core.cache.base import Cache


class RedisCache(Cache):
    """Redis-backed cache for cross-process shared state.

    Uses ``redis.asyncio.Redis`` for non-blocking IO.
    ``clear()`` is prefix-scoped (SCAN + DEL) — never calls ``flushdb()``.
    """

    def __init__(self, client: aioredis.Redis, *, prefix: str = "") -> None:
        self._client = client
        self._prefix = prefix

    def _key(self, key: str) -> str:
        return f"{self._prefix}{key}" if self._prefix else key

    # --- Value ---

    async def get(self, key: str) -> Any | None:
        val = await self._client.get(self._key(key))
        if val is None:
            return None
        return json.loads(val)

    async def set(self, key: str, value: Any, *, ttl: int | None = None) -> None:
        serialized = json.dumps(value)
        rk = self._key(key)
        if ttl is not None:
            await self._client.setex(rk, ttl, serialized)
        else:
            await self._client.set(rk, serialized)

    async def delete(self, key: str) -> None:
        await self._client.delete(self._key(key))

    async def get_ttl(self, key: str) -> int | None:
        ttl = await self._client.ttl(self._key(key))
        if ttl < 0:
            return None
        return ttl

    # --- Counter ---

    async def increment(self, key: str, amount: int = 1) -> int:
        return await self._client.incrby(self._key(key), amount)

    # --- Set ---

    async def sadd(self, key: str, *members: str, ttl: int | None = None) -> int:
        rk = self._key(key)
        added = await self._client.sadd(rk, *members)
        if ttl is not None:
            await self._client.expire(rk, ttl)
        return added

    async def sismember(self, key: str, member: str) -> bool:
        return bool(await self._client.sismember(self._key(key), member))

    async def smembers(self, key: str) -> set[str]:
        result = await self._client.smembers(self._key(key))
        return set(result) if result else set()

    async def srem(self, key: str, *members: str) -> int:
        return await self._client.srem(self._key(key), *members)

    # --- List ---

    async def lpush(self, key: str, value: Any, *, ttl: int | None = None) -> int:
        rk = self._key(key)
        serialized = json.dumps(value)
        length = await self._client.lpush(rk, serialized)
        if ttl is not None:
            await self._client.expire(rk, ttl)
        return length

    async def lrange(self, key: str, start: int, stop: int) -> list:
        rk = self._key(key)
        raw = await self._client.lrange(rk, start, stop)
        result = []
        for item in raw:
            try:
                result.append(json.loads(item))
            except (json.JSONDecodeError, TypeError):
                result.append(item)
        return result

    async def ltrim(self, key: str, start: int, stop: int) -> None:
        await self._client.ltrim(self._key(key), start, stop)

    # --- Lifecycle ---

    async def clear(self) -> None:
        """Delete all keys with this cache's prefix. Safe for shared Redis."""
        if not self._prefix:
            # No prefix = delete everything (single-app Redis, backward compat)
            await self._client.flushdb()
            return
        cursor = 0
        pattern = f"{self._prefix}*"
        while True:
            cursor, batch = await self._client.scan(cursor, match=pattern, count=100)
            if batch:
                await self._client.delete(*batch)
            if cursor == 0:
                break
```

- [ ] **Step 6: Create `keys.py` — key prefix constants**

```python
# server/packages/core/cache/keys.py
"""Key prefix constants for the unified Cache.

Callers construct keys as ``f"{RATE_LIMIT}:{scope}:{key}"``.
"""

RATE_LIMIT = "ratelimit"
CAPTCHA = "captcha"
FAM_SETTING = "famsetting"
AGENT_REG = "agentreg"
FX_RATE = "fxrate"
SEC_EVENT = "secevent"
SEC_SUSPECT = "secsuspect"
SEC_COUNTER = "seccounter"
```

- [ ] **Step 7: Create `factory.py` — init/get/reset**

```python
# server/packages/core/cache/factory.py
"""Cache factory — singleton lifecycle management."""

from packages.core.cache.base import Cache
from packages.core.cache.memory import MemoryCache
from packages.core.cache.redis import RedisCache

import redis.asyncio as aioredis

from packages.core.logging import get_logger

logger = get_logger(__name__)

_instance: Cache | None = None


def init_cache(backend: str = "memory", *, redis_url: str = "", prefix: str = "") -> Cache:
    """Create the global Cache singleton.

    Args:
        backend: ``"memory"`` or ``"redis"``.
        redis_url: Redis connection URL (required when ``backend="redis"``).
        prefix: Key prefix for namespace isolation in shared Redis.

    Returns:
        The newly created Cache instance.

    Raises:
        RuntimeError: If ``backend="redis"`` but connection fails.
    """
    global _instance

    if backend == "redis":
        if not redis_url:
            raise RuntimeError("CACHE_BACKEND=redis requires REDIS_URL")
        client = aioredis.from_url(redis_url, decode_responses=True, max_connections=10)
        _instance = RedisCache(client, prefix=prefix)
        logger.info("Cache initialized: redis (prefix=%r)", prefix)
    else:
        _instance = MemoryCache()
        logger.info("Cache initialized: memory")

    return _instance


def get_cache() -> Cache:
    """Return the global Cache singleton.

    Raises:
        RuntimeError: If ``init_cache()`` has not been called.
    """
    if _instance is None:
        raise RuntimeError("Cache not initialized — call init_cache() first")
    return _instance


def reset_cache() -> None:
    """Reset the singleton (for testing)."""
    global _instance
    _instance = None
```

- [ ] **Step 8: Create `__init__.py` — public exports**

```python
# server/packages/core/cache/__init__.py
"""Unified cache abstraction — memory/redis dual implementation."""

from packages.core.cache.base import Cache
from packages.core.cache.factory import get_cache, init_cache, reset_cache
from packages.core.cache.memory import MemoryCache
from packages.core.cache.redis import RedisCache

__all__ = [
    "Cache",
    "MemoryCache",
    "RedisCache",
    "init_cache",
    "get_cache",
    "reset_cache",
]
```

- [ ] **Step 9: Run tests to verify they pass**

Run: `cd server && uv run pytest tests/packages/core/test_cache.py -v`
Expected: All PASS

If `asyncio_mode` is not set for core tests, add to `server/pyproject.toml` under `[tool.pytest.ini_options]`:
```toml
# Check if asyncio is already configured; if not, add:
# asyncio_mode = "auto" is already set for agent tests
# For core tests, check if conftest or pyproject already configures it
```

If the test runner doesn't support `async def test_*` natively, check `pyproject.toml` for `asyncio_mode` and adjust accordingly. The existing `pyproject.toml` should have `asyncio_mode = "auto"` since agent tests use it.

- [ ] **Step 10: Run lint and type check**

Run: `cd server && uv run ruff check packages/core/cache/ && uv run ruff format packages/core/cache/`
Run: `cd server && uv run mypy packages/core/cache/ --explicit-package-bases`
Expected: No errors

- [ ] **Step 11: Commit**

```bash
git add packages/core/cache/ tests/packages/core/test_cache.py
git commit -m "feat(cache): add unified Cache abstraction to packages/core

- Cache ABC with Value/Counter/Set/List operations (async interface)
- MemoryCache: process-local dict-based implementation
- RedisCache: redis.asyncio implementation with prefix-scoped clear()
- Factory: init_cache()/get_cache()/reset_cache() singleton pattern
- Key prefix constants in keys.py

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: Backend Consumer Migration

**Files:**
- Modify: `server/apps/backend/app/main.py` (lifespan: add `init_cache()` call)
- Modify: `server/apps/backend/app/middleware/rate_limit.py` (use `get_cache()`, remove `_rate_store`)
- Modify: `server/apps/backend/app/services/auth.py` (replace `get_rate_limit_cache()` → `get_cache()`)
- Modify: `server/apps/backend/app/auth/captcha.py` (replace `get_captcha_payload_cache()` → `get_cache()`)
- Modify: `server/apps/backend/app/routers/device.py` (replace `get_rate_limit_cache()` → `get_cache()`)
- Modify: `server/apps/backend/app/routers/shared.py` (replace `get_rate_limit_cache()` → `get_cache()`)
- Modify: `server/apps/backend/app/services/config_service.py` (replace `_family_setting_cache` → `get_cache()`)
- Modify: `server/apps/backend/app/services/security_monitoring.py` (replace `InMemorySecurityStore` → `get_cache()`)
- Modify: `server/apps/backend/app/routers/ai_report.py` (await `get_family_setting_cached`)
- Modify: `server/apps/backend/app/services/finance_coach_cache.py` (await `get_family_setting_cached`)

**Interfaces:**
- Consumes: `packages.core.cache.get_cache`, `packages.core.cache.init_cache`, `packages.core.cache.keys.*`
- Produces: All backend cache access goes through `get_cache()` with key prefixes from `keys.py`

- [ ] **Step 1: Add `init_cache()` to backend lifespan**

In `server/apps/backend/app/main.py`, add near the top of the `lifespan()` function (after logging setup, before DB operations):

```python
# In lifespan(), after setup_logging():
from packages.core.cache import init_cache

cache = init_cache(
    backend=settings.CACHE_BACKEND,
    redis_url=settings.REDIS_URL,
    prefix="backend:",
)
app.state.cache = cache
```

Also add Redis connection check when `CACHE_BACKEND=redis`:

```python
if settings.CACHE_BACKEND == "redis":
    from packages.core.cache import _check_redis_connection  # add to factory.py
    await _check_redis_connection(settings.REDIS_URL)
```

Add `_check_redis_connection` to `factory.py`:

```python
async def _check_redis_connection(redis_url: str) -> None:
    """Verify Redis connectivity at startup. Only called when CACHE_BACKEND=redis."""
    try:
        import redis.asyncio as aioredis
        r = aioredis.from_url(redis_url)
        await r.ping()
        await r.aclose()
    except Exception as e:
        raise RuntimeError(f"Redis connection failed: {e}") from e
```

- [ ] **Step 2: Migrate `middleware/rate_limit.py`**

Replace the class-level `_rate_store` dict with `get_cache()`. Key changes:

```python
# Remove:
_rate_store: dict[str, tuple[int, float]] = {}

# In _check_rate_limit (rename to async _check_rate_limit_async):
async def _check_rate_limit(self, client_id: str) -> bool:
    from packages.core.cache import get_cache
    from packages.core.cache.keys import RATE_LIMIT

    cache = get_cache()
    key = f"{RATE_LIMIT}:global:{client_id}"
    count = await cache.increment(key)
    if count == 1:
        # First request in window — set TTL
        await cache.set(key, count, ttl=60)
    limit = settings.GLOBAL_RATE_LIMIT_PER_MINUTE
    return count <= limit
```

In `dispatch()`, change `self._check_rate_limit(client_id)` to `await self._check_rate_limit_async(client_id)`.

Note: This changes the algorithm from sliding-window to fixed-window. See spec §5.1 for trade-off discussion.

- [ ] **Step 3: Migrate `services/auth.py`**

Replace all occurrences of:
```python
from apps.backend.app.services.cache.factory import get_rate_limit_cache
cache = get_rate_limit_cache()
```

With:
```python
from packages.core.cache import get_cache
from packages.core.cache.keys import RATE_LIMIT
cache = get_cache()
```

And update all cache operations to use `await` and key prefixes. There are 8 call sites in `auth.py` (lines 110-321). Each follows the same pattern:

```python
# Before (sync):
cache = get_rate_limit_cache()
cache_key = f"login_rate:{ip}"
count = cache.get(cache_key) or 0
if count >= max_attempts:
    ...
cache.set(cache_key, count + 1, ttl_seconds=lockout_seconds)

# After (async):
cache = get_cache()
cache_key = f"{RATE_LIMIT}:login:{ip}"
count = await cache.get(cache_key) or 0
if count >= max_attempts:
    ...
await cache.set(cache_key, count + 1, ttl=lockout_seconds)
```

All auth functions that call the cache are already `async def`, so no signature changes needed — just add `await` and update import paths.

- [ ] **Step 4: Migrate `auth/captcha.py`**

Replace:
```python
from apps.backend.app.services.cache import get_captcha_payload_cache
cache = get_captcha_payload_cache()
cache.get(cache_key)
cache.set(cache_key, "1", ttl_seconds=3600)
```

With:
```python
from packages.core.cache import get_cache
from packages.core.cache.keys import CAPTCHA
cache = get_cache()
await cache.get(f"{CAPTCHA}:{cache_key}")
await cache.set(f"{CAPTCHA}:{cache_key}", "1", ttl=3600)
```

The `verify_captcha` function is already `async def`, so `await` works naturally.

- [ ] **Step 5: Migrate `routers/device.py` and `routers/shared.py`**

Both files import `get_rate_limit_cache` from the old factory. Replace with:
```python
from packages.core.cache import get_cache
from packages.core.cache.keys import RATE_LIMIT
cache = get_cache()
```

Update cache operations to use `await` and key prefixes.

- [ ] **Step 6: Migrate `config_service.py` — family setting cache**

Replace the inline `_family_setting_cache` dict with `get_cache()`:

```python
# Remove:
_family_setting_cache: dict[tuple[int, str], tuple[float, Any]] = {}
_cache_lock = threading.Lock()

# Replace get_family_setting_cached with async version:
async def get_family_setting_cached(family_id: int, key: str) -> Any:
    from packages.core.cache import get_cache
    from packages.core.cache.keys import FAM_SETTING

    cache = get_cache()
    cache_key = f"{FAM_SETTING}:{family_id}:{key}"
    value = await cache.get(cache_key)
    if value is not None:
        return value

    # Cache miss — read from DB
    from apps.backend.app.database import SessionLocal
    db = SessionLocal()
    try:
        value = get_family_setting(db, family_id, key)
    finally:
        db.close()

    await cache.set(cache_key, value, ttl=_CACHE_TTL_SECONDS)
    return value
```

Update callers to `await`:
- `routers/ai_report.py` — already in async handler, add `await`
- `services/finance_coach_cache.py` — check if the calling function is async; if sync, convert to async

Update `_invalidate_family_cache` to use cache:
```python
async def _invalidate_family_cache(family_id: int) -> None:
    from packages.core.cache import get_cache
    from packages.core.cache.keys import FAM_SETTING
    cache = get_cache()
    # Scan for keys matching this family (memory mode: iterate; redis: SCAN)
    # For simplicity, delete known patterns or use a different invalidation strategy
    # Since we know the key pattern: f"{FAM_SETTING}:{family_id}:*"
    # In memory mode, we need to iterate _expire_at or _store keys
    # For both modes, use cache-level scan or accept that TTL will expire stale entries
```

**Important**: The `_invalidate_family_cache` function is called from `set_family_setting` (sync context). It needs to become async, and its caller needs to await it. Check the call chain and convert as needed.

- [ ] **Step 7: Migrate `security_monitoring.py` — replace `InMemorySecurityStore`**

Replace `InMemorySecurityStore` with `get_cache()` operations:

```python
class SecurityMonitor:
    def __init__(self):
        # Remove: self._store = InMemorySecurityStore()
        self.event_buffer: list[SecurityEvent] = []
        self.alert_handlers: list[Callable[[dict], Any]] = []

    async def _store_event(self, event: SecurityEvent):
        from packages.core.cache import get_cache
        from packages.core.cache.keys import SEC_EVENT

        cache = get_cache()
        event_data = {
            "timestamp": event.timestamp.isoformat(),
            "level": event.threat_level.value,
            "ip": event.client_ip,
            "path": event.path,
            "details": event.details,
        }
        key = f"{SEC_EVENT}:{event.threat_type.value}"
        await cache.lpush(key, event_data, ttl=86400)  # 24h TTL

    async def _check_threat(self, event: SecurityEvent):
        from packages.core.cache import get_cache
        from packages.core.cache.keys import SEC_SUSPECT

        cache = get_cache()
        if await cache.sismember(f"{SEC_SUSPECT}:global", event.client_ip):
            if event.threat_level in [ThreatLevel.HIGH, ThreatLevel.CRITICAL]:
                await self._trigger_alert(event)
            return

        threat_detected = await self._analyze_pattern(event)
        if threat_detected:
            await cache.sadd(f"{SEC_SUSPECT}:global", event.client_ip)
            await self._trigger_alert(event)

    async def _analyze_pattern(self, event: SecurityEvent) -> bool:
        from packages.core.cache import get_cache
        from packages.core.cache.keys import SEC_COUNTER

        cache = get_cache()
        if event.threat_type == ThreatType.RATE_LIMIT_EXCEEDED:
            key = f"{SEC_COUNTER}:rate_violations:{event.client_ip}"
            count = await cache.increment(key)
            if count == 1:
                await cache.set(key, count, ttl=300)
            threshold = self.THRESHOLDS["rate_limit_violations"]
            if count >= threshold["count"]:
                return True

        key = f"{SEC_COUNTER}:suspicious_count:{event.client_ip}"
        count = await cache.increment(key)
        if count == 1:
            await cache.set(key, count, ttl=300)
        return bool(count >= self.THRESHOLDS["suspicious_requests"]["count"])
```

Delete the `InMemorySecurityStore` class entirely. `SecurityMonitor` no longer needs `threading.Lock` since `Cache` is async-safe.

- [ ] **Step 8: Run backend tests to verify**

Run: `cd server && uv run pytest tests/backend/test_cache.py tests/backend/test_auth_security.py tests/backend/test_device_auth.py tests/backend/test_captcha.py tests/backend/test_family.py tests/backend/test_family_settings.py -v`

Note: Tests will still import from old paths — they'll fail until Task 3 updates them. At this stage, run a broader test to check that non-cache tests still pass:

Run: `cd server && uv run pytest tests/backend/ -v --ignore=tests/backend/test_cache.py -x`
Expected: Existing tests pass (with updated imports if you've already changed them).

- [ ] **Step 9: Commit**

```bash
git add -A
git commit -m "feat(cache): migrate all backend consumers to unified Cache

- Backend lifespan: init_cache() with CACHE_BACKEND/REDIS_URL
- Rate limit middleware: get_cache() + fixed-window algorithm
- Auth rate limits: get_cache() with await + key prefixes
- Captcha replay: get_cache() with CAPTCHA prefix
- Family setting cache: get_cache() replacing inline dict
- Security monitoring: get_cache() replacing InMemorySecurityStore
- Key prefixes from keys.py prevent cross-purpose collision

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: Delete Old Cache Module + Test Import Updates

**Files:**
- Delete: `server/apps/backend/app/services/cache/` (entire directory: `__init__.py`, `base.py`, `memory.py`, `redis.py`, `factory.py`)
- Modify: `server/tests/backend/test_cache.py` — rewrite to import from `packages.core.cache`
- Modify: `server/tests/backend/test_auth_security.py` — update imports
- Modify: `server/tests/backend/test_device_auth.py` — update imports
- Modify: `server/tests/backend/test_captcha.py` — update imports
- Modify: `server/tests/backend/test_family.py` — update imports
- Modify: `server/tests/backend/test_cache_config.py` — update imports (if exists)
- Modify: `server/tests/backend/conftest.py` — update cache reset calls

**Interfaces:**
- Consumes: `packages.core.cache.*` (new module from Task 1)
- Produces: No remaining imports of `apps.backend.app.services.cache.*`

- [ ] **Step 1: Delete the old cache module**

```bash
rm -rf server/apps/backend/app/services/cache/
```

- [ ] **Step 2: Verify no remaining imports of old module**

Run: `cd server && grep -rn "from apps.backend.app.services.cache" --include="*.py" | grep -v __pycache__ | grep -v test`
Expected: No results (all production code migrated in Task 2)

- [ ] **Step 3: Update `conftest.py` — replace old reset functions**

Replace:
```python
from apps.backend.app.services.cache import (
    reset_captcha_payload_cache,
    reset_rate_limit_cache,
)
```

With:
```python
from packages.core.cache import reset_cache
```

Replace all calls to `reset_rate_limit_cache()` and `reset_captcha_payload_cache()` with `reset_cache()`.

Also remove the `RateLimitMiddleware._rate_store` cleanup (it no longer exists):
```python
# Remove:
if hasattr(RateLimitMiddleware, "_rate_store"):
    RateLimitMiddleware._rate_store.clear()
```

- [ ] **Step 4: Update `test_cache.py` — rewrite for new module**

The existing `test_cache.py` tests `MemoryCacheBackend`, `RedisCacheBackend`, and the old factory. Since Task 1 already created comprehensive tests in `tests/packages/core/test_cache.py`, this file should be simplified to:
- Test that backend-specific integration works (if any backend-specific test logic exists)
- Or be deleted entirely if Task 1's tests cover everything

Recommended: Delete `test_cache.py` content and replace with a thin re-export or delete the file.

```python
# server/tests/backend/test_cache.py
"""Backend cache integration — core tests live in tests/packages/core/test_cache.py."""

# All cache abstraction tests are in tests/packages/core/test_cache.py.
# This file is retained for backend-specific integration tests if needed.
```

- [ ] **Step 5: Update `test_auth_security.py` — update cache imports**

Replace all occurrences of:
```python
from apps.backend.app.services.cache.factory import get_rate_limit_cache
cache = get_rate_limit_cache()
```

With:
```python
from packages.core.cache import get_cache
from packages.core.cache.keys import RATE_LIMIT
cache = get_cache()
```

And update all cache operations to use `await` and key prefixes. Since these are in test functions (which may be sync), use `asyncio.get_event_loop().run_until_complete()` or convert the test functions to `async def`.

- [ ] **Step 6: Update `test_captcha.py` — update cache imports**

Replace:
```python
from apps.backend.app.services.cache import get_captcha_payload_cache
```

With:
```python
from packages.core.cache import get_cache
```

Update all `cache.get()`/`cache.set()` calls to use `await` and key prefixes.

- [ ] **Step 7: Update `test_device_auth.py` and `test_family.py`**

Same pattern: replace `get_rate_limit_cache` → `get_cache()`, add `await`, use key prefixes.

- [ ] **Step 8: Run all backend tests**

Run: `cd server && uv run pytest tests/backend/ -v -x`
Expected: All PASS

- [ ] **Step 9: Run lint and type check**

Run: `cd server && uv run ruff check apps/backend/ --fix && uv run ruff format apps/backend/`
Run: `cd server && uv run ruff check tests/backend/ --fix && uv run ruff format tests/backend/`

- [ ] **Step 10: Commit**

```bash
git add -A
git commit -m "refactor(cache): delete old backend cache module, update test imports

- Remove server/apps/backend/app/services/cache/ entirely
- Update conftest.py: reset_cache() replaces per-purpose reset functions
- Update test_cache.py, test_auth_security.py, test_device_auth.py,
  test_captcha.py, test_family.py: import from packages.core.cache

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 4: Agent Registry Migration

**Files:**
- Modify: `server/apps/agent/services/agent_registry.py` — use `get_cache()` instead of inline dict
- Modify: `server/apps/agent/app/main.py` — add `init_cache()` in lifespan

**Interfaces:**
- Consumes: `packages.core.cache.get_cache`, `packages.core.cache.init_cache`, `packages.core.cache.keys.AGENT_REG`
- Produces: `AgentRegistry.get()` uses cache for storage; HTTP invalidation path still works (for memory mode compatibility)

- [ ] **Step 1: Write failing test for agent registry cache behavior**

In the existing agent test file (or create `server/tests/agent/unit/test_agent_registry_cache.py`):

```python
"""Test AgentRegistry uses unified Cache."""

import pytest
from unittest.mock import AsyncMock, patch

from packages.core.cache import init_cache, reset_cache, get_cache
from packages.core.cache.memory import MemoryCache


class TestAgentRegistryWithCache:
    async def test_registry_uses_cache(self):
        """AgentRegistry should store/retrieve from unified Cache."""
        reset_cache()
        cache = init_cache(backend="memory")

        from apps.agent.services.agent_registry import AgentRegistry
        registry = AgentRegistry()

        # Mock backend client to return agent data
        with patch.object(registry, '_fetch_agent', new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = {"name": "test-agent", "memory_enabled": True}
            result = await registry.get("test-agent", "123")
            assert result is not None

        reset_cache()
```

- [ ] **Step 2: Add `init_cache()` to agent lifespan**

In `server/apps/agent/app/main.py`, add to `lifespan()`:

```python
from packages.core.cache import init_cache

cache = init_cache(
    backend=settings.CACHE_BACKEND,
    redis_url=settings.REDIS_URL,
    prefix="agent:",
)
app.state.cache = cache
```

Note: Agent's `settings` is `AgentSettings` from `apps.agent.app.config`. Check if it inherits `CACHE_BACKEND`/`REDIS_URL` from `packages.core.settings` or needs its own config. If `AgentSettings` extends `Settings`, the fields are inherited.

- [ ] **Step 3: Migrate `agent_registry.py`**

The current `AgentRegistry` uses an inline `dict` with per-key locks and negative caching. Migrate to use `get_cache()`:

```python
class AgentRegistry:
    """Async singleton caching agent attributes by (family_id, agent_name)."""

    async def get(self, agent_name: str, family_id: str) -> dict | None:
        from packages.core.cache import get_cache
        from packages.core.cache.keys import AGENT_REG

        cache = get_cache()
        key = f"{AGENT_REG}:{family_id}:{agent_name}"

        cached = await cache.get(key)
        if cached is not None:
            return cached

        # Cache miss — fetch from backend
        try:
            client = BackendClient(family_id=family_id)
            agent = await client.get_agent_by_name(agent_name)
            if agent:
                await cache.set(key, agent, ttl=300)  # 5min TTL
                logger.info(
                    "[AgentRegistry] cached agent %s family=%s memory_enabled=%s",
                    agent_name, family_id, agent.get("memory_enabled"),
                )
                return agent
            return None
        except Exception as exc:
            # Negative cache: short TTL to avoid pinning stale fallback
            await cache.set(key, None, ttl=_NEGATIVE_CACHE_TTL_SECONDS)
            logger.warning(
                "[AgentRegistry] lookup failed agent=%s family=%s: %s — "
                "falling back to defaults (memory_enabled=True, TTL=%ss)",
                agent_name, family_id, type(exc).__name__,
                int(_NEGATIVE_CACHE_TTL_SECONDS),
            )
            return None

    async def invalidate(self, family_id: str | None = None, agent_name: str | None = None) -> None:
        """Drop cached entries. Called when agent attributes change."""
        from packages.core.cache import get_cache
        from packages.core.cache.keys import AGENT_REG

        cache = get_cache()
        if family_id is None and agent_name is None:
            await cache.clear()  # Note: in prefix mode, this only clears agent: prefix
            return
        # For specific invalidation, construct the key
        if family_id is not None and agent_name is not None:
            key = f"{AGENT_REG}:{family_id}:{agent_name}"
            await cache.delete(key)
        # For partial keys (only family_id or only agent_name), we'd need SCAN
        # In memory mode, iterate. In redis mode, use SCAN with pattern.
```

**Important**: The `invalidate` method is currently sync. Converting to async means the cache invalidation endpoint (`POST /internal/cache/invalidate/{family_id}`) must also be async. Check if it already is.

- [ ] **Step 4: Run agent tests**

Run: `cd server && uv run pytest tests/agent/ -v -x --exclude vendor`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "feat(cache): migrate agent registry to unified Cache

- AgentRegistry uses get_cache() with AGENT_REG prefix instead of inline dict
- Agent lifespan calls init_cache() with prefix="agent:"
- Negative caching via short TTL on None values
- Invalidation via cache.delete() per key

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 5: Scheduler Worker Exchange Rate Migration

**Files:**
- Modify: `server/packages/db/exchange_rate_adapter.py` — use `get_cache()` instead of inline dict
- Modify: `server/apps/scheduler_worker/main.py` — add `init_cache()` in lifespan

**Interfaces:**
- Consumes: `packages.core.cache.get_cache`, `packages.core.cache.init_cache`, `packages.core.cache.keys.FX_RATE`
- Produces: `ExchangeRateAdapter` uses `get_cache()` for rate caching

- [ ] **Step 1: Add `init_cache()` to scheduler worker lifespan**

In `server/apps/scheduler_worker/main.py`:

```python
from packages.core.cache import init_cache

cache = init_cache(
    backend=settings.CACHE_BACKEND,
    redis_url=settings.REDIS_URL,
    prefix="scheduler:",
)
app.state.cache = cache
```

- [ ] **Step 2: Migrate `exchange_rate_adapter.py`**

Replace the inline `_cache` dict with `get_cache()`:

```python
class ExchangeRateAdapter:
    def __init__(self) -> None:
        # Remove: self._cache = {}
        # Remove: self._lock = threading.Lock()
        pass

    async def get_cached_rate(self, currency: str) -> tuple[float | None, datetime | None]:
        if currency == "CNY":
            return (1.0, datetime.now(UTC))

        from packages.core.cache import get_cache
        from packages.core.cache.keys import FX_RATE

        cache = get_cache()
        key = f"{FX_RATE}:{currency}"
        cached = await cache.get(key)
        if cached is not None:
            rate, fetched_at = cached
            return (rate, fetched_at)
        return (None, None)

    async def populate_cache(self, currency: str, rate: float, fetched_at: datetime) -> None:
        from packages.core.cache import get_cache
        from packages.core.cache.keys import FX_RATE

        cache = get_cache()
        key = f"{FX_RATE}:{currency}"
        await cache.set(key, (rate, fetched_at.isoformat()), ttl=int(_CACHE_TTL.total_seconds()))

    def fetch_and_store_rates(self, db: Session) -> bool:
        # This method is sync (called from sync job context).
        # It clears the in-memory cache after storing. With unified cache,
        # we clear FX_RATE keys. Since this is sync and cache is async,
        # we need to handle this carefully.
        # Option: use asyncio.get_event_loop().run_until_complete() in sync context
        # Or: convert the job to async
        ...
```

**Important consideration**: `fetch_and_store_rates` is currently sync (called from `fetch_rates_job`). The scheduler job `fetch_rates_job` is also sync. The `ExchangeRateAdapter.get_cached_rate` is called from domain services. Check if those callers are sync or async.

If callers are sync, either:
1. Convert them to async (preferred)
2. Use `asyncio.run()` wrapper (less clean but works for sync→async bridge)

Check the call chain from `fetch_rates_job` and domain services to determine the conversion path.

- [ ] **Step 3: Run scheduler worker tests**

Run: `cd server && uv run pytest tests/scheduler_worker/ -v`
Run: `cd server && uv run pytest tests/packages/db/ -v`
Expected: All PASS

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "feat(cache): migrate exchange rate adapter to unified Cache

- ExchangeRateAdapter uses get_cache() with FX_RATE prefix
- Scheduler worker lifespan calls init_cache() with prefix="scheduler:"
- 4h TTL matches existing behavior

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

### Task 6: Full Suite Verification + Cleanup

**Files:**
- Verify: all test suites pass
- Verify: no remaining imports of old cache module
- Verify: lint + type check clean

- [ ] **Step 1: Run full test suite**

```bash
cd server && uv run pytest tests/ -v
```

Expected: All PASS across backend, agent, scheduler_worker, and packages tests.

- [ ] **Step 2: Verify no old imports remain**

```bash
cd server && grep -rn "from apps.backend.app.services.cache" --include="*.py" | grep -v __pycache__
cd server && grep -rn "CacheBackend\|MemoryCacheBackend\|RedisCacheBackend" --include="*.py" | grep -v __pycache__
```

Expected: No results.

- [ ] **Step 3: Run lint and type check on all modules**

```bash
cd server && uv run ruff check packages/core/cache/ apps/backend/ apps/agent/ apps/scheduler_worker/ packages/db/
cd server && uv run ruff format --check packages/core/cache/ apps/backend/ apps/agent/ apps/scheduler_worker/ packages/db/
cd server && uv run mypy packages/core/cache/ --explicit-package-bases
```

- [ ] **Step 4: Run docker-compose build to verify Docker image**

```bash
docker-compose build --no-cache 2>&1 | tail -20
```

Expected: Build succeeds without import errors.

- [ ] **Step 5: Final commit (if any cleanup needed)**

```bash
git add -A
git commit -m "chore(cache): final cleanup after unified cache migration

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

## Task Dependency Summary

```
Task 1 (Core Cache Module)
    ↓
Task 2 (Backend Consumer Migration)
    ↓
Task 3 (Delete Old Module + Test Updates)
    ↓
Task 4 (Agent Registry) ──┐
    ↓                      │
Task 5 (Scheduler Worker) ─┤
    ↓                      ↓
Task 6 (Full Verification)
```

Tasks 4 and 5 are independent of each other but both depend on Task 1. Task 3 depends on Task 2 (must delete old module only after all consumers are migrated).
