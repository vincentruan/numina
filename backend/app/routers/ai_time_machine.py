"""资产时光机 API 端点 — What-if 模拟、财务推演、购买力计算。"""

from fastapi import APIRouter, Depends, Query

from app.auth.deps import require_adult
from app.models.user import User
from app.schemas.purchasing_power import PurchasingPowerResponse
from app.services.purchasing_power import calculate_purchasing_power

router = APIRouter(prefix="/ai", tags=["ai-time-machine"])


@router.get("/purchasing-power", response_model=PurchasingPowerResponse)
def get_purchasing_power(
    amount: float = Query(..., gt=0),
    from_year: int = Query(..., ge=1990, le=2050),
    to_year: int = Query(..., ge=1990, le=2050),
    custom_inflation_rate: float | None = Query(None, ge=0, le=1),
    user: User = Depends(require_adult),
):
    return calculate_purchasing_power(
        amount=amount,
        from_year=from_year,
        to_year=to_year,
        custom_inflation_rate=custom_inflation_rate,
    )
