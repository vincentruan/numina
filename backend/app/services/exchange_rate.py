import logging
from datetime import datetime

import httpx
from sqlalchemy.orm import Session

from app.models.currency import Currency
from app.models.exchange_rate import ExchangeRate

logger = logging.getLogger(__name__)


class ExchangeRateService:
    _cache: dict[str, tuple[float, datetime]] = {}

    @classmethod
    def get_rate(cls, target_currency: str, db: Session) -> tuple[float, datetime]:
        """Return (rate, fetched_at) for target_currency relative to CNY base.
        Rate means: 1 CNY = rate target_currency units.
        Falls back to (1.0, now()) if no data available."""
        if target_currency == "CNY":
            return (1.0, datetime.now())

        if target_currency in cls._cache:
            return cls._cache[target_currency]

        row = (
            db.query(ExchangeRate)
            .filter(ExchangeRate.target_currency == target_currency)
            .order_by(ExchangeRate.fetched_at.desc())
            .first()
        )
        if row is None:
            logger.warning(f"汇率数据不存在: {target_currency}，使用 1:1 回退")
            return (1.0, datetime.now())

        cls._cache[target_currency] = (row.rate, row.fetched_at)
        return cls._cache[target_currency]

    @classmethod
    def fetch_and_store_rates(cls, db: Session) -> None:
        """Fetch latest rates from exchangerate-api.com and persist to DB."""
        try:
            resp = httpx.get(
                "https://api.exchangerate-api.com/v4/latest/CNY",
                timeout=10,
            )
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            logger.error(f"汇率获取失败: {e}")
            return

        fetched_at = datetime.now()
        rates: dict[str, float] = data.get("rates", {})

        for code, rate in rates.items():
            if code == "CNY":
                continue
            try:
                row = ExchangeRate(
                    target_currency=code,
                    rate=rate,
                    fetched_at=fetched_at,
                )
                db.add(row)
                db.flush()
            except Exception:
                db.rollback()
                # Row with same (target_currency, fetched_at) already exists — skip
                continue

        # Upsert any new currency codes into currencies table (code only)
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

        # rate = target units per 1 CNY
        # amount_in_cny = amount / rate_from
        # result = amount_in_cny * rate_to
        amount_in_cny = amount / rate_from
        result = amount_in_cny * rate_to

        # JPY has no fractional units
        if to_currency == "JPY":
            return round(result)

        return round(result, 2)