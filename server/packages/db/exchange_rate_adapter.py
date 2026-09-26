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
        Cache entries are NOT explicitly cleared — they expire naturally via
        TTL (4h). The DB is the source of truth; stale cache entries (up to
        4h old) are replaced on expiry. Exchange rates change slowly enough
        that this is acceptable.
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

            db.commit()
        except Exception:
            db.rollback()
            raise

        logger.info(f"汇率更新完成，共 {len(rates)} 种货币")
        return True
