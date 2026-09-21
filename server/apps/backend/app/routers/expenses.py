"""Expense entry router — scoped under a trip."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from apps.backend.app.auth.deps import require_adult
from apps.backend.app.database import get_db
from apps.backend.app.models.user import User
from apps.backend.app.schemas.expense_entry import (
    ExpenseEntryCreate,
    ExpenseEntryResponse,
)
from apps.backend.app.services import expense_ledger
from apps.backend.app.services import trip as trip_service

router = APIRouter(prefix="/trips/{trip_id}/expenses", tags=["travel"])


@router.get("", response_model=list[ExpenseEntryResponse])
def list_expenses(
    trip_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    trip_service.get_trip(db, trip_id, user.family_id)
    return expense_ledger.list_expenses(
        db, user.family_id, ref_id=trip_id, ref_type="trip"
    )


@router.post("", response_model=ExpenseEntryResponse, status_code=201)
def create_expense(
    trip_id: int,
    req: ExpenseEntryCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    trip_service.get_trip(db, trip_id, user.family_id)
    # Force ref to this trip
    req.ref_id = trip_id
    req.ref_type = "trip"
    result = expense_ledger.create_expense(db, user.family_id, user.id, req)
    return result["debit"]


@router.get("/{entry_id}", response_model=ExpenseEntryResponse)
def get_expense(
    trip_id: int,
    entry_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    trip_service.get_trip(db, trip_id, user.family_id)
    return expense_ledger.get_expense(db, entry_id, user.family_id)


@router.delete("/{entry_id}")
def delete_expense(
    trip_id: int,
    entry_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    trip_service.get_trip(db, trip_id, user.family_id)
    expense_ledger.delete_expense(db, entry_id, user.family_id, user.id)
    return {"detail": "已删除"}
