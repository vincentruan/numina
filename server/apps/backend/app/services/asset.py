from datetime import date

from fastapi import HTTPException
from sqlalchemy.orm import Session, joinedload

from apps.backend.app.errors.codes import ErrorCode
from apps.backend.app.errors.exceptions import AppError
from apps.backend.app.models.asset import Asset, asset_tags
from apps.backend.app.models.asset_lifecycle_event import AssetLifecycleEvent
from apps.backend.app.models.tag import Tag
from apps.backend.app.models.user import User
from apps.backend.app.schemas.asset import (
    AssetCreate,
    AssetUpdate,
    BatchItemError,
    BatchOperationResponse,
)


def list_assets(
    db: Session,
    user: User,
    category_id: str | None = None,
    asset_type: str | None = None,
    asset_status: str | None = None,
    tag_id: str | None = None,
    search: str | None = None,
    sort: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[Asset], int]:
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

    # Calculate total before pagination
    total = query.count()

    # Apply pagination
    offset = (page - 1) * page_size
    assets = query.offset(offset).limit(page_size).all()

    return assets, total


def get_asset(db: Session, user: User, asset_id: str) -> Asset:
    asset = (
        db.query(Asset)
        .options(joinedload(Asset.category), joinedload(Asset.tags))
        .filter(Asset.id == asset_id, Asset.family_id == user.family_id)
        .first()
    )
    if not asset:
        raise AppError(ErrorCode.ASSET_NOT_FOUND)
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
        image_url=req.image_url,
    )
    if req.tag_ids:
        tags = db.query(Tag).filter(Tag.id.in_(req.tag_ids), Tag.family_id == user.family_id).all()
        asset.tags = tags
    db.add(asset)
    db.commit()
    db.refresh(asset)
    from apps.backend.app.services.notification.dispatcher import check_on_asset_write
    try:
        check_on_asset_write(db, asset)
    except Exception:
        pass  # 提醒检测失败不影响主流程
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
    from apps.backend.app.services.notification.dispatcher import check_on_asset_write
    try:
        check_on_asset_write(db, asset)
    except Exception:
        pass  # 提醒检测失败不影响主流程
    return asset


def archive_asset(db: Session, user: User, asset_id: str) -> Asset:
    asset = get_asset(db, user, asset_id)
    asset.is_archived = True
    db.commit()
    db.refresh(asset)
    return asset


def update_asset_value(db: Session, user: User, asset_id: str, value: float) -> Asset:
    from apps.backend.app.models.valuation import AssetValuation
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
        raise AppError(ErrorCode.ASSET_ALREADY_SOLD)

    asset.status = 'sold'
    if req.notes:
        asset.notes = req.notes

    net_recovery = req.sell_price - (req.sell_fee or 0)
    days_held = (date.today() - asset.purchase_date).days if asset.purchase_date else 0

    years = days_held / 365.0 if days_held > 0 else 0
    total_maintenance = (asset.annual_maintenance_cost or 0) * years
    total_cost = (asset.purchase_price or 0) + total_maintenance
    total_profit_loss = net_recovery - total_cost
    actual_daily_cost = round(total_cost / days_held, 2) if days_held > 0 else 0

    event = AssetLifecycleEvent(
        asset_id=asset.id,
        event_type="sold",
        event_date=date.today(),
        sell_price=req.sell_price,
        sell_fee=req.sell_fee or 0,
        sell_channel=req.sell_channel,
    )
    db.add(event)

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
        raise AppError(ErrorCode.ASSET_ALREADY_SOLD)
    asset.status = 'retired'

    event = AssetLifecycleEvent(
        asset_id=asset.id,
        event_type="retired",
        event_date=date.today(),
    )
    db.add(event)

    db.commit()
    db.refresh(asset)
    return asset


def reactivate_asset(db: Session, user: User, asset_id: str) -> Asset:
    asset = get_asset(db, user, asset_id)
    if asset.status not in ('retired', 'idle'):
        raise AppError(ErrorCode.ASSET_FORBIDDEN)
    asset.status = 'in_use'
    db.commit()
    db.refresh(asset)
    return asset


def get_valuations(db: Session, user: User, asset_id: str) -> list:
    from apps.backend.app.models.valuation import AssetValuation
    get_asset(db, user, asset_id)  # Verify access
    return (
        db.query(AssetValuation)
        .filter(AssetValuation.asset_id == asset_id)
        .order_by(AssetValuation.valued_at.desc())
        .all()
    )


def batch_archive_assets(db: Session, user: User, asset_ids: list[str]) -> BatchOperationResponse:
    """Batch archive assets. Returns success/failed counts and errors."""
    errors: list[BatchItemError] = []
    success_count = 0

    for asset_id in asset_ids:
        try:
            asset = get_asset(db, user, asset_id)
            asset.is_archived = True
            success_count += 1
        except (HTTPException, AppError) as e:
            if isinstance(e, AppError):
                error_code = e.code.value
                message = str(e)
            else:
                error_code = ErrorCode.INTERNAL_ERROR.value
                message = getattr(e, "detail", "操作失败")
            errors.append(BatchItemError(id=asset_id, error_code=error_code, message=message))
        except Exception:
            errors.append(BatchItemError(id=asset_id, error_code=ErrorCode.INTERNAL_ERROR.value, message="内部错误"))

    failed_count = len(asset_ids) - success_count
    try:
        db.commit()
    except Exception:
        return BatchOperationResponse(
            success_count=0,
            failed_count=len(asset_ids),
            partial=False,
            errors=[BatchItemError(id=aid, error_code=ErrorCode.INTERNAL_ERROR.value, message="提交失败") for aid in asset_ids],
        )
    return BatchOperationResponse(
        success_count=success_count,
        failed_count=failed_count,
        partial=failed_count > 0 and success_count > 0,
        errors=errors,
    )


def batch_update_category(db: Session, user: User, asset_ids: list[str], category_id: str) -> BatchOperationResponse:
    """Batch update asset category. Returns success/failed counts and errors."""
    from apps.backend.app.models.category import Category

    # Verify category exists and belongs to user's family or is system category
    category = db.query(Category).filter(Category.id == category_id).first()
    if not category:
        raise AppError(ErrorCode.CATEGORY_NOT_FOUND)
    if category.family_id is not None and category.family_id != user.family_id:
        raise AppError(ErrorCode.CATEGORY_FORBIDDEN)

    errors: list[BatchItemError] = []
    success_count = 0

    for asset_id in asset_ids:
        try:
            asset = get_asset(db, user, asset_id)
            asset.category_id = category_id
            success_count += 1
        except (HTTPException, AppError) as e:
            if isinstance(e, AppError):
                error_code = e.code.value
                message = str(e)
            else:
                error_code = ErrorCode.INTERNAL_ERROR.value
                message = getattr(e, "detail", "操作失败")
            errors.append(BatchItemError(id=asset_id, error_code=error_code, message=message))
        except Exception:
            errors.append(BatchItemError(id=asset_id, error_code=ErrorCode.INTERNAL_ERROR.value, message="内部错误"))

    failed_count = len(asset_ids) - success_count
    try:
        db.commit()
    except Exception:
        return BatchOperationResponse(
            success_count=0,
            failed_count=len(asset_ids),
            partial=False,
            errors=[BatchItemError(id=aid, error_code=ErrorCode.INTERNAL_ERROR.value, message="提交失败") for aid in asset_ids],
        )
    return BatchOperationResponse(
        success_count=success_count,
        failed_count=failed_count,
        partial=failed_count > 0 and success_count > 0,
        errors=errors,
    )


def batch_update_tags(db: Session, user: User, asset_ids: list[str], tag_ids: list[str]) -> BatchOperationResponse:
    """Batch update asset tags. Returns success/failed counts and errors."""
    # Verify tags exist and belong to user's family
    valid_tags = []
    if tag_ids:
        valid_tags = db.query(Tag).filter(
            Tag.id.in_(tag_ids),
            Tag.family_id == user.family_id
        ).all()

        if len(valid_tags) != len(tag_ids):
            raise AppError(ErrorCode.TAG_NOT_FOUND)

    errors: list[BatchItemError] = []
    success_count = 0

    for asset_id in asset_ids:
        try:
            asset = get_asset(db, user, asset_id)
            asset.tags = valid_tags
            success_count += 1
        except (HTTPException, AppError) as e:
            if isinstance(e, AppError):
                error_code = e.code.value
                message = str(e)
            else:
                error_code = ErrorCode.INTERNAL_ERROR.value
                message = getattr(e, "detail", "操作失败")
            errors.append(BatchItemError(id=asset_id, error_code=error_code, message=message))
        except Exception:
            errors.append(BatchItemError(id=asset_id, error_code=ErrorCode.INTERNAL_ERROR.value, message="内部错误"))

    failed_count = len(asset_ids) - success_count
    try:
        db.commit()
    except Exception:
        return BatchOperationResponse(
            success_count=0,
            failed_count=len(asset_ids),
            partial=False,
            errors=[BatchItemError(id=aid, error_code=ErrorCode.INTERNAL_ERROR.value, message="提交失败") for aid in asset_ids],
        )
    return BatchOperationResponse(
        success_count=success_count,
        failed_count=failed_count,
        partial=failed_count > 0 and success_count > 0,
        errors=errors,
    )


def batch_update_status(db: Session, user: User, asset_ids: list[str], status: str) -> BatchOperationResponse:
    """Batch update asset status. Returns success/failed counts and errors."""
    valid_statuses = ['active', 'archived']
    if status not in valid_statuses:
        raise AppError(ErrorCode.VALIDATION_ERROR)

    is_archived = (status == 'archived')
    errors: list[BatchItemError] = []
    success_count = 0

    for asset_id in asset_ids:
        try:
            asset = get_asset(db, user, asset_id)
            asset.is_archived = is_archived
            success_count += 1
        except (HTTPException, AppError) as e:
            if isinstance(e, AppError):
                error_code = e.code.value
                message = str(e)
            else:
                error_code = ErrorCode.INTERNAL_ERROR.value
                message = getattr(e, "detail", "操作失败")
            errors.append(BatchItemError(id=asset_id, error_code=error_code, message=message))
        except Exception:
            errors.append(BatchItemError(id=asset_id, error_code=ErrorCode.INTERNAL_ERROR.value, message="内部错误"))

    failed_count = len(asset_ids) - success_count
    try:
        db.commit()
    except Exception:
        return BatchOperationResponse(
            success_count=0,
            failed_count=len(asset_ids),
            partial=False,
            errors=[BatchItemError(id=aid, error_code=ErrorCode.INTERNAL_ERROR.value, message="提交失败") for aid in asset_ids],
        )
    return BatchOperationResponse(
        success_count=success_count,
        failed_count=failed_count,
        partial=failed_count > 0 and success_count > 0,
        errors=errors,
    )


def batch_export_assets(db: Session, user: User, asset_ids: list[str]) -> dict:
    """Export assets data. Returns list of asset data for export."""
    assets_data = []
    errors = []

    for asset_id in asset_ids:
        try:
            asset = (
                db.query(Asset)
                .options(joinedload(Asset.category), joinedload(Asset.tags))
                .filter(Asset.id == asset_id, Asset.family_id == user.family_id)
                .first()
            )
            if not asset:
                errors.append(f"资产 {asset_id}: 资产不存在")
                continue

            asset_dict = {
                "id": asset.id,
                "name": asset.name,
                "asset_type": asset.asset_type,
                "category": asset.category.name if asset.category else "",
                "purchase_price": asset.purchase_price,
                "current_value": asset.current_value,
                "currency": asset.currency,
                "purchase_date": str(asset.purchase_date) if asset.purchase_date else "",
                "status": asset.status,
                "location": asset.location or "",
                "institution": asset.institution or "",
                "daily_cost": compute_daily_cost(asset),
                "return_rate": compute_return_rate(asset),
                "tags": ", ".join([t.name for t in asset.tags]) if asset.tags else "",
                "is_archived": asset.is_archived,
            }
            assets_data.append(asset_dict)
        except Exception:
            errors.append(f"资产 {asset_id}: 导出失败")

    return {
        "format": "json",
        "data": assets_data,
        "count": len(assets_data),
    }
