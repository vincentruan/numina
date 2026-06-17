"""AI capability discovery endpoint."""

import logging

import httpx
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from apps.backend.app.auth.ai_deps import require_ai_enabled
from apps.backend.app.auth.deps import require_adult
from apps.backend.app.config import settings
from apps.backend.app.database import get_db
from apps.backend.app.models.family_skill_config import FamilySkillConfig
from apps.backend.app.models.user import User
from apps.backend.app.routers.ai_skills import BUILTIN_CAPABILITIES
from apps.backend.app.schemas.ai_capability import AICapabilitySchema
from apps.backend.app.services.agent_client import AgentClient
from apps.backend.app.services.capability_catalog import apply_capability_overrides

router = APIRouter(prefix="/ai/capabilities", tags=["ai-capabilities"])
logger = logging.getLogger(__name__)

# Routing-only capabilities exposed by /ai/capabilities for frontend discovery.
# These are not skills (not toggleable in skill management) — they map to fixed
# routes (`/ai/chat`, `/ai/time-machine`) that always exist when AI is enabled.
# The agent's `services.capability_registry.FIXED_CAPABILITY_DEFS` is the source
# of truth for their full UI metadata; this list mirrors their IDs locally for
# the enabled-set check and the fallback when the agent is unreachable.
_ROUTING_CAPABILITIES: tuple[str, ...] = ("chat", "time_machine")


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
    # Routing capabilities (chat, time_machine) are always enabled — they are
    # fixed destinations, not skills. They do not appear in FamilySkillConfig.
    enabled.update(_ROUTING_CAPABILITIES)
    return enabled


async def _load_agent_capabilities(family_id: int) -> list[dict]:
    try:
        agent_client = AgentClient(family_id, timeout=10.0)
        resp = await agent_client.get("/capabilities")
        resp.raise_for_status()
        return list(resp.json())
    except Exception as exc:
        logger.warning(
            "capability discovery fell back to built-ins: %s", type(exc).__name__
        )
        ids = list(BUILTIN_CAPABILITIES) + list(_ROUTING_CAPABILITIES)
        return [_fallback_capability(capability) for capability in ids]


@router.get("", response_model=list[AICapabilitySchema])
async def list_capabilities(
    current_user: User = Depends(require_adult),
    _ai: None = Depends(require_ai_enabled),
    db: Session = Depends(get_db),
) -> list[AICapabilitySchema]:
    enabled_ids = _enabled_capability_ids(str(current_user.family_id), db)
    agent_capabilities = await _load_agent_capabilities(current_user.family_id)
    filtered = [
        apply_capability_overrides(cap)
        for cap in agent_capabilities
        if cap.get("id") in enabled_ids
    ]
    return [AICapabilitySchema.model_validate(cap) for cap in filtered]
