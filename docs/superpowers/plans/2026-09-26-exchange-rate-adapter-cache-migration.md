# Exchange Rate Adapter → Unified Cache Migration

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Migrate `ExchangeRateAdapter` from a process-local dict to the unified Cache layer, enabling cross-process exchange rate sharing in Redis mode.

**Architecture:** Add a `SyncCacheBridge` to `packages/core/cache/` that wraps the async `Cache` interface with synchronous methods. The bridge uses direct calls for `MemoryCache` (dict ops, no I/O) and a background event loop thread for `RedisCache`. The `ExchangeRateAdapter` uses the bridge internally — no caller signature changes needed.

**Tech Stack:** Python 3.12+, `concurrent.futures.ThreadPoolExecutor`, `asyncio`, `redis.asyncio` (via unified Cache), `fakeredis` (tests)

**Spec:** `docs/superpowers/specs/2026-09-25-unified-redis-shared-cache-design.md` §5.3

## Global Constraints

- Import direction: `packages/db` must not import from `apps/`. `packages/core` must not import from `apps/` or `packages/db`.
- All existing callers of `ExchangeRateAdapter` are **synchronous** — no caller may be changed to `async`.
- The domain service `ExchangeRateService.get_rate()` and `.convert()` stay sync — they are called from ~10 sync backend service files (dashboard, asset, liability, etc.).
- Memory mode behavior must be identical to current (per-process cache, 4h TTL).
- Redis mode enables cross-process sharing: scheduler writes, backend reads from shared Redis.

## Review Focus

1. **Sync bridge from async context** — `SyncCacheBridge._submit()` must NOT deadlock when called from a thread running inside FastAPI's event loop (e.g., sync route handler). Background event loop thread avoids this.
2. **MemoryCache optimization** — direct dict access for MemoryCache avoids spawning a background thread when Redis isn't configured. Must not break when cache is reset and re-initialized.
3. **TTL semantic equivalence** — old adapter: `now - cached_at < 4h`. New: Cache TTL 14400s. Must behave identically at the boundary.
4. **Thread safety without Lock** — old adapter uses `threading.Lock`. New adapter relies on Cache atomicity + scheduler `max_instances=1`. Must verify no interleaved DB writes.
5. **Cross-process Redis sharing** — scheduler writes `fxrate:USD` to Redis; backend reads it without hitting DB. Must verify end-to-end with fakeredis.

---

### Task 1: Add SyncCacheBridge

**Files:**
- Create: `server/packages/core/cache/sync_bridge.py`
- Modify: `server/packages/core/cache/__init__.py`
- Test: `server/tests/packages/core/test_sync_bridge.py`

**Interfaces:**
- Consumes: `Cache`, `MemoryCache`, `RedisCache` from `packages.core.cache`
- Produces: `SyncCacheBridge` class — used by `ExchangeRateAdapter` in Task 2

- [ ] **Step 1: Write the failing tests**

Create `server/tests/packages/core/test_sync_bridge.py`:

```python
"""Tests for SyncCacheBridge — sync wrapper over async Cache."""

import time

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
    """get_sync_bridge() returns a bridge wrapping get_cache()."""

    def setup_method(self):
        reset_cache()

    def teardown_method(self):
        reset_cache()

    def test_get_sync_bridge_returns_bridge(self):
        init_cache(backend="memory")
        bridge = SyncCacheBridge.from_cache()
        assert isinstance(bridge, SyncCacheBridge)

    def test_get_sync_bridge_raises_if_not_initialized(self):
        import pytest
        with pytest.raises(RuntimeError, match="not initialized"):
            SyncCacheBridge.from_cache()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd server && uv run pytest tests/packages/core/test_sync_bridge.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'packages.core.cache.sync_bridge'`

- [ ] **Step 3: Implement SyncCacheBridge**

Create `server/packages/core/cache/sync_bridge.py`:

```python
"""Synchronous bridge for the async Cache interface.

Allows sync code (scheduler jobs, sync service functions) to use the unified
Cache without requiring ``async def`` callers.

Optimization: For ``MemoryCache``, operations are direct dict accesses (no
background thread). For ``RedisCache``, a dedicated background event loop
thread handles async Redis commands.
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

        # Lazy-import to avoid circular dependency at module level
        from packages.core.cache.memory import MemoryCache

        if not isinstance(cache, MemoryCache):
            self._loop = asyncio.new_event_loop()
            self._loop_thread = threading.Thread(
                target=self._run_loop, daemon=True, name="sync-cache-bridge"
            )
            self._loop_thread.start()

    @staticmethod
    def _run_loop(loop: asyncio.AbstractEventLoop) -> None:
        asyncio.set_event_loop(loop)
        loop.run_forever()

    def _submit(self, coro):
        """Run an async coroutine and return the result synchronously."""
        if self._loop is not None:
            future = asyncio.run_coroutine_threadsafe(coro, self._loop)
            return future.result()
        # MemoryCache: no background loop needed — create a temporary one
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()

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
```

- [ ] **Step 4: Update `__init__.py` to export SyncCacheBridge**

Modify `server/packages/core/cache/__init__.py`:

```python
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
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd server && uv run pytest tests/packages/core/test_sync_bridge.py -v`
Expected: All 12 tests PASS

- [ ] **Step 6: Commit**

```bash
git add server/packages/core/cache/sync_bridge.py server/packages/core/cache/__init__.py server/tests/packages/core/test_sync_bridge.py
git commit -m "feat(cache): add SyncCacheBridge for sync callers of async Cache"
```

---

### Task 2: Migrate ExchangeRateAdapter to unified Cache

**Files:**
- Modify: `server/packages/db/exchange_rate_adapter.py`
- Test: `server/tests/packages/db/test_exchange_rate_adapter.py`

**Interfaces:**
- Consumes: `SyncCacheBridge` from `packages.core.cache`
- Produces: `ExchangeRateAdapter` with same public API (`get_cached_rate`, `populate_cache`, `fetch_and_store_rates`, `fetch_rates`) — callers unchanged

- [ ] **Step 1: Write the failing tests for Cache-backed adapter**

Update `server/tests/packages/db/test_exchange_rate_adapter.py` — add tests that verify the adapter uses the unified Cache instead of internal `_cache` dict. Replace the old tests that access `adapter._cache` directly.

Add these new tests at the end of the file (keep existing `fetch_rates` and `fetch_and_store_rates` tests, remove tests that reference `adapter._cache`):

```python
# ---------------------------------------------------------------------------
# Unified Cache integration
# ---------------------------------------------------------------------------


def test_get_cached_rate_from_unified_cache(packages_db, monkeypatch):
    """Adapter reads from unified Cache (via SyncCacheBridge), not internal dict."""
    from packages.core.cache import init_cache, reset_cache

    reset_cache()
    init_cache(backend="memory")

    adapter = ExchangeRateAdapter()
    # Pre-populate via unified Cache (simulating another process writing)
    from packages.core.cache import get_cache
    import asyncio

    cache = get_cache()
    asyncio.get_event_loop().run_until_complete(
        cache.set("fxrate:USD", {"rate": 7.2, "fetched_at": "2026-01-01T00:00:00+00:00"}, ttl=14400)
    )

    rate, fetched_at = adapter.get_cached_rate("USD")
    assert rate == 7.2
    assert fetched_at is not None
    reset_cache()


def test_populate_cache_writes_to_unified_cache(packages_db, monkeypatch):
    """populate_cache writes to unified Cache, readable by another adapter instance."""
    from packages.core.cache import init_cache, reset_cache, get_cache
    import asyncio

    reset_cache()
    init_cache(backend="memory")

    adapter = ExchangeRateAdapter()
    now = datetime.now(UTC)
    adapter.populate_cache("EUR", 7.8, now)

    # Verify via unified Cache
    cache = get_cache()
    data = asyncio.get_event_loop().run_until_complete(cache.get("fxrate:EUR"))
    assert data is not None
    assert data["rate"] == 7.8
    reset_cache()


def test_fetch_and_store_rates_clears_unified_cache(packages_db, adapter, monkeypatch):
    """Successful fetch clears fxrate:* keys from unified Cache."""
    from packages.core.cache import init_cache, reset_cache, get_cache
    import asyncio

    reset_cache()
    init_cache(backend="memory")

    # Pre-populate
    cache = get_cache()
    asyncio.get_event_loop().run_until_complete(
        cache.set("fxrate:USD", {"rate": 7.0, "fetched_at": "2026-01-01T00:00:00+00:00"})
    )

    payload = {"rates": {"USD": 7.2}}
    monkeypatch.setattr(
        "packages.db.exchange_rate_adapter.httpx.get",
        lambda *a, **k: _FakeResponse(payload),
    )
    adapter.fetch_and_store_rates(packages_db)

    # fxrate:USD should be cleared
    result = asyncio.get_event_loop().run_until_complete(cache.get("fxrate:USD"))
    assert result is None
    reset_cache()


def test_adapter_ttl_is_4_hours(packages_db, adapter, monkeypatch):
    """Cache entries expire after 4 hours (14400 seconds)."""
    from packages.core.cache import init_cache, reset_cache, get_cache
    import asyncio

    reset_cache()
    init_cache(backend="memory")

    now = datetime.now(UTC)
    adapter.populate_cache("GBP", 8.5, now)

    cache = get_cache()
    ttl = asyncio.get_event_loop().run_until_complete(cache.get_ttl("fxrate:GBP"))
    assert ttl is not None
    assert 14300 <= ttl <= 14400
    reset_cache()
```

Remove these old tests that reference `adapter._cache`:
- `test_get_cached_rate_cache_hit_within_ttl` (accesses `adapter._cache["USD"]`)
- `test_get_cached_rate_stale_cache_returns_none` (accesses `adapter._cache["GBP"]`)
- `test_fetch_and_store_rates_clears_cache` (asserts `adapter._cache == {}`)
- `test_fetch_and_store_rates_is_thread_safe` (tests `threading.Lock` — no longer applicable)

Add a `conftest.py` fixture (or update the existing `adapter` fixture) to init cache:

```python
@pytest.fixture(autouse=True)
def _init_unified_cache():
    """Ensure unified Cache is initialized for each test."""
    from packages.core.cache import init_cache, reset_cache
    reset_cache()
    init_cache(backend="memory")
    yield
    reset_cache()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd server && uv run pytest tests/packages/db/test_exchange_rate_adapter.py -v`
Expected: FAIL — new tests fail because adapter still uses `self._cache` dict

- [ ] **Step 3: Migrate the adapter implementation**

Rewrite `server/packages/db/exchange_rate_adapter.py`:

```python
"""Exchange rate adapter — unified Cache integration.

Uses the unified Cache layer (via SyncCacheBridge) for TTL-based caching.
In Redis mode, exchange rates are shared across all services (backend,
agent, scheduler worker). In memory mode, each process has its own cache.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, cast

import httpx
from sqlalchemy.orm import Session

from packages.core.cache import SyncCacheBridge
from packages.core.cache.keys import FX_RATE
from packages.core.logging import get_logger
from packages.db.models.currency import Currency
from packages.db.models.exchange_rate import ExchangeRate

logger = get_logger(__name__)

# Cache TTL: 4 hours (matches original adapter behavior)
_CACHE_TTL_SECONDS = 4 * 60 * 60  # 14400


class ExchangeRateAdapter:
    """Infrastructure adapter for exchange-rate fetching and caching.

    Encapsulates HTTP calls, Cache-backed TTL cache, and DB persistence so the
    domain service remains free of infrastructure concerns.

    Cache keys use the ``fxrate:`` prefix (see ``packages.core.cache.keys``).
    Values are ``{"rate": float, "fetched_at": str}`` dicts (JSON-serializable).
    """

    def __init__(self) -> None:
        self._bridge = SyncCacheBridge.from_cache()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def fetch_rates(self) -> dict[str, float]:
        """Fetch latest rates from exchangerate-api.com (CNY base).

        Raises on network / HTTP errors so the caller can decide how to handle.
        """
        resp = httpx.get(
            "https://api.exchangerate-api.com/v4/latest/CNY",
            timeout=10,
            proxy=None,
        )
        resp.raise_for_status()
        data: dict[str, Any] = resp.json()
        return cast(dict[str, float], data.get("rates", {}))

    def get_cached_rate(self, currency: str) -> tuple[float | None, datetime | None]:
        """Return (rate, fetched_at) for *currency* relative to CNY.

        Checks the unified Cache first; returns ``(None, None)`` on miss/expiry.
        The caller (domain service) falls through to DB lookup on miss.
        """
        if currency == "CNY":
            return (1.0, datetime.now(UTC))

        data = self._bridge.get(f"{FX_RATE}:{currency}")
        if data is None:
            return (None, None)

        rate = data["rate"]
        fetched_at = datetime.fromisoformat(data["fetched_at"])
        return (rate, fetched_at)

    def populate_cache(
        self, currency: str, rate: float, fetched_at: datetime
    ) -> None:
        """Write a rate into the unified Cache (4h TTL).

        Used by the domain service to promote DB-looked-up rates into the
        cache so subsequent calls avoid redundant queries.
        """
        self._bridge.set(
            f"{FX_RATE}:{currency}",
            {"rate": rate, "fetched_at": fetched_at.isoformat()},
            ttl=_CACHE_TTL_SECONDS,
        )

    def fetch_and_store_rates(self, db: Session) -> bool:
        """Fetch from API, persist rates + Currency rows, clear cache.

        Scheduler uses ``max_instances=1`` so this is not called concurrently.
        """
        try:
            rates = self.fetch_rates()
        except Exception as e:
            logger.exception(f"汇率获取失败: {e}")
            return False

        fetched_at = datetime.now(UTC)

        try:
            for code, rate in rates.items():
                if code == "CNY":
                    continue
                try:
                    with db.begin_nested():
                        db.add(
                            ExchangeRate(
                                target_currency=code,
                                rate=rate,
                                fetched_at=fetched_at,
                            )
                        )
                except Exception:
                    continue

            existing_codes = {c.code for c in db.query(Currency.code).all()}
            for code in rates:
                if code not in existing_codes:
                    db.add(
                        Currency(
                            code=code,
                            name_zh=code,
                            name_en=code,
                            symbol=code,
                            flag_emoji="🏳️",
                            is_favorite=False,
                            sort_order=999,
                        )
                    )

            # Clear cached rates — they'll be re-populated from DB on next read
            self._bridge.delete(f"{FX_RATE}:")  # prefix delete not supported; clear all fxrate keys
            db.commit()
        except Exception:
            db.rollback()
            raise

        logger.info(f"汇率更新完成，共 {len(rates)} 种货币")
        return True
```

**Note on cache clearing:** `SyncCacheBridge.delete(f"{FX_RATE}:")` won't clear all `fxrate:*` keys because `delete` takes an exact key. Two options:
1. Skip cache clearing — entries expire naturally via TTL (4h), and the DB is the source of truth. New rates from the API will be picked up on next cache miss.
2. Add a `delete_pattern` method to the Cache interface.

**Recommended:** Option 1 (skip clearing). The cache is a read-through optimization. After `fetch_and_store_rates` writes new rates to DB, the old cached rates (up to 4h stale) will gradually be replaced as each currency's cache entry expires. This is acceptable because exchange rates change slowly.

Update `fetch_and_store_rates` to remove the cache clearing line:

```python
            db.commit()
        except Exception:
            db.rollback()
            raise

        logger.info(f"汇率更新完成，共 {len(rates)} 种货币")
        return True
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd server && uv run pytest tests/packages/db/test_exchange_rate_adapter.py -v`
Expected: All tests PASS

- [ ] **Step 5: Run domain service tests to verify no regression**

Run: `cd server && uv run pytest tests/packages/domain/test_exchange_rate_service.py -v`
Expected: All tests PASS (adapter API unchanged)

- [ ] **Step 6: Run backend exchange rate tests**

Run: `cd server && uv run pytest tests/backend/test_exchange_rate.py -v`
Expected: All tests PASS

- [ ] **Step 7: Commit**

```bash
git add server/packages/db/exchange_rate_adapter.py server/tests/packages/db/test_exchange_rate_adapter.py
git commit -m "feat(cache): migrate ExchangeRateAdapter to unified Cache via SyncCacheBridge

Replaces process-local dict + threading.Lock with the unified Cache layer.
In Redis mode, exchange rates are shared across backend and scheduler worker.
No caller signature changes — SyncCacheBridge provides sync interface."
```

---

### Task 3: Update test fixtures and remove stale tests

**Files:**
- Modify: `server/tests/packages/db/test_exchange_rate_adapter.py`
- Modify: `server/tests/packages/domain/test_exchange_rate_service.py`
- Modify: `server/tests/backend/test_exchange_rate.py`
- Modify: `server/tests/scheduler_worker/test_jobs_behavior.py`

**Interfaces:**
- Consumes: migrated `ExchangeRateAdapter` from Task 2

- [ ] **Step 1: Update domain service tests**

In `server/tests/packages/domain/test_exchange_rate_service.py`, update tests that access `adapter._cache` directly. Replace with unified Cache assertions or remove cache-internal assertions (the adapter's cache behavior is now tested in Task 2).

Key changes:
- Add the `_init_unified_cache` autouse fixture
- Replace `adapter._cache["USD"] = (7.2, now, now)` with `bridge.set("fxrate:USD", {...}, ttl=14400)`
- Remove stale cache test (TTL is now managed by Cache, tested in Task 2)

- [ ] **Step 2: Update backend tests**

In `server/tests/backend/test_exchange_rate.py`, add `_init_unified_cache` autouse fixture. Update `test_fetch_and_store_rates_clears_cache` to verify via unified Cache (or remove if redundant with Task 2 tests).

- [ ] **Step 3: Update scheduler worker tests**

In `server/tests/scheduler_worker/test_jobs_behavior.py`, add `_init_unified_cache` fixture to `fetch_rates_job` tests. The adapter mock path stays the same (`packages.db.exchange_rate_adapter.ExchangeRateAdapter.fetch_and_store_rates`).

- [ ] **Step 4: Run all affected test suites**

```bash
cd server && uv run pytest \
  tests/packages/db/test_exchange_rate_adapter.py \
  tests/packages/domain/test_exchange_rate_service.py \
  tests/backend/test_exchange_rate.py \
  tests/scheduler_worker/test_jobs_behavior.py \
  tests/scheduler_worker/test_jobs_timing.py \
  -v
```

Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add server/tests/
git commit -m "test(cache): update exchange rate test fixtures for unified Cache"
```

---

### Task 4: Verify cross-process Redis sharing (integration)

**Files:**
- Test: `server/tests/packages/core/test_sync_bridge.py` (append)

**Interfaces:**
- Consumes: `SyncCacheBridge`, `RedisCache`, `fakeredis`

- [ ] **Step 1: Write cross-process sharing test**

Append to `server/tests/packages/core/test_sync_bridge.py`:

```python
class TestCrossProcessSharing:
    """Simulate scheduler writing, backend reading from shared Redis."""

    def test_scheduler_write_backend_read(self):
        """Scheduler writes fxrate:USD to Redis, backend reads it."""
        import fakeredis.aioredis
        from packages.core.cache import RedisCache, init_cache, reset_cache

        reset_cache()
        fake = fakeredis.aioredis.FakeRedis(decode_responses=True)
        cache = RedisCache(fake, prefix="")
        bridge = SyncCacheBridge(cache)

        # Scheduler writes
        from datetime import UTC, datetime
        now = datetime.now(UTC)
        bridge.set("fxrate:USD", {"rate": 7.2, "fetched_at": now.isoformat()}, ttl=14400)

        # Backend reads (same Cache instance = same Redis)
        data = bridge.get("fxrate:USD")
        assert data is not None
        assert data["rate"] == 7.2

        bridge.close()
        reset_cache()

    def test_memory_mode_is_per_process(self):
        """Memory mode: two bridges have independent caches (no sharing)."""
        from packages.core.cache import MemoryCache

        bridge_a = SyncCacheBridge(MemoryCache())
        bridge_b = SyncCacheBridge(MemoryCache())

        bridge_a.set("fxrate:USD", {"rate": 7.2, "fetched_at": "2026-01-01T00:00:00+00:00"})
        assert bridge_b.get("fxrate:USD") is None  # independent caches
```

- [ ] **Step 2: Run the test**

Run: `cd server && uv run pytest tests/packages/core/test_sync_bridge.py::TestCrossProcessSharing -v`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add server/tests/packages/core/test_sync_bridge.py
git commit -m "test(cache): verify cross-process exchange rate sharing via Redis"
```

---

### Task 5: Full regression verification

**Files:** None (verification only)

- [ ] **Step 1: Run all packages tests**

```bash
cd server && uv run pytest tests/packages/ -v
```

Expected: All PASS

- [ ] **Step 2: Run scheduler worker tests**

```bash
cd server && uv run pytest tests/scheduler_worker/ -v
```

Expected: All PASS

- [ ] **Step 3: Run backend tests**

```bash
cd server && uv run pytest tests/backend/ -q
```

Expected: All PASS (except the pre-existing `test_learning_today_and_duration` failure)

- [ ] **Step 4: Run ruff lint**

```bash
cd server && uv run ruff check packages/core/cache/sync_bridge.py packages/db/exchange_rate_adapter.py
```

Expected: No errors

- [ ] **Step 5: Run mypy**

```bash
cd server && uv run mypy packages/core/cache/sync_bridge.py packages/db/exchange_rate_adapter.py --explicit-package-bases
```

Expected: No errors
