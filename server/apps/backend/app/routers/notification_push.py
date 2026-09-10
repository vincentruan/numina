"""Web Push subscription management endpoints."""

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from apps.backend.app.auth.deps import require_adult
from apps.backend.app.database import get_db
from apps.backend.app.models.user import User
from apps.backend.app.schemas.base import SnowflakeBase
from apps.backend.app.utils.snowflake import next_id
from packages.db.models.push_subscription import PushSubscription

router = APIRouter(prefix="/notifications/push", tags=["notifications"])


class PushSubscriptionCreate(BaseModel):
    endpoint: str
    p256dh: str
    auth: str
    user_agent: str | None = None
    app_type: str = "main"


class PushSubscriptionResponse(SnowflakeBase):
    id: int
    endpoint: str
    app_type: str


@router.post("/subscribe", response_model=PushSubscriptionResponse)
def subscribe(
    data: PushSubscriptionCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    """Register a push subscription for the current user (upsert on same user+endpoint)."""
    existing = db.query(PushSubscription).filter(
        PushSubscription.user_id == user.id,
        PushSubscription.endpoint == data.endpoint,
    ).first()

    if existing:
        existing.p256dh = data.p256dh
        existing.auth = data.auth
        existing.user_agent = data.user_agent
        existing.app_type = data.app_type
    else:
        existing = PushSubscription(
            id=next_id(),
            user_id=user.id,
            family_id=user.family_id,
            endpoint=data.endpoint,
            p256dh=data.p256dh,
            auth=data.auth,
            user_agent=data.user_agent,
            app_type=data.app_type,
        )
        db.add(existing)

    db.commit()
    db.refresh(existing)
    return existing


@router.delete("/subscribe")
def unsubscribe(
    endpoint: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    """Remove a push subscription."""
    sub = db.query(PushSubscription).filter(
        PushSubscription.user_id == user.id,
        PushSubscription.endpoint == endpoint,
    ).first()
    if sub:
        db.delete(sub)
        db.commit()
    return {"status": "ok"}


@router.get("/vapid-public-key")
def get_vapid_public_key():
    """Return the VAPID public key for client subscription."""
    from apps.backend.app.config import settings

    return {"public_key": settings.VAPID_PUBLIC_KEY}
