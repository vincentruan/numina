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
    }
