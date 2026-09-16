"""Tests for ExchangeRateAdapter (packages/core).

Covers:
- fetch_rates(): mocked httpx → dict[str, float]
- get_cached_rate(): CNY shortcut, cache miss, cache hit within TTL, stale cache
- fetch_and_store_rates(): writes ExchangeRate rows, adds Currency rows, clears cache
- Thread safety: concurrent access via threading.Lock
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


def test_get_cached_rate_cache_hit_within_ttl(adapter):
    """Cache hit within TTL → returns cached (rate, fetched_at)."""
    now = datetime.now(UTC)
    adapter._cache["USD"] = (7.2, now, now)
    rate, fetched_at = adapter.get_cached_rate("USD")
    assert rate == 7.2
    assert fetched_at == now


def test_get_cached_rate_stale_cache_returns_none(adapter):
    """Cache entry expired (>4h) → treated as missing, returns (None, None)."""
    stale = datetime.now(UTC) - timedelta(hours=5)
    adapter._cache["GBP"] = (8.0, stale, stale)
    rate, fetched_at = adapter.get_cached_rate("GBP")
    assert rate is None
    assert fetched_at is None


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


def test_fetch_and_store_rates_clears_cache(packages_db, adapter, monkeypatch):
    """Successful fetch clears the in-memory cache."""
    adapter._cache["USD"] = (7.0, datetime.now(UTC), datetime.now(UTC))
    payload = {"rates": {"USD": 7.2}}
    monkeypatch.setattr(
        "packages.db.exchange_rate_adapter.httpx.get",
        lambda *a, **k: _FakeResponse(payload),
    )
    adapter.fetch_and_store_rates(packages_db)
    assert adapter._cache == {}


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


# ---------------------------------------------------------------------------
# Thread safety
# ---------------------------------------------------------------------------


def test_fetch_and_store_rates_is_thread_safe(packages_db, adapter, monkeypatch):
    """Concurrent calls to fetch_and_store_rates are serialized by the lock."""
    payload = {"rates": {"USD": 7.2, "EUR": 7.8}}
    monkeypatch.setattr(
        "packages.db.exchange_rate_adapter.httpx.get",
        lambda *a, **k: _FakeResponse(payload),
    )

    import threading

    results = []
    errors = []

    def _worker():
        try:
            adapter.fetch_and_store_rates(packages_db)
            results.append(True)
        except Exception as e:
            errors.append(e)

    threads = [threading.Thread(target=_worker) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors, errors
    assert len(results) == 4
    assert adapter._cache == {}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def adapter():
    return ExchangeRateAdapter()
