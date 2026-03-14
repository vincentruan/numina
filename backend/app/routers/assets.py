from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.auth.deps import get_current_user
from app.database import get_db
from app.models.user import User
from app.schemas.asset import AssetCreate, AssetResponse, AssetUpdate, AssetValueUpdate
from app.services import asset as asset_service

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
    tag: str | None = Query(None),
    sort: str | None = Query(None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    assets = asset_service.list_assets(db, user, category_id, asset_type, status, tag, sort)
    return [_to_response(a) for a in assets]


@router.post("/", response_model=AssetResponse, status_code=201)
def create_asset(
    req: AssetCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    asset = asset_service.create_asset(db, user, req)
    return _to_response(asset)


@router.get("/{asset_id}", response_model=AssetResponse)
def get_asset(
    asset_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    asset = asset_service.get_asset(db, user, asset_id)
    return _to_response(asset)


@router.put("/{asset_id}", response_model=AssetResponse)
def update_asset(
    asset_id: str,
    req: AssetUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    asset = asset_service.update_asset(db, user, asset_id, req)
    return _to_response(asset)


@router.delete("/{asset_id}")
def delete_asset(
    asset_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    asset_service.archive_asset(db, user, asset_id)
    return {"detail": "已归档"}


@router.put("/{asset_id}/value", response_model=AssetResponse)
def update_value(
    asset_id: str,
    req: AssetValueUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    asset = asset_service.update_asset_value(db, user, asset_id, req.current_value)
    return _to_response(asset)
