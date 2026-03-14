from datetime import date

from fastapi import HTTPException, status
from sqlalchemy.orm import Session, joinedload

from app.models.asset import Asset, asset_tags
from app.models.tag import Tag
from app.models.user import User
from app.schemas.asset import AssetCreate, AssetUpdate


def list_assets(
    db: Session,
    user: User,
    category_id: str | None = None,
    asset_type: str | None = None,
    asset_status: str | None = None,
    tag: str | None = None,
    sort: str | None = None,
) -> list[Asset]:
    query = (
        db.query(Asset)
        .options(joinedload(Asset.category), joinedload(Asset.tags))
        .filter(Asset.family_id == user.family_id, Asset.is_archived == False)
    )
    if category_id:
        query = query.filter(Asset.category_id == category_id)
    if asset_type:
        query = query.filter(Asset.asset_type == asset_type)
    if asset_status:
        query = query.filter(Asset.status == asset_status)
    if tag:
        query = query.join(asset_tags).join(Tag).filter(Tag.id == tag)

    if sort == "value":
        query = query.order_by(Asset.current_value.desc().nullslast())
    elif sort == "date":
        query = query.order_by(Asset.purchase_date.desc().nullslast())
    elif sort == "name":
        query = query.order_by(Asset.name)
    else:
        query = query.order_by(Asset.created_at.desc())

    return query.all()


def get_asset(db: Session, user: User, asset_id: str) -> Asset:
    asset = (
        db.query(Asset)
        .options(joinedload(Asset.category), joinedload(Asset.tags))
        .filter(Asset.id == asset_id, Asset.family_id == user.family_id)
        .first()
    )
    if not asset:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="资产不存在")
    return asset


def compute_daily_cost(asset: Asset) -> float | None:
    if not asset.purchase_date or not asset.purchase_price:
        return None
    days = (date.today() - asset.purchase_date).days
    if days <= 0:
        return None
    years = days / 365.0
    total_cost = asset.purchase_price + (asset.annual_maintenance_cost or 0) * years
    return round(total_cost / days, 2)


def compute_return_rate(asset: Asset) -> float | None:
    if not asset.purchase_price or asset.purchase_price == 0 or not asset.current_value:
        return None
    return round((asset.current_value - asset.purchase_price) / asset.purchase_price * 100, 2)


def create_asset(db: Session, user: User, req: AssetCreate) -> Asset:
    asset = Asset(
        user_id=user.id,
        family_id=user.family_id,
        category_id=req.category_id,
        name=req.name,
        asset_type=req.asset_type,
        purchase_price=req.purchase_price,
        current_value=req.current_value,
        currency=req.currency,
        purchase_date=req.purchase_date,
        status=req.status,
        location=req.location,
        institution=req.institution,
        interest_rate=req.interest_rate,
        maturity_date=req.maturity_date,
        expected_lifespan_days=req.expected_lifespan_days,
        annual_maintenance_cost=req.annual_maintenance_cost,
        usage_frequency=req.usage_frequency,
        properties=req.properties,
        notes=req.notes,
    )
    if req.tag_ids:
        tags = db.query(Tag).filter(Tag.id.in_(req.tag_ids), Tag.family_id == user.family_id).all()
        asset.tags = tags
    db.add(asset)
    db.commit()
    db.refresh(asset)
    return asset


def update_asset(db: Session, user: User, asset_id: str, req: AssetUpdate) -> Asset:
    asset = get_asset(db, user, asset_id)
    update_data = req.model_dump(exclude_unset=True)
    tag_ids = update_data.pop("tag_ids", None)

    for key, value in update_data.items():
        setattr(asset, key, value)

    if tag_ids is not None:
        tags = db.query(Tag).filter(Tag.id.in_(tag_ids), Tag.family_id == user.family_id).all()
        asset.tags = tags

    db.commit()
    db.refresh(asset)
    return asset


def archive_asset(db: Session, user: User, asset_id: str) -> Asset:
    asset = get_asset(db, user, asset_id)
    asset.is_archived = True
    db.commit()
    db.refresh(asset)
    return asset


def update_asset_value(db: Session, user: User, asset_id: str, value: float) -> Asset:
    asset = get_asset(db, user, asset_id)
    asset.current_value = value
    db.commit()
    db.refresh(asset)
    return asset
