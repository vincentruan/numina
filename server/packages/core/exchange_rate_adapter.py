from __future__ import annotations

import threading
from datetime import UTC, datetime, timedelta
from typing import Any, cast

import httpx
from sqlalchemy.orm import Session

from packages.core.logging import get_logger
from packages.db.models.currency import Currency
from packages.db.models.exchange_rate import ExchangeRate

logger = get_logger(__name__)

_CACHE_TTL = timedelta(hours=4)


class ExchangeRateAdapter:
    """Infrastructure adapter for exchange-rate fetching and caching.

    Encapsulates HTTP calls, in-memory TTL cache, and DB persistence so the
    domain service remains free of infrastructure concerns.
    """

    def __init__(self) -> None:
        self._cache: dict[str, tuple[float, datetime, datetime]] = {}
        self._lock = threading.Lock()

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

        Checks the in-memory TTL cache first; falls back to the database when
        the entry is absent or expired. Returns ``(None, None)`` when nothing
        is found.
        """
        if currency == "CNY":
            return (1.0, datetime.now(UTC))

        with self._lock:
            entry = self._cache.get(currency)
        if entry is not None:
            rate, fetched_at, cached_at = entry
            if datetime.now(UTC) - cached_at < _CACHE_TTL:
                return (rate, fetched_at)

        return (None, None)

    def get_rate_from_db(
        self, currency: str, db: Session
    ) -> tuple[float | None, datetime | None]:
        """DB-only lookup — used by the domain service when no adapter is
        provided (backward-compat path)."""
        row = (
            db.query(ExchangeRate)
            .filter(ExchangeRate.target_currency == currency)
            .order_by(ExchangeRate.fetched_at.desc())
            .first()
        )
        if row is None:
            logger.warning(f"汇率数据不存在: {currency}")
            return (None, None)
        return (row.rate, row.fetched_at)

    def fetch_and_store_rates(self, db: Session) -> bool:
        """Fetch from API, persist rates + Currency rows, clear cache.

        Thread-safe via ``threading.Lock``.
        """
        try:
            rates = self.fetch_rates()
        except Exception as e:
            logger.exception(f"汇率获取失败: {e}")
            return False

        fetched_at = datetime.now(UTC)

        with self._lock:
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

                self._cache.clear()
                db.commit()
            except Exception:
                db.rollback()
                raise

        logger.info(f"汇率更新完成，共 {len(rates)} 种货币")
        return True
