from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.auth.deps import require_adult
from app.database import get_db
from app.models.user import User
from app.schemas.asset import AssetCreate, AssetResponse, AssetSellRequest, AssetSellResponse, AssetUpdate, AssetValueUpdate, ValuationResponse, BatchAssetRequest, BatchUpdateCategoryRequest, BatchUpdateTagsRequest, BatchUpdateStatusRequest, BatchOperationResponse, BatchExportResponse
from app.services import asset as asset_service
from app.services.activity import record_activity

router = APIRouter(prefix="/assets", tags=["assets"])


def _to_response(asset) -> AssetResponse:
    resp = AssetResponse.model_validate(asset)
    resp.daily_cost = asset_service.compute_daily_cost(asset)
    resp.return_rate = asset_service.compute_return_rate(asset)
    return resp


@router.get("/", response_model=list[AssetResponse])
def list_assets(
    category_id: str | None = Query(None),
    asset_type: str | None = Query(None),
    status: str | None = Query(None),
    tag_id: str | None = Query(None),
    search: str | None = Query(None),
    sort: str | None = Query(None),
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    assets = asset_service.list_assets(db, user, category_id, asset_type, status, tag_id, search, sort)
    return [_to_response(a) for a in assets]


@router.post("/", response_model=AssetResponse, status_code=201)
def create_asset(
    req: AssetCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    asset = asset_service.create_asset(db, user, req)
    record_activity(db, user, "create", "asset", asset.id, f"添加资产「{asset.name}」", asset.purchase_price)
    return _to_response(asset)


@router.get("/{asset_id}", response_model=AssetResponse)
def get_asset(
    asset_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    asset = asset_service.get_asset(db, user, asset_id)
    return _to_response(asset)


@router.put("/{asset_id}", response_model=AssetResponse)
def update_asset(
    asset_id: str,
    req: AssetUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    asset = asset_service.update_asset(db, user, asset_id, req)
    return _to_response(asset)


@router.delete("/{asset_id}")
def delete_asset(
    asset_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    asset_service.archive_asset(db, user, asset_id)
    return {"detail": "已归档"}


@router.put("/{asset_id}/value", response_model=AssetResponse)
def update_value(
    asset_id: str,
    req: AssetValueUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    asset = asset_service.update_asset_value(db, user, asset_id, req.current_value)
    return _to_response(asset)


@router.post("/{asset_id}/sell", response_model=AssetSellResponse)
def sell_asset(
    asset_id: str,
    req: AssetSellRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    result = asset_service.sell_asset(db, user, asset_id, req)
    record_activity(db, user, "sell", "asset", asset_id, f"出售资产「{result['name']}」", req.sell_price)
    return result


@router.post("/{asset_id}/retire", response_model=AssetResponse)
def retire_asset(
    asset_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    asset = asset_service.retire_asset(db, user, asset_id)
    record_activity(db, user, "retire", "asset", asset_id, f"退役资产「{asset.name}」")
    return _to_response(asset)


@router.post("/{asset_id}/reactivate", response_model=AssetResponse)
def reactivate_asset(
    asset_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    asset = asset_service.reactivate_asset(db, user, asset_id)
    record_activity(db, user, "reactivate", "asset", asset_id, f"恢复资产「{asset.name}」")
    return _to_response(asset)


@router.get("/{asset_id}/valuations", response_model=list[ValuationResponse])
def get_valuations(
    asset_id: str,
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
    return asset_service.batch_archive_assets(db, user, req.asset_ids)


@router.put("/batch/category", response_model=BatchOperationResponse)
def batch_update_category(
    req: BatchUpdateCategoryRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    """批量修改资产分类"""
    return asset_service.batch_update_category(db, user, req.asset_ids, req.category_id)


@router.put("/batch/tags", response_model=BatchOperationResponse)
def batch_update_tags(
    req: BatchUpdateTagsRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    """批量修改资产标签"""
    return asset_service.batch_update_tags(db, user, req.asset_ids, req.tag_ids)


@router.put("/batch/status", response_model=BatchOperationResponse)
def batch_update_status(
    req: BatchUpdateStatusRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    """批量修改资产状态"""
    return asset_service.batch_update_status(db, user, req.asset_ids, req.status)


@router.post("/batch/export", response_model=BatchExportResponse)
def batch_export_assets(
    req: BatchAssetRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    """批量导出资产数据"""
    return asset_service.batch_export_assets(db, user, req.asset_ids)
