from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from apps.backend.app.auth.deps import require_adult
from apps.backend.app.database import get_db
from apps.backend.app.models.user import User
from apps.backend.app.schemas.rental_contract import (
    RentalContractCreate,
    RentalContractResponse,
    RentalContractSummary,
    RentalContractUpdate,
)
from apps.backend.app.services import rental_contract as rental_service

router = APIRouter(prefix="/rental-contracts", tags=["rental-contracts"])


@router.get("", response_model=list[RentalContractResponse])
def list_rental_contracts(
    role: str | None = Query(None),
    active_only: bool | None = Query(None),
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    return rental_service.list_rental_contracts(db, user, role, active_only)


@router.get("/summary", response_model=RentalContractSummary)
def get_rental_summary(
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    return rental_service.get_rental_summary(db, user)


@router.post("", response_model=RentalContractResponse, status_code=201)
def create_rental_contract(
    req: RentalContractCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    return rental_service.create_rental_contract(db, user, req)


@router.get("/{contract_id}", response_model=RentalContractResponse)
def get_rental_contract(
    contract_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    return rental_service.get_rental_contract(db, user, contract_id)


@router.patch("/{contract_id}", response_model=RentalContractResponse)
def update_rental_contract(
    contract_id: str,
    req: RentalContractUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    return rental_service.update_rental_contract(db, user, contract_id, req)


@router.delete("/{contract_id}")
def delete_rental_contract(
    contract_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    rental_service.delete_rental_contract(db, user, contract_id)
    return {"detail": "已删除"}
