# backend/app/routers/notification_config.py
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from apps.backend.app.auth.deps import require_adult
from apps.backend.app.database import get_db
from apps.backend.app.models.user import User
from apps.backend.app.schemas.notification_config import (
    LargePurchaseStatus,
    NotificationConfigResponse,
    NotificationConfigUpdate,
    NotificationFeatureStatus,
)
from apps.backend.app.utils.snowflake import next_id
from packages.db.models.notification_channel import NotificationChannel
from packages.db.models.notification_config import NotificationConfig
from packages.db.models.notification_subscription import NotificationSubscription

router = APIRouter(prefix="/notification-config", tags=["notification-config"])


@router.get("/status", response_model=NotificationFeatureStatus)
def get_feature_status(
    db: Session = Depends(get_db), user: User = Depends(require_adult)
):
    """Report which half of a two-part feature is missing.

    ``large_purchase`` only fires when *both* a threshold is configured and at
    least one enabled channel subscribes to the event. Each side lives on a
    different page, so the UI needs this to tell the user what is missing.
    """
    config = db.query(NotificationConfig).filter_by(family_id=user.family_id).first()
    threshold_configured = config is not None and (
        config.large_purchase_threshold_fixed is not None
        or config.large_purchase_threshold_multiplier is not None
    )

    subscribing_channels = (
        db.query(NotificationChannel)
        .join(
            NotificationSubscription,
            NotificationChannel.id == NotificationSubscription.channel_id,
        )
        .filter(
            NotificationChannel.family_id == user.family_id,
            NotificationSubscription.reminder_type == "large_purchase",
        )
        .all()
    )
    return NotificationFeatureStatus(
        large_purchase=LargePurchaseStatus(
            threshold_configured=threshold_configured,
            subscribing_channel_count=len(subscribing_channels),
            subscribing_channel_names=[c.name for c in subscribing_channels],
        )
    )


@router.get("", response_model=NotificationConfigResponse)
def get_config(db: Session = Depends(get_db), user: User = Depends(require_adult)):
    config = db.query(NotificationConfig).filter_by(family_id=user.family_id).first()
    if not config:
        config = NotificationConfig(id=next_id(), family_id=user.family_id)
        db.add(config)
        db.commit()
        db.refresh(config)
    return NotificationConfigResponse.model_validate(config)


@router.put("", response_model=NotificationConfigResponse)
def update_config(
    req: NotificationConfigUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    config = db.query(NotificationConfig).filter_by(family_id=user.family_id).first()
    if not config:
        config = NotificationConfig(id=next_id(), family_id=user.family_id)
        db.add(config)
    for key, val in req.model_dump(exclude_unset=True).items():
        setattr(config, key, val)
    db.commit()
    db.refresh(config)
    return NotificationConfigResponse.model_validate(config)
