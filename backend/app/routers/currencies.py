from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.auth.deps import get_current_user
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
    from datetime import datetime

    if code.upper() == "CNY":
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