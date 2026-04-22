from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.auth.deps import require_adult
from app.database import get_db
from app.models.user import User
from app.schemas.asset import AssetResponse
from app.schemas.wish import WishCreate, WishRealizeRequest, WishResponse, WishUpdate
from app.services import wish as wish_service

router = APIRouter(prefix="/wishes", tags=["wishes"])


@router.get("/", response_model=list[WishResponse])
def list_wishes(
    status: str | None = Query(None),
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    return wish_service.list_wishes(db, user, status)


@router.post("/", response_model=WishResponse, status_code=201)
def create_wish(req: WishCreate, db: Session = Depends(get_db), user: User = Depends(require_adult)):
    return wish_service.create_wish(db, user, req)


@router.get("/{wish_id}", response_model=WishResponse)
def get_wish(wish_id: int, db: Session = Depends(get_db), user: User = Depends(require_adult)):
    return wish_service.get_wish(db, user, wish_id)


@router.put("/{wish_id}", response_model=WishResponse)
def update_wish(wish_id: int, req: WishUpdate, db: Session = Depends(get_db), user: User = Depends(require_adult)):
    return wish_service.update_wish(db, user, wish_id, req)


@router.delete("/{wish_id}")
def delete_wish(wish_id: int, db: Session = Depends(get_db), user: User = Depends(require_adult)):
    wish_service.delete_wish(db, user, wish_id)
    return {"detail": "已删除"}


@router.post("/{wish_id}/realize", response_model=AssetResponse, status_code=201)
def realize_wish(
    wish_id: int,
    req: WishRealizeRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    asset = wish_service.realize_wish(db, user, wish_id, req)
    # Return asset response with computed fields
    from app.services import asset as asset_service
    resp = AssetResponse.model_validate(asset)
    resp.daily_cost = asset_service.compute_daily_cost(asset)
    resp.return_rate = asset_service.compute_return_rate(asset)
    return resp
