"""Bootstrap system expense categories for the travel module."""

from sqlalchemy.orm import Session

from packages.db.models.expense_category import ExpenseCategory

SYSTEM_EXPENSE_CATEGORIES: list[dict] = [
    {"name": "餐饮", "icon": "food-o", "sort_order": 1},
    {"name": "交通", "icon": "logistics", "sort_order": 2},
    {"name": "住宿", "icon": "hotel-o", "sort_order": 3},
    {"name": "活动", "icon": "flag-o", "sort_order": 4},
    {"name": "购物", "icon": "shopping-cart", "sort_order": 5},
    {"name": "杂项", "icon": "balance-o", "sort_order": 6},
]


def bootstrap_expense_categories(db: Session) -> None:
    """Ensure system expense categories exist with correct icons. Idempotent — upserts per name."""
    for cat_data in SYSTEM_EXPENSE_CATEGORIES:
        existing = db.query(ExpenseCategory).filter(
            ExpenseCategory.name == cat_data["name"],
            ExpenseCategory.is_system.is_(True),
            ExpenseCategory.family_id.is_(None),
        ).first()
        if existing:
            if existing.icon != cat_data["icon"]:
                existing.icon = cat_data["icon"]
        else:
            cat = ExpenseCategory(
                family_id=None,
                is_system=True,
                **cat_data,
            )
            db.add(cat)
    db.commit()
