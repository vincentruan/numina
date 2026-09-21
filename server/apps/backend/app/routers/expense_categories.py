"""Expense category router."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from apps.backend.app.auth.deps import require_adult
from apps.backend.app.database import get_db
from apps.backend.app.models.user import User
from apps.backend.app.schemas.expense_category import (
    ExpenseCategoryCreate,
    ExpenseCategoryResponse,
)
from apps.backend.app.services import expense_category as category_service

router = APIRouter(prefix="/expense-categories", tags=["travel"])


@router.get("", response_model=list[ExpenseCategoryResponse])
def list_categories(
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    return category_service.list_categories(db, user.family_id)


@router.post("", response_model=ExpenseCategoryResponse, status_code=201)
def create_category(
    req: ExpenseCategoryCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    return category_service.create_category(db, user.family_id, req)
