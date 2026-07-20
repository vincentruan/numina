from decimal import Decimal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from apps.backend.app.auth.deps import require_adult
from apps.backend.app.database import get_db
from apps.backend.app.models.user import User
from apps.backend.app.schemas.liability import (
    LiabilityCreate,
    LiabilityResponse,
    LiabilityUpdate,
    PaymentRequest,
)
from apps.backend.app.schemas.liability_simulate import (
    SimulateRequest,
    SimulateResponse,
)
from apps.backend.app.services import liability as liability_service
from apps.backend.app.services.activity import record_activity
from packages.domain.liability_calculator import calc_amortization

router = APIRouter(prefix="/liabilities", tags=["liabilities"])


@router.get("", response_model=list[LiabilityResponse])
def list_liabilities(
    is_active: bool | None = Query(None),
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    return liability_service.list_liabilities(db, user, is_active)


@router.post("", response_model=LiabilityResponse, status_code=201)
def create_liability(
    req: LiabilityCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    liability = liability_service.create_liability(db, user, req)
    record_activity(db, user, "create", "liability", liability.id, f"添加负债「{liability.name}」", liability.original_amount)
    return liability


@router.post("/simulate", response_model=SimulateResponse)
def simulate_liability(
    req: SimulateRequest,
    user: User = Depends(require_adult),
):
    """L2: forecast total interest + months, with optional extra-payment comparison.

    Pure compute (no db write). When extra_monthly > 0, also computes the
    baseline (extra=0) so the frontend shows '省 ¥Y, 提前 N 月'.
    """
    extra = req.extra_monthly or Decimal("0")
    result = calc_amortization(req.remaining, req.annual_rate, req.monthly_payment, extra)
    if result is None:
        # No usable rate — return a response the frontend treats as 'no interest region'.
        return SimulateResponse(
            total_interest="0.00",
            months=0,
            monthly_payment=None,
            warning="无利率，无法计算利息预测",
        )
    resp = SimulateResponse(
        total_interest=str(result.total_interest.quantize(Decimal("0.01"))),
        months=result.months,
        monthly_payment=(
            str(result.monthly_payment.quantize(Decimal("0.01")))
            if result.monthly_payment is not None
            else None
        ),
        warning=result.warning,
    )
    if extra > 0:
        base = calc_amortization(req.remaining, req.annual_rate, req.monthly_payment, Decimal("0"))
        if base is not None:
            # Pre-quantize to str so the str-typed fields don't carry raw Decimal
            # (avoids Pydantic serialization warnings on assignment).
            resp.baseline_total_interest = str(base.total_interest.quantize(Decimal("0.01")))
            resp.baseline_months = base.months
            savings = base.total_interest - result.total_interest
            resp.savings_vs_baseline = str(savings.quantize(Decimal("0.01")))
            resp.months_saved = base.months - result.months
    return resp


@router.get("/{liability_id}", response_model=LiabilityResponse)
def get_liability(
    liability_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    return liability_service.get_liability(db, user, liability_id)


@router.put("/{liability_id}", response_model=LiabilityResponse)
def update_liability(
    liability_id: int,
    req: LiabilityUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    result = liability_service.update_liability(db, user, liability_id, req)
    return result


@router.delete("/{liability_id}")
def delete_liability(
    liability_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    liability_service.delete_liability(db, user, liability_id)
    return {"detail": "已删除"}


@router.put("/{liability_id}/payment", response_model=LiabilityResponse)
def record_payment(
    liability_id: int,
    req: PaymentRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    liability = liability_service.record_payment(db, user, liability_id, req.amount)
    record_activity(db, user, "payment", "liability", liability_id, f"还款「{liability.name}」", req.amount)
    return liability


@router.get("/{liability_id}/payments")
def get_payments(
    liability_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    return liability_service.get_payments(db, user, liability_id)
