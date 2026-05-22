from fastapi import APIRouter, Depends
from sqlalchemy import or_
from sqlalchemy.orm import Session

from apps.backend.app.auth.deps import require_adult, require_owner
from apps.backend.app.database import get_db
from apps.backend.app.errors import AppError, ErrorCode
from apps.backend.app.models.ai_agent import AIAgent
from apps.backend.app.models.user import User
from apps.backend.app.schemas.ai_agent import (
    AgentCreateRequest,
    AgentListResponse,
    AgentResponse,
    AgentUpdateRequest,
)

router = APIRouter(prefix="/ai/agents", tags=["ai-agents"])


def _to_response(agent: AIAgent, user: User) -> AgentResponse:
    is_owner = user.role == "owner"
    data = {
        col.name: getattr(agent, col.name)
        for col in agent.__table__.columns
    }
    data["can_edit"] = is_owner if agent.is_builtin else (is_owner and agent.family_id == user.family_id)
    data["can_delete"] = False if agent.is_builtin else (is_owner and agent.family_id == user.family_id)
    return AgentResponse.model_validate(data)


@router.get("", response_model=AgentListResponse)
def list_agents(
    current_user: User = Depends(require_adult),
    db: Session = Depends(get_db),
) -> AgentListResponse:
    agents = (
        db.query(AIAgent)
        .filter(
            or_(
                AIAgent.family_id == 0,
                AIAgent.family_id == current_user.family_id,
            )
        )
        .order_by(AIAgent.display_order, AIAgent.created_at)
        .all()
    )
    builtin = [_to_response(a, current_user) for a in agents if a.is_builtin]
    custom = [_to_response(a, current_user) for a in agents if not a.is_builtin]
    return AgentListResponse(builtin=builtin, custom=custom)


@router.get("/{agent_id}", response_model=AgentResponse)
def get_agent(
    agent_id: int,
    current_user: User = Depends(require_adult),
    db: Session = Depends(get_db),
) -> AgentResponse:
    agent = db.query(AIAgent).filter(AIAgent.id == agent_id).first()
    if not agent:
        raise AppError(ErrorCode.NOT_FOUND)
    if agent.family_id != 0 and agent.family_id != current_user.family_id:
        raise AppError(ErrorCode.NOT_FOUND)
    return _to_response(agent, current_user)


@router.post("", response_model=AgentResponse, status_code=201)
def create_agent(
    payload: AgentCreateRequest,
    current_user: User = Depends(require_owner),
    db: Session = Depends(get_db),
) -> AgentResponse:
    existing = (
        db.query(AIAgent)
        .filter(
            AIAgent.family_id == current_user.family_id,
            AIAgent.agent_name == payload.agent_name,
        )
        .first()
    )
    if existing:
        raise AppError(ErrorCode.VALIDATION_ERROR, "agent_name 已存在")

    builtin_conflict = (
        db.query(AIAgent)
        .filter(AIAgent.family_id == 0, AIAgent.agent_name == payload.agent_name)
        .first()
    )
    if builtin_conflict:
        raise AppError(ErrorCode.VALIDATION_ERROR, "不能使用内置智能体的名称")

    agent = AIAgent(
        family_id=current_user.family_id,
        created_by=current_user.id,
        **payload.model_dump(),
    )
    db.add(agent)
    db.commit()
    db.refresh(agent)
    return _to_response(agent, current_user)


@router.put("/{agent_id}", response_model=AgentResponse)
def update_agent(
    agent_id: int,
    payload: AgentUpdateRequest,
    current_user: User = Depends(require_owner),
    db: Session = Depends(get_db),
) -> AgentResponse:
    agent = db.query(AIAgent).filter(AIAgent.id == agent_id).first()
    if not agent:
        raise AppError(ErrorCode.NOT_FOUND)
    if agent.family_id != 0 and agent.family_id != current_user.family_id:
        raise AppError(ErrorCode.NOT_FOUND)

    updates = payload.model_dump(exclude_unset=True)

    if agent.is_builtin:
        allowed = {"icon", "color", "display_order"}
        disallowed = set(updates.keys()) - allowed
        if disallowed:
            raise AppError(ErrorCode.VALIDATION_ERROR, f"内置智能体只允许修改: {', '.join(allowed)}")

    for key, value in updates.items():
        setattr(agent, key, value)

    db.commit()
    db.refresh(agent)
    return _to_response(agent, current_user)


@router.delete("/{agent_id}", status_code=204)
def delete_agent(
    agent_id: int,
    current_user: User = Depends(require_owner),
    db: Session = Depends(get_db),
) -> None:
    agent = db.query(AIAgent).filter(AIAgent.id == agent_id).first()
    if not agent:
        raise AppError(ErrorCode.NOT_FOUND)
    if agent.is_builtin:
        raise AppError(ErrorCode.FAMILY_FORBIDDEN, "内置智能体不可删除")
    if agent.family_id != current_user.family_id:
        raise AppError(ErrorCode.NOT_FOUND)
    db.delete(agent)
    db.commit()


@router.put("/{agent_id}/toggle", response_model=AgentResponse)
def toggle_agent(
    agent_id: int,
    enabled: bool,
    current_user: User = Depends(require_owner),
    db: Session = Depends(get_db),
) -> AgentResponse:
    agent = db.query(AIAgent).filter(AIAgent.id == agent_id).first()
    if not agent:
        raise AppError(ErrorCode.NOT_FOUND)
    if agent.family_id != 0 and agent.family_id != current_user.family_id:
        raise AppError(ErrorCode.NOT_FOUND)
    agent.is_enabled = enabled
    db.commit()
    db.refresh(agent)
    return _to_response(agent, current_user)
