from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from apps.backend.app.auth.ai_deps import verify_agent_token
from apps.backend.app.database import get_db
from apps.backend.app.errors import AppError, ErrorCode
from apps.backend.app.models.ai_agent import AIAgent

router = APIRouter(prefix="/internal/ai/agents", tags=["internal"])


@router.get("/{agent_id}")
def get_agent_config(
    agent_id: int,
    family_id: str = Depends(verify_agent_token),
    db: Session = Depends(get_db),
) -> dict:
    agent = db.query(AIAgent).filter(AIAgent.id == agent_id).first()
    if not agent:
        raise AppError(ErrorCode.NOT_FOUND)
    if agent.family_id != 0 and str(agent.family_id) != family_id:
        raise AppError(ErrorCode.NOT_FOUND)
    return _agent_to_dict(agent)


@router.get("/by-name/{agent_name}")
def get_agent_config_by_name(
    agent_name: str,
    family_id: str = Depends(verify_agent_token),
    db: Session = Depends(get_db),
) -> dict:
    """Look up an agent by name for the agent-side AgentRegistry.

    Returns the system agent (family_id=0) if it matches, else the family's
    custom agent with that name. Used by the agent DeerFlowAdapter to read
    per-agent attributes (e.g. memory_enabled) without threading agent_id
    through every call site.
    """
    # System agents are family_id=0 (shared). Prefer a system match, then fall
    # back to the family's own custom agent.
    agent = (
        db.query(AIAgent)
        .filter(
            AIAgent.agent_name == agent_name,
            (AIAgent.family_id == 0) | (AIAgent.family_id == int(family_id)),
        )
        .order_by(AIAgent.family_id.asc())  # system (0) first
        .first()
    )
    if not agent:
        raise AppError(ErrorCode.NOT_FOUND)
    return _agent_to_dict(agent)


def _agent_to_dict(agent: AIAgent) -> dict:
    return {
        "id": str(agent.id),
        "family_id": str(agent.family_id),
        "agent_name": agent.agent_name,
        "display_name": agent.display_name,
        "description": agent.description,
        "soul_md": agent.soul_md,
        "skills": agent.skills,
        "model": agent.model,
        "subagent_enabled": agent.subagent_enabled,
        "tool_groups": agent.tool_groups,
        "agent_type": agent.agent_type,
        "is_enabled": agent.is_enabled,
        "memory_enabled": agent.memory_enabled,
    }
