# backend/app/routers/notification_config.py
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth.deps import require_adult
from app.database import get_db
from app.models.notification_config import NotificationConfig
from app.models.user import User
from app.schemas.notification_config import (
    NotificationConfigResponse,
    NotificationConfigUpdate,
)
from app.utils.snowflake import next_id

router = APIRouter(prefix="/notification-config", tags=["notification-config"])


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
