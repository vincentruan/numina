"""AI capability discovery endpoint."""

import logging

import httpx
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth.ai_deps import require_ai_enabled
from app.auth.deps import require_adult
from app.config import settings
from app.database import get_db
from app.models.family_skill_config import FamilySkillConfig
from app.models.user import User
from app.routers.ai_skills import BUILTIN_CAPABILITIES
from app.schemas.ai_capability import AICapabilitySchema
from app.services.capability_catalog import apply_capability_overrides

router = APIRouter(prefix="/ai/capabilities", tags=["ai-capabilities"])
logger = logging.getLogger(__name__)


def _fallback_capability(capability_id: str) -> dict:
    return {
        "id": capability_id,
        "name": capability_id,
        "description": "",
        "category": "general",
        "ui": {
            "icon": "message-circle",
            "color": "#6366f1",
            "route": None,
            "input_mode": "free_text",
            "placeholder": None,
            "example_questions": [],
        },
        "policy": {
            "allowed_roles": ["member", "admin"],
            "require_confirmation": False,
            "max_tokens": 2000,
            "enable_thinking": True,
            "enable_tools": [],
        },
        "skill_id": capability_id,
        "harness_config": {},
    }


def _enabled_capability_ids(family_id: str, db: Session) -> set[str]:
    rows = {
        row.capability: row
        for row in db.query(FamilySkillConfig)
        .filter(FamilySkillConfig.family_id == family_id)
        .all()
    }
    enabled: set[str] = set()
    for capability in BUILTIN_CAPABILITIES:
        row = rows.get(capability)
        if row is None or row.is_enabled:
            enabled.add(capability)
    return enabled


async def _load_agent_capabilities() -> list[dict]:
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"{settings.AGENT_BASE_URL}/capabilities",
                headers={"X-Agent-Token": settings.AGENT_INTERNAL_TOKEN},
            )
            resp.raise_for_status()
            return list(resp.json())
    except Exception as exc:
        logger.warning("capability discovery fell back to built-ins: %s", type(exc).__name__)
        return [_fallback_capability(capability) for capability in BUILTIN_CAPABILITIES]


@router.get("", response_model=list[AICapabilitySchema])
async def list_capabilities(
    current_user: User = Depends(require_adult),
    _ai: None = Depends(require_ai_enabled),
    db: Session = Depends(get_db),
) -> list[AICapabilitySchema]:
    enabled_ids = _enabled_capability_ids(str(current_user.family_id), db)
    agent_capabilities = await _load_agent_capabilities()
    filtered = [
        apply_capability_overrides(cap)
        for cap in agent_capabilities
        if cap.get("id") in enabled_ids
    ]
    return [AICapabilitySchema.model_validate(cap) for cap in filtered]
