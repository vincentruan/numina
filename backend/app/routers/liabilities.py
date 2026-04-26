from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.auth.deps import require_adult
from app.database import get_db
from app.models.user import User
from app.schemas.liability import (
    LiabilityCreate,
    LiabilityResponse,
    LiabilityUpdate,
    PaymentRequest,
)
from app.services import liability as liability_service
from app.services.activity import record_activity

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
