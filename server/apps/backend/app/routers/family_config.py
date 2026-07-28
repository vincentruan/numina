"""Family-level configurable settings API.

GET   /api/v1/family/config             — read all settings (any adult)
PATCH /api/v1/family/config             — update settings (owner only)
GET   /api/v1/family/config/definitions — get setting metadata (any adult)
"""
import logging

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from apps.backend.app.auth.deps import require_adult
from apps.backend.app.database import get_db
from apps.backend.app.errors.codes import ErrorCode
from apps.backend.app.errors.exceptions import AppError
from apps.backend.app.models.user import User
from apps.backend.app.schemas.config import (
    FamilyConfigResponse,
    FamilyConfigUpdate,
    SettingDefinitionResponse,
)
from apps.backend.app.services.config_registry import FAMILY_SETTING_DEFINITIONS
from apps.backend.app.services.config_service import (
    get_all_family_settings,
    update_family_settings,
)

router = APIRouter(prefix="/family/config", tags=["family-config"])
logger = logging.getLogger(__name__)


@router.get("", response_model=FamilyConfigResponse)
def get_config(
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    """Return all family settings merged with defaults."""
    return get_all_family_settings(db, user.family_id)


@router.patch("", response_model=FamilyConfigResponse)
def update_config(
    req: FamilyConfigUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    """Update family settings. Owner only."""
    if user.role != "owner":
        raise AppError(ErrorCode.FAMILY_FORBIDDEN)
    return update_family_settings(db, user.family_id, req.settings)


@router.get("/definitions", response_model=dict[str, SettingDefinitionResponse])
def get_definitions(
    user: User = Depends(require_adult),
):
    """Return setting definitions for frontend rendering."""
    return {
        key: SettingDefinitionResponse(
            type=defn.type,
            default=defn.default,
            min=defn.min,
            max=defn.max,
            step=defn.step,
            allowed_values=defn.allowed_values,
            label_key=defn.label_key,
            description_key=defn.description_key,
        )
        for key, defn in FAMILY_SETTING_DEFINITIONS.items()
    }
