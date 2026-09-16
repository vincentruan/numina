from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy.orm import Session

from packages.core.logging import get_logger
from packages.db.models.exchange_rate import ExchangeRate

if TYPE_CHECKING:
    from packages.db.exchange_rate_adapter import ExchangeRateAdapter

logger = get_logger(__name__)


class ExchangeRateService:
    """Thin domain-layer service for exchange-rate lookups and conversions.

    Infrastructure concerns (HTTP, caching) live in
    :class:`packages.db.exchange_rate_adapter.ExchangeRateAdapter`.
    This class delegates to the adapter when one is supplied; otherwise it
    performs plain DB lookups (no caching) for backward compatibility.
    """

    @classmethod
    def get_rate(
        cls,
        target_currency: str,
        db: Session,
        adapter: ExchangeRateAdapter | None = None,
    ) -> tuple[float | None, datetime | None]:
        """Return (rate, fetched_at) for *target_currency* relative to CNY base.

        Returns ``(None, None)`` when no rate row exists — callers must handle
        this instead of silently treating missing rates as 1:1.
        """
        if target_currency == "CNY":
            return (1.0, datetime.now(UTC))

        if adapter is not None:
            rate, fetched_at = adapter.get_cached_rate(target_currency)
            if rate is not None:
                return (rate, fetched_at)
            # Cache miss or stale — fall through to DB lookup

        row = (
            db.query(ExchangeRate)
            .filter(ExchangeRate.target_currency == target_currency)
            .order_by(ExchangeRate.fetched_at.desc())
            .first()
        )
        if row is None:
            logger.warning(f"汇率数据不存在: {target_currency}")
            return (None, None)

        # Update adapter cache so subsequent calls use it
        if adapter is not None:
            adapter.populate_cache(target_currency, row.rate, row.fetched_at)

        return (row.rate, row.fetched_at)

    @classmethod
    def convert(
        cls,
        amount: float,
        from_currency: str,
        to_currency: str,
        db: Session,
        adapter: ExchangeRateAdapter | None = None,
    ) -> float:
        """Convert *amount* from *from_currency* to *to_currency* via CNY.

        Returns the original amount unchanged when either rate is missing —
        this avoids silently distorting values with a 1:1 fallback.
        """
        if from_currency == to_currency:
            return amount

        rate_from, _ = cls.get_rate(from_currency, db, adapter=adapter)
        rate_to, _ = cls.get_rate(to_currency, db, adapter=adapter)

        if rate_from is None or rate_to is None:
            logger.warning(
                f"汇率缺失，跳过转换: {from_currency}→{to_currency}，"
                f"返回原始金额 {amount}"
            )
            return amount

        amount_in_cny = amount / rate_from
        result = amount_in_cny * rate_to

        if to_currency == "JPY":
            return round(result)

        return round(result, 2)

    @classmethod
    def fetch_and_store_rates(cls, db: Session) -> bool:
        """Deprecated: use :class:`ExchangeRateAdapter` directly.

        .. deprecated::
            Use ``ExchangeRateAdapter().fetch_and_store_rates(db)`` instead.
        """
        import warnings

        warnings.warn(
            "ExchangeRateService.fetch_and_store_rates is deprecated, "
            "use ExchangeRateAdapter",
            DeprecationWarning,
            stacklevel=2,
        )
        from packages.db.exchange_rate_adapter import ExchangeRateAdapter

        adapter = ExchangeRateAdapter()
        return adapter.fetch_and_store_rates(db)
