from fastapi import HTTPException, status
from sqlalchemy.orm import Session, joinedload

from app.models.asset import Asset
from app.models.wish import Wish
from app.models.user import User
from app.schemas.wish import WishCreate, WishUpdate, WishRealizeRequest


def list_wishes(db: Session, user: User, status_filter: str | None = None) -> list[Wish]:
    query = (
        db.query(Wish)
        .options(joinedload(Wish.category))
        .filter(Wish.family_id == user.family_id)
    )
    if status_filter:
        query = query.filter(Wish.status == status_filter)
    return query.order_by(Wish.created_at.desc()).all()


def get_wish(db: Session, user: User, wish_id: str) -> Wish:
    wish = (
        db.query(Wish)
        .options(joinedload(Wish.category))
        .filter(Wish.id == wish_id, Wish.family_id == user.family_id)
        .first()
    )
    if not wish:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="心愿不存在")
    return wish


def create_wish(db: Session, user: User, req: WishCreate) -> Wish:
    wish = Wish(
        family_id=user.family_id,
        user_id=user.id,
        name=req.name,
        description=req.description,
        expected_price=req.expected_price,
        priority=req.priority,
        category_id=req.category_id,
    )
    db.add(wish)
    db.commit()
    db.refresh(wish)
    return wish


def update_wish(db: Session, user: User, wish_id: str, req: WishUpdate) -> Wish:
    wish = get_wish(db, user, wish_id)
    if wish.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权限修改此心愿")

    update_data = req.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(wish, key, value)
    db.commit()
    db.refresh(wish)
    return wish


def delete_wish(db: Session, user: User, wish_id: str) -> None:
    wish = get_wish(db, user, wish_id)
    if wish.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权限删除此心愿")
    db.delete(wish)
    db.commit()


def realize_wish(db: Session, user: User, wish_id: str, req: WishRealizeRequest) -> Asset:
    wish = get_wish(db, user, wish_id)

    if wish.status == "realized":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="心愿已实现")

    # Determine category_id
    category_id = req.category_id if req.category_id else wish.category_id
    if not category_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="必须提供分类")

    try:
        # Create asset
        asset = Asset(
            family_id=user.family_id,
            user_id=user.id,
            category_id=category_id,
            name=wish.name,
            asset_type="physical",  # Default to physical, can be overridden by category
            purchase_price=req.purchase_price,
            current_value=req.purchase_price,
            purchase_date=req.purchase_date,
            status="in_use",
        )
        db.add(asset)
        db.flush()  # Get asset.id without committing

        # Update wish
        wish.status = "realized"
        wish.realized_asset_id = asset.id

        db.commit()
        db.refresh(asset)
        return asset
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"转化失败: {str(e)}")
