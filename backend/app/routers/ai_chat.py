"""AI 问答助手端点。"""

import logging
from datetime import datetime
from pathlib import Path

import httpx
from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, field_validator
from sqlalchemy.orm import Session

from app.auth.ai_deps import require_ai_enabled
from app.auth.deps import require_adult
from app.config import settings
from app.database import SessionLocal, get_db
from app.errors import AppError, ErrorCode
from app.models.ai_chat_session import AIChatSession
from app.models.cached_file import CachedFile
from app.models.file_remote_location import FileRemoteLocation
from app.models.user import User
from app.services.chat_session import ChatSessionService

router = APIRouter(prefix="/ai/chat", tags=["ai-chat"])
logger = logging.getLogger(__name__)


class ChatRequest(BaseModel):
    question: str
    session_id: str | None = None

    @field_validator("question")
    @classmethod
    def validate_question(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("问题不能为空")
        if len(v) > 500:
            raise ValueError("问题不能超过500字")
        return v


class ChatStreamRequest(BaseModel):
    question: str
    deep_think: bool = False
    session_id: str | None = None

    @field_validator("question")
    @classmethod
    def validate_question(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("问题不能为空")
        if len(v) > 500:
            raise ValueError("问题不能超过500字")
        return v


def _get_session_for_family(
    session_id: str | None,
    family_id: str,
    db: Session,
) -> AIChatSession | None:
    """Load a session by ID, enforcing family_id ownership (security invariant)."""
    if session_id is None:
        return None
    return (
        db.query(AIChatSession)
        .filter_by(id=session_id, family_id=family_id)
        .first()
    )


def _get_latest_session(family_id: str, db: Session) -> AIChatSession | None:
    """Get the most recent session for a family."""
    return (
        db.query(AIChatSession)
        .filter_by(family_id=family_id)
        .order_by(AIChatSession.created_at.desc())
        .first()
    )


@router.post("")
async def chat(
    body: ChatRequest,
    current_user: User = Depends(require_adult),
    _ai: None = Depends(require_ai_enabled),
    db: Session = Depends(get_db),
):
    """发送问题，获取 AI 回答，并持久化对话历史到 JSONL 文件。"""
    # Resolve session — always filter by family_id (security invariant)
    if body.session_id is not None:
        session = _get_session_for_family(body.session_id, current_user.family_id, db)
        if session is None:
            raise AppError(ErrorCode.NOT_FOUND)
    else:
        session = _get_latest_session(current_user.family_id, db)
        if session is None:
            session = await ChatSessionService.create_session(
                current_user.family_id, current_user.id, db
            )

    # Append user message to JSONL
    await ChatSessionService.append_message(session, "user", body.question, current_user, db)
    # Refresh session object after executor commit to avoid stale ORM state on next call
    db.refresh(session)

    # Call agent
    try:
        async with httpx.AsyncClient(timeout=45.0) as client:
            resp = await client.post(
                f"{settings.AGENT_BASE_URL}/chat/ask",
                json={"question": body.question},
                headers={
                    "X-Family-Id": str(current_user.family_id),
                    "X-Agent-Token": settings.AGENT_INTERNAL_TOKEN,
                    "X-Thread-Id": str(session.id),
                },
            )
            resp.raise_for_status()
            resp_data = resp.json()
            answer = resp_data.get("summary") or resp_data.get("answer", "")
    except httpx.TimeoutException:
        raise AppError(ErrorCode.AI_SERVICE_TIMEOUT) from None
    except Exception as e:
        logger.error("调用 agent chat 失败: %s", type(e).__name__)
        raise AppError(ErrorCode.AI_SERVICE_UNAVAILABLE) from e

    # Append assistant message to JSONL
    await ChatSessionService.append_message(session, "assistant", answer, current_user, db)

    return {
        "question": body.question,
        "answer": answer,
        "message_id": session.id,
        "session_id": session.id,
    }


@router.post("/stream")
async def chat_stream(
    body: ChatStreamRequest,
    current_user: User = Depends(require_adult),
    _ai: None = Depends(require_ai_enabled),
    db: Session = Depends(get_db),
):
    """流式问答，支持 deep_think 模式。透传 agent 的 [THINK]/[TEXT] 前缀流。"""
    if body.session_id is not None:
        session = _get_session_for_family(body.session_id, current_user.family_id, db)
        if session is None:
            raise AppError(ErrorCode.NOT_FOUND)
    else:
        session = _get_latest_session(current_user.family_id, db)
        if session is None:
            session = await ChatSessionService.create_session(
                current_user.family_id, current_user.id, db
            )

    await ChatSessionService.append_message(session, "user", body.question, current_user, db)
    db.refresh(session)

    session_id = session.id

    async def proxy_stream():
        answer_chunks: list[str] = []
        try:
            async with (
                httpx.AsyncClient(timeout=None) as client,
                client.stream(
                    "POST",
                    f"{settings.AGENT_BASE_URL}/chat/ask/stream",
                    json={"question": body.question, "deep_think": body.deep_think},
                    headers={
                        "X-Family-Id": str(current_user.family_id),
                        "X-Agent-Token": settings.AGENT_INTERNAL_TOKEN,
                        "X-Thread-Id": str(session_id),
                    },
                    timeout=None,
                ) as resp,
            ):
                async for chunk in resp.aiter_text():
                    # Collect answer chunks for persistence (strip [TEXT] prefix)
                    if chunk.startswith("[TEXT]"):
                        answer_chunks.append(chunk[6:])
                    yield chunk.encode("utf-8")

        except Exception as e:
            logger.error("chat_stream proxy failed: %s", type(e).__name__)
            yield "[TEXT]抱歉，AI 服务暂时不可用。".encode()
        finally:
            # Persist the full answer after stream completes
            if answer_chunks:
                with SessionLocal() as persist_db:
                    try:
                        persist_session = _get_session_for_family(session_id, current_user.family_id, persist_db)
                        if persist_session:
                            await ChatSessionService.append_message(
                                persist_session, "assistant", "".join(answer_chunks), current_user, persist_db
                            )
                    except Exception as e:
                        logger.error("chat_stream persist failed: %s", type(e).__name__)

    return StreamingResponse(proxy_stream(), media_type="text/plain; charset=utf-8")


@router.get("/sessions")
def get_sessions(
    limit: int = Query(default=50, ge=1, le=200),
    current_user: User = Depends(require_adult),
    db: Session = Depends(get_db),
):
    """列出当前家庭的所有对话会话。"""
    sessions = (
        db.query(AIChatSession)
        .filter_by(family_id=current_user.family_id)
        .order_by(AIChatSession.created_at.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "session_id": s.id,
            "created_at": s.created_at.isoformat(),
            "message_count": s.message_count,
            "last_preview": s.last_preview,
        }
        for s in sessions
    ]


@router.get("/history")
async def get_history(
    session_id: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=200),
    current_user: User = Depends(require_adult),
    db: Session = Depends(get_db),
):
    """获取对话历史。"""
    if session_id is not None:
        session = _get_session_for_family(session_id, current_user.family_id, db)
        if session is None:
            raise AppError(ErrorCode.NOT_FOUND)
    else:
        session = _get_latest_session(current_user.family_id, db)
        if session is None:
            return []

    messages = await ChatSessionService.read_messages(session)
    # Return last N messages in ascending order (file is already ascending)
    if limit and len(messages) > limit:
        messages = messages[-limit:]
    return [
        {
            "id": m.get("message_id", ""),
            "role": m.get("role", ""),
            "content": m.get("content", ""),
            "created_at": m.get("timestamp", ""),
        }
        for m in messages
    ]


@router.delete("/history")
def clear_history(
    session_id: str | None = Query(default=None),
    current_user: User = Depends(require_adult),
    db: Session = Depends(get_db),
):
    """删除对话历史。"""
    if session_id is not None:
        sessions = []
        session = _get_session_for_family(session_id, current_user.family_id, db)
        if session:
            sessions = [session]
    else:
        sessions = (
            db.query(AIChatSession)
            .filter_by(family_id=current_user.family_id)
            .all()
        )

    for s in sessions:
        if s.cached_file_id:
            cached_file = db.query(CachedFile).filter_by(id=s.cached_file_id).first()
            if cached_file:
                cached_file.deleted_at = datetime.utcnow()
                # Mark pending sync locations as deleted to prevent syncing deleted files
                db.query(FileRemoteLocation).filter_by(
                    file_id=s.cached_file_id, sync_status="pending"
                ).update({"sync_status": "deleted"})
        # Delete JSONL file from disk to avoid orphaned files
        try:
            jsonl_abs = Path(settings.CHAT_DIR) / s.jsonl_path
            jsonl_abs.resolve()  # validate path exists before unlink
            if jsonl_abs.exists():
                jsonl_abs.unlink()
            # Remove lock file if present
            lock_file = jsonl_abs.with_suffix(".lock")
            if lock_file.exists():
                lock_file.unlink()
        except OSError as e:
            logger.warning("删除 JSONL 文件失败 session=%s: %s", s.id, type(e).__name__)
        db.delete(s)

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
