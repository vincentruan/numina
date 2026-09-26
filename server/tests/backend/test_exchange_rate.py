from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from apps.backend.app.models.exchange_rate import ExchangeRate
from apps.backend.app.services.exchange_rate import ExchangeRateService
from packages.core.cache import init_cache, reset_cache
from packages.core.cache.sync_bridge import SyncCacheBridge
from packages.db.exchange_rate_adapter import ExchangeRateAdapter


@pytest.fixture(autouse=True)
def _init_unified_cache():
    """Ensure unified Cache is initialized for each test."""
    reset_cache()
    init_cache(backend="memory")
    yield
    reset_cache()


def test_convert_same_currency(db):
    """Same currency returns amount unchanged without hitting DB."""
    result = ExchangeRateService.convert(1000.0, "CNY", "CNY", db)
    assert result == 1000.0


def test_convert_usd_to_cny(db):
    """USD -> CNY conversion uses stored rate correctly."""
    rate_row = ExchangeRate(
        target_currency="USD",
        rate=0.1374,
        fetched_at=datetime(2026, 3, 24, 8, 0, 0),
    )
    db.add(rate_row)
    db.commit()

    adapter = ExchangeRateAdapter()
    result = ExchangeRateService.convert(1000.0, "USD", "CNY", db, adapter=adapter)
    # amount_in_cny = 1000 / 0.1374 = 7278.02...
    # result = 7278.02 * 1.0 = 7278.02
    assert result == pytest.approx(7278.02, rel=1e-3)


def test_convert_without_adapter_no_cache(db):
    """When no adapter is given, calls fall back to DB-only lookup (no cache)."""
    rate_row = ExchangeRate(
        target_currency="EUR",
        rate=0.128,
        fetched_at=datetime(2026, 3, 24, 8, 0, 0),
    )
    db.add(rate_row)
    db.commit()

    # Two calls: both hit DB (no adapter = no cache)
    r1, _ = ExchangeRateService.get_rate("EUR", db)
    r2, _ = ExchangeRateService.get_rate("EUR", db)
    assert r1 == 0.128
    assert r2 == 0.128


def test_cache_hit_no_db_query(db):
    """With adapter: second call for same currency uses cache, not DB."""
    rate_row = ExchangeRate(
        target_currency="EUR",
        rate=0.128,
        fetched_at=datetime(2026, 3, 24, 8, 0, 0),
    )
    db.add(rate_row)
    db.commit()

    adapter = ExchangeRateAdapter()

    # First call populates unified cache
    ExchangeRateService.get_rate("EUR", db, adapter=adapter)
    bridge = SyncCacheBridge.from_cache()
    assert bridge.get("fxrate:EUR") is not None

    # Second call: patch DB query to confirm it is NOT called
    with patch.object(db, "query", wraps=db.query) as mock_query:
        ExchangeRateService.get_rate("EUR", db, adapter=adapter)
        mock_query.assert_not_called()


def test_fallback_when_no_rates(db):
    """Returns (None, None) when no rate data exists in DB — callers must not assume 1:1."""
    rate, fetched_at = ExchangeRateService.get_rate("XYZ", db)
    assert rate is None
    assert fetched_at is None


def test_fetch_and_store_rates_success(db):
    """Successful API fetch inserts rates into DB."""
    adapter = ExchangeRateAdapter()

    mock_response = MagicMock()
    mock_response.json.return_value = {
        "rates": {"USD": 0.1374, "EUR": 0.128, "JPY": 20.5, "CNY": 1.0}
    }
    mock_response.raise_for_status = MagicMock()

    with patch("httpx.get", return_value=mock_response):
        result = adapter.fetch_and_store_rates(db)

    assert result is True
    rates = db.query(ExchangeRate).order_by(ExchangeRate.target_currency).all()
    assert len(rates) == 3  # USD, EUR, JPY (CNY skipped)


def test_fetch_and_store_rates_http_failure(db):
    """HTTP failure returns False without modifying DB."""
    existing_rate = ExchangeRate(
        target_currency="USD",
        rate=0.14,
        fetched_at=datetime(2026, 1, 1, 0, 0, 0),
    )
    db.add(existing_rate)
    db.commit()
    initial_count = db.query(ExchangeRate).count()

    with patch("httpx.get", side_effect=Exception("Connection error")):
        adapter = ExchangeRateAdapter()
        result = adapter.fetch_and_store_rates(db)

    assert result is False
    assert db.query(ExchangeRate).count() == initial_count


def test_fetch_and_store_rates_bypasses_proxy(db):
    """Exchange rate fetch explicitly bypasses system proxy (proxy=None)."""
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "rates": {"USD": 0.1374, "CNY": 1.0}
    }
    mock_response.raise_for_status = MagicMock()

    with patch("httpx.get", return_value=mock_response) as mock_get:
        adapter = ExchangeRateAdapter()
        adapter.fetch_and_store_rates(db)

    mock_get.assert_called_once()
    call_kwargs = mock_get.call_args.kwargs
    assert "proxy" in call_kwargs
    assert call_kwargs["proxy"] is None


def test_deprecated_fetch_and_store_rates_warns(db, monkeypatch):
    """Deprecated wrapper emits DeprecationWarning and delegates to adapter."""
    mock_adapter_fetch = MagicMock(return_value=True)
    monkeypatch.setattr(
        "packages.db.exchange_rate_adapter.ExchangeRateAdapter.fetch_and_store_rates",
        mock_adapter_fetch,
    )

    with pytest.warns(DeprecationWarning, match="ExchangeRateAdapter"):
        ExchangeRateService.fetch_and_store_rates(db)

    mock_adapter_fetch.assert_called_once_with(db)
