"""Expense category service."""

from sqlalchemy import or_
from sqlalchemy.orm import Session

from apps.backend.app.errors import AppError, ErrorCode
from apps.backend.app.schemas.expense_category import ExpenseCategoryCreate
from packages.db.models.expense_category import ExpenseCategory


def list_categories(db: Session, family_id: int) -> list[ExpenseCategory]:
    """List system defaults (family_id IS NULL) and family-specific categories."""
    return (
        db.query(ExpenseCategory)
        .filter(
            or_(
                ExpenseCategory.family_id.is_(None),
                ExpenseCategory.family_id == family_id,
            )
        )
        .order_by(ExpenseCategory.sort_order, ExpenseCategory.id)
        .all()
    )


def create_category(
    db: Session,
    family_id: int,
    req: ExpenseCategoryCreate,
) -> ExpenseCategory:
    """Create a family-specific expense category."""
    category = ExpenseCategory(
        family_id=family_id,
        name=req.name,
        icon=req.icon,
        sort_order=req.sort_order,
        is_system=False,
    )
    db.add(category)
    db.commit()
    db.refresh(category)
    return category


def get_category(
    db: Session,
    category_id: int,
    family_id: int,
) -> ExpenseCategory:
    """Get a single expense category."""
    category = (
        db.query(ExpenseCategory)
        .filter(
            ExpenseCategory.id == category_id,
            or_(
                ExpenseCategory.family_id.is_(None),
                ExpenseCategory.family_id == family_id,
            ),
        )
        .first()
    )
    if not category:
        raise AppError(ErrorCode.EXPENSE_CATEGORY_NOT_FOUND)
    return category
