from decimal import Decimal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from apps.backend.app.auth.deps import require_adult
from apps.backend.app.database import get_db
from apps.backend.app.models.user import User
from apps.backend.app.schemas.liability import (
    BalanceCorrectionRequest,
    BalanceCorrectionResponse,
    LiabilityCreate,
    LiabilityDetailResponse,
    LiabilityResponse,
    LiabilityUpdate,
    PaymentRecordResponse,
    PaymentRequest,
)
from apps.backend.app.schemas.liability_simulate import (
    SimulateRequest,
    SimulateResponse,
)
from apps.backend.app.services import balance_correction as correction_service
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
    record_activity(db, user, "create", "liability", str(liability.id), f"添加负债「{liability.name}」", float(liability.original_amount) if liability.original_amount is not None else None)
    return liability


@router.post("/simulate", response_model=SimulateResponse)
def simulate_liability(
    req: SimulateRequest,
    user: User = Depends(require_adult),
):
    """L2: forecast total interest + months, with optional extra-payment comparison.

    Pure compute (no db write). When extra_monthly > 0, also computes the
    baseline (extra=0) so the frontend shows '省 ¥Y, 提前 N 月'.
    Supports 5 repayment methods: equal_payment, equal_principal, interest_only,
    bullet, minimum_payment.
    """
    extra = req.extra_monthly or Decimal("0")
    result = calc_amortization(
        req.remaining, req.annual_rate, req.monthly_payment, extra,
        repayment_method=req.repayment_method,
        total_periods=req.total_periods,
    )
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
    if result.schedule:
        # Serialize schedule: Decimal values → str (2 decimals).
        resp.schedule = [
            {
                "month": row["month"],
                "payment": str(row["payment"].quantize(Decimal("0.01"))),
                "principal": str(row["principal"].quantize(Decimal("0.01"))),
                "interest": str(row["interest"].quantize(Decimal("0.01"))),
                "balance": str(row["balance"].quantize(Decimal("0.01"))),
            }
            for row in result.schedule
        ]
    if extra > 0:
        base = calc_amortization(
            req.remaining, req.annual_rate, req.monthly_payment, Decimal("0"),
            repayment_method=req.repayment_method,
            total_periods=req.total_periods,
        )
        if base is not None:
            # Pre-quantize to str so the str-typed fields don't carry raw Decimal
            # (avoids Pydantic serialization warnings on assignment).
            resp.baseline_total_interest = str(base.total_interest.quantize(Decimal("0.01")))
            resp.baseline_months = base.months
            savings = base.total_interest - result.total_interest
            resp.savings_vs_baseline = str(savings.quantize(Decimal("0.01")))
            resp.months_saved = base.months - result.months
    return resp


@router.get("/{liability_id}", response_model=LiabilityDetailResponse)
def get_liability(
    liability_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    """L7 (KTD-2): detail endpoint enriches the linked_asset relationship into a
    {name, current_value} summary so the frontend can render a collateral
    coverage comparison without a second round-trip. Only detail — list is not
    enriched (the list LiabilityResponse has no linked_asset field, avoiding N+1).
    """
    liability = liability_service.get_liability(db, user, liability_id)
    return LiabilityDetailResponse.model_validate(liability)


@router.put("/{liability_id}", response_model=LiabilityResponse)
def update_liability(
    liability_id: str,
    req: LiabilityUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    result = liability_service.update_liability(db, user, liability_id, req)
    return result


@router.delete("/{liability_id}")
def delete_liability(
    liability_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    liability_service.delete_liability(db, user, liability_id)
    return {"detail": "已删除"}


@router.put("/{liability_id}/payment", response_model=LiabilityResponse)
def record_payment(
    liability_id: str,
    req: PaymentRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    liability = liability_service.record_payment(db, user, liability_id, req.amount, req.paid_at)
    record_activity(db, user, "payment", "liability", liability_id, f"还款「{liability.name}」", float(req.amount))
    return liability


@router.get("/{liability_id}/payments", response_model=list[PaymentRecordResponse])
def get_payments(
    liability_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    return liability_service.get_payments(db, user, liability_id)


@router.post(
    "/{liability_id}/balance-correction",
    response_model=BalanceCorrectionResponse,
    status_code=201,
)
def create_balance_correction(
    liability_id: str,
    req: BalanceCorrectionRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    """U3: post-creation balance adjustment (Path 1 — not used during create_liability)."""
    correction = correction_service.create_correction(
        db, user, liability_id, req.amount, req.reason,
    )
    return correction


@router.get(
    "/{liability_id}/balance-corrections",
    response_model=list[BalanceCorrectionResponse],
)
def list_balance_corrections(
    liability_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    """U3: list all balance corrections for a liability."""
    return correction_service.list_corrections(db, user, liability_id)
