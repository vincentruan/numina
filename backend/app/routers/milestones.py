"""Milestone query endpoints."""

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.auth.deps import get_current_child_user, require_adult
from app.database import get_db
from app.errors import AppError, ErrorCode
from app.models.user import User
from app.services import milestones as svc

router = APIRouter(tags=["milestones"])


class MilestoneResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    milestone_type: str
    triggered_at: datetime
    ref_id: str | None
    ref_type: str | None


@router.get("/child/milestones", response_model=list[MilestoneResponse])
def list_my_milestones(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_child_user),
):
    return svc.list_milestones(db, user.id, user.family_id)


@router.get("/family/children/{child_id}/milestones", response_model=list[MilestoneResponse])
def list_child_milestones(
    child_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    child_id_str = str(child_id)
    # Validate child belongs to same family
    child = db.query(User).filter(
        User.id == child_id_str,
        User.family_id == user.family_id,
        User.role == "child",
    ).first()
    if not child:
        raise AppError(ErrorCode.FAMILY_MEMBER_NOT_FOUND)
    return svc.list_milestones(db, child_id_str, user.family_id)
