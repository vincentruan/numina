from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.wish import Wish
from app.models.user import User
from app.schemas.wish import WishCreate, WishUpdate


def list_wishes(db: Session, user: User) -> list[Wish]:
    return (
        db.query(Wish)
        .filter(Wish.family_id == user.family_id)
        .order_by(Wish.priority.desc(), Wish.created_at.desc())
        .all()
    )


def get_wish(db: Session, user: User, wish_id: str) -> Wish:
    wish = db.query(Wish).filter(Wish.id == wish_id, Wish.family_id == user.family_id).first()
    if not wish:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="心愿不存在")
    return wish


def create_wish(db: Session, user: User, req: WishCreate) -> Wish:
    wish = Wish(
        family_id=user.family_id,
        user_id=user.id,
        name=req.name,
        category_id=req.category_id,
        expected_price=req.expected_price,
        target_date=req.target_date,
        priority=req.priority,
        notes=req.notes,
    )
    db.add(wish)
    db.commit()
    db.refresh(wish)
    return wish


def update_wish(db: Session, user: User, wish_id: str, req: WishUpdate) -> Wish:
    wish = get_wish(db, user, wish_id)
    update_data = req.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(wish, key, value)
    db.commit()
    db.refresh(wish)
    return wish


def delete_wish(db: Session, user: User, wish_id: str) -> None:
    wish = get_wish(db, user, wish_id)
    db.delete(wish)
    db.commit()


def fulfill_wish(db: Session, user: User, wish_id: str, asset_id: str) -> Wish:
    wish = get_wish(db, user, wish_id)
    wish.is_fulfilled = True
    wish.fulfilled_asset_id = asset_id
    db.commit()
    db.refresh(wish)
    return wish
