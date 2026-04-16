"""AI 问答助手端点。"""

import logging
from datetime import datetime

import httpx
from fastapi import APIRouter, Depends
from pydantic import BaseModel, field_validator
from sqlalchemy.orm import Session

from app.auth.ai_deps import require_ai_enabled
from app.auth.deps import require_adult
from app.config import settings
from app.database import get_db
from app.errors import AppError, ErrorCode
from app.models.ai_chat_message import AIChatMessage
from app.models.user import User

router = APIRouter(prefix="/ai/chat", tags=["ai-chat"])
logger = logging.getLogger(__name__)


class ChatRequest(BaseModel):
    question: str

    @field_validator("question")
    @classmethod
    def validate_question(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("问题不能为空")
        if len(v) > 500:
            raise ValueError("问题不能超过500字")
        return v


@router.post("")
async def chat(
    body: ChatRequest,
    current_user: User = Depends(require_adult),
    _ai: None = Depends(require_ai_enabled),
    db: Session = Depends(get_db),
):
    """发送问题，获取 AI 回答，并持久化对话历史。"""
    if not body.question.strip():
        raise AppError(ErrorCode.AI_QUESTION_EMPTY)

    # Save user message
    user_msg = AIChatMessage(
        family_id=current_user.family_id,
        role="user",
        content=body.question.strip(),
    )
    db.add(user_msg)
    db.commit()

    # Call agent
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{settings.AGENT_BASE_URL}/chat/ask",
                json={"question": body.question.strip()},
                headers={
                    "X-Family-Id": current_user.family_id,
                    "X-Agent-Token": settings.AGENT_INTERNAL_TOKEN,
                },
            )
            resp.raise_for_status()
            resp_data = resp.json()
            # AgentResponse shape: summary carries the answer text
            answer = resp_data.get("summary") or resp_data.get("answer", "")
    except httpx.TimeoutException:
        db.rollback()
        raise AppError(ErrorCode.AI_SERVICE_TIMEOUT) from None
    except Exception as e:
        logger.error(f"调用 agent chat 失败: {e}")
        db.rollback()
        raise AppError(ErrorCode.AI_SERVICE_UNAVAILABLE) from e

    # Save assistant message only on success
    assistant_msg = AIChatMessage(
        family_id=current_user.family_id,
        role="assistant",
        content=answer,
    )
    db.add(assistant_msg)
    db.commit()

    return {
        "question": body.question.strip(),
        "answer": answer,
        "message_id": assistant_msg.id,
    }


@router.get("/history")
def get_history(
    limit: int = 20,
    current_user: User = Depends(require_adult),
    db: Session = Depends(get_db),
):
    messages = (
        db.query(AIChatMessage)
        .filter(AIChatMessage.family_id == current_user.family_id)
        .order_by(AIChatMessage.created_at.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "id": m.id,
            "role": m.role,
            "content": m.content,
            "created_at": m.created_at.isoformat(),
        }
        for m in reversed(messages)
    ]


@router.delete("/history")
def clear_history(
    current_user: User = Depends(require_adult),
    db: Session = Depends(get_db),
):
    db.query(AIChatMessage).filter(
        AIChatMessage.family_id == current_user.family_id
    ).delete()
    db.commit()
    return {"ok": True}


@router.put("/read")
def mark_read(
    current_user: User = Depends(require_adult),
    db: Session = Depends(get_db),
):
    """更新 ai_chat_last_read_at，清除未读红点。"""
    current_user.ai_chat_last_read_at = datetime.utcnow()
    db.commit()
    return {"ok": True}
