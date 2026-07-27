"""Milestone query endpoints."""

from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from apps.backend.app.auth.deps import get_current_child_user, require_adult
from apps.backend.app.database import get_db
from apps.backend.app.errors import AppError, ErrorCode
from apps.backend.app.models.user import User
from apps.backend.app.schemas.base import SnowflakeBase
from apps.backend.app.services import milestones as svc

router = APIRouter(tags=["milestones"])


class MilestoneResponse(SnowflakeBase):
    id: int
    milestone_type: str
    triggered_at: datetime
    ref_id: int | None
    ref_type: str | None


@router.get("/child/milestones", response_model=list[MilestoneResponse])
def list_my_milestones(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_child_user),
):
    return svc.list_milestones(db, user.id, user.family_id)


@router.get(
    "/family/children/{child_id}/milestones", response_model=list[MilestoneResponse]
)
def list_child_milestones(
    child_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    # Validate child belongs to same family
    child = (
        db.query(User)
        .filter(
            User.id == child_id,
            User.family_id == user.family_id,
            User.role == "child",
        )
        .first()
    )
    if not child:
        raise AppError(ErrorCode.FAMILY_MEMBER_NOT_FOUND)
    return svc.list_milestones(db, child.id, user.family_id)
