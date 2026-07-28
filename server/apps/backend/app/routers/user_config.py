"""User-level configurable settings API.

GET   /api/v1/user/config  — read all settings
PATCH /api/v1/user/config  — update settings
"""
import logging

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from apps.backend.app.auth.deps import get_current_user
from apps.backend.app.database import get_db
from apps.backend.app.models.user import User
from apps.backend.app.schemas.config import UserConfigResponse, UserConfigUpdate
from apps.backend.app.services.config_service import (
    get_all_user_settings,
    update_user_settings,
)

router = APIRouter(prefix="/user/config", tags=["user-config"])
logger = logging.getLogger(__name__)


@router.get("", response_model=UserConfigResponse)
def get_config(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Return all user settings merged with defaults."""
    return get_all_user_settings(db, user.id)


@router.patch("", response_model=UserConfigResponse)
def update_config(
    req: UserConfigUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Update user settings."""
    return update_user_settings(db, user.id, req.settings)
