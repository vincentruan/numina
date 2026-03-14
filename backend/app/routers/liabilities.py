from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth.deps import get_current_user
from app.database import get_db
from app.models.user import User
from app.schemas.liability import (
    LiabilityCreate,
    LiabilityResponse,
    LiabilityUpdate,
    PaymentRequest,
)
from app.services import liability as liability_service

router = APIRouter(prefix="/liabilities", tags=["liabilities"])


@router.get("/", response_model=list[LiabilityResponse])
def list_liabilities(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return liability_service.list_liabilities(db, user)


@router.post("/", response_model=LiabilityResponse, status_code=201)
def create_liability(
    req: LiabilityCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return liability_service.create_liability(db, user, req)


@router.get("/{liability_id}", response_model=LiabilityResponse)
def get_liability(
    liability_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return liability_service.get_liability(db, user, liability_id)


@router.put("/{liability_id}", response_model=LiabilityResponse)
def update_liability(
    liability_id: str,
    req: LiabilityUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return liability_service.update_liability(db, user, liability_id, req)


@router.delete("/{liability_id}")
def delete_liability(
    liability_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    liability_service.delete_liability(db, user, liability_id)
    return {"detail": "已删除"}


@router.put("/{liability_id}/payment", response_model=LiabilityResponse)
def record_payment(
    liability_id: str,
    req: PaymentRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return liability_service.record_payment(db, user, liability_id, req.amount)
