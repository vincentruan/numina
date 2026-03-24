# Multi-Currency Support Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add multi-currency support so assets/liabilities/wishes can be recorded in any currency and displayed unified in the user's default currency via exchange rate conversion.

**Architecture:** Store original currency+amount unchanged in DB. Convert at display/aggregation time using ExchangeRateService (sync, in-memory cache + SQLite). BackgroundScheduler fetches rates from exchangerate-api.com every 2 hours (08:00-23:00) with random 0-15 min offset.

**Tech Stack:** FastAPI + SQLAlchemy + APScheduler (new) + httpx | Vue 3 + TypeScript + Vant 4 + Pinia

---

## Task 1: Backend models — ExchangeRate, Currency, add currency to Liability + Wish

**Files to create:**
- `backend/app/models/exchange_rate.py` (new)
- `backend/app/models/currency.py` (new)

**Files to modify:**
- `backend/app/models/liability.py`
- `backend/app/models/wish.py`
- `backend/app/main.py`

### Steps

- [ ] Create `backend/app/models/exchange_rate.py`:

```python
from datetime import datetime
from uuid import uuid4

from sqlalchemy import DateTime, Float, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ExchangeRate(Base):
    __tablename__ = "exchange_rates"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    base_currency: Mapped[str] = mapped_column(String(10), default="CNY")
    target_currency: Mapped[str] = mapped_column(String(10), nullable=False)
    rate: Mapped[float] = mapped_column(Float, nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    __table_args__ = (UniqueConstraint("target_currency", "fetched_at"),)
```

- [ ] Create `backend/app/models/currency.py`:

```python
from sqlalchemy import Boolean, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Currency(Base):
    __tablename__ = "currencies"

    code: Mapped[str] = mapped_column(String(10), primary_key=True)
    name_zh: Mapped[str] = mapped_column(String(50), nullable=False)
    name_en: Mapped[str] = mapped_column(String(50), nullable=False)
    symbol: Mapped[str] = mapped_column(String(10), nullable=False)
    flag_emoji: Mapped[str] = mapped_column(String(10), nullable=False)
    is_favorite: Mapped[bool] = mapped_column(Boolean, default=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=999)
```

- [ ] Add `currency` field to `backend/app/models/liability.py` after the `is_active` field:

```python
currency: Mapped[str] = mapped_column(String(10), default="CNY")
```

- [ ] Add `currency` field to `backend/app/models/wish.py` after the `category_id` field:

```python
currency: Mapped[str] = mapped_column(String(10), default="CNY")
```

- [ ] Add model imports to `backend/app/main.py` after the existing model imports block:

```python
from app.models.exchange_rate import ExchangeRate  # noqa: F401
from app.models.currency import Currency  # noqa: F401
```

- [ ] Verify: `cd /path/to/numina/backend && uv run pytest tests/ -v -k "test_create"` — all existing create tests pass

### Git commit

```bash
git add backend/app/models/exchange_rate.py backend/app/models/currency.py \
        backend/app/models/liability.py backend/app/models/wish.py backend/app/main.py
git commit -m "feat: add ExchangeRate and Currency models, add currency field to Liability and Wish

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 2: Seed 13 favorite currencies

**Files to create:**
- `backend/app/seed/currencies.py` (new)

**Files to modify:**
- `backend/app/main.py`

### Steps

- [ ] Create `backend/app/seed/currencies.py` following the same pattern as `seed/categories.py`:

```python
FAVORITE_CURRENCIES = [
    {"code": "CNY", "name_zh": "人民币", "name_en": "Chinese Yuan",      "symbol": "¥",   "flag_emoji": "🇨🇳", "sort_order": 1},
    {"code": "USD", "name_zh": "美元",   "name_en": "US Dollar",         "symbol": "$",   "flag_emoji": "🇺🇸", "sort_order": 2},
    {"code": "EUR", "name_zh": "欧元",   "name_en": "Euro",              "symbol": "€",   "flag_emoji": "🇪🇺", "sort_order": 3},
    {"code": "JPY", "name_zh": "日元",   "name_en": "Japanese Yen",      "symbol": "¥",   "flag_emoji": "🇯🇵", "sort_order": 4},
    {"code": "GBP", "name_zh": "英镑",   "name_en": "British Pound",     "symbol": "£",   "flag_emoji": "🇬🇧", "sort_order": 5},
    {"code": "AUD", "name_zh": "澳元",   "name_en": "Australian Dollar", "symbol": "A$",  "flag_emoji": "🇦🇺", "sort_order": 6},
    {"code": "CAD", "name_zh": "加元",   "name_en": "Canadian Dollar",   "symbol": "C$",  "flag_emoji": "🇨🇦", "sort_order": 7},
    {"code": "CHF", "name_zh": "瑞士法郎","name_en": "Swiss Franc",      "symbol": "Fr",  "flag_emoji": "🇨🇭", "sort_order": 8},
    {"code": "HKD", "name_zh": "港币",   "name_en": "Hong Kong Dollar",  "symbol": "HK$", "flag_emoji": "🇭🇰", "sort_order": 9},
    {"code": "SGD", "name_zh": "新加坡元","name_en": "Singapore Dollar", "symbol": "S$",  "flag_emoji": "🇸🇬", "sort_order": 10},
    {"code": "RUB", "name_zh": "卢布",   "name_en": "Russian Ruble",     "symbol": "₽",   "flag_emoji": "🇷🇺", "sort_order": 11},
    {"code": "INR", "name_zh": "卢比",   "name_en": "Indian Rupee",      "symbol": "₹",   "flag_emoji": "🇮🇳", "sort_order": 12},
    {"code": "BRL", "name_zh": "巴西雷亚尔","name_en": "Brazilian Real", "symbol": "R$",  "flag_emoji": "🇧🇷", "sort_order": 13},
]


def seed_currencies(db):
    from app.models.currency import Currency

    existing = db.query(Currency).filter(Currency.is_favorite == True).first()
    if existing:
        return

    for cur_data in FAVORITE_CURRENCIES:
        cur = Currency(is_favorite=True, **cur_data)
        db.add(cur)
    db.commit()
```

- [ ] In `backend/app/main.py`, add the import at the top with the other seed imports:

```python
from app.seed.currencies import seed_currencies
```

- [ ] In `backend/app/main.py` lifespan, call `seed_currencies(db)` immediately after `seed_categories(db)`:

```python
seed_categories(db)
seed_currencies(db)
```

- [ ] Verify: `cd /path/to/numina/backend && uv run pytest tests/ -v` — all 36 tests pass

### Git commit

```bash
git add backend/app/seed/currencies.py backend/app/main.py
git commit -m "feat: seed 13 favorite currencies on startup

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---
## Task 3: ExchangeRateService (synchronous)

**Files to create:**
- `backend/app/services/exchange_rate.py` (new)
- `backend/tests/test_exchange_rate.py` (new)

### Steps

- [ ] Create `backend/app/services/exchange_rate.py`:

```python
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
```

- [ ] Create `backend/tests/test_exchange_rate.py`:

```python
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
```

- [ ] Run tests: `cd /path/to/numina/backend && uv run pytest tests/test_exchange_rate.py -v`

Expected output:
```
tests/test_exchange_rate.py::test_convert_same_currency PASSED
tests/test_exchange_rate.py::test_convert_usd_to_cny PASSED
tests/test_exchange_rate.py::test_cache_hit_no_db_query PASSED
tests/test_exchange_rate.py::test_fallback_when_no_rates PASSED
4 passed
```

### Git commit

```bash
git add backend/app/services/exchange_rate.py backend/tests/test_exchange_rate.py
git commit -m "feat: add ExchangeRateService with in-memory cache and httpx fetch

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 4: APScheduler setup

**Files to create:**
- `backend/app/scheduler.py` (new)

**Files to modify:**
- `backend/app/main.py`
- `backend/pyproject.toml` (via `uv add`)

### Steps

- [ ] Add apscheduler dependency: `cd /path/to/numina/backend && uv add apscheduler`

- [ ] Create `backend/app/scheduler.py`:

```python
import logging
import random

from apscheduler.schedulers.background import BackgroundScheduler

from app.database import SessionLocal
from app.services.exchange_rate import ExchangeRateService

logger = logging.getLogger(__name__)

scheduler = BackgroundScheduler()


def fetch_rates_job() -> None:
    """APScheduler job: fetch and store latest exchange rates."""
    db = SessionLocal()
    try:
        ExchangeRateService.fetch_and_store_rates(db)
    except Exception as e:
        logger.error(f"定时汇率更新失败: {e}")
    finally:
        db.close()


def setup_exchange_rate_schedule() -> None:
    """Schedule rate updates every 2 hours from 08:00 to 22:00 with random 0-15 min offset."""
    for hour in [8, 10, 12, 14, 16, 18, 20, 22]:
        offset = random.randint(0, 15)
        scheduler.add_job(
            fetch_rates_job,
            trigger="cron",
            hour=hour,
            minute=offset,
            id=f"exchange_rate_{hour}",
            replace_existing=True,
        )
    logger.info("汇率定时任务已配置（每2小时，08:00-22:00）")
```

- [ ] Modify `backend/app/main.py` lifespan to import and wire up the scheduler. Add imports at the top:

```python
from app.scheduler import fetch_rates_job, scheduler, setup_exchange_rate_schedule
from app.services.exchange_rate import ExchangeRateService
```

- [ ] Replace the lifespan function body in `backend/app/main.py` with:

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        seed_categories(db)
        seed_currencies(db)
        # Auto-generate daily snapshots for all families
        try:
            auto_generate_daily_snapshots(db)
        except Exception as e:
            logger.warning(f"自动快照生成失败: {e}")
        # Fetch exchange rates immediately if none exist
        try:
            from app.models.exchange_rate import ExchangeRate
            has_rates = db.query(ExchangeRate).first() is not None
            if not has_rates:
                logger.info("首次启动，立即获取汇率数据...")
                ExchangeRateService.fetch_and_store_rates(db)
        except Exception as e:
            logger.warning(f"初始汇率获取失败: {e}")
    finally:
        db.close()

    if settings.ENVIRONMENT == "production" and settings.CORS_ORIGINS == ["*"]:
        logger.warning("生产环境 CORS_ORIGINS 设置为 ['*']，建议配置具体域名。")

    setup_exchange_rate_schedule()
    scheduler.start()
    logger.info("APScheduler 已启动")

    yield

    scheduler.shutdown()
    logger.info("APScheduler 已停止")
```

- [ ] Verify: `cd /path/to/numina/backend && uv run pytest tests/ -v` — all tests pass

### Git commit

```bash
git add backend/app/scheduler.py backend/app/main.py backend/pyproject.toml backend/uv.lock
git commit -m "feat: add APScheduler for periodic exchange rate updates every 2 hours

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 5: Currencies router + Pydantic schemas

**Files to create:**
- `backend/app/schemas/currency.py` (new)
- `backend/app/routers/currencies.py` (new)

**Files to modify:**
- `backend/app/main.py`

### Steps

- [ ] Create `backend/app/schemas/currency.py`:

```python
from pydantic import BaseModel


class CurrencyResponse(BaseModel):
    code: str
    name_zh: str
    name_en: str
    symbol: str
    flag_emoji: str
    is_favorite: bool
    sort_order: int

    model_config = {"from_attributes": True}


class RateResponse(BaseModel):
    rate: float
    fetched_at: str
```

- [ ] Create `backend/app/routers/currencies.py`:

```python
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.database import get_db
from app.models.currency import Currency
from app.models.exchange_rate import ExchangeRate
from app.models.user import User
from app.schemas.currency import CurrencyResponse, RateResponse

router = APIRouter(prefix="/currencies", tags=["currencies"])


@router.get("", response_model=list[CurrencyResponse])
def list_currencies(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[CurrencyResponse]:
    """List all currencies: favorites first, then alphabetical by code."""
    currencies = (
        db.query(Currency)
        .order_by(Currency.is_favorite.desc(), Currency.sort_order.asc(), Currency.code.asc())
        .all()
    )
    return [CurrencyResponse.model_validate(c) for c in currencies]


@router.get("/rates", response_model=dict[str, RateResponse])
def list_rates(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, RateResponse]:
    """Return the latest rate for each currency."""
    # Subquery: max fetched_at per target_currency
    from sqlalchemy import func
    subq = (
        db.query(
            ExchangeRate.target_currency,
            func.max(ExchangeRate.fetched_at).label("max_fetched_at"),
        )
        .group_by(ExchangeRate.target_currency)
        .subquery()
    )
    rows = (
        db.query(ExchangeRate)
        .join(
            subq,
            (ExchangeRate.target_currency == subq.c.target_currency)
            & (ExchangeRate.fetched_at == subq.c.max_fetched_at),
        )
        .all()
    )
    return {
        r.target_currency: RateResponse(
            rate=r.rate,
            fetched_at=r.fetched_at.isoformat(),
        )
        for r in rows
    }


@router.get("/rates/{code}", response_model=RateResponse)
def get_rate(
    code: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> RateResponse:
    """Return the latest rate for a single currency code."""
    from fastapi import HTTPException

    if code.upper() == "CNY":
        from datetime import datetime
        return RateResponse(rate=1.0, fetched_at=datetime.now().isoformat())

    row = (
        db.query(ExchangeRate)
        .filter(ExchangeRate.target_currency == code.upper())
        .order_by(ExchangeRate.fetched_at.desc())
        .first()
    )
    if row is None:
        raise HTTPException(status_code=404, detail=f"汇率数据不存在: {code}")
    return RateResponse(rate=row.rate, fetched_at=row.fetched_at.isoformat())
```

- [ ] In `backend/app/main.py`, add the currencies router import alongside the other router imports:

```python
from app.routers import currencies as currencies_router
```

- [ ] Register the router in `backend/app/main.py` after the existing `app.include_router` calls:

```python
app.include_router(currencies_router.router, prefix="/api/v1")
```

- [ ] Verify: `cd /path/to/numina/backend && uv run pytest tests/ -v` — all tests pass

### Git commit

```bash
git add backend/app/schemas/currency.py backend/app/routers/currencies.py backend/app/main.py
git commit -m "feat: add /currencies router with rate endpoints

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---
## Task 6: Dashboard schemas — add currency fields

**Files to modify:**
- `backend/app/schemas/dashboard.py`

### Steps

- [ ] Modify `backend/app/schemas/dashboard.py` — add `currency` and `original_value` fields to `TopAssetItem`:

```python
class TopAssetItem(BaseModel):
    id: str
    name: str
    category_name: str
    icon: str
    current_value: float
    currency: str = "CNY"
    original_value: float = 0.0
```

- [ ] Add `currency` and `original_value` fields to `DailyCostItem`:

```python
class DailyCostItem(BaseModel):
    id: str
    name: str
    category_name: str
    icon: str
    daily_cost: float
    days_used: int
    total_cost: float
    currency: str = "CNY"
    original_value: float = 0.0
```

- [ ] Add `currency` and `original_value` fields to `LowUsageItem`:

```python
class LowUsageItem(BaseModel):
    id: str
    name: str
    category_name: str
    icon: str
    current_value: float
    usage_frequency: str
    purchase_date: str | None = None
    currency: str = "CNY"
    original_value: float = 0.0
```

- [ ] Add `currency`, `original_purchase_price`, and `original_current_value` fields to `InvestmentReturnItem`:

```python
class InvestmentReturnItem(BaseModel):
    id: str
    name: str
    category_name: str
    icon: str
    purchase_price: float
    current_value: float
    return_rate: float
    profit: float
    currency: str = "CNY"
    original_purchase_price: float = 0.0
    original_current_value: float = 0.0
```

- [ ] Verify: `cd /path/to/numina/backend && uv run pytest tests/test_dashboard.py -v` — all dashboard tests pass (defaults mean no breaking change)

### Git commit

```bash
git add backend/app/schemas/dashboard.py
git commit -m "feat: add currency and original_value fields to dashboard schemas

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 7: Dashboard service — add currency conversion

**Files to modify:**
- `backend/app/services/dashboard.py`

### Steps

- [ ] Add `ExchangeRateService` import at the top of `backend/app/services/dashboard.py`:

```python
from app.services.exchange_rate import ExchangeRateService
```

- [ ] Replace `get_overview()` — swap the raw SQL `func.sum` aggregations with per-asset/liability loops that convert each value to `user.default_currency` before summing. Replace the entire function:

```python
def get_overview(db: Session, user: User) -> OverviewResponse:
    family_id = user.family_id
    default_currency = user.default_currency or "CNY"

    assets = (
        db.query(Asset)
        .filter(Asset.family_id == family_id, Asset.is_archived == False)
        .all()
    )
    total_assets_val = sum(
        ExchangeRateService.convert(a.current_value or 0, a.currency or "CNY", default_currency, db)
        for a in assets
    )

    liabilities = (
        db.query(Liability)
        .filter(Liability.family_id == family_id, Liability.is_active == True)
        .all()
    )
    total_liabilities_val = sum(
        ExchangeRateService.convert(
            l.remaining_amount or 0,
            getattr(l, "currency", "CNY") or "CNY",
            default_currency,
            db,
        )
        for l in liabilities
    )

    asset_count = (
        db.query(func.count(Asset.id))
        .filter(Asset.family_id == family_id, Asset.is_archived == False)
        .scalar()
    )

    # Calculate total daily cost (convert each asset's daily cost)
    daily_cost_assets = (
        db.query(Asset)
        .filter(
            Asset.family_id == family_id,
            Asset.is_archived == False,
            Asset.purchase_date != None,
            Asset.purchase_price != None,
        )
        .all()
    )
    total_daily_cost = 0.0
    for a in daily_cost_assets:
        dc = compute_daily_cost(a)
        if dc is not None and dc > 0:
            converted_dc = ExchangeRateService.convert(dc, a.currency or "CNY", default_currency, db)
            total_daily_cost += converted_dc
    total_daily_cost = round(total_daily_cost, 2)

    # Month over month change
    today = date.today()
    last_month = today.replace(day=1) - timedelta(days=1)
    last_snapshot = (
        db.query(AssetSnapshot)
        .filter(
            AssetSnapshot.family_id == family_id,
            AssetSnapshot.user_id == None,
            AssetSnapshot.snapshot_date <= last_month,
        )
        .order_by(AssetSnapshot.snapshot_date.desc())
        .first()
    )
    mom_change = None
    if last_snapshot and last_snapshot.net_worth != 0:
        # Snapshot is stored in CNY; convert to default_currency for comparison
        snapshot_net = ExchangeRateService.convert(
            last_snapshot.net_worth, "CNY", default_currency, db
        )
        current_net = total_assets_val - total_liabilities_val
        if snapshot_net != 0:
            mom_change = round((current_net - snapshot_net) / abs(snapshot_net) * 100, 2)

    return OverviewResponse(
        total_assets=round(total_assets_val, 2),
        total_liabilities=round(total_liabilities_val, 2),
        net_worth=round(total_assets_val - total_liabilities_val, 2),
        asset_count=asset_count,
        month_over_month_change=mom_change,
        total_daily_cost=total_daily_cost,
    )
```

- [ ] Replace `get_allocation()` — convert each asset's `current_value` before grouping. Replace the entire function:

```python
def get_allocation(db: Session, user: User) -> AllocationResponse:
    family_id = user.family_id
    default_currency = user.default_currency or "CNY"

    assets = (
        db.query(Asset)
        .options(joinedload(Asset.category))
        .filter(Asset.family_id == family_id, Asset.is_archived == False)
        .all()
    )

    category_totals: dict[str, dict] = {}
    for a in assets:
        if a.category is None:
            continue
        converted = ExchangeRateService.convert(
            a.current_value or 0, a.currency or "CNY", default_currency, db
        )
        cid = a.category.id
        if cid not in category_totals:
            category_totals[cid] = {
                "name": a.category.name,
                "icon": a.category.icon,
                "color": a.category.color,
                "amount": 0.0,
            }
        category_totals[cid]["amount"] += converted

    total = sum(v["amount"] for v in category_totals.values()) or 1
    items = [
        AllocationItem(
            category_id=cid,
            category_name=v["name"],
            icon=v["icon"],
            color=v["color"],
            amount=round(v["amount"], 2),
            percentage=round(v["amount"] / total * 100, 2),
        )
        for cid, v in category_totals.items()
    ]
    return AllocationResponse(items=items, total=round(total, 2))
```

- [ ] Replace `get_top_assets()` — convert `current_value`, populate `currency` + `original_value`. Replace the entire function:

```python
def get_top_assets(db: Session, user: User, limit: int = 10) -> list[TopAssetItem]:
    default_currency = user.default_currency or "CNY"
    assets = (
        db.query(Asset)
        .options(joinedload(Asset.category))
        .filter(
            Asset.family_id == user.family_id,
            Asset.is_archived == False,
            Asset.current_value != None,
        )
        .all()
    )

    items = []
    for a in assets:
        converted = ExchangeRateService.convert(
            a.current_value or 0, a.currency or "CNY", default_currency, db
        )
        items.append(
            TopAssetItem(
                id=a.id,
                name=a.name,
                category_name=a.category.name if a.category else "",
                icon=a.category.icon if a.category else "",
                current_value=converted,
                currency=a.currency or "CNY",
                original_value=a.current_value or 0,
            )
        )

    items.sort(key=lambda x: x.current_value, reverse=True)
    return items[:limit]
```

- [ ] Replace `get_daily_cost_ranking()` — convert `daily_cost` and `total_cost`, populate `currency` + `original_value`. Replace the entire function:

```python
def get_daily_cost_ranking(db: Session, user: User) -> list[DailyCostItem]:
    default_currency = user.default_currency or "CNY"
    assets = (
        db.query(Asset)
        .options(joinedload(Asset.category))
        .filter(
            Asset.family_id == user.family_id,
            Asset.is_archived == False,
            Asset.purchase_date != None,
            Asset.purchase_price != None,
        )
        .all()
    )

    items = []
    for a in assets:
        dc = compute_daily_cost(a)
        if dc is not None and dc > 0:
            days = (date.today() - a.purchase_date).days
            years = days / 365.0
            total_cost = a.purchase_price + (a.annual_maintenance_cost or 0) * years
            asset_currency = a.currency or "CNY"
            converted_dc = ExchangeRateService.convert(dc, asset_currency, default_currency, db)
            converted_total = ExchangeRateService.convert(total_cost, asset_currency, default_currency, db)
            items.append(
                DailyCostItem(
                    id=a.id,
                    name=a.name,
                    category_name=a.category.name if a.category else "",
                    icon=a.category.icon if a.category else "",
                    daily_cost=converted_dc,
                    days_used=days,
                    total_cost=round(converted_total, 2),
                    currency=asset_currency,
                    original_value=round(total_cost, 2),
                )
            )

    items.sort(key=lambda x: x.daily_cost, reverse=True)
    return items
```

- [ ] Replace `get_low_usage_assets()` — convert `current_value`, populate `currency` + `original_value`. Replace the entire function:

```python
def get_low_usage_assets(db: Session, user: User) -> list[LowUsageItem]:
    default_currency = user.default_currency or "CNY"
    assets = (
        db.query(Asset)
        .options(joinedload(Asset.category))
        .filter(
            Asset.family_id == user.family_id,
            Asset.is_archived == False,
            Asset.usage_frequency.in_(["rarely", "idle"]),
        )
        .all()
    )
    return [
        LowUsageItem(
            id=a.id,
            name=a.name,
            category_name=a.category.name if a.category else "",
            icon=a.category.icon if a.category else "",
            current_value=ExchangeRateService.convert(
                a.current_value or 0, a.currency or "CNY", default_currency, db
            ),
            usage_frequency=a.usage_frequency or "",
            purchase_date=a.purchase_date.isoformat() if a.purchase_date else None,
            currency=a.currency or "CNY",
            original_value=a.current_value or 0,
        )
        for a in assets
    ]
```

- [ ] Replace `get_investment_returns()` — convert `purchase_price`, `current_value`, `profit`, populate `currency` + original fields. Replace the entire function:

```python
def get_investment_returns(db: Session, user: User) -> list[InvestmentReturnItem]:
    default_currency = user.default_currency or "CNY"
    assets = (
        db.query(Asset)
        .options(joinedload(Asset.category))
        .filter(
            Asset.family_id == user.family_id,
            Asset.is_archived == False,
            Asset.asset_type == "financial",
            Asset.purchase_price != None,
            Asset.current_value != None,
        )
        .all()
    )

    items = []
    for a in assets:
        rr = compute_return_rate(a)
        if rr is not None:
            asset_currency = a.currency or "CNY"
            conv_purchase = ExchangeRateService.convert(a.purchase_price, asset_currency, default_currency, db)
            conv_current = ExchangeRateService.convert(a.current_value, asset_currency, default_currency, db)
            items.append(
                InvestmentReturnItem(
                    id=a.id,
                    name=a.name,
                    category_name=a.category.name if a.category else "",
                    icon=a.category.icon if a.category else "",
                    purchase_price=conv_purchase,
                    current_value=conv_current,
                    return_rate=rr,
                    profit=round(conv_current - conv_purchase, 2),
                    currency=asset_currency,
                    original_purchase_price=a.purchase_price,
                    original_current_value=a.current_value,
                )
            )

    items.sort(key=lambda x: x.return_rate, reverse=True)
    return items
```

- [ ] Verify: `cd /path/to/numina/backend && uv run pytest tests/test_dashboard.py -v` — all dashboard tests pass

### Git commit

```bash
git add backend/app/services/dashboard.py
git commit -m "feat: add currency conversion to all dashboard service functions

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---
## Task 8: Snapshot service — convert to CNY

**Files to modify:**
- `backend/app/services/snapshot.py`
- `backend/app/services/dashboard.py` (get_trend function)

### Steps

- [ ] Add `ExchangeRateService` import at the top of `backend/app/services/snapshot.py`:

```python
from app.services.exchange_rate import ExchangeRateService
```

- [ ] In `backend/app/services/snapshot.py`, replace the `generate_snapshots()` function body where it sums asset and liability values. Change the per-member asset sum from:

```python
member_assets = sum(a.current_value or 0 for a in total_assets)
```

to a loop that fetches full Asset objects and converts each to CNY:

```python
assets_full = (
    db.query(Asset)
    .filter(Asset.user_id == member.id, Asset.is_archived == False)
    .all()
)
member_assets = sum(
    ExchangeRateService.convert(a.current_value or 0, a.currency or "CNY", "CNY", db)
    for a in assets_full
)
```

- [ ] Change the per-member liability sum from:

```python
total_liabilities = (
    db.query(Liability)
    .filter(Liability.user_id == member.id, Liability.is_active == True)
    .with_entities(Liability.remaining_amount)
    .all()
)
member_liabilities = sum(l.remaining_amount or 0 for l in total_liabilities)
```

to:

```python
liabilities_full = (
    db.query(Liability)
    .filter(Liability.user_id == member.id, Liability.is_active == True)
    .all()
)
member_liabilities = sum(
    ExchangeRateService.convert(
        l.remaining_amount or 0,
        getattr(l, "currency", "CNY") or "CNY",
        "CNY",
        db,
    )
    for l in liabilities_full
)
```

- [ ] In `backend/app/services/dashboard.py`, replace `get_trend()` to convert CNY snapshot values to the user's `default_currency` at read time. Replace the entire function:

```python
def get_trend(db: Session, user: User, period: str = "month") -> TrendResponse:
    family_id = user.family_id
    default_currency = user.default_currency or "CNY"
    today = date.today()

    if period == "year":
        start_date = today - timedelta(days=365)
    elif period == "quarter":
        start_date = today - timedelta(days=90)
    else:
        start_date = today - timedelta(days=30)

    snapshots = (
        db.query(AssetSnapshot)
        .filter(
            AssetSnapshot.family_id == family_id,
            AssetSnapshot.user_id == None,
            AssetSnapshot.snapshot_date >= start_date,
        )
        .order_by(AssetSnapshot.snapshot_date)
        .all()
    )

    points = [
        TrendPoint(
            date=s.snapshot_date.isoformat(),
            total_assets=ExchangeRateService.convert(s.total_assets, "CNY", default_currency, db),
            total_liabilities=ExchangeRateService.convert(s.total_liabilities, "CNY", default_currency, db),
            net_worth=ExchangeRateService.convert(s.net_worth, "CNY", default_currency, db),
        )
        for s in snapshots
    ]
    return TrendResponse(points=points)
```

- [ ] Verify: `cd /path/to/numina/backend && uv run pytest tests/ -v` — all tests pass

### Git commit

```bash
git add backend/app/services/snapshot.py backend/app/services/dashboard.py
git commit -m "feat: convert asset/liability values to CNY in snapshots, convert trend to default_currency at read time

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 9: Frontend — useCurrencyStore Pinia store

**Files to create:**
- `frontend/src/stores/currency.ts` (new)
- `frontend/src/api/currencies.ts` (new)

**Files to modify:**
- `frontend/src/types/index.ts`
- `frontend/src/main.ts`

### Steps

- [ ] Add `Currency` interface to `frontend/src/types/index.ts` alongside the other interfaces:

```typescript
export interface Currency {
  code: string
  name_zh: string
  name_en: string
  symbol: string
  flag_emoji: string
  is_favorite: boolean
  sort_order: number
}

export interface RateInfo {
  rate: number
  fetched_at: string
}
```

- [ ] Create `frontend/src/api/currencies.ts`:

```typescript
import api from './index'
import type { Currency, RateInfo } from '@/types'

export function getCurrencies(): Promise<Currency[]> {
  return api.get<Currency[]>('/currencies').then(r => r.data)
}

export function getRates(): Promise<Record<string, RateInfo>> {
  return api.get<Record<string, RateInfo>>('/currencies/rates').then(r => r.data)
}

export function getRate(code: string): Promise<RateInfo> {
  return api.get<RateInfo>(`/currencies/rates/${code}`).then(r => r.data)
}
```

- [ ] Create `frontend/src/stores/currency.ts`:

```typescript
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { getCurrencies } from '@/api/currencies'
import type { Currency } from '@/types'

export const useCurrencyStore = defineStore('currency', () => {
  const currencies = ref<Currency[]>([])

  const symbolMap = computed<Record<string, string>>(() =>
    Object.fromEntries(currencies.value.map(c => [c.code, c.symbol]))
  )

  const flagMap = computed<Record<string, string>>(() =>
    Object.fromEntries(currencies.value.map(c => [c.code, c.flag_emoji]))
  )

  const nameMap = computed<Record<string, { zh: string; en: string }>>(() =>
    Object.fromEntries(currencies.value.map(c => [c.code, { zh: c.name_zh, en: c.name_en }]))
  )

  const favorites = computed<Currency[]>(() =>
    currencies.value.filter(c => c.is_favorite)
  )

  const nonFavorites = computed<Currency[]>(() =>
    currencies.value.filter(c => !c.is_favorite)
  )

  async function fetchCurrencies(): Promise<void> {
    if (currencies.value.length > 0) return
    try {
      currencies.value = await getCurrencies()
    } catch (e) {
      console.warn('[CurrencyStore] Failed to fetch currencies:', e)
    }
  }

  return { currencies, symbolMap, flagMap, nameMap, favorites, nonFavorites, fetchCurrencies }
})
```

- [ ] Modify `frontend/src/main.ts` — after the app is mounted and auth is initialized, call `fetchCurrencies()`. Find the block where the app is mounted (the `app.mount('#app')` call) and add the currency store initialization. The exact location depends on the current `main.ts` structure; add it in the same async init block as auth:

```typescript
import { useCurrencyStore } from '@/stores/currency'

// Inside the async init block, after auth initialization:
const currencyStore = useCurrencyStore()
currencyStore.fetchCurrencies()  // fire-and-forget, non-blocking
```

- [ ] Build check: `cd /path/to/numina/frontend && npm run build` — zero TypeScript errors

### Git commit

```bash
git add frontend/src/stores/currency.ts frontend/src/api/currencies.ts \
        frontend/src/types/index.ts frontend/src/main.ts
git commit -m "feat: add useCurrencyStore and currencies API client

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 10: Frontend — i18n keys

**Files to modify:**
- `frontend/src/i18n/locales/zh-CN.ts`
- `frontend/src/i18n/locales/en-US.ts`

### Steps

- [ ] Add `currency` section to `frontend/src/i18n/locales/zh-CN.ts` inside the exported default object, after the `auth` section:

```typescript
  currency: {
    searchPlaceholder: '搜索币种名称或代码',
    favorites: '常用货币',
    all: '全部货币',
    selectCurrency: '选择币种',
    rateInfo: '1 {from} = {rate} {to}',
    rateUpdatedAt: '汇率更新时间：{time}',
    fetchFailed: '汇率获取失败，使用缓存数据',
  },
```

- [ ] Add `currency` section to `frontend/src/i18n/locales/en-US.ts` inside the exported default object, after the `auth` section:

```typescript
  currency: {
    searchPlaceholder: 'Search by name or code',
    favorites: 'Popular Currencies',
    all: 'All Currencies',
    selectCurrency: 'Select Currency',
    rateInfo: '1 {from} = {rate} {to}',
    rateUpdatedAt: 'Rate updated: {time}',
    fetchFailed: 'Rate fetch failed, using cached data',
  },
```

- [ ] Build check: `cd /path/to/numina/frontend && npm run build` — zero errors

### Git commit

```bash
git add frontend/src/i18n/locales/zh-CN.ts frontend/src/i18n/locales/en-US.ts
git commit -m "feat: add currency i18n keys for zh-CN and en-US

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---
## Task 11: Frontend — CurrencyPicker component

**Files to create:**
- `frontend/src/components/common/CurrencyPicker.vue` (new)

### Steps

- [ ] Create `frontend/src/components/common/CurrencyPicker.vue`:

```vue
<template>
  <van-popup
    :show="show"
    position="bottom"
    round
    :style="{ height: '80vh' }"
    @update:show="$emit('update:show', $event)"
  >
    <div class="currency-picker">
      <div class="picker-header">
        <span class="picker-title">{{ t('currency.selectCurrency') }}</span>
        <van-icon name="cross" class="picker-close" @click="$emit('update:show', false)" />
      </div>

      <van-search
        v-model="searchQuery"
        :placeholder="t('currency.searchPlaceholder')"
        class="picker-search"
      />

      <div class="picker-list">
        <!-- Favorites section: always visible, not filtered -->
        <van-cell-group :title="t('currency.favorites')" inset>
          <van-cell
            v-for="cur in currencyStore.favorites"
            :key="cur.code"
            :title="`${cur.flag_emoji} ${locale === 'zh-CN' ? cur.name_zh : cur.name_en}（${cur.code}）${cur.symbol}`"
            :class="{ 'currency-selected': modelValue === cur.code }"
            clickable
            @click="onSelect(cur.code)"
          >
            <template #right-icon>
              <van-icon v-if="modelValue === cur.code" name="success" class="check-icon" />
            </template>
          </van-cell>
        </van-cell-group>

        <!-- All currencies section: filtered by search -->
        <van-cell-group
          v-if="filteredNonFavorites.length > 0"
          :title="t('currency.all')"
          inset
          class="all-section"
        >
          <van-cell
            v-for="cur in filteredNonFavorites"
            :key="cur.code"
            :title="`${cur.flag_emoji} ${locale === 'zh-CN' ? cur.name_zh : cur.name_en}（${cur.code}）${cur.symbol}`"
            :class="{ 'currency-selected': modelValue === cur.code }"
            clickable
            @click="onSelect(cur.code)"
          >
            <template #right-icon>
              <van-icon v-if="modelValue === cur.code" name="success" class="check-icon" />
            </template>
          </van-cell>
        </van-cell-group>
      </div>
    </div>
  </van-popup>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { useCurrencyStore } from '@/stores/currency'

const props = defineProps<{
  modelValue: string
  show: boolean
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', value: string): void
  (e: 'update:show', value: boolean): void
}>()

const { t, locale } = useI18n()
const currencyStore = useCurrencyStore()

const searchQuery = ref('')

const filteredNonFavorites = computed(() => {
  const q = searchQuery.value.trim().toLowerCase()
  if (!q) return currencyStore.nonFavorites
  return currencyStore.nonFavorites.filter(c =>
    c.code.toLowerCase().includes(q) ||
    c.name_zh.toLowerCase().includes(q) ||
    c.name_en.toLowerCase().includes(q)
  )
})

function onSelect(code: string) {
  emit('update:modelValue', code)
  emit('update:show', false)
}
</script>

<style scoped>
.currency-picker {
  display: flex;
  flex-direction: column;
  height: 100%;
}
.picker-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 16px 8px;
}
.picker-title {
  font-size: 16px;
  font-weight: 600;
}
.picker-close {
  font-size: 18px;
  color: var(--van-gray-6);
  cursor: pointer;
}
.picker-search {
  padding: 0 8px 8px;
}
.picker-list {
  flex: 1;
  overflow-y: auto;
  padding-bottom: 24px;
}
.all-section {
  margin-top: 8px;
}
.currency-selected {
  background: var(--van-primary-color-light);
}
.check-icon {
  color: var(--van-primary-color);
  font-size: 16px;
}
</style>
```

- [ ] Build check: `cd /path/to/numina/frontend && npm run build` — zero errors

### Git commit

```bash
git add frontend/src/components/common/CurrencyPicker.vue
git commit -m "feat: add CurrencyPicker bottom-sheet component with search

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 12: Frontend — CurrencySelector component + useExchangeRate composable

**Files to create:**
- `frontend/src/composables/useExchangeRate.ts` (new)
- `frontend/src/components/common/CurrencySelector.vue` (new)

### Steps

- [ ] Create `frontend/src/composables/useExchangeRate.ts`:

```typescript
import { useI18n } from 'vue-i18n'
import { getRate } from '@/api/currencies'
import type { RateInfo } from '@/types'
import { useCurrencyStore } from '@/stores/currency'

// Module-level cache — persists across component instances within a page session
const rateCache = new Map<string, RateInfo>()

export function useExchangeRate() {
  const { t, locale } = useI18n()
  const currencyStore = useCurrencyStore()

  async function fetchRate(currency: string): Promise<RateInfo | null> {
    if (currency === 'CNY') {
      return { rate: 1.0, fetched_at: new Date().toISOString() }
    }
    if (rateCache.has(currency)) {
      return rateCache.get(currency)!
    }
    try {
      const data = await getRate(currency)
      rateCache.set(currency, data)
      return data
    } catch (e) {
      console.warn(`[useExchangeRate] Failed to fetch rate for ${currency}:`, e)
      return null
    }
  }

  function getRateInfo(
    originalAmount: number,
    sourceCurrency: string,
    targetCurrency: string,
    rateData: RateInfo,
  ): { originalText: string; rateText: string; updatedAt: string } {
    const symbolMap = currencyStore.symbolMap
    const sourceSymbol = symbolMap[sourceCurrency] || sourceCurrency
    const targetSymbol = symbolMap[targetCurrency] || targetCurrency

    // Format original amount
    const originalText = `${sourceSymbol}${originalAmount.toLocaleString(undefined, {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    })}`

    // Rate: 1 sourceCurrency = X targetCurrency
    // API rate = targetCurrency per 1 CNY
    // If source=USD, target=CNY: 1 USD = (1/rate_USD) CNY
    // If source=USD, target=EUR: 1 USD = (rate_EUR/rate_USD) EUR
    // rateData.rate is already the rate for sourceCurrency (target per 1 CNY)
    // So 1 sourceCurrency = (1/rateData.rate) CNY
    // For display we show: 1 {from} = {1/rate} {to} when to=CNY
    const displayRate = targetCurrency === 'CNY'
      ? (1 / rateData.rate).toFixed(4)
      : rateData.rate.toFixed(4)

    const rateText = t('currency.rateInfo', {
      from: sourceCurrency,
      rate: displayRate,
      to: targetCurrency,
    })

    // Format timestamp
    const dt = new Date(rateData.fetched_at)
    let updatedAtFormatted: string
    if (locale.value === 'zh-CN') {
      updatedAtFormatted = dt.toLocaleString('zh-CN', {
        year: 'numeric', month: '2-digit', day: '2-digit',
        hour: '2-digit', minute: '2-digit', second: '2-digit',
        hour12: false,
      }).replace(/\//g, '-')
    } else {
      updatedAtFormatted = dt.toLocaleString('en-US', {
        year: 'numeric', month: 'short', day: '2-digit',
        hour: '2-digit', minute: '2-digit', second: '2-digit',
        hour12: false,
      })
    }

    const updatedAt = t('currency.rateUpdatedAt', { time: updatedAtFormatted })

    return { originalText, rateText, updatedAt }
  }

  return { fetchRate, getRateInfo }
}
```

- [ ] Create `frontend/src/components/common/CurrencySelector.vue`:

```vue
<template>
  <div class="currency-selector">
    <button type="button" class="currency-btn" @click="showPicker = true">
      <span class="currency-flag">{{ flagMap[selectedCurrency] || '' }}</span>
      <span class="currency-symbol">{{ symbolMap[selectedCurrency] || selectedCurrency }}</span>
      <van-icon name="arrow-down" class="currency-arrow" />
    </button>
    <div class="currency-divider" />
    <input
      class="currency-input"
      type="number"
      inputmode="decimal"
      :value="modelValue.amount"
      :placeholder="'0.00'"
      @input="onAmountInput"
    />
    <CurrencyPicker
      v-model="selectedCurrency"
      :show="showPicker"
      @update:show="showPicker = $event"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { useCurrencyStore } from '@/stores/currency'
import CurrencyPicker from './CurrencyPicker.vue'

const props = defineProps<{
  modelValue: { amount: number; currency: string }
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', value: { amount: number; currency: string }): void
}>()

const authStore = useAuthStore()
const currencyStore = useCurrencyStore()

const showPicker = ref(false)
const selectedCurrency = ref(props.modelValue.currency || authStore.user?.default_currency || 'CNY')

const symbolMap = computed(() => currencyStore.symbolMap)
const flagMap = computed(() => currencyStore.flagMap)

watch(selectedCurrency, (code) => {
  emit('update:modelValue', { amount: props.modelValue.amount, currency: code })
})

watch(() => props.modelValue.currency, (code) => {
  if (code && code !== selectedCurrency.value) {
    selectedCurrency.value = code
  }
})

function onAmountInput(e: Event) {
  const val = parseFloat((e.target as HTMLInputElement).value) || 0
  emit('update:modelValue', { amount: val, currency: selectedCurrency.value })
}
</script>

<style scoped>
.currency-selector {
  display: flex;
  align-items: center;
  border: 1px solid var(--van-gray-3);
  border-radius: 8px;
  overflow: hidden;
  background: var(--van-white);
}
.currency-btn {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 10px 12px;
  background: var(--van-gray-1);
  border: none;
  cursor: pointer;
  white-space: nowrap;
  font-size: 14px;
}
.currency-flag {
  font-size: 16px;
}
.currency-symbol {
  font-weight: 600;
  color: var(--van-text-color);
}
.currency-arrow {
  font-size: 12px;
  color: var(--van-gray-6);
}
.currency-divider {
  width: 1px;
  height: 24px;
  background: var(--van-gray-3);
}
.currency-input {
  flex: 1;
  padding: 10px 12px;
  border: none;
  outline: none;
  font-size: 16px;
  background: transparent;
  color: var(--van-text-color);
}
.currency-input::placeholder {
  color: var(--van-gray-5);
}
</style>
```

- [ ] Build check: `cd /path/to/numina/frontend && npm run build` — zero errors

### Git commit

```bash
git add frontend/src/composables/useExchangeRate.ts frontend/src/components/common/CurrencySelector.vue
git commit -m "feat: add useExchangeRate composable and CurrencySelector input component

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---
## Task 13: Frontend — MoneyDisplay update

**Files to modify:**
- `frontend/src/components/common/MoneyDisplay.vue`

### Steps

- [ ] Replace the entire `frontend/src/components/common/MoneyDisplay.vue` with the updated version that adds `sourceCurrency`/`originalValue` props, replaces the hardcoded `CURRENCY_SYMBOLS` map with the store, and adds the info popover:

```vue
<template>
  <span class="money-display" :class="[colorClass, sizeClass]">
    <span class="money-sign">{{ sign }}</span>
    <span class="money-prefix">{{ currencySymbol }}</span>
    <span class="money-value">{{ displayValue }}</span>
    <van-popover
      v-if="showInfoIcon"
      v-model:show="showPopover"
      placement="top"
      :actions="[]"
    >
      <template #reference>
        <van-icon
          name="info-o"
          class="rate-info-icon"
          @click.stop="onInfoClick"
        />
      </template>
      <div class="rate-popover-content">
        <template v-if="rateInfo">
          {{ rateInfo.originalText }}（{{ rateInfo.rateText }}，{{ rateInfo.updatedAt }}）
        </template>
        <template v-else>
          {{ t('currency.fetchFailed') }}
        </template>
      </div>
    </van-popover>
  </span>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { useCurrency } from '@/composables/useCurrency'
import { useCurrencyStore } from '@/stores/currency'
import { useExchangeRate } from '@/composables/useExchangeRate'

const props = withDefaults(defineProps<{
  amount: number
  size?: 'small' | 'normal' | 'large'
  showSign?: boolean
  colorful?: boolean
  sourceCurrency?: string
  originalValue?: number
}>(), {
  size: 'normal',
  showSign: false,
  colorful: false,
})

const { t } = useI18n()
const { currency } = useCurrency()
const currencyStore = useCurrencyStore()
const { fetchRate, getRateInfo } = useExchangeRate()

const CURRENCY_LOCALES: Record<string, string> = {
  CNY: 'zh-CN',
  USD: 'en-US',
  EUR: 'de-DE',
  GBP: 'en-GB',
  JPY: 'ja-JP',
  HKD: 'zh-HK',
  SGD: 'en-SG',
  AUD: 'en-AU',
  CAD: 'en-CA',
  CHF: 'de-CH',
  RUB: 'ru-RU',
  INR: 'hi-IN',
  BRL: 'pt-BR',
}

const currencySymbol = computed(() => currencyStore.symbolMap[currency.value] || currency.value)
const locale = computed(() => CURRENCY_LOCALES[currency.value] || 'zh-CN')

const displayValue = computed(() => {
  const abs = Math.abs(props.amount)

  if (currency.value === 'CNY') {
    if (abs >= 100000000) {
      return `${(abs / 100000000).toFixed(2)}亿`
    } else if (abs >= 10000) {
      return `${(abs / 10000).toFixed(2)}万`
    }
  }

  if (abs >= 1000) {
    return abs.toLocaleString(locale.value, { minimumFractionDigits: 0, maximumFractionDigits: 0 })
  }
  return abs.toLocaleString(locale.value, { minimumFractionDigits: 2, maximumFractionDigits: 2 })
})

const sign = computed(() => {
  if (!props.showSign) return ''
  return props.amount >= 0 ? '+' : '-'
})

const colorClass = computed(() => {
  if (!props.colorful) return ''
  return props.amount >= 0 ? 'money-positive' : 'money-negative'
})

const sizeClass = computed(() => `money-${props.size}`)

// Info icon logic
const showInfoIcon = computed(() =>
  !!props.sourceCurrency &&
  props.sourceCurrency !== currency.value &&
  props.originalValue !== undefined
)

const showPopover = ref(false)
const rateInfo = ref<{ originalText: string; rateText: string; updatedAt: string } | null>(null)

async function onInfoClick() {
  if (!props.sourceCurrency || props.originalValue === undefined) return
  showPopover.value = true
  if (!rateInfo.value) {
    const data = await fetchRate(props.sourceCurrency)
    if (data) {
      rateInfo.value = getRateInfo(props.originalValue, props.sourceCurrency, currency.value, data)
    }
  }
}
</script>

<style scoped>
.money-display {
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
  display: inline-flex;
  align-items: center;
  gap: 2px;
}
.money-prefix {
  margin-right: 1px;
}
.money-small {
  font-size: 12px;
}
.money-normal {
  font-size: 14px;
}
.money-large {
  font-size: 24px;
  font-weight: 600;
}
.money-positive {
  color: #07c160;
}
.money-negative {
  color: #ee0a24;
}
.rate-info-icon {
  font-size: 12px;
  color: var(--van-gray-5);
  cursor: pointer;
  margin-left: 2px;
  vertical-align: middle;
}
.rate-popover-content {
  padding: 8px 12px;
  font-size: 12px;
  color: var(--van-text-color);
  max-width: 240px;
  line-height: 1.5;
}
</style>
```

- [ ] Build check: `cd /path/to/numina/frontend && npm run build` — zero errors

### Git commit

```bash
git add frontend/src/components/common/MoneyDisplay.vue
git commit -m "feat: update MoneyDisplay to use currency store and show rate info popover

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 14: Frontend — update pages (Settings, AssetForm, LiabilityForm, WishDetail)

**Files to modify:**
- `frontend/src/pages/SettingsPage.vue`
- `frontend/src/components/asset/AssetForm.vue`
- `frontend/src/components/liability/LiabilityForm.vue` (or `LiabilityFormPage.vue` — check which file contains the form fields)
- `frontend/src/pages/WishDetailPage.vue`
- `frontend/src/pages/WishListPage.vue`
- `frontend/src/pages/DashboardPage.vue`

### Steps

#### SettingsPage.vue

- [ ] In `frontend/src/pages/SettingsPage.vue`, import `CurrencyPicker` and `useCurrencyStore`:

```typescript
import CurrencyPicker from '@/components/common/CurrencyPicker.vue'
import { useCurrencyStore } from '@/stores/currency'
```

- [ ] Add `currencyStore` to the script setup:

```typescript
const currencyStore = useCurrencyStore()
```

- [ ] Replace the `currencyLabel` computed (currently just shows the code) with one that shows name + code:

```typescript
const currencyLabel = computed(() => {
  const code = authStore.user?.default_currency || 'CNY'
  const names = currencyStore.nameMap[code]
  if (!names) return code
  const name = locale.value === 'zh-CN' ? names.zh : names.en
  return `${name} (${code})`
})
```

- [ ] Update the currency cell in the template to use `currencyLabel`:

```html
<van-cell
  :title="t('settings.defaultCurrency')"
  :value="currencyLabel"
  @click="showCurrencyPicker = true"
  is-link
/>
```

- [ ] Replace the existing Currency Picker popup block (the `van-popup` with `van-picker` for currencies) with the new `CurrencyPicker` component:

```html
<!-- Currency Picker -->
<CurrencyPicker
  v-model="selectedCurrencyCode"
  :show="showCurrencyPicker"
  @update:show="showCurrencyPicker = $event"
/>
```

- [ ] Add `selectedCurrencyCode` ref and wire it to the settings update:

```typescript
const selectedCurrencyCode = ref(authStore.user?.default_currency || 'CNY')

watch(selectedCurrencyCode, (code) => {
  updateSetting('default_currency', code)
})
```

- [ ] Remove the old `currencyOptions` array and `onCurrencyConfirm` function (they are replaced by the above).

#### AssetForm.vue

- [ ] In `frontend/src/components/asset/AssetForm.vue`, import `CurrencySelector`:

```typescript
import CurrencySelector from '@/components/common/CurrencySelector.vue'
```

- [ ] Find the `purchase_price` input field and replace it with `CurrencySelector`. The form data object should have `purchase_price` and `currency` fields. Replace the van-field for purchase_price:

```html
<!-- Before: -->
<van-field v-model="form.purchase_price" type="number" :label="t('asset.purchasePrice')" />

<!-- After: -->
<van-field :label="t('asset.purchasePrice')" :border="false">
  <template #input>
    <CurrencySelector
      :model-value="{ amount: form.purchase_price || 0, currency: form.currency || defaultCurrency }"
      @update:model-value="val => { form.purchase_price = val.amount; form.currency = val.currency }"
    />
  </template>
</van-field>
```

- [ ] Do the same for `current_value` field:

```html
<van-field :label="t('asset.currentValue')" :border="false">
  <template #input>
    <CurrencySelector
      :model-value="{ amount: form.current_value || 0, currency: form.currency || defaultCurrency }"
      @update:model-value="val => { form.current_value = val.amount; form.currency = val.currency }"
    />
  </template>
</van-field>
```

- [ ] Add `defaultCurrency` computed from auth store:

```typescript
import { useAuthStore } from '@/stores/auth'
const authStore = useAuthStore()
const defaultCurrency = computed(() => authStore.user?.default_currency || 'CNY')
```

- [ ] Ensure `form.currency` is initialized in the form object (it should already exist on the Asset model; if not, add it with default `'CNY'`).

#### LiabilityForm (check file location first)

- [ ] Check whether the liability form fields live in `frontend/src/components/liability/LiabilityForm.vue` or `frontend/src/pages/LiabilityFormPage.vue`. Read the file that contains `original_amount` and `monthly_payment` van-field inputs.

- [ ] Import `CurrencySelector` in that file:

```typescript
import CurrencySelector from '@/components/common/CurrencySelector.vue'
```

- [ ] Replace the `original_amount` van-field with `CurrencySelector`:

```html
<van-field :label="t('liability.originalAmount')" :border="false">
  <template #input>
    <CurrencySelector
      :model-value="{ amount: form.original_amount || 0, currency: form.currency || defaultCurrency }"
      @update:model-value="val => { form.original_amount = val.amount; form.currency = val.currency }"
    />
  </template>
</van-field>
```

- [ ] Replace the `monthly_payment` van-field with `CurrencySelector` (currency locked to same as original_amount):

```html
<van-field :label="t('liability.monthlyPayment')" :border="false">
  <template #input>
    <CurrencySelector
      :model-value="{ amount: form.monthly_payment || 0, currency: form.currency || defaultCurrency }"
      @update:model-value="val => { form.monthly_payment = val.amount }"
    />
  </template>
</van-field>
```

- [ ] Ensure `form.currency` is initialized with `'CNY'` default in the form object.

#### WishDetailPage.vue and WishListPage.vue

- [ ] In `frontend/src/pages/WishDetailPage.vue`, import `CurrencySelector` and replace the `expected_price` input:

```typescript
import CurrencySelector from '@/components/common/CurrencySelector.vue'
```

```html
<van-field :label="'期望价格'" :border="false">
  <template #input>
    <CurrencySelector
      :model-value="{ amount: form.expected_price || 0, currency: form.currency || defaultCurrency }"
      @update:model-value="val => { form.expected_price = val.amount; form.currency = val.currency }"
    />
  </template>
</van-field>
```

- [ ] Where `MoneyDisplay` is used to show `expected_price` in `WishDetailPage.vue` and `WishListPage.vue`, pass `sourceCurrency` and `originalValue` from the API response:

```html
<!-- Before: -->
<MoneyDisplay :amount="wish.expected_price" />

<!-- After: -->
<MoneyDisplay
  :amount="wish.expected_price"
  :source-currency="wish.currency"
  :original-value="wish.expected_price"
/>
```

Note: Since wishes are not converted by the backend (no dashboard aggregation), `sourceCurrency` and `originalValue` will be the same value here. The `ⓘ` icon will only appear if `wish.currency` differs from the user's `default_currency`.

#### DashboardPage.vue

- [ ] In `frontend/src/pages/DashboardPage.vue`, find all `MoneyDisplay` usages that display values from dashboard API responses (`topAssets`, `dailyCostRanking`, `lowUsage`, `investmentReturns`). Update each to pass `sourceCurrency` and `originalValue`:

For top assets list:
```html
<MoneyDisplay
  :amount="asset.current_value"
  :source-currency="asset.currency"
  :original-value="asset.original_value"
/>
```

For daily cost ranking:
```html
<MoneyDisplay
  :amount="item.daily_cost"
  :source-currency="item.currency"
  :original-value="item.original_value"
/>
```

For low usage assets:
```html
<MoneyDisplay
  :amount="item.current_value"
  :source-currency="item.currency"
  :original-value="item.original_value"
/>
```

For investment returns:
```html
<MoneyDisplay
  :amount="item.current_value"
  :source-currency="item.currency"
  :original-value="item.original_current_value"
/>
```

### Final verification

- [ ] Run full backend test suite: `cd /path/to/numina/backend && uv run pytest tests/ -v`

Expected output:
```
tests/test_auth.py::... PASSED (10 tests)
tests/test_assets.py::... PASSED (11 tests)
tests/test_liabilities.py::... PASSED (8 tests)
tests/test_dashboard.py::... PASSED (7 tests)
tests/test_exchange_rate.py::... PASSED (4 tests)
40 passed
```

- [ ] Run frontend build: `cd /path/to/numina/frontend && npm run build`

Expected output:
```
vite v5.x.x building for production...
✓ built in X.XXs
```
Zero TypeScript errors, zero build errors.

### Git commit

```bash
git add frontend/src/pages/SettingsPage.vue \
        frontend/src/components/asset/AssetForm.vue \
        frontend/src/pages/WishDetailPage.vue \
        frontend/src/pages/WishListPage.vue \
        frontend/src/pages/DashboardPage.vue
# Also add LiabilityForm file (whichever contains the form fields)
git commit -m "feat: integrate CurrencySelector into forms and MoneyDisplay into dashboard pages

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Implementation Notes

### Auth dependency path

The currencies router uses `get_current_user`. Check the exact import path in existing routers — it is likely `from app.auth.dependencies import get_current_user` or `from app.auth import get_current_user`. Match the pattern used in `backend/app/routers/assets.py`.

### Asset model `currency` field

The spec states `assets` already has a `currency` field. Verify this before Task 7 by reading `backend/app/models/asset.py`. If the field is missing, add it the same way as for Liability in Task 1.

### `get_db` dependency

The currencies router uses `get_db`. Verify the import path from existing routers — likely `from app.database import get_db`.

### `user.default_currency` fallback

`user.default_currency` may be `None` for users created before this feature. Always use `user.default_currency or "CNY"` throughout the service layer.

### APScheduler and test isolation

APScheduler's `BackgroundScheduler` starts a daemon thread. In tests, the scheduler is never started (lifespan is not invoked by TestClient by default in pytest). No test isolation issues expected.

### Frontend `main.ts` structure

Read `frontend/src/main.ts` before Task 9 to find the exact location of the auth init block. The `fetchCurrencies()` call should be fire-and-forget (no `await`) so it does not block app startup.

### Liability form file location

Before Task 14, read both `frontend/src/components/liability/LiabilityForm.vue` and `frontend/src/pages/LiabilityFormPage.vue` to determine which file contains the `original_amount` and `monthly_payment` input fields.
