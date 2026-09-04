# backend/app/routers/reminders.py
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from apps.backend.app.auth.deps import require_adult
from apps.backend.app.database import get_db
from apps.backend.app.errors import AppError, ErrorCode
from apps.backend.app.models.reminder import Reminder
from apps.backend.app.models.user import User
from apps.backend.app.schemas.reminder import ReminderResponse, ReminderSummary
from apps.backend.app.services.notification.dispatcher import get_reminder_summary

router = APIRouter(prefix="/reminders", tags=["reminders"])


@router.get("/summary", response_model=ReminderSummary)
def get_summary(db: Session = Depends(get_db), user: User = Depends(require_adult)):
    return get_reminder_summary(db, family_id=user.family_id)


@router.get("", response_model=list[ReminderResponse])
def list_reminders(
    status: str = Query("active"),
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    reminders = (
        db.query(Reminder)
        .filter_by(family_id=user.family_id, status=status)
        .order_by(Reminder.created_at.desc())
        .all()
    )
    return [ReminderResponse.model_validate(r) for r in reminders]


@router.patch("/{reminder_id}/dismiss", response_model=ReminderResponse)
def dismiss_reminder(
    reminder_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    reminder = db.query(Reminder).filter_by(id=reminder_id, family_id=user.family_id).first()
    if not reminder:
        raise AppError(ErrorCode.NOT_FOUND)
    reminder.status = "dismissed"
    reminder.dismissed_at = datetime.now(UTC)
    db.commit()
    db.refresh(reminder)
    return ReminderResponse.model_validate(reminder)
