# backend/app/routers/notification_channels.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth.deps import require_adult
from app.database import get_db
from app.models.notification_channel import NotificationChannel
from app.models.notification_subscription import NotificationSubscription
from app.models.user import User
from app.schemas.notification_channel import (
    NotificationChannelCreate,
    NotificationChannelResponse,
    NotificationChannelUpdate,
)
from app.services.storage.config_crypto import decrypt_config, encrypt_config
from app.utils.snowflake import next_id

router = APIRouter(prefix="/notification-channels", tags=["notification-channels"])

VALID_CHANNEL_TYPES = {"telegram", "email"}
VALID_REMINDER_TYPES = {"large_purchase", "allocation_drift", "expiring_soon", "maturity"}


def _to_response(channel: NotificationChannel, db: Session) -> NotificationChannelResponse:
    subs = db.query(NotificationSubscription).filter_by(channel_id=channel.id).all()
    return NotificationChannelResponse(
        id=channel.id,
        family_id=channel.family_id,
        channel_type=channel.channel_type,
        name=channel.name,
        is_enabled=channel.is_enabled,
        subscriptions=[s.reminder_type for s in subs],
        created_at=channel.created_at,
        updated_at=channel.updated_at,
    )


@router.get("", response_model=list[NotificationChannelResponse])
def list_channels(db: Session = Depends(get_db), user: User = Depends(require_adult)):
    channels = db.query(NotificationChannel).filter_by(family_id=user.family_id).all()
    return [_to_response(c, db) for c in channels]


@router.post("", response_model=NotificationChannelResponse, status_code=201)
def create_channel(
    req: NotificationChannelCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    if req.channel_type not in VALID_CHANNEL_TYPES:
        raise HTTPException(status_code=422, detail="不支持的渠道类型")
    channel = NotificationChannel(
        id=next_id(),
        family_id=user.family_id,
        channel_type=req.channel_type,
        name=req.name,
        config=encrypt_config(req.config),
        is_enabled=req.is_enabled,
    )
    db.add(channel)
    db.flush()
    for rtype in req.subscriptions:
        if rtype in VALID_REMINDER_TYPES:
            db.add(NotificationSubscription(id=next_id(), channel_id=channel.id, reminder_type=rtype))
    db.commit()
    db.refresh(channel)
    return _to_response(channel, db)


@router.put("/{channel_id}", response_model=NotificationChannelResponse)
def update_channel(
    channel_id: int,
    req: NotificationChannelUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    channel = db.query(NotificationChannel).filter_by(id=channel_id, family_id=user.family_id).first()
    if not channel:
        raise HTTPException(status_code=404, detail="渠道不存在")
    if req.name is not None:
        channel.name = req.name
    if req.config is not None:
        channel.config = encrypt_config(req.config)
    if req.is_enabled is not None:
        channel.is_enabled = req.is_enabled
    if req.subscriptions is not None:
        db.query(NotificationSubscription).filter_by(channel_id=channel.id).delete()
        for rtype in req.subscriptions:
            if rtype in VALID_REMINDER_TYPES:
                db.add(NotificationSubscription(id=next_id(), channel_id=channel.id, reminder_type=rtype))
    db.commit()
    db.refresh(channel)
    return _to_response(channel, db)


@router.delete("/{channel_id}", status_code=204)
def delete_channel(
    channel_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    channel = db.query(NotificationChannel).filter_by(id=channel_id, family_id=user.family_id).first()
    if not channel:
        raise HTTPException(status_code=404, detail="渠道不存在")
    db.query(NotificationSubscription).filter_by(channel_id=channel.id).delete()
    db.delete(channel)
    db.commit()
