from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from app.models.exchange_rate import ExchangeRate
from app.services.exchange_rate import ExchangeRateService


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