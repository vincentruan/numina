from datetime import datetime, timedelta

import httpx
from sqlalchemy.orm import Session

from packages.core.logging import get_logger
from packages.db.models.currency import Currency
from packages.db.models.exchange_rate import ExchangeRate

logger = get_logger(__name__)

_CACHE_TTL = timedelta(hours=4)


class ExchangeRateService:
    # Maps currency code → (rate, fetched_at, cached_at)
    _cache: dict[str, tuple[float, datetime, datetime]] = {}

    @classmethod
    def get_rate(cls, target_currency: str, db: Session) -> tuple[float, datetime]:
        """Return (rate, fetched_at) for target_currency relative to CNY base."""
        if target_currency == "CNY":
            return (1.0, datetime.now())

        entry = cls._cache.get(target_currency)
        if entry is not None:
            rate, fetched_at, cached_at = entry
            if datetime.now() - cached_at < _CACHE_TTL:
                return (rate, fetched_at)

        row = (
            db.query(ExchangeRate)
            .filter(ExchangeRate.target_currency == target_currency)
            .order_by(ExchangeRate.fetched_at.desc())
            .first()
        )
        if row is None:
            logger.warning(f"汇率数据不存在: {target_currency}，使用 1:1 回退")
            return (1.0, datetime.now())

        cls._cache[target_currency] = (row.rate, row.fetched_at, datetime.now())
        return (row.rate, row.fetched_at)

    @classmethod
    def fetch_and_store_rates(cls, db: Session) -> bool:
        """Fetch latest rates from exchangerate-api.com and persist to DB."""
        try:
            resp = httpx.get(
                "https://api.exchangerate-api.com/v4/latest/CNY",
                timeout=10,
                proxy=None,
            )
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            logger.exception(f"汇率获取失败: {e}")
            return False

        fetched_at = datetime.now()
        rates: dict[str, float] = data.get("rates", {})

        for code, rate in rates.items():
            if code == "CNY":
                continue
            try:
                with db.begin_nested():
                    row = ExchangeRate(
                        target_currency=code,
                        rate=rate,
                        fetched_at=fetched_at,
                    )
                    db.add(row)
            except Exception:
                continue

        existing_codes = {c.code for c in db.query(Currency.code).all()}
        for code in rates:
            if code not in existing_codes:
                db.add(Currency(
                    code=code,
                    name_zh=code,
                    name_en=code,
                    symbol=code,
                    flag_emoji="🏳️",
                    is_favorite=False,
                    sort_order=999,
                ))

        db.commit()
        cls._cache.clear()
        logger.info(f"汇率更新完成，共 {len(rates)} 种货币")
        return True

    @classmethod
    def convert(
        cls,
        amount: float,
        from_currency: str,
        to_currency: str,
        db: Session,
    ) -> float:
        """Convert amount from from_currency to to_currency via CNY as intermediate."""
        if from_currency == to_currency:
            return amount

        rate_from, _ = cls.get_rate(from_currency, db)
        rate_to, _ = cls.get_rate(to_currency, db)

        amount_in_cny = amount / rate_from
        result = amount_in_cny * rate_to

        if to_currency == "JPY":
            return round(result)

        return round(result, 2)
