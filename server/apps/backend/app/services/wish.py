from datetime import UTC, datetime

from sqlalchemy.orm import Session, joinedload

from apps.backend.app.errors import AppError, ErrorCode
from apps.backend.app.models.asset import Asset
from apps.backend.app.models.user import User
from apps.backend.app.models.wish import Wish
from apps.backend.app.schemas.wish import WishCreate, WishRealizeRequest, WishUpdate


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
        raise AppError(ErrorCode.NOT_FOUND)
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
        converts_to_asset=req.converts_to_asset,
    )
    db.add(wish)
    db.commit()
    db.refresh(wish)
    return wish


def update_wish(db: Session, user: User, wish_id: str, req: WishUpdate) -> Wish:
    wish = get_wish(db, user, wish_id)
    if wish.user_id != user.id:
        raise AppError(ErrorCode.FORBIDDEN)

    update_data = req.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(wish, key, value)
    db.commit()
    db.refresh(wish)
    return wish


def delete_wish(db: Session, user: User, wish_id: str) -> None:
    wish = get_wish(db, user, wish_id)
    if wish.user_id != user.id:
        raise AppError(ErrorCode.FORBIDDEN)
    db.delete(wish)
    db.commit()


def realize_wish(db: Session, user: User, wish_id: str, req: WishRealizeRequest) -> Asset:
    wish = get_wish(db, user, wish_id)

    if wish.status == "realized":
        raise AppError(ErrorCode.VALIDATION_ERROR)

    if not wish.converts_to_asset:
        raise AppError(ErrorCode.VALIDATION_ERROR)

    # Determine category_id
    category_id = req.category_id if req.category_id else wish.category_id
    if not category_id:
        raise AppError(ErrorCode.VALIDATION_ERROR)

    # Validate category is physical type (wishes only create physical assets)
    from apps.backend.app.models.category import Category
    category = db.query(Category).filter(Category.id == category_id).first()
    if category and category.asset_type != "physical":
        raise AppError(ErrorCode.VALIDATION_ERROR, detail="Category must be physical type for wish realization")

    try:
        # Create asset
        asset = Asset(
            family_id=user.family_id,
            user_id=user.id,
            category_id=category_id,
            name=wish.name,
            asset_type="physical",  # All realized wishes create physical assets
            purchase_price=req.purchase_price,
            current_value=req.purchase_price,
            purchase_date=req.purchase_date,
            status="in_use",
        )
        db.add(asset)
        db.flush()  # Get asset.id without committing

        # Update wish
        wish.status = "realized"
        wish.realized_asset_id = asset.id  # FK to assets.id
        wish.fulfilled_at = datetime.now(UTC)
        asset.from_wish_id = wish.id  # wish.id is int, FK to wishes.id

        db.commit()
        db.refresh(asset)
        return asset
    except AppError:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        raise AppError(ErrorCode.INTERNAL_ERROR) from e
