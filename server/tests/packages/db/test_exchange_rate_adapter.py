"""Tests for ExchangeRateAdapter (packages/db).

Covers:
- fetch_rates(): mocked httpx → dict[str, float]
- get_cached_rate(): CNY shortcut, cache miss, cache hit from unified Cache
- fetch_and_store_rates(): writes ExchangeRate rows, adds Currency rows
- Unified Cache integration: populate writes, TTL matches 4h
"""
from datetime import UTC, datetime, timedelta

import pytest

from packages.db.exchange_rate_adapter import ExchangeRateAdapter
from packages.db.models.currency import Currency
from packages.db.models.exchange_rate import ExchangeRate

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _FakeResponse:
    def __init__(self, payload: dict):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _init_unified_cache():
    """Ensure unified Cache is initialized for each test."""
    from packages.core.cache import init_cache, reset_cache

    reset_cache()
    init_cache(backend="memory")
    yield
    reset_cache()


@pytest.fixture
def adapter():
    return ExchangeRateAdapter()


# ---------------------------------------------------------------------------
# fetch_rates
# ---------------------------------------------------------------------------


def test_fetch_rates_returns_dict(packages_db, monkeypatch):
    """fetch_rates() returns the rates dict from the API response."""
    payload = {"rates": {"USD": 7.2, "EUR": 7.8, "JPY": 20.5, "CNY": 1.0}}
    monkeypatch.setattr(
        "packages.db.exchange_rate_adapter.httpx.get",
        lambda *a, **k: _FakeResponse(payload),
    )
    adapter = ExchangeRateAdapter()
    rates = adapter.fetch_rates()
    assert rates == payload["rates"]


def test_fetch_rates_raises_on_http_error(monkeypatch):
    """fetch_rates() re-raises when the HTTP response indicates an error."""

    class _ErrResponse:
        def raise_for_status(self):
            raise RuntimeError("HTTP 500")

        def json(self):
            return {}

    monkeypatch.setattr(
        "packages.db.exchange_rate_adapter.httpx.get",
        lambda *a, **k: _ErrResponse(),
    )
    adapter = ExchangeRateAdapter()
    with pytest.raises(RuntimeError, match="HTTP 500"):
        adapter.fetch_rates()


# ---------------------------------------------------------------------------
# get_cached_rate
# ---------------------------------------------------------------------------


def test_get_cached_rate_cny_shortcut(adapter):
    """CNY shortcut: returns (1.0, now) without touching cache or DB."""
    rate, fetched_at = adapter.get_cached_rate("CNY")
    assert rate == 1.0
    assert isinstance(fetched_at, datetime)


def test_get_cached_rate_missing_returns_none(adapter):
    """Currency not in cache → returns (None, None)."""
    rate, fetched_at = adapter.get_cached_rate("XXX")
    assert rate is None
    assert fetched_at is None


def test_get_cached_rate_from_unified_cache(adapter):
    """Adapter reads from unified Cache (via SyncCacheBridge)."""
    from packages.core.cache import get_cache
    from packages.core.cache.sync_bridge import SyncCacheBridge

    bridge = SyncCacheBridge.from_cache()
    now = datetime.now(UTC)
    bridge.set(
        "fxrate:USD",
        {"rate": 7.2, "fetched_at": now.isoformat()},
        ttl=14400,
    )

    rate, fetched_at = adapter.get_cached_rate("USD")
    assert rate == 7.2
    assert fetched_at is not None


# ---------------------------------------------------------------------------
# populate_cache
# ---------------------------------------------------------------------------


def test_populate_cache_writes_to_unified_cache(adapter):
    """populate_cache writes to unified Cache, readable by bridge."""
    from packages.core.cache.sync_bridge import SyncCacheBridge

    now = datetime.now(UTC)
    adapter.populate_cache("EUR", 7.8, now)

    bridge = SyncCacheBridge.from_cache()
    data = bridge.get("fxrate:EUR")
    assert data is not None
    assert data["rate"] == 7.8


def test_adapter_ttl_is_4_hours(adapter):
    """Cache entries expire after 4 hours (14400 seconds)."""
    from packages.core.cache import get_cache
    from packages.core.cache.sync_bridge import SyncCacheBridge

    now = datetime.now(UTC)
    adapter.populate_cache("GBP", 8.5, now)

    cache = get_cache()
    import asyncio

    # Use bridge for sync access
    bridge = SyncCacheBridge.from_cache()
    ttl_data = bridge.get("fxrate:GBP")
    assert ttl_data is not None

    # Verify TTL via async cache
    loop = asyncio.new_event_loop()
    try:
        ttl = loop.run_until_complete(cache.get_ttl("fxrate:GBP"))
    finally:
        loop.close()
    assert ttl is not None
    assert 14300 <= ttl <= 14400


# ---------------------------------------------------------------------------
# fetch_and_store_rates
# ---------------------------------------------------------------------------


def test_fetch_and_store_rates_stores_rates_skips_cny(packages_db, adapter, monkeypatch):
    """Successful fetch: writes non-CNY ExchangeRate rows; CNY is skipped."""
    payload = {"rates": {"CNY": 1.0, "USD": 7.2, "EUR": 7.8}}
    monkeypatch.setattr(
        "packages.db.exchange_rate_adapter.httpx.get",
        lambda *a, **k: _FakeResponse(payload),
    )
    ok = adapter.fetch_and_store_rates(packages_db)
    assert ok is True

    targets = {r.target_currency for r in packages_db.query(ExchangeRate).all()}
    assert "USD" in targets
    assert "EUR" in targets
    assert "CNY" not in targets


def test_fetch_and_store_rates_adds_new_currency_rows(packages_db, adapter, monkeypatch):
    """Rates contain a new currency → a new Currency row is created."""
    packages_db.add(Currency(
        code="USD", name_zh="美元", name_en="US Dollar", symbol="$",
        flag_emoji="🇺🇸", is_favorite=True, sort_order=1,
    ))
    packages_db.flush()

    payload = {"rates": {"CNY": 1.0, "USD": 7.2, "ABC": 3.3}}
    monkeypatch.setattr(
        "packages.db.exchange_rate_adapter.httpx.get",
        lambda *a, **k: _FakeResponse(payload),
    )
    adapter.fetch_and_store_rates(packages_db)

    codes = [c.code for c in packages_db.query(Currency).all()]
    assert codes.count("USD") == 1
    assert "ABC" in codes


def test_fetch_and_store_rates_returns_false_on_exception(packages_db, adapter, monkeypatch):
    """httpx.get raises → returns False, DB unchanged."""

    def _boom(*a, **k):
        raise RuntimeError("network down")

    monkeypatch.setattr(
        "packages.db.exchange_rate_adapter.httpx.get", _boom
    )
    ok = adapter.fetch_and_store_rates(packages_db)
    assert ok is False
    assert packages_db.query(ExchangeRate).count() == 0
