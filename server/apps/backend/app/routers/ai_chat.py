"""AI 问答助手端点。"""

import json
import logging
import re
import time
import uuid
from datetime import datetime
from pathlib import Path

import httpx
from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, field_validator
from sqlalchemy.orm import Session

from apps.backend.app.auth.ai_deps import require_ai_enabled
from apps.backend.app.auth.deps import require_adult
from apps.backend.app.config import settings
from apps.backend.app.database import SessionLocal, get_db
from apps.backend.app.errors import AppError, ErrorCode
from apps.backend.app.models.ai_chat_session import AIChatSession
from apps.backend.app.models.cached_file import CachedFile
from apps.backend.app.models.file_remote_location import FileRemoteLocation
from apps.backend.app.models.user import User
from apps.backend.app.schemas.ai_chat_responses import ChatResponse
from apps.backend.app.services.chat_session import ChatSessionService

router = APIRouter(prefix="/ai/chat", tags=["ai-chat"])
sessions_router = APIRouter(prefix="/ai", tags=["ai-sessions"])
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
    web_search: bool = False
    session_id: str | None = None
    # R4/R5: when present, /chat/stream proxies to /agent/{agent_id}/stream so
    # the request runs through agent_dispatch._resolve_skills (per-agent skill
    # scoping). Omitted requests fall back to the legacy /chat/ask/stream
    # adapter for backward compatibility.
    agent_id: str | None = None

    @field_validator("question")
    @classmethod
    def validate_question(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("问题不能为空")
        if len(v) > 500:
            raise ValueError("问题不能超过500字")
        return v

    @field_validator("agent_id")
    @classmethod
    def validate_agent_id(cls, v: str | None) -> str | None:
        if v is not None and not re.fullmatch(r"\d{15,20}", v):
            raise ValueError("agent_id 格式无效")
        return v


def _get_session_for_family(
    session_id: int | str | None,
    family_id: int | str,
    db: Session,
) -> AIChatSession | None:
    """Load a session by ID, enforcing family_id ownership (security invariant)."""
    if session_id is None:
        return None
    try:
        sid = int(session_id)
    except (ValueError, TypeError):
        return None
    return (
        db.query(AIChatSession)
        .filter(AIChatSession.id == sid, AIChatSession.family_id == int(family_id))
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


def _collect_answer_token_from_event(line: str) -> str | None:
    """Return final-answer token from a stream event, excluding thinking tokens."""
    try:
        event = json.loads(line)
    except json.JSONDecodeError:
        logger.warning("chat_stream received invalid NDJSON line")
        return None
    if event.get("type") != "token.stream":
        return None
    if event.get("is_thinking") is not False:
        return None
    return str(event.get("token", ""))


def _stream_error_event(task_id: str, message: str, code: str) -> str:
    return json.dumps(
        {
            "id": f"{task_id}-proxy-error",
            "type": "capability.error",
            "timestamp": time.time(),
            "capability_id": "chat",
            "task_id": task_id,
            "error": {"message": message, "code": code},
        },
        ensure_ascii=False,
        separators=(",", ":"),
    ) + "\n"


@router.post("", response_model=ChatResponse)
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
                    "X-User-Id": str(current_user.id),
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
    """流式问答，透传 agent 的 NDJSON 事件流。"""
    if body.session_id is not None:
        session = _get_session_for_family(body.session_id, current_user.family_id, db)
        if session is None:
            raise AppError(ErrorCode.NOT_FOUND)
    else:
        # Always create a new session when session_id is not provided
        session = await ChatSessionService.create_session(
            current_user.family_id, current_user.id, db
        )

    await ChatSessionService.append_message(session, "user", body.question, current_user, db)
    db.refresh(session)

    session_id = session.id
    task_id = str(uuid.uuid4())

    async def proxy_stream():
        # Emit session.start event first
        yield json.dumps(
            {"type": "session.start", "session_id": str(session_id), "task_id": task_id},
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode() + b"\n"

        # R4: when agent_id is present, route to the agent-dispatch endpoint so
        # the request runs through _resolve_skills (per-agent skill scoping).
        # Otherwise use the legacy chat_adapter path.
        if body.agent_id:
            agent_url = f"{settings.AGENT_BASE_URL}/agent/{body.agent_id}/stream"
            agent_body = {
                "message": body.question,
                "thread_id": str(session_id),
                "enable_thinking": body.deep_think,
                "web_search": body.web_search,
            }
        else:
            agent_url = f"{settings.AGENT_BASE_URL}/chat/ask/stream"
            agent_body = {
                "question": body.question,
                "deep_think": body.deep_think,
                "web_search": body.web_search,
            }

        answer_chunks: list[str] = []
        buffer = ""
        try:
            async with (
                httpx.AsyncClient(timeout=None) as client,
                client.stream(
                    "POST",
                    agent_url,
                    json=agent_body,
                    headers={
                        "X-Family-Id": str(current_user.family_id),
                        "X-Agent-Token": settings.AGENT_INTERNAL_TOKEN,
                        "X-Thread-Id": str(session_id),
                        "X-User-Id": str(current_user.id),
                    },
                    timeout=None,
                ) as resp,
            ):
                async for chunk in resp.aiter_text():
                    buffer += chunk
                    while "\n" in buffer:
                        line, buffer = buffer.split("\n", 1)
                        if not line.strip():
                            continue
                        token = _collect_answer_token_from_event(line)
                        if token is not None:
                            answer_chunks.append(token)
                        yield f"{line}\n".encode()

                if buffer.strip():
                    token = _collect_answer_token_from_event(buffer)
                    if token is not None:
                        answer_chunks.append(token)
                    yield f"{buffer}\n".encode()

        except Exception as e:
            logger.error("chat_stream proxy failed: %s", type(e).__name__)
            yield _stream_error_event(
                task_id,
                "抱歉，AI 服务暂时不可用。",
                "backend_proxy_error",
            ).encode()
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

    return StreamingResponse(proxy_stream(), media_type="application/x-ndjson; charset=utf-8")


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
            "title": s.title,
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
            return {"session_id": None, "messages": []}

    messages = await ChatSessionService.read_messages(session)
    # Return last N messages in ascending order (file is already ascending)
    if limit and len(messages) > limit:
        messages = messages[-limit:]
    return {
        "session_id": str(session.id),
        "messages": [
            {
                "id": m.get("message_id", ""),
                "role": m.get("role", ""),
                "content": m.get("content", ""),
                "created_at": m.get("timestamp", ""),
            }
            for m in messages
        ],
    }


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


# ── Unified sessions endpoints (all capabilities) ──────────────────────────

@sessions_router.get("/sessions")
def list_all_sessions(
    capability: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(require_adult),
    db: Session = Depends(get_db),
):
    """列出当前家庭所有 AI 功能的会话，支持按 capability 过滤。"""
    q = db.query(AIChatSession).filter_by(family_id=current_user.family_id)
    if capability:
        q = q.filter(AIChatSession.capability == capability)
    total = q.count()
    rows = (
        q.order_by(AIChatSession.is_pinned.desc(), AIChatSession.updated_at.desc())
        .limit(limit)
        .offset(offset)
        .all()
    )
    return {
        "sessions": [
            {
                "session_id": str(s.id),
                "family_id": str(s.family_id),
                "user_id": str(s.user_id) if s.user_id else None,
                "capability": s.capability,
                "title": s.title,
                "status": s.status,
                "last_message_summary": s.last_message_summary,
                "last_model": s.last_model,
                "has_attachments": s.has_attachments,
                "is_pinned": s.is_pinned,
                "created_at": s.created_at.isoformat() if s.created_at else None,
                "updated_at": s.updated_at.isoformat() if s.updated_at else None,
            }
            for s in rows
        ],
        "total": total,
    }


class SessionUpdateRequest(BaseModel):
    title: str | None = None
    is_pinned: bool | None = None


@sessions_router.patch("/sessions/{session_id}")
def update_session(
    session_id: str,
    body: SessionUpdateRequest,
    current_user: User = Depends(require_adult),
    db: Session = Depends(get_db),
):
    """重命名或置顶/取消置顶会话。"""
    if not re.fullmatch(r"\d{15,19}|[0-9a-fA-F\-]{32,36}", session_id):
        raise AppError(ErrorCode.NOT_FOUND)
    session = _get_session_for_family(session_id, current_user.family_id, db)
    if session is None:
        raise AppError(ErrorCode.NOT_FOUND)
    if body.title is not None:
        session.title = body.title.strip()[:256] or None
    if body.is_pinned is not None:
        session.is_pinned = body.is_pinned
    db.commit()
    return {"ok": True}


@sessions_router.delete("/sessions/{session_id}")
def delete_session(
    session_id: str,
    current_user: User = Depends(require_adult),
    db: Session = Depends(get_db),
):
    """删除单个会话及其消息文件。"""
    if not re.fullmatch(r"\d{15,19}|[0-9a-fA-F\-]{32,36}", session_id):
        raise AppError(ErrorCode.NOT_FOUND)
    session = _get_session_for_family(session_id, current_user.family_id, db)
    if session is None:
        raise AppError(ErrorCode.NOT_FOUND)
    if session.cached_file_id:
        cached_file = db.query(CachedFile).filter_by(id=session.cached_file_id).first()
        if cached_file:
            cached_file.deleted_at = datetime.utcnow()
            db.query(FileRemoteLocation).filter_by(
                file_id=session.cached_file_id, sync_status="pending"
            ).update({"sync_status": "deleted"})
    try:
        jsonl_abs = Path(settings.CHAT_DIR) / session.jsonl_path
        jsonl_abs.resolve()
        if jsonl_abs.exists():
            jsonl_abs.unlink()
        lock_file = jsonl_abs.with_suffix(".lock")
        if lock_file.exists():
            lock_file.unlink()
    except OSError as e:
        logger.warning("删除 JSONL 文件失败 session=%s: %s", session.id, type(e).__name__)
    db.delete(session)
    db.commit()
    return {"ok": True}


@sessions_router.get("/sessions/{session_id}/events")
async def stream_session_events(
    session_id: str,
    current_user: User = Depends(require_adult),
    db: Session = Depends(get_db),
):
    """代理 agent 的会话事件流（NDJSON），用于历史回放。"""
    if not re.fullmatch(r"\d{15,19}|[0-9a-fA-F\-]{32,36}", session_id):
        raise AppError(ErrorCode.NOT_FOUND)
    session = _get_session_for_family(session_id, current_user.family_id, db)
    if session is None:
        raise AppError(ErrorCode.NOT_FOUND)

    async def proxy_events():
        try:
            async with (
                httpx.AsyncClient(timeout=httpx.Timeout(connect=5.0, read=120.0, write=10.0, pool=5.0)) as client,
                client.stream(
                    "GET",
                    f"{settings.AGENT_BASE_URL}/sessions/{session_id}/events",
                    headers={
                        "X-Agent-Token": settings.AGENT_INTERNAL_TOKEN,
                        "X-Family-Id": str(current_user.family_id),
                    },
                ) as resp,
            ):
                async for chunk in resp.aiter_bytes():
                    yield chunk
        except Exception as e:
            logger.error("session events proxy failed session=%s: %s", session_id, type(e).__name__)

    return StreamingResponse(proxy_events(), media_type="application/x-ndjson; charset=utf-8")
