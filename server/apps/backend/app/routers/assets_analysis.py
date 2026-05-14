"""资产分析工具端点 — 买租计算器、消费等价换算（纯计算，无 LLM）。"""

from datetime import date

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict, field_validator
from sqlalchemy.orm import Session

from apps.backend.app.auth.deps import require_adult
from apps.backend.app.database import get_db
from apps.backend.app.errors import AppError, ErrorCode
from apps.backend.app.models.asset import Asset
from apps.backend.app.models.user import User

router = APIRouter(tags=["assets-analysis"])


class BuyVsRentRequest(BaseModel):
    purchase_price: float
    monthly_rent: float
    usage_months: int
    annual_maintenance_cost: float = 0.0
    depreciation_years: int = 10
    residual_value_rate: float = 0.1

    @field_validator("usage_months")
    @classmethod
    def validate_usage_months(cls, v: int) -> int:
        if not (1 <= v <= 600):
            raise ValueError("usage_months 必须在 1-600 之间")
        return v

    @field_validator("residual_value_rate")
    @classmethod
    def validate_residual_rate(cls, v: float) -> float:
        if not (0.0 <= v <= 1.0):
            raise ValueError("residual_value_rate 必须在 0-1 之间")
        return v


class BuyVsRentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    buy_total: float
    rent_total: float
    breakeven_months: float | None
    recommendation: str
    buy_advantage_pct: float


@router.post("/assets/buy-vs-rent", response_model=BuyVsRentResponse)
def calculate_buy_vs_rent(
    body: BuyVsRentRequest,
    user: User = Depends(require_adult),
):
    usage_years = body.usage_months / 12.0
    total_maintenance = body.annual_maintenance_cost * usage_years
    residual_value = body.purchase_price * body.residual_value_rate * max(
        0.0, 1.0 - usage_years / body.depreciation_years
    )
    buy_total = body.purchase_price + total_maintenance - residual_value
    rent_total = body.monthly_rent * body.usage_months

    monthly_maintenance = body.annual_maintenance_cost / 12.0
    if body.monthly_rent > monthly_maintenance:
        breakeven_months: float | None = body.purchase_price / (body.monthly_rent - monthly_maintenance)
    else:
        breakeven_months = None

    diff_pct = (rent_total - buy_total) / rent_total * 100 if rent_total else 0.0
    if abs(diff_pct) < 10.0:
        recommendation = "两者相近，建议租赁以保持灵活性"
    elif buy_total < rent_total:
        recommendation = "购买更划算"
    else:
        recommendation = "租赁更划算"

    return BuyVsRentResponse(
        buy_total=round(buy_total, 2),
        rent_total=round(rent_total, 2),
        breakeven_months=round(breakeven_months, 1) if breakeven_months is not None else None,
        recommendation=recommendation,
        buy_advantage_pct=round(diff_pct, 1),
    )


@router.get("/assets/{asset_id}/cost-equivalence")
def get_cost_equivalence(
    asset_id: int,
    hourly_wage: float = Query(50.0, gt=0),
    yield_rate: float = Query(0.05, ge=0, le=1),
    years: int = Query(10, ge=1, le=30),
    user: User = Depends(require_adult),
    db: Session = Depends(get_db),
):
    asset = db.query(Asset).filter(
        Asset.id == asset_id,
        Asset.family_id == user.family_id,
        Asset.is_archived.is_(False),
    ).first()
    if not asset:
        raise AppError(ErrorCode.ASSET_NOT_FOUND)

    if asset.purchase_price is None or asset.purchase_date is None:
        return {
            "asset_id": asset.id,
            "asset_name": asset.name,
            "held_days": None,
            "total_held_cost": None,
            "daily_cost": None,
            "time_cost_hours": None,
            "opportunity_cost": None,
        }

    today = date.today()
    held_days = (today - asset.purchase_date).days
    if held_days <= 0:
        held_days = 1

    annual_maintenance = asset.annual_maintenance_cost or 0.0
    total_held_cost = asset.purchase_price + annual_maintenance * (held_days / 365.0)
    daily_cost = total_held_cost / held_days
    time_cost_hours = total_held_cost / hourly_wage
    opportunity_cost = total_held_cost * ((1 + yield_rate) ** years) - total_held_cost

    return {
        "asset_id": asset.id,
        "asset_name": asset.name,
        "held_days": held_days,
        "total_held_cost": round(total_held_cost, 2),
        "daily_cost": round(daily_cost, 4),
        "time_cost_hours": round(time_cost_hours, 2),
        "opportunity_cost": round(opportunity_cost, 2),
    }


@router.get("/assets/{asset_id}/purchasing-power")
def get_asset_purchasing_power(
    asset_id: int,
    user: User = Depends(require_adult),
    db: Session = Depends(get_db),
):
    from datetime import date as date_type

    from apps.backend.app.services.purchasing_power import calculate_purchasing_power

    asset = (
        db.query(Asset)
        .filter(
            Asset.id == asset_id,
            Asset.family_id == user.family_id,
            Asset.is_archived.is_(False),
        )
        .first()
    )
    if not asset:
        raise AppError(ErrorCode.ASSET_NOT_FOUND)

    if asset.purchase_price is None or asset.purchase_date is None:
        return {
            "original_amount": None,
            "adjusted_amount": None,
            "from_year": None,
            "to_year": None,
            "cumulative_inflation": None,
            "annual_avg_inflation": None,
            "explanation": None,
        }

    return calculate_purchasing_power(
        amount=asset.purchase_price,
        from_year=asset.purchase_date.year,
        to_year=date_type.today().year,
    )
