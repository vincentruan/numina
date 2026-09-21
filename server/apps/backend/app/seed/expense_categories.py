"""Bootstrap system expense categories for the travel module."""

from sqlalchemy.orm import Session

from packages.db.models.expense_category import ExpenseCategory

SYSTEM_EXPENSE_CATEGORIES: list[dict] = [
    {"name": "餐饮", "icon": "🍜", "sort_order": 1},
    {"name": "交通", "icon": "🚗", "sort_order": 2},
    {"name": "住宿", "icon": "🏨", "sort_order": 3},
    {"name": "活动", "icon": "🎯", "sort_order": 4},
    {"name": "购物", "icon": "🛍", "sort_order": 5},
    {"name": "杂项", "icon": "📦", "sort_order": 6},
]


def bootstrap_expense_categories(db: Session) -> None:
    """Ensure system expense categories exist. Idempotent."""
    existing = db.query(ExpenseCategory).filter(ExpenseCategory.is_system).first()
    if existing:
        return

    for cat_data in SYSTEM_EXPENSE_CATEGORIES:
        cat = ExpenseCategory(
            family_id=None,
            is_system=True,
            **cat_data,
        )
        db.add(cat)
    db.commit()
