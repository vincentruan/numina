"""AI 问答助手端点。

SSE event type mapping from the agent's internal NDJSON event types to
the public SSE event names used in the three-track protocol:

    token.stream     → messages   (AI text/thinking tokens)
    session.start    → session.start
    phase.*          → custom     (connection/thinking/answering phases)
    tool.call/result → custom     (tool execution progress)
    capability.end   → end        (stream complete)
    capability.error → error      (stream error)
"""

import json
import logging
import re
import urllib.parse
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Literal

import httpx
from fastapi import APIRouter, Depends, Query, Request, UploadFile
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel, field_validator
from sqlalchemy.orm import Session

from apps.backend.app.auth.ai_deps import require_ai_enabled
from apps.backend.app.auth.deps import require_adult
from apps.backend.app.config import settings
from apps.backend.app.constants.system_ids import NUMINA_AGENT_ID
from apps.backend.app.database import get_db
from apps.backend.app.errors import AppError, ErrorCode
from apps.backend.app.models.ai_chat_feedback import AIChatMessageFeedback
from apps.backend.app.models.ai_chat_session import AIChatSession
from apps.backend.app.models.user import User
from apps.backend.app.schemas.ai_chat_responses import ChatResponse
from apps.backend.app.schemas.base import SnowflakeBase
from apps.backend.app.schemas.file_record import FileRecordResponse
from apps.backend.app.services.agent_client import AgentClient
from apps.backend.app.services.chat_session import ChatSessionService
from apps.backend.app.services.storage.service import StorageService

router = APIRouter(prefix="/ai/chat", tags=["ai-chat"])
sessions_router = APIRouter(prefix="/ai", tags=["ai-sessions"])
logger = logging.getLogger(__name__)

# ── SSE Constants ──────────────────────────────────────────────────────────────

# SSE response headers shared across all streaming endpoints.
_SSE_HEADERS: dict[str, str] = {
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",
}


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


class SessionDefaultResponse(SnowflakeBase):
    """Response for get_system_default_session endpoint."""

    # session_id can be either a Snowflake int (legacy) or a UUID string
    # (current LangGraph thread IDs). Typed as str so both serialize correctly.
    session_id: str
    status: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


class SessionDefaultWrapper(BaseModel):
    """Wrapper for system default session response."""

    session: SessionDefaultResponse | None = None


def _get_session_for_family(
    session_id: int | str | None,
    family_id: int | str,
    db: Session,
) -> AIChatSession | None:
    """Load a session by ID, enforcing family_id ownership (security invariant)."""
    if session_id is None:
        return None
    try:
        fid = int(family_id)
    except (ValueError, TypeError):
        return None
    try:
        sid = int(session_id)
        return (
            db.query(AIChatSession)
            .filter(AIChatSession.id == sid, AIChatSession.family_id == fid)
            .first()
        )
    except (ValueError, TypeError):
        # UUID format — query as string (DeerFlow agent creates UUID thread_ids)
        return (
            db.query(AIChatSession)
            .filter(AIChatSession.id == str(session_id), AIChatSession.family_id == fid)
            .first()
        )


def _get_latest_session(family_id: int, db: Session) -> AIChatSession | None:
    """Get the most recent session for a family."""
    return (
        db.query(AIChatSession)
        .filter_by(family_id=family_id)
        .order_by(AIChatSession.created_at.desc())
        .first()
    )


@router.post("", response_model=ChatResponse)
async def chat(
    body: ChatRequest,
    current_user: User = Depends(require_adult),
    _ai: None = Depends(require_ai_enabled),
    db: Session = Depends(get_db),
):
    """发送问题，获取 AI 回答。

    对话历史由 DeerFlow checkpointer 持久化（agent /api/threads/{id}/runs/stream），
    后端不再写 JSONL（旧 ChatSessionService 路径已废弃）。
    """
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

    # Call agent
    try:
        agent_client = AgentClient(
            current_user.family_id, current_user.id, timeout=45.0
        )
        resp = await agent_client.post(
            "/chat/ask",
            json={"question": body.question},
            headers={
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

    return {
        "question": body.question,
        "answer": answer,
        "message_id": session.id,
        "session_id": session.id,
    }


@router.post("/stream")
async def chat_stream(
    body: ChatStreamRequest,
    request: Request,
    current_user: User = Depends(require_adult),
    _ai: None = Depends(require_ai_enabled),
    db: Session = Depends(get_db),
):
    """流式问答，透传 agent 的 NDJSON 事件流，并根据 Accept header 决定输出格式。

    - `Accept: text/event-stream` → SSE 格式（默认，新版前端）
    - 其他 Accept → NDJSON 格式（向后兼容，旧版前端）
    """
    # U5: Backward compatibility — detect preferred output format from Accept header
    accept_header = request.headers.get("Accept", "")
    use_sse = "text/event-stream" in accept_header or not accept_header
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

    session_id = session.id
    task_id = str(uuid.uuid4())

    async def proxy_stream():
        # Emit session.start as first event (SSE or NDJSON depending on Accept header)
        start_event = {"session_id": str(session_id), "task_id": task_id}
        if use_sse:
            yield f"event: session.start\ndata: {json.dumps(start_event, ensure_ascii=False)}\n\n".encode()
        else:
            yield (
                json.dumps(
                    {"type": "session.start", **start_event},
                    ensure_ascii=False,
                    separators=(",", ":"),
                ).encode()
                + b"\n"
            )

        # Route to the runs.py endpoint (LangGraph SSE format).
        # When agent_id is absent, fall back to the 小鸣 system agent (NUMINA_AGENT_ID).
        agent_id = body.agent_id or str(NUMINA_AGENT_ID)
        agent_url = f"/api/threads/{session_id}/runs/stream"
        request_json = {
            "assistant_id": agent_id,
            "input": {
                "messages": [{"role": "user", "content": body.question}],
            },
            "metadata": {
                "deep_think": body.deep_think,
                "web_search": body.web_search,
                "reasoning_effort": body.reasoning_effort,
                "source": body.source,
                "is_plan_mode": body.is_plan_mode,
                "subagent_enabled": body.subagent_enabled,
            },
        }

        answer_chunks: list[str] = []
        try:
            agent_client = AgentClient(
                current_user.family_id, current_user.id, timeout=130.0
            )
            async with agent_client.stream(
                "POST",
                agent_url,
                json=request_json,
                headers={"X-Thread-Id": str(session_id)},
            ) as resp:
                # runs.py returns SSE directly — passthrough with SSE-aware parsing
                sse_buffer: list[str] = []
                async for line in resp.aiter_lines():
                    if not line.strip() and sse_buffer:
                        # Complete SSE event — forward it
                        full_event = "\n".join(sse_buffer) + "\n\n"
                        yield full_event.encode()

                        # Parse event type and data for answer token collection
                        event_type = ""
                        data_text = ""
                        for ev_line in sse_buffer:
                            if ev_line.startswith("event: "):
                                event_type = ev_line[7:]
                            elif ev_line.startswith("data: "):
                                data_text = ev_line[6:]

                        if event_type == "messages" and data_text:
                            try:
                                msg_data = json.loads(data_text)
                                if (
                                    isinstance(msg_data, dict)
                                    and msg_data.get("type") == "ai"
                                    and msg_data.get("content")
                                ):
                                    answer_chunks.append(msg_data["content"])
                            except json.JSONDecodeError:
                                pass

                        sse_buffer = []
                    elif line.strip():
                        sse_buffer.append(line)

                    if await request.is_disconnected():
                        logger.info(
                            "chat_stream client disconnected session=%s", session_id
                        )
                        break

        except Exception as e:
            logger.error("chat_stream proxy failed: %s", type(e).__name__)
            if use_sse:
                err_payload = json.dumps(
                    {
                        "error": "抱歉，AI 服务暂时不可用。",
                        "code": "backend_proxy_error",
                    },
                    ensure_ascii=False,
                )
                yield f"event: error\ndata: {err_payload}\n\n".encode()
            else:
                yield (
                    json.dumps(
                        {
                            "type": "capability.error",
                            "error": {
                                "message": "抱歉，AI 服务暂时不可用。",
                                "code": "backend_proxy_error",
                            },
                        },
                        ensure_ascii=False,
                        separators=(",", ":"),
                    ).encode()
                    + b"\n"
                )

    return StreamingResponse(
        proxy_stream(),
        media_type="text/event-stream"
        if use_sse
        else "application/x-ndjson; charset=utf-8",
        headers=_SSE_HEADERS if use_sse else {},
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
            session_id=str(session.id),
            status=session.status,
            created_at=session.created_at.isoformat() if session.created_at else None,
            updated_at=session.updated_at.isoformat() if session.updated_at else None,
        )
    )


@sessions_router.get("/sessions/{session_id}/events")
async def stream_session_events(
    session_id: str,
    current_user: User = Depends(require_adult),
    db: Session = Depends(get_db),
):
    """代理 agent 的会话事件流（SSE），用于历史回放。"""
    if not re.fullmatch(r"\d{15,19}|[0-9a-fA-F\-]{32,36}", session_id):
        raise AppError(ErrorCode.NOT_FOUND)
    session = _get_session_for_family(session_id, current_user.family_id, db)
    if session is None:
        raise AppError(ErrorCode.NOT_FOUND)

    async def proxy_events():
        try:
            agent_client = AgentClient(
                current_user.family_id, current_user.id, timeout=120.0
            )
            async with agent_client.stream(
                "GET",
                f"/sessions/{session_id}/events",
            ) as resp:
                async for chunk in resp.aiter_bytes():
                    yield chunk
        except Exception as e:
            logger.error(
                "session events proxy failed session=%s: %s",
                session_id,
                type(e).__name__,
            )

    return StreamingResponse(
        proxy_events(),
        media_type="text/event-stream",
        headers=_SSE_HEADERS,
    )


# ── Message Feedback (点赞/点踩) ─────────────────────────────────────────────


class FeedbackRequest(BaseModel):
    """点赞/点踩请求体。feedback: 1=点赞, -1=点踩, 0=取消。"""

    feedback: Literal[1, -1, 0]


class FeedbackResponse(BaseModel):
    """单条消息的反馈状态回执。"""

    message_id: str
    feedback: int


class FeedbackMapResponse(BaseModel):
    """某会话下当前用户所有消息的反馈状态 (用于历史回填)。"""

    items: dict[str, int]


@sessions_router.post(
    "/sessions/{session_id}/messages/{message_id}/feedback",
    response_model=FeedbackResponse,
)
def submit_message_feedback(
    session_id: str,
    message_id: str,
    body: FeedbackRequest,
    current_user: User = Depends(require_adult),
    db: Session = Depends(get_db),
) -> FeedbackResponse:
    """提交对某条 AI 消息的点赞/点踩。

    语义:再点同一个值会取消(feedback=0)。按用户独立记录,家庭内成员互不影响。
    安全校验:session_id 必须属于当前 family。
    """
    if not re.fullmatch(r"\d{15,19}|[0-9a-fA-F\-]{32,36}", session_id):
        raise AppError(ErrorCode.NOT_FOUND)
    session = _get_session_for_family(session_id, current_user.family_id, db)
    if session is None:
        raise AppError(ErrorCode.NOT_FOUND)

    thread_id = str(session.id)
    row = (
        db.query(AIChatMessageFeedback)
        .filter(
            AIChatMessageFeedback.family_id == current_user.family_id,
            AIChatMessageFeedback.thread_id == thread_id,
            AIChatMessageFeedback.message_id == message_id,
            AIChatMessageFeedback.user_id == current_user.id,
        )
        .first()
    )
    if row is None:
        row = AIChatMessageFeedback(
            family_id=current_user.family_id,
            user_id=current_user.id,
            thread_id=thread_id,
            message_id=message_id,
            feedback=body.feedback,
        )
        db.add(row)
    else:
        # 再点同一个值 → 取消 (0);否则切换为新值
        row.feedback = 0 if row.feedback == body.feedback else body.feedback
    db.commit()
    return FeedbackResponse(message_id=message_id, feedback=row.feedback)


@sessions_router.get(
    "/sessions/{session_id}/feedback",
    response_model=FeedbackMapResponse,
)
def get_session_feedback(
    session_id: str,
    current_user: User = Depends(require_adult),
    db: Session = Depends(get_db),
) -> FeedbackMapResponse:
    """获取某会话下当前用户对所有消息的反馈状态 (用于历史加载时回填高亮)。"""
    if not re.fullmatch(r"\d{15,19}|[0-9a-fA-F\-]{32,36}", session_id):
        raise AppError(ErrorCode.NOT_FOUND)
    session = _get_session_for_family(session_id, current_user.family_id, db)
    if session is None:
        raise AppError(ErrorCode.NOT_FOUND)

    thread_id = str(session.id)
    rows = (
        db.query(AIChatMessageFeedback)
        .filter(
            AIChatMessageFeedback.family_id == current_user.family_id,
            AIChatMessageFeedback.thread_id == thread_id,
            AIChatMessageFeedback.user_id == current_user.id,
            AIChatMessageFeedback.feedback != 0,
        )
        .all()
    )
    items = {r.message_id: r.feedback for r in rows}
    return FeedbackMapResponse(items=items)


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
    if ".." in decoded_filepath:
        logger.warning(
            "artifact path traversal attempt: %s -> %s", filepath, decoded_filepath
        )
        raise AppError(ErrorCode.NOT_FOUND)

    # Strip DeerFlow virtual sandbox prefix (/mnt/user-data/outputs/) so the
    # bare filename can be resolved against the tenant reports directory.
    from packages.core.path_manager import (
        DEERFLOW_SANDBOX_OUTPUT_PREFIX,
        DEERFLOW_SANDBOX_SKILLS_PREFIX,
    )

    is_skills_path = False
    if decoded_filepath.startswith(DEERFLOW_SANDBOX_SKILLS_PREFIX):
        # /mnt/skills/ paths resolve to the agent's builtin skills directory
        # (read-only, shared across families — no tenant isolation needed for
        # public skill definitions like SKILL.md)
        is_skills_path = True
        decoded_filepath = decoded_filepath[len(DEERFLOW_SANDBOX_SKILLS_PREFIX) :]
    elif decoded_filepath.startswith(DEERFLOW_SANDBOX_OUTPUT_PREFIX):
        decoded_filepath = decoded_filepath[len(DEERFLOW_SANDBOX_OUTPUT_PREFIX) :]

    # After stripping, reject any remaining absolute paths
    if decoded_filepath.startswith("/") or decoded_filepath.startswith("\\"):
        logger.warning(
            "artifact path traversal attempt: %s -> %s", filepath, decoded_filepath
        )
        raise AppError(ErrorCode.NOT_FOUND)

    # Try to find artifact in two locations (search order matters):
    # 1. Per-thread sandbox outputs (DeerFlow layout, unified 2026-07-19):
    #    workspaces/users/{family_id}/threads/{thread_id}/user-data/outputs/
    #    (agent write_file/str_replace with thread_id write here — per-thread isolation)
    # 2. Tenant reports directory: workspaces/tenants/{family_id}/reports/
    #    (MCP tools without thread_id, or old files — per-family fallback)
    # 3. Builtin skills directory (read-only, for /mnt/skills/ paths):
    #    workspaces/builtin/skills/ (symlinked from agent/skills/builtin at startup)
    family_id = current_user.family_id
    data_root = (
        Path(settings.DATA_ROOT).expanduser()
        if hasattr(settings, "DATA_ROOT")
        else Path.home() / ".numina" / "data"
    )

    # DeerFlow layout: {DEER_FLOW_HOME}/users/{family_id}/threads/{tid}/user-data/outputs/
    # DEER_FLOW_HOME (agent) = AGENT_DATA_DIR = {DATA_ROOT}/workspaces
    family_threads = data_root / "workspaces" / "users" / str(family_id) / "threads"
    builtin_skills_root = data_root / "workspaces" / "builtin" / "skills"
    possible_paths = []
    allowed_dirs = []

    if is_skills_path:
        # /mnt/skills/ paths → resolve against builtin skills directory (read-only).
        # DeerFlow maps /mnt/skills/public → agent/skills/builtin/public, but the
        # agent startup symlinks flatten the public/private category, so
        # "public/chat/SKILL.md" → builtin/skills/chat/SKILL.md.
        # Try both with and without the first segment (category prefix).
        skills_rel = Path(decoded_filepath)
        candidates = [
            builtin_skills_root / skills_rel,
        ]
        if len(skills_rel.parts) > 1:
            # Strip category prefix (public/ or private/)
            candidates.append(builtin_skills_root / Path(*skills_rel.parts[1:]))
        # Security: lexical prefix check is sufficient (no .. in decoded path,
        # path constructed from root + relative). Do NOT use resolve() here
        # because symlinks inside may point to external volumes, breaking
        # resolve()-based is_relative_to across mount points.
        for cand in candidates:
            if cand.is_relative_to(builtin_skills_root) and cand.exists():
                artifact_path = cand
                break
        if artifact_path is None:
            logger.warning(
                "artifact not found: session=%s family=%s filepath=%s",
                session_id,
                family_id,
                decoded_filepath,
            )
            raise AppError(ErrorCode.NOT_FOUND)
    else:
        possible_paths = [
            # Per-thread sandbox outputs (primary — agent writes with thread_id here)
            family_threads / session_id / "user-data" / "outputs" / decoded_filepath,
            # Tenant reports (backward compat — MCP tools without thread_id)
            data_root
            / "workspaces"
            / "tenants"
            / str(family_id)
            / "reports"
            / decoded_filepath,
        ]
        # Fallback: scan all per-thread user-data/outputs dirs for the family. This
        # handles the case where session_id is a Snowflake int (agent writes use a
        # UUID thread_id, so files land in a different thread dir than session_id
        # would suggest). The filename regex validation above ensures the glob
        # only matches safe filenames.
        if family_threads.exists():
            for match in family_threads.glob(f"*/user-data/outputs/{decoded_filepath}"):
                possible_paths.append(match)

        allowed_dirs = [
            (family_threads / session_id / "user-data" / "outputs").resolve(),
            (
                data_root / "workspaces" / "tenants" / str(family_id) / "reports"
            ).resolve(),
        ]
        # Also allow any resolved thread user-data/outputs dir (for the glob fallback)
        if family_threads.exists():
            allowed_dirs.append(family_threads.resolve())

    if not is_skills_path:
        artifact_path = None  # type: ignore[assignment,no-redef]
        for candidate_path in possible_paths:
            try:
                resolved = candidate_path.resolve()
                # Security: resolved path must be within allowed directories
                if resolved.exists() and any(
                    resolved.is_relative_to(allowed)
                    for allowed in allowed_dirs
                    if allowed.exists()
                ):
                    artifact_path = resolved
                    break
            except (ValueError, OSError):
                continue

        if artifact_path is None:
            logger.warning(
                "artifact not found: session=%s family=%s filepath=%s",
                session_id,
                family_id,
                decoded_filepath,
            )
            raise AppError(ErrorCode.NOT_FOUND)

    # Read file content
    try:
        content: str | bytes = artifact_path.read_text()
    except UnicodeDecodeError:
        # Binary file - read as bytes
        content = artifact_path.read_bytes()
        media_type = "application/octet-stream"
    except OSError as e:
        logger.warning(
            "artifact read failed session=%s path=%s: %s",
            session_id,
            filepath,
            type(e).__name__,
        )
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
        headers["Content-Disposition"] = f'attachment; filename="{quoted_filename}"'

    return Response(
        content=content,
        media_type=media_type,
        headers=headers,
    )


# ── Chat Attachment Upload ────────────────────────────────────────────────────

# Max 10MB per attachment (matches DeerFlow gateway default)
_MAX_ATTACHMENT_SIZE = 10 * 1024 * 1024

_ALLOWED_IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
_ALLOWED_FILE_EXTS = {
    ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
    ".txt", ".csv", ".md", ".json", ".yaml", ".yml",
} | _ALLOWED_IMAGE_EXTS


@router.post("/attachments", response_model=FileRecordResponse, status_code=201)
async def upload_chat_attachment(
    file: UploadFile,
    current_user: User = Depends(require_adult),
    db: Session = Depends(get_db),
) -> FileRecordResponse:
    """上传聊天附件（图片/文档）。

    返回 FileRecordResponse（file_id, url, filename, size_bytes），
    前端将其作为 FileInMessage 加入 SubmitPayload.files。
    """
    if not file.filename:
        raise AppError(ErrorCode.VALIDATION_ERROR, "文件名不能为空")

    ext = Path(file.filename).suffix.lower()
    if ext not in _ALLOWED_FILE_EXTS:
        raise AppError(
            ErrorCode.VALIDATION_ERROR,
            f"不支持的文件类型: {ext}",
        )

    content = await file.read()
    if len(content) > _MAX_ATTACHMENT_SIZE:
        raise AppError(
            ErrorCode.VALIDATION_ERROR,
            "文件大小超过限制（最大 10MB）",
        )

    return await StorageService.upload_file(
        content=content,
        original_filename=file.filename,
        ext=ext,
        user=current_user,
        db=db,
    )
