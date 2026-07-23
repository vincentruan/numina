from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from apps.backend.app.auth.deps import require_adult
from apps.backend.app.database import get_db
from apps.backend.app.models.asset_lifecycle_event import AssetLifecycleEvent
from apps.backend.app.models.user import User
from apps.backend.app.schemas.asset import (
    AssetCreate,
    AssetResponse,
    AssetSellRequest,
    AssetSellResponse,
    AssetUpdate,
    AssetValueUpdate,
    BatchAssetRequest,
    BatchExportResponse,
    BatchOperationResponse,
    BatchUpdateCategoryRequest,
    BatchUpdateStatusRequest,
    BatchUpdateTagsRequest,
    PaginatedAssetResponse,
    ValuationResponse,
)
from apps.backend.app.services import asset as asset_service
from apps.backend.app.services.activity import record_activity

router = APIRouter(prefix="/assets", tags=["assets"])


def _to_response(asset, db: Session) -> AssetResponse:
    resp = AssetResponse.model_validate(asset)
    resp.daily_cost = asset_service.compute_daily_cost(asset)
    resp.return_rate = asset_service.compute_return_rate(asset)
    resp.lifecycle_events = (
        db.query(AssetLifecycleEvent)
        .filter(AssetLifecycleEvent.asset_id == asset.id)
        .order_by(AssetLifecycleEvent.event_date.desc())
        .all()
    )
    return resp


@router.get("", response_model=PaginatedAssetResponse)
def list_assets(
    category_id: int | None = Query(None),
    asset_type: str | None = Query(None),
    status: str | None = Query(None),
    tag_id: int | None = Query(None),
    search: str | None = Query(None),
    sort: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    import math
    assets, total = asset_service.list_assets(db, user, category_id, asset_type, status, tag_id, search, sort, page, page_size)
    total_pages = math.ceil(total / page_size) if total > 0 else 1
    return PaginatedAssetResponse(
        items=[_to_response(a, db) for a in assets],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
        has_next=page < total_pages,
        has_prev=page > 1,
    )


@router.post("", response_model=AssetResponse, status_code=201)
def create_asset(
    req: AssetCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    asset = asset_service.create_asset(db, user, req)
    record_activity(db, user, "create", "asset", asset.id, f"添加资产「{asset.name}」", float(asset.purchase_price) if asset.purchase_price is not None else None)
    return _to_response(asset, db)


@router.get("/{asset_id}", response_model=AssetResponse)
def get_asset(
    asset_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    asset = asset_service.get_asset(db, user, asset_id)
    return _to_response(asset, db)


@router.put("/{asset_id}", response_model=AssetResponse)
def update_asset(
    asset_id: int,
    req: AssetUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    asset = asset_service.update_asset(db, user, asset_id, req)
    return _to_response(asset, db)


@router.delete("/{asset_id}")
def delete_asset(
    asset_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    asset_service.archive_asset(db, user, asset_id)
    return {"detail": "已归档"}


@router.put("/{asset_id}/value", response_model=AssetResponse)
def update_value(
    asset_id: int,
    req: AssetValueUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    asset = asset_service.update_asset_value(db, user, asset_id, req.current_value)
    return _to_response(asset, db)


@router.post("/{asset_id}/sell", response_model=AssetSellResponse)
def sell_asset(
    asset_id: int,
    req: AssetSellRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    result = asset_service.sell_asset(db, user, asset_id, req)
    record_activity(db, user, "sell", "asset", asset_id, f"出售资产「{result['name']}」", float(req.sell_price))
    return result


@router.post("/{asset_id}/retire", response_model=AssetResponse)
def retire_asset(
    asset_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    asset = asset_service.retire_asset(db, user, asset_id)
    record_activity(db, user, "retire", "asset", asset_id, f"退役资产「{asset.name}」")
    return _to_response(asset, db)


@router.post("/{asset_id}/reactivate", response_model=AssetResponse)
def reactivate_asset(
    asset_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    asset = asset_service.reactivate_asset(db, user, asset_id)
    record_activity(db, user, "reactivate", "asset", asset_id, f"恢复资产「{asset.name}」")
    return _to_response(asset, db)


@router.get("/{asset_id}/valuations", response_model=list[ValuationResponse])
def get_valuations(
    asset_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    return asset_service.get_valuations(db, user, asset_id)


# Batch operations
@router.post("/batch/archive", response_model=BatchOperationResponse)
def batch_archive_assets(
    req: BatchAssetRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    """批量归档资产"""
    result = asset_service.batch_archive_assets(db, user, req.asset_ids)
    return result


@router.put("/batch/category", response_model=BatchOperationResponse)
def batch_update_category(
    req: BatchUpdateCategoryRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    """批量修改资产分类"""
    result = asset_service.batch_update_category(db, user, req.asset_ids, req.category_id)
    return result


@router.put("/batch/tags", response_model=BatchOperationResponse)
def batch_update_tags(
    req: BatchUpdateTagsRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    """批量修改资产标签"""
    result = asset_service.batch_update_tags(db, user, req.asset_ids, req.tag_ids)
    return result


@router.put("/batch/status", response_model=BatchOperationResponse)
def batch_update_status(
    req: BatchUpdateStatusRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    """批量修改资产状态"""
    result = asset_service.batch_update_status(db, user, req.asset_ids, req.status)
    return result


@router.post("/batch/export", response_model=BatchExportResponse)
def batch_export_assets(
    req: BatchAssetRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    """批量导出资产数据"""
    return asset_service.batch_export_assets(db, user, req.asset_ids)
