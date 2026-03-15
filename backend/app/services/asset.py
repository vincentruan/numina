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
    tag_id: str | None = None,
    search: str | None = None,
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
    if tag_id:
        query = query.join(asset_tags).join(Tag).filter(Tag.id == tag_id)
    if search:
        query = query.filter(Asset.name.ilike(f"%{search}%"))

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
    from app.models.valuation import AssetValuation
    asset = get_asset(db, user, asset_id)
    asset.current_value = value
    valuation = AssetValuation(asset_id=asset.id, value=value)
    db.add(valuation)
    db.commit()
    db.refresh(asset)
    return asset


def sell_asset(db: Session, user: User, asset_id: str, req) -> dict:
    asset = get_asset(db, user, asset_id)
    if asset.status == 'sold':
        raise HTTPException(status_code=400, detail="资产已卖出")

    asset.status = 'sold'
    asset.sell_price = req.sell_price
    asset.sell_fee = req.sell_fee
    asset.sell_channel = req.sell_channel
    asset.sell_date = date.today()
    if req.notes:
        asset.notes = req.notes

    net_recovery = req.sell_price - (req.sell_fee or 0)
    days_held = (date.today() - asset.purchase_date).days if asset.purchase_date else 0

    years = days_held / 365.0 if days_held > 0 else 0
    total_maintenance = (asset.annual_maintenance_cost or 0) * years
    total_cost = (asset.purchase_price or 0) + total_maintenance
    total_profit_loss = net_recovery - total_cost
    actual_daily_cost = round(total_cost / days_held, 2) if days_held > 0 else 0

    db.commit()
    db.refresh(asset)

    return {
        "asset_id": asset.id,
        "name": asset.name,
        "net_recovery": round(net_recovery, 2),
        "total_profit_loss": round(total_profit_loss, 2),
        "actual_daily_cost": actual_daily_cost,
        "target_daily_cost": asset.target_daily_cost,
        "days_held": days_held,
        "purchase_price": asset.purchase_price,
        "sell_price": req.sell_price,
    }


def retire_asset(db: Session, user: User, asset_id: str) -> Asset:
    asset = get_asset(db, user, asset_id)
    if asset.status == 'sold':
        raise HTTPException(status_code=400, detail="已卖出的资产不能退役")
    asset.status = 'retired'
    asset.retire_date = date.today()
    db.commit()
    db.refresh(asset)
    return asset


def reactivate_asset(db: Session, user: User, asset_id: str) -> Asset:
    asset = get_asset(db, user, asset_id)
    if asset.status not in ('retired', 'idle'):
        raise HTTPException(status_code=400, detail="只有退役或闲置的资产可以恢复服役")
    asset.status = 'in_use'
    asset.retire_date = None
    db.commit()
    db.refresh(asset)
    return asset


def get_valuations(db: Session, user: User, asset_id: str) -> list:
    from app.models.valuation import AssetValuation
    get_asset(db, user, asset_id)  # Verify access
    return (
        db.query(AssetValuation)
        .filter(AssetValuation.asset_id == asset_id)
        .order_by(AssetValuation.valued_at.desc())
        .all()
    )
