from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from apps.backend.app.auth.deps import get_current_child_user, require_adult
from apps.backend.app.database import get_db
from apps.backend.app.models.asset import Asset
from apps.backend.app.models.user import User
from apps.backend.app.schemas.asset import ChildAssetResponse
from apps.backend.app.schemas.child_wish import (
    ApproveChildWishRequest,
    ChildWishCreate,
    ChildWishListResponse,
    ChildWishResponse,
    ChildWishStatsResponse,
    ParentWishResponse,
    RealizeChildWishRequest,
    RejectChildWishRequest,
    UpdateChildWishCostRequest,
)
from apps.backend.app.services import child_wishes as svc

router = APIRouter(tags=["child-wishes"])


# ---------------------------------------------------------------------------
# Child endpoints
# ---------------------------------------------------------------------------

@router.post("/child/wishes", response_model=ChildWishResponse, status_code=201)
def create_wish(
    req: ChildWishCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_child_user),
):
    return svc.create_child_wish(db, user, req)


@router.get("/child/wishes/stats", response_model=ChildWishStatsResponse)
def get_stats(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_child_user),
):
    return svc.get_child_stats(db, user)


@router.get("/child/wishes", response_model=ChildWishListResponse)
def list_wishes(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_child_user),
):
    return svc.list_child_wishes(db, user)


@router.get("/child/wishes/{wish_id}", response_model=ChildWishResponse)
def get_wish(
    wish_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_child_user),
):
    return svc.get_child_wish(db, user, wish_id)


@router.post("/child/wishes/{wish_id}/request-redemption", response_model=ChildWishResponse)
def request_redemption(
    wish_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_child_user),
):
    return svc.request_redemption(db, user, wish_id)


@router.get("/child/assets/{asset_id}", response_model=ChildAssetResponse)
def get_child_asset(
    asset_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_child_user),
):
    asset = db.query(Asset).filter(
        Asset.id == asset_id,
        Asset.user_id == user.id,
        Asset.family_id == user.family_id,
    ).first()
    if not asset:
        raise HTTPException(status_code=404, detail="资产不存在")
    return ChildAssetResponse.model_validate(asset)


# ---------------------------------------------------------------------------
# Parent endpoints
# ---------------------------------------------------------------------------

@router.get("/family/child-wishes", response_model=list[ParentWishResponse])
def list_parent_queue(
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    return svc.list_parent_queue(db, user)


@router.post("/family/child-wishes/{wish_id}/approve", response_model=ParentWishResponse)
def approve_wish(
    wish_id: int,
    req: ApproveChildWishRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    return svc.approve_child_wish(db, user, wish_id, req)


@router.post("/family/child-wishes/{wish_id}/reject", response_model=ParentWishResponse)
def reject_wish(
    wish_id: int,
    req: RejectChildWishRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    return svc.reject_child_wish(db, user, wish_id, req)


@router.patch("/family/child-wishes/{wish_id}/cost", response_model=ParentWishResponse)
def update_cost(
    wish_id: int,
    req: UpdateChildWishCostRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    return svc.update_child_wish_cost(db, user, wish_id, req)


@router.post("/family/child-wishes/{wish_id}/realize", response_model=ParentWishResponse)
def realize_wish(
    wish_id: int,
    req: RealizeChildWishRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    return svc.realize_child_wish(db, user, wish_id, req)


@router.post("/family/child-wishes/{wish_id}/defer", response_model=ParentWishResponse)
def defer_wish(
    wish_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    return svc.defer_redemption(db, user, wish_id)
