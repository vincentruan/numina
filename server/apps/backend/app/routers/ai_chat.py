"""AI 问答助手端点。"""

import json
import logging
import re
import time
import urllib.parse
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Literal

import httpx
from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response, StreamingResponse
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
from apps.backend.app.schemas.base import SnowflakeBase
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
    # When deep_think=true, controls the agent's reasoning depth/tool budget.
    # Maps to OpenAI o-series reasoning_effort + DeerFlow planning toggles.
    # Ignored when deep_think=false.
    reasoning_effort: Literal["low", "medium", "high"] = "medium"
    session_id: str | None = None
    # R4/R5: when present, /chat/stream proxies to /agent/{agent_id}/stream so
    # the request runs through agent_dispatch._resolve_skills (per-agent skill
    # scoping). Omitted requests fall back to the legacy /chat/ask/stream
    # adapter for backward compatibility.
    agent_id: str | None = None
    source: str | None = None
    # DeerFlow execution mode parameters (Phase 2)
    # is_plan_mode: enables DeerFlow plan_mode for multi-step task decomposition
    is_plan_mode: bool = False
    # subagent_enabled: enables DeerFlow subagent coordination (Ultra mode)
    subagent_enabled: bool = False

    @field_validator("question")
    @classmethod
    def validate_question(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("问题不能为空")
        if len(v) > 3000:
            raise ValueError("问题不能超过3000字")
        return v

    @field_validator("agent_id")
    @classmethod
    def validate_agent_id(cls, v: str | None) -> str | None:
        if v is not None and not re.fullmatch(r"\d{15,20}", v):
            raise ValueError("agent_id 格式无效")
        return v


# ── Session Response Schemas (SnowflakeBase for ID serialization) ────────────

class SessionSummaryResponse(SnowflakeBase):
    """Single session summary for list_all_sessions endpoint."""

    session_id: int
    family_id: int
    user_id: int | None = None
    agent_id: int | None = None
    title: str | None = None
    status: str | None = None
    last_message_summary: str | None = None
    last_model: str | None = None
    has_attachments: bool = False
    is_pinned: bool = False
    source: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


class SessionListResponse(BaseModel):
    """Response wrapper for list_all_sessions endpoint."""

    sessions: list[SessionSummaryResponse]
    total: int


class SessionDefaultResponse(SnowflakeBase):
    """Response for get_system_default_session endpoint."""

    session_id: int
    status: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


class SessionDefaultWrapper(BaseModel):
    """Wrapper for system default session response."""

    session: SessionDefaultResponse | None = None


class SessionForkResponse(SnowflakeBase):
    """Response for fork_session endpoint."""

    session_id: int
    message_count: int = 0


class SessionForkWrapper(BaseModel):
    """Wrapper for fork session response."""

    ok: bool = True
    session_id: int
    message_count: int = 0


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
        agent_id_int = int(body.agent_id) if body.agent_id else None
        session = await ChatSessionService.create_session(
            current_user.family_id, current_user.id, db, agent_id=agent_id_int
        )
        if body.source:
            session.source = body.source
            db.commit()

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
                "reasoning_effort": body.reasoning_effort,
                "source": body.source,
                # DeerFlow execution mode parameters (Phase 2)
                "is_plan_mode": body.is_plan_mode,
                "subagent_enabled": body.subagent_enabled,
            }
        else:
            agent_url = f"{settings.AGENT_BASE_URL}/chat/ask/stream"
            agent_body = {
                "question": body.question,
                "deep_think": body.deep_think,
                "web_search": body.web_search,
                "reasoning_effort": body.reasoning_effort,
                "source": body.source,
                # DeerFlow execution mode parameters (Phase 2)
                "is_plan_mode": body.is_plan_mode,
                "subagent_enabled": body.subagent_enabled,
            }

        answer_chunks: list[str] = []
        try:
            async with (
                httpx.AsyncClient(timeout=130.0) as client,  # 130s to allow backend errors before frontend 120s timeout
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
                ) as resp,
            ):
                async for line in resp.aiter_lines():
                    if not line.strip():
                        continue
                    token = _collect_answer_token_from_event(line)
                    if token is not None:
                        answer_chunks.append(token)
                    yield f"{line}\n".encode()

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
    agent_id: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(require_adult),
    db: Session = Depends(get_db),
) -> SessionListResponse:
    """列出当前家庭所有 AI 功能的会话，支持按 agent_id 过滤。"""
    q = db.query(AIChatSession).filter_by(family_id=current_user.family_id)
    if agent_id:
        try:
            q = q.filter(AIChatSession.agent_id == int(agent_id))
        except (ValueError, TypeError):
            raise AppError(ErrorCode.VALIDATION_ERROR, "agent_id 必须为数字") from None
    total = q.count()
    rows = (
        q.order_by(AIChatSession.is_pinned.desc(), AIChatSession.updated_at.desc())
        .limit(limit)
        .offset(offset)
        .all()
    )
    return SessionListResponse(
        sessions=[
            SessionSummaryResponse(
                session_id=s.id,
                family_id=s.family_id,
                user_id=s.user_id,
                agent_id=s.agent_id,
                title=s.title,
                status=s.status,
                last_message_summary=s.last_message_summary,
                last_model=s.last_model,
                has_attachments=s.has_attachments,
                is_pinned=s.is_pinned,
                source=s.source,
                created_at=s.created_at.isoformat() if s.created_at else None,
                updated_at=s.updated_at.isoformat() if s.updated_at else None,
            )
            for s in rows
        ],
        total=total,
    )


@sessions_router.get("/sessions/system-default")
def get_system_default_session(
    max_age_hours: int = Query(default=6, ge=1, le=24),
    current_user: User = Depends(require_adult),
    db: Session = Depends(get_db),
) -> SessionDefaultWrapper:
    """查找当前用户最近的系统默认会话（source=system_default），用于缓存复用。"""
    cutoff = datetime.utcnow() - timedelta(hours=max_age_hours)
    session = (
        db.query(AIChatSession)
        .filter(
            AIChatSession.family_id == current_user.family_id,
            AIChatSession.user_id == current_user.id,
            AIChatSession.source == "system_default",
            AIChatSession.created_at >= cutoff,
        )
        .order_by(AIChatSession.created_at.desc())
        .first()
    )
    if session is None:
        return SessionDefaultWrapper(session=None)
    return SessionDefaultWrapper(
        session=SessionDefaultResponse(
            session_id=session.id,
            status=session.status,
            created_at=session.created_at.isoformat() if session.created_at else None,
            updated_at=session.updated_at.isoformat() if session.updated_at else None,
        )
    )


class SessionUpdateRequest(BaseModel):
    title: str | None = None
    is_pinned: bool | None = None


class SessionForkRequest(BaseModel):
    fork_from_message_id: str  # The message_id to fork from (exclusive - this message and all after are excluded)


@sessions_router.post("/sessions/{session_id}/fork")
async def fork_session(
    session_id: str,
    body: SessionForkRequest,
    current_user: User = Depends(require_adult),
    db: Session = Depends(get_db),
) -> SessionForkWrapper:
    """Fork a session from a specific message, creating a new branch.

    This is used for the "edit and resend" feature - when a user edits a message,
    we fork the session from that message's position, preserving all previous context,
    and the edited message will be sent as a new message in the forked session.

    Args:
        session_id: The original session to fork
        body: Contains fork_from_message_id - the message to fork from (exclusive)

    Returns:
        New session info with session_id for the frontend to use
    """
    if not re.fullmatch(r"\d{15,19}|[0-9a-fA-F\-]{32,36}", session_id):
        raise AppError(ErrorCode.NOT_FOUND)
    session = _get_session_for_family(session_id, current_user.family_id, db)
    if session is None:
        raise AppError(ErrorCode.NOT_FOUND)

    try:
        new_session = await ChatSessionService.fork_session(
            session, body.fork_from_message_id, current_user, db
        )
    except ValueError as e:
        logger.warning("fork_session failed: %s", str(e))
        raise AppError(ErrorCode.NOT_FOUND) from e

    return SessionForkWrapper(
        ok=True,
        session_id=new_session.id,
        message_count=new_session.message_count,
    )


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


# ── Suggestions endpoint (Phase 7: DeerFlow follow-up suggestions) ─────────────

class SuggestionMessage(BaseModel):
    role: str  # "user" | "assistant"
    content: str


class SuggestionsRequest(BaseModel):
    messages: list[SuggestionMessage]
    n: int = 3
    model_name: str | None = None


class SuggestionsResponse(BaseModel):
    suggestions: list[str]


@sessions_router.post("/sessions/{session_id}/suggestions", response_model=SuggestionsResponse)
async def generate_suggestions(
    session_id: str,
    body: SuggestionsRequest,
    current_user: User = Depends(require_adult),
    db: Session = Depends(get_db),
):
    """生成追问建议（DeerFlow Phase 7）。

    安全校验:
    1. session_id 必须属于当前 family
    2. 使用租户配置的模型调用 LLM

    返回:
    - suggestions: 3 条追问建议字符串
    """
    if not re.fullmatch(r"\d{15,19}|[0-9a-fA-F\-]{32,36}", session_id):
        raise AppError(ErrorCode.NOT_FOUND)
    session = _get_session_for_family(session_id, current_user.family_id, db)
    if session is None:
        raise AppError(ErrorCode.NOT_FOUND)

    if not body.messages:
        return SuggestionsResponse(suggestions=[])

    n = body.n

    # Format conversation for LLM
    conversation_parts: list[str] = []
    for m in body.messages:
        role = m.role.strip().lower()
        if role in ("user", "human"):
            conversation_parts.append(f"用户: {m.content.strip()}")
        elif role in ("assistant", "ai"):
            conversation_parts.append(f"助手: {m.content.strip()}")
        else:
            conversation_parts.append(f"{m.role}: {m.content.strip()}")
    conversation = "\n".join(conversation_parts).strip()

    if not conversation:
        return SuggestionsResponse(suggestions=[])

    # Call agent for suggestions
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{settings.AGENT_BASE_URL}/suggestions/generate",
                json={
                    "conversation": conversation,
                    "n": n,
                    "model_name": body.model_name,
                },
                headers={
                    "X-Family-Id": str(current_user.family_id),
                    "X-Agent-Token": settings.AGENT_INTERNAL_TOKEN,
                    "X-User-Id": str(current_user.id),
                },
            )
            resp.raise_for_status()
            resp_data = resp.json()
            suggestions = resp_data.get("suggestions", [])
    except httpx.TimeoutException:
        logger.warning("suggestions request timed out session=%s", session_id)
        return SuggestionsResponse(suggestions=[])
    except Exception as e:
        logger.error("suggestions request failed session=%s: %s", session_id, type(e).__name__)
        return SuggestionsResponse(suggestions=[])

    # Clean suggestions
    cleaned = [s.replace("\n", " ").strip() for s in suggestions if s.strip()]
    cleaned = cleaned[:n]
    return SuggestionsResponse(suggestions=cleaned)


# ── Artifacts endpoint (Phase 5: DeerFlow artifact preview) ───────────────────


@sessions_router.get("/sessions/{session_id}/artifacts/{filepath:path}")
async def get_artifact(
    session_id: str,
    filepath: str,
    download: bool = Query(default=False),
    current_user: User = Depends(require_adult),
    db: Session = Depends(get_db),
):
    """获取 Artifact 内容（DeerFlow Phase 5）。

    安全校验:
    1. session_id 必须属于当前 family
    2. filepath 必须是该 session 产生的 artifact
    3. 防止路径遍历攻击（包括双编码绕过）

    返回:
    - 文件内容（Content-Type 根据扩展名自动设置）
    """
    if not re.fullmatch(r"\d{15,19}|[0-9a-fA-F\-]{32,36}", session_id):
        raise AppError(ErrorCode.NOT_FOUND)
    session = _get_session_for_family(session_id, current_user.family_id, db)
    if session is None:
        raise AppError(ErrorCode.NOT_FOUND)

    # Security: Decode filepath completely to prevent double-encoding bypass
    # FastAPI decodes once, but attacker can double-encode to bypass traversal check
    decoded_filepath = filepath
    prev_decoded = None
    max_decode_iterations = 3  # Prevent infinite loop
    iteration = 0
    while decoded_filepath != prev_decoded and iteration < max_decode_iterations:
        prev_decoded = decoded_filepath
        decoded_filepath = urllib.parse.unquote(decoded_filepath)
        iteration += 1

    # Security: Reject any path containing URL-encoded characters after max iterations
    # This catches triple-encoding and other edge cases
    if "%" in decoded_filepath:
        logger.warning(
            "artifact filepath still contains encoded chars after decode: %s",
            filepath,
        )
        raise AppError(ErrorCode.NOT_FOUND)

    # Security: Reject path traversal patterns in decoded path
    if ".." in decoded_filepath or decoded_filepath.startswith("/") or decoded_filepath.startswith("\\"):
        logger.warning("artifact path traversal attempt: %s -> %s", filepath, decoded_filepath)
        raise AppError(ErrorCode.NOT_FOUND)

    # Try to find artifact in session's artifact directory
    # For now, artifacts are stored in the chat directory alongside JSONL
    artifact_dir = Path(settings.CHAT_DIR) / f"session_{session_id}" / "artifacts"
    artifact_path = artifact_dir / decoded_filepath

    # Security: Final check - resolved path must be within artifact_dir
    try:
        artifact_path.resolve().relative_to(artifact_dir.resolve())
    except ValueError:
        logger.warning("artifact resolved path escapes directory: %s", decoded_filepath)
        raise AppError(ErrorCode.NOT_FOUND) from None

    if not artifact_path.exists():
        raise AppError(ErrorCode.NOT_FOUND)

    # Read file content
    try:
        content = artifact_path.read_text()
    except UnicodeDecodeError:
        # Binary file - read as bytes
        content = artifact_path.read_bytes()
        media_type = "application/octet-stream"
    except OSError as e:
        logger.warning("artifact read failed session=%s path=%s: %s", session_id, filepath, type(e).__name__)
        raise AppError(ErrorCode.NOT_FOUND) from None

    # Determine media type from extension
    ext = artifact_path.suffix.lower()
    MEDIA_TYPES: dict[str, str] = {
        ".json": "application/json",
        ".yaml": "application/yaml",
        ".yml": "application/yaml",
        ".md": "text/markdown",
        ".markdown": "text/markdown",
        ".html": "text/html",
        ".htm": "text/html",
        ".css": "text/css",
        ".js": "application/javascript",
        ".ts": "application/javascript",
        ".vue": "text/x-vue",
        ".py": "text/x-python",
        ".go": "text/x-go",
        ".rs": "text/x-rust",
        ".txt": "text/plain",
        ".pdf": "application/pdf",
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".gif": "image/gif",
        ".webp": "image/webp",
        ".svg": "image/svg+xml",
    }
    media_type = MEDIA_TYPES.get(ext, "text/plain")

    # Set headers
    headers = {}
    if download:
        filename = artifact_path.name
        # Security: sanitize filename to prevent CRLF injection in Content-Disposition
        # Replace any CR/LF characters and quote the filename per RFC 6266
        safe_filename = filename.replace("\r", "").replace("\n", "")
        quoted_filename = urllib.parse.quote(safe_filename)
        headers["Content-Disposition"] = f"attachment; filename=\"{quoted_filename}\""

    return Response(
        content=content,
        media_type=media_type,
        headers=headers,
    )
