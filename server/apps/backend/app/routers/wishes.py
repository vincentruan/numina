from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from apps.backend.app.auth.deps import require_adult
from apps.backend.app.database import get_db
from apps.backend.app.models.user import User
from apps.backend.app.schemas.asset import AssetResponse
from apps.backend.app.schemas.wish import (
    WishCreate,
    WishIgnoreDebtWarning,
    WishRealizeRequest,
    WishResponse,
    WishUpdate,
)
from apps.backend.app.schemas.wish_savings import SavingsLogCreate, SavingsLogResponse
from apps.backend.app.services import wish as wish_service
from apps.backend.app.services import wish_savings

router = APIRouter(prefix="/wishes", tags=["wishes"])


@router.get("", response_model=list[WishResponse])
def list_wishes(
    status: str | None = Query(None),
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    return wish_service.list_wishes(db, user, status)


@router.post("", response_model=WishResponse, status_code=201)
def create_wish(
    req: WishCreate, db: Session = Depends(get_db), user: User = Depends(require_adult)
):
    return wish_service.create_wish(db, user, req)


@router.get("/{wish_id}", response_model=WishResponse)
def get_wish(
    wish_id: int, db: Session = Depends(get_db), user: User = Depends(require_adult)
):
    return wish_service.get_wish(db, user, wish_id)


@router.put("/{wish_id}", response_model=WishResponse)
def update_wish(
    wish_id: int,
    req: WishUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    return wish_service.update_wish(db, user, wish_id, req)


@router.delete("/{wish_id}")
def delete_wish(
    wish_id: int, db: Session = Depends(get_db), user: User = Depends(require_adult)
):
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
    from apps.backend.app.services import asset as asset_service

    resp = AssetResponse.model_validate(asset)
    resp.daily_cost = asset_service.compute_daily_cost(asset)
    resp.return_rate = asset_service.compute_return_rate(asset)
    return resp


@router.post("/{wish_id}/savings", response_model=SavingsLogResponse, status_code=201)
def record_savings(
    wish_id: int,
    req: SavingsLogCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    """Record a savings deposit/withdrawal for a wish (W1)."""
    return wish_savings.record_savings(
        db, user, str(wish_id), req.amount, req.log_date, req.note
    )


@router.get("/{wish_id}/savings", response_model=list[SavingsLogResponse])
def list_savings(
    wish_id: int,
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    """List a wish's savings logs, newest first (W1)."""
    return wish_savings.list_savings(db, user, str(wish_id), page, size)


@router.delete("/{wish_id}/savings/{log_id}")
def delete_savings(
    wish_id: int,
    log_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    """Delete a savings log + reverse its amount from saved_amount (W1)."""
    wish_savings.delete_savings(db, user, str(wish_id), str(log_id))
    return {"detail": "已删除"}


@router.patch("/{wish_id}/ignore-debt-warning", response_model=WishResponse)
def set_ignore_debt_warning(
    wish_id: int,
    req: WishIgnoreDebtWarning,
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    """Toggle the wish's debt-warning override flag (W5)."""
    return wish_service.set_ignore_debt_warning(db, user, wish_id, req.ignore)
