# backend/app/routers/notification_config.py
from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from apps.backend.app.auth.deps import require_adult
from apps.backend.app.database import get_db
from apps.backend.app.models.user import User
from apps.backend.app.schemas.notification_config import (
    EventAvailability,
    LargePurchaseStatus,
    NotificationConfigResponse,
    NotificationConfigUpdate,
    NotificationFeatureStatus,
)
from apps.backend.app.services.notification.registry import NOTIFICATION_CATEGORIES
from apps.backend.app.utils.snowflake import next_id
from packages.db.models.asset import Asset
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
            NotificationChannel.is_enabled == True,  # noqa: E712
            NotificationSubscription.reminder_type == "large_purchase",
        )
        .all()
    )
    # Check data availability for event-selector badges. Dates already in the
    # past can never fire (rules.check_expiring_soon / check_maturity bail on
    # days_left < 0), so they must not count toward "ready".
    # NOTE: uses server local date (not UTC). The digest_time convention is
    # also server-local; see scheduler_worker/jobs/__init__.py:_in_digest_window.
    today = date.today()
    has_expiring = (
        db.query(func.count(Asset.id))
        .filter(
            Asset.family_id == user.family_id,
            Asset.is_archived == False,  # noqa: E712
            Asset.warranty_expiry_date.isnot(None),
            Asset.warranty_expiry_date >= today,
        )
        .scalar()
        > 0
    )
    has_maturity = (
        db.query(func.count(Asset.id))
        .filter(
            Asset.family_id == user.family_id,
            Asset.is_archived == False,  # noqa: E712
            Asset.maturity_date.isnot(None),
            Asset.maturity_date >= today,
        )
        .scalar()
        > 0
    )

    event_availability = [
        EventAvailability(
            event_type="expiring_soon",
            status="ready" if has_expiring else "no_data",
        ),
        EventAvailability(
            event_type="maturity",
            status="ready" if has_maturity else "no_data",
        ),
        EventAvailability(
            event_type="large_purchase",
            # check_on_asset_write needs BOTH a threshold and a subscribed
            # channel before it dispatches; either half missing means the
            # event cannot fire.
            status=(
                "ready"
                if threshold_configured and subscribing_channels
                else "needs_config"
            ),
        ),
    ]
    # Every remaining registry event has no data prerequisite, so it is always
    # triggerable. Emitting them keeps the selector's badge map complete; an
    # absent entry would render as an unexplained blank.
    covered = {e.event_type for e in event_availability}
    for category in NOTIFICATION_CATEGORIES.values():
        for event_type in category["events"]:
            if event_type not in covered:
                event_availability.append(
                    EventAvailability(event_type=event_type, status="ready")
                )

    return NotificationFeatureStatus(
        large_purchase=LargePurchaseStatus(
            threshold_configured=threshold_configured,
            subscribing_channel_count=len(subscribing_channels),
            subscribing_channel_names=[c.name for c in subscribing_channels],
        ),
        event_availability=event_availability,
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
