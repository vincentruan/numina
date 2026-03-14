from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.asset import Asset
from app.models.category import Category
from app.models.user import User
from app.schemas.category import CategoryCreate, CategoryUpdate


def list_categories(db: Session, user: User) -> list[Category]:
    return (
        db.query(Category)
        .filter(
            (Category.family_id == user.family_id) | (Category.is_system == True)
        )
        .order_by(Category.sort_order)
        .all()
    )


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
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="分类不存在")
    if category.is_system:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="系统分类不可修改")
    if category.family_id != user.family_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权修改此分类")

    update_data = req.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(category, key, value)
    db.commit()
    db.refresh(category)
    return category


def delete_category(db: Session, user: User, category_id: str) -> None:
    category = db.query(Category).filter(Category.id == category_id).first()
    if not category:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="分类不存在")
    if category.is_system:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="系统分类不可删除")
    if category.family_id != user.family_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权删除此分类")

    asset_count = db.query(Asset).filter(Asset.category_id == category_id).count()
    if asset_count > 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="该分类下还有资产，无法删除")

    db.delete(category)
    db.commit()
