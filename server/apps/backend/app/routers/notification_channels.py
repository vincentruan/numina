# backend/app/routers/notification_channels.py
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from apps.backend.app.auth.deps import require_adult
from apps.backend.app.database import get_db
from apps.backend.app.errors import AppError, ErrorCode
from apps.backend.app.models.notification_channel import NotificationChannel
from apps.backend.app.models.notification_subscription import NotificationSubscription
from apps.backend.app.models.reminder import Reminder
from apps.backend.app.models.user import User
from apps.backend.app.schemas.notification_channel import (
    ChannelTestResult,
    DeliveryRecord,
    NotificationChannelCreate,
    NotificationChannelResponse,
    NotificationChannelUpdate,
)
from apps.backend.app.services.notification.dispatcher import (
    send_test_notification,
)
from apps.backend.app.services.notification.registry import (
    VALID_REMINDER_TYPES,
    get_categorized_events,
)
from apps.backend.app.services.storage.config_crypto import (
    decrypt_config,
    encrypt_config,
)
from apps.backend.app.utils.snowflake import next_id
from packages.db.models.notification_channel_config import (
    NotificationChannelConfig,
)
from packages.db.models.reminder_notification import ReminderNotification

router = APIRouter(prefix="/notification-channels", tags=["notification-channels"])

VALID_CHANNEL_TYPES = {"telegram", "email", "feishu", "webpush"}

# Keys whose values must never be returned in plaintext to the frontend.
_SENSITIVE_KEYS = {
    "bot_token",
    "smtp_password",
    "secret",
    "vapid_private_key",
}
_MASK_PLACEHOLDER = "••••••••"


def _mask_config(config: dict) -> dict:
    """Return a copy of *config* with sensitive values replaced by a mask."""
    masked = {}
    for key, value in config.items():
        if key in _SENSITIVE_KEYS and value:
            masked[key] = _MASK_PLACEHOLDER
        else:
            masked[key] = value
    return masked


def _load_channel_config(db: Session, channel_id: int) -> dict:
    """Decrypt a channel's config rows.

    Values that fail to decrypt are surfaced as the mask placeholder rather
    than raw ciphertext, so the frontend knows it must ask the user to
    re-enter them.
    """
    config: dict = {}
    for row in (
        db.query(NotificationChannelConfig).filter_by(channel_id=channel_id).all()
    ):
        decrypted = decrypt_config(row.value_encrypted)
        if decrypted is not None:
            config.update(decrypted)
        else:
            config[row.key] = _MASK_PLACEHOLDER
    return config


def _latest_deliveries(
    db: Session, channel_ids: list[int]
) -> dict[int, ReminderNotification]:
    """Return the newest ReminderNotification row per channel, in one query."""
    if not channel_ids:
        return {}
    rows = (
        db.query(ReminderNotification)
        .filter(ReminderNotification.channel_id.in_(channel_ids))
        .order_by(ReminderNotification.created_at.desc())
        .all()
    )
    latest: dict[int, ReminderNotification] = {}
    for row in rows:
        latest.setdefault(row.channel_id, row)
    return latest


def _to_response(
    channel: NotificationChannel,
    db: Session,
    last_delivery: ReminderNotification | None = None,
) -> NotificationChannelResponse:
    subs = db.query(NotificationSubscription).filter_by(channel_id=channel.id).all()
    config = _load_channel_config(db, channel.id)
    return NotificationChannelResponse(
        id=channel.id,
        family_id=channel.family_id,
        channel_type=channel.channel_type,
        name=channel.name,
        is_enabled=channel.is_enabled,
        config=_mask_config(config),
        subscriptions=[s.reminder_type for s in subs],
        digest_mode=channel.digest_mode,
        digest_time=channel.digest_time,
        created_at=channel.created_at,
        updated_at=channel.updated_at,
        last_delivery_status=last_delivery.status if last_delivery else None,
        last_delivery_at=last_delivery.created_at if last_delivery else None,
    )


@router.get("/events")
def get_events(user: User = Depends(require_adult)):
    """Return categorized event types for frontend event selector."""
    return get_categorized_events()


@router.get("", response_model=list[NotificationChannelResponse])
def list_channels(db: Session = Depends(get_db), user: User = Depends(require_adult)):
    channels = db.query(NotificationChannel).filter_by(family_id=user.family_id).all()
    latest = _latest_deliveries(db, [c.id for c in channels])
    return [_to_response(c, db, latest.get(c.id)) for c in channels]


@router.post("", response_model=NotificationChannelResponse, status_code=201)
def create_channel(
    req: NotificationChannelCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    if req.channel_type not in VALID_CHANNEL_TYPES:
        raise AppError(ErrorCode.VALIDATION_ERROR)
    # email / webpush cannot deliver digests today — pin them to immediate so a
    # mis-sent request cannot produce failed ReminderNotifications.
    digest_mode = getattr(req, "digest_mode", "immediate")
    if req.channel_type in ("email", "webpush"):
        digest_mode = "immediate"
    channel = NotificationChannel(
        id=next_id(),
        family_id=user.family_id,
        channel_type=req.channel_type,
        name=req.name,
        is_enabled=req.is_enabled if req.is_enabled is not None else True,
        digest_mode=digest_mode,
        digest_time=getattr(req, "digest_time", "21:00"),
    )
    db.add(channel)
    db.flush()
    for key, value in (req.config or {}).items():
        db.add(
            NotificationChannelConfig(
                channel_id=channel.id,
                key=key,
                value_encrypted=encrypt_config({key: str(value)}),
            )
        )
    for rtype in req.subscriptions:
        if rtype in VALID_REMINDER_TYPES:
            db.add(
                NotificationSubscription(
                    id=next_id(), channel_id=channel.id, reminder_type=rtype
                )
            )
    db.commit()
    db.refresh(channel)
    return _to_response(channel, db, _latest_deliveries(db, [channel.id]).get(channel.id))


@router.put("/{channel_id}", response_model=NotificationChannelResponse)
def update_channel(
    channel_id: int,
    req: NotificationChannelUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    channel = (
        db.query(NotificationChannel)
        .filter_by(id=channel_id, family_id=user.family_id)
        .first()
    )
    if not channel:
        raise AppError(ErrorCode.NOT_FOUND)
    if req.name is not None:
        channel.name = req.name
    if req.config is not None:
        # When the frontend echoes back the mask for a sensitive field it means
        # "unchanged" — keep the stored ciphertext instead of re-encrypting the
        # literal mask over the real secret.
        existing_rows = {
            row.key: row.value_encrypted
            for row in db.query(NotificationChannelConfig)
            .filter_by(channel_id=channel.id)
            .all()
        }
        db.query(NotificationChannelConfig).filter_by(channel_id=channel.id).delete()
        for key, value in req.config.items():
            if key in _SENSITIVE_KEYS and value == _MASK_PLACEHOLDER:
                if key in existing_rows:
                    db.add(
                        NotificationChannelConfig(
                            channel_id=channel.id,
                            key=key,
                            value_encrypted=existing_rows[key],
                        )
                    )
                continue
            db.add(
                NotificationChannelConfig(
                    channel_id=channel.id,
                    key=key,
                    value_encrypted=encrypt_config({key: str(value)}),
                )
            )
    if req.is_enabled is not None:
        channel.is_enabled = req.is_enabled
    if req.subscriptions is not None:
        db.query(NotificationSubscription).filter_by(channel_id=channel.id).delete()
        for rtype in req.subscriptions:
            if rtype in VALID_REMINDER_TYPES:
                db.add(
                    NotificationSubscription(
                        id=next_id(), channel_id=channel.id, reminder_type=rtype
                    )
                )
    # email / webpush cannot deliver digests today — silently pin them to immediate
    # so a stale value from the frontend cannot produce failed ReminderNotifications.
    digest_mode = req.digest_mode
    if digest_mode is not None and channel.channel_type in ("email", "webpush"):
        digest_mode = "immediate"
    if digest_mode is not None:
        channel.digest_mode = digest_mode
    if req.digest_time is not None:
        channel.digest_time = req.digest_time
    db.commit()
    db.refresh(channel)
    return _to_response(channel, db, _latest_deliveries(db, [channel.id]).get(channel.id))


@router.get("/{channel_id}/delivery-history", response_model=list[DeliveryRecord])
def get_delivery_history(
    channel_id: int,
    limit: int = 20,
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    """Return the most recent deliveries for a channel, newest first."""
    channel = (
        db.query(NotificationChannel)
        .filter_by(id=channel_id, family_id=user.family_id)
        .first()
    )
    if not channel:
        raise AppError(ErrorCode.NOT_FOUND)

    rows = (
        db.query(ReminderNotification, Reminder)
        .join(Reminder, Reminder.id == ReminderNotification.reminder_id)
        .filter(ReminderNotification.channel_id == channel.id)
        .order_by(ReminderNotification.created_at.desc())
        .limit(max(1, min(limit, 100)))
        .all()
    )
    return [
        DeliveryRecord(
            id=rn.id,
            reminder_id=rn.reminder_id,
            reminder_type=reminder.reminder_type,
            reminder_title=reminder.title,
            status=rn.status,
            created_at=rn.created_at,
        )
        for rn, reminder in rows
    ]


@router.post("/{channel_id}/test", response_model=ChannelTestResult)
async def test_channel(
    channel_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    """Send a one-off test message so the user can verify connectivity."""
    channel = (
        db.query(NotificationChannel)
        .filter_by(id=channel_id, family_id=user.family_id)
        .first()
    )
    if not channel:
        raise AppError(ErrorCode.NOT_FOUND)
    config = _load_channel_config(db, channel.id)
    success, error = await send_test_notification(db, channel, config)
    return ChannelTestResult(success=success, error=error)


@router.delete("/{channel_id}", status_code=204)
def delete_channel(
    channel_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    channel = (
        db.query(NotificationChannel)
        .filter_by(id=channel_id, family_id=user.family_id)
        .first()
    )
    if not channel:
        raise AppError(ErrorCode.NOT_FOUND)
    db.query(NotificationSubscription).filter_by(channel_id=channel.id).delete()
    db.query(NotificationChannelConfig).filter_by(channel_id=channel.id).delete()
    db.delete(channel)
    db.commit()
