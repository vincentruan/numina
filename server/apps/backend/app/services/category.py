from sqlalchemy.orm import Session

from apps.backend.app.errors import AppError, ErrorCode
from apps.backend.app.models.asset import Asset
from apps.backend.app.models.category import Category
from apps.backend.app.models.user import User
from apps.backend.app.schemas.category import CategoryCreate, CategoryUpdate


def list_categories(db: Session, user: User, asset_type: str | None = None) -> list[Category]:
    query = db.query(Category).filter(
        (Category.family_id == user.family_id) | Category.is_system
    )
    if asset_type:
        query = query.filter(Category.asset_type == asset_type)
    return query.order_by(Category.sort_order).all()


def create_category(db: Session, user: User, req: CategoryCreate) -> Category:
    category = Category(
        family_id=user.family_id,
        name=req.name,
        icon=req.icon,
        color=req.color,
        asset_type=req.asset_type,
        sort_order=req.sort_order,
        is_system=False,
    )
    db.add(category)
    db.commit()
    db.refresh(category)
    return category


def update_category(db: Session, user: User, category_id: str, req: CategoryUpdate) -> Category:
    category = db.query(Category).filter(Category.id == category_id).first()
    if not category:
        raise AppError(ErrorCode.CATEGORY_NOT_FOUND)
    if category.is_system:
        raise AppError(ErrorCode.CATEGORY_SYSTEM_READONLY)
    if category.family_id != user.family_id:
        raise AppError(ErrorCode.CATEGORY_FORBIDDEN)

    update_data = req.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(category, key, value)
    db.commit()
    db.refresh(category)
    return category


def delete_category(db: Session, user: User, category_id: str) -> None:
    category = db.query(Category).filter(Category.id == category_id).first()
    if not category:
        raise AppError(ErrorCode.CATEGORY_NOT_FOUND)
    if category.is_system:
        raise AppError(ErrorCode.CATEGORY_SYSTEM_READONLY)
    if category.family_id != user.family_id:
        raise AppError(ErrorCode.CATEGORY_FORBIDDEN)

    asset_count = db.query(Asset).filter(Asset.category_id == category_id).count()
    if asset_count > 0:
        raise AppError(ErrorCode.CATEGORY_FORBIDDEN)

    db.delete(category)
    db.commit()
