from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from apps.backend.app.models.exchange_rate import ExchangeRate
from apps.backend.app.services.exchange_rate import ExchangeRateService


@pytest.fixture(autouse=True)
def clear_cache():
    """Clear the in-memory cache before each test."""
    ExchangeRateService._cache.clear()
    yield
    ExchangeRateService._cache.clear()


def test_convert_same_currency(db):
    """Same currency returns amount unchanged without hitting DB."""
    result = ExchangeRateService.convert(1000.0, "CNY", "CNY", db)
    assert result == 1000.0


def test_convert_usd_to_cny(db):
    """USD -> CNY conversion uses stored rate correctly."""
    # Insert a rate: 1 CNY = 0.1374 USD  =>  1 USD = 7.2779 CNY
    rate_row = ExchangeRate(
        target_currency="USD",
        rate=0.1374,
        fetched_at=datetime(2026, 3, 24, 8, 0, 0),
    )
    db.add(rate_row)
    db.commit()

    result = ExchangeRateService.convert(1000.0, "USD", "CNY", db)
    # amount_in_cny = 1000 / 0.1374 = 7278.02...
    # result = 7278.02 * 1.0 = 7278.02
    assert result == pytest.approx(7278.02, rel=1e-3)


def test_cache_hit_no_db_query(db):
    """Second call for same currency uses cache, not DB."""
    rate_row = ExchangeRate(
        target_currency="EUR",
        rate=0.128,
        fetched_at=datetime(2026, 3, 24, 8, 0, 0),
    )
    db.add(rate_row)
    db.commit()

    # First call populates cache
    ExchangeRateService.get_rate("EUR", db)
    assert "EUR" in ExchangeRateService._cache

    # Second call: patch DB query to confirm it is NOT called
    with patch.object(db, "query", wraps=db.query) as mock_query:
        ExchangeRateService.get_rate("EUR", db)
        mock_query.assert_not_called()


def test_fallback_when_no_rates(db):
    """Returns (1.0, now()) when no rate data exists in DB."""
    rate, fetched_at = ExchangeRateService.get_rate("XYZ", db)
    assert rate == 1.0
    assert isinstance(fetched_at, datetime)


def test_fetch_and_store_rates_success(db):
    """Successful API fetch inserts rates and clears cache."""
    # Pre-populate cache to verify it gets cleared
    ExchangeRateService._cache["USD"] = (0.15, datetime(2026, 1, 1, 0, 0, 0))

    mock_response = MagicMock()
    mock_response.json.return_value = {
        "rates": {"USD": 0.1374, "EUR": 0.128, "JPY": 20.5, "CNY": 1.0}
    }
    mock_response.raise_for_status = MagicMock()

    with patch("httpx.get", return_value=mock_response):
        result = ExchangeRateService.fetch_and_store_rates(db)

    assert result is True
    # Verify cache was cleared
    assert ExchangeRateService._cache == {}
    # Verify rates were inserted
    rates = db.query(ExchangeRate).order_by(ExchangeRate.target_currency).all()
    assert len(rates) == 3  # USD, EUR, JPY (CNY skipped)


def test_fetch_and_store_rates_http_failure(db):
    """HTTP failure returns False without modifying DB."""
    # Pre-populate DB with existing rate
    existing_rate = ExchangeRate(
        target_currency="USD",
        rate=0.14,
        fetched_at=datetime(2026, 1, 1, 0, 0, 0),
    )
    db.add(existing_rate)
    db.commit()
    initial_count = db.query(ExchangeRate).count()

    with patch("httpx.get", side_effect=Exception("Connection error")):
        result = ExchangeRateService.fetch_and_store_rates(db)

    assert result is False
    # Verify DB is unchanged
    assert db.query(ExchangeRate).count() == initial_count


def test_fetch_and_store_rates_bypasses_proxy(db):
    """Exchange rate fetch explicitly bypasses system proxy (proxy=None)."""
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "rates": {"USD": 0.1374, "CNY": 1.0}
    }
    mock_response.raise_for_status = MagicMock()

    # Mock httpx.get to capture the proxy parameter
    with patch("httpx.get", return_value=mock_response) as mock_get:
        result = ExchangeRateService.fetch_and_store_rates(db)

    assert result is True
    # Verify proxy=None was passed to bypass system proxy
    mock_get.assert_called_once()
    call_kwargs = mock_get.call_args.kwargs
    assert "proxy" in call_kwargs, "proxy parameter must be explicitly set"
    assert call_kwargs["proxy"] is None, "proxy=None should bypass system proxy"