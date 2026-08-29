"""家庭资产体检报告端点。

- GET  /api/v1/ai/report          — 获取最新报告
- GET  /api/v1/ai/report/markdown — 获取markdown报告文件内容
- POST /api/v1/ai/report/generate/events — 触发生成（SSE 流式推送三步进度，U4）
"""

import asyncio
import contextlib
import logging
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, field_serializer
from sqlalchemy.orm import Session

from apps.backend.app.auth.ai_deps import require_ai_enabled
from apps.backend.app.auth.deps import require_adult, require_owner
from apps.backend.app.database import get_db
from apps.backend.app.errors import AppError, ErrorCode
from apps.backend.app.models.ai_chat_session import AIChatSession
from apps.backend.app.models.ai_report import AIReport
from apps.backend.app.models.user import User
from apps.backend.app.routers._ai_events_helper import check_circuit_blocked
from apps.backend.app.schemas.base import ensure_utc
from apps.backend.app.services.agent_client import AgentClient
from apps.backend.app.services.ai_result_parser import (
    _contains_markdown_table,
    _validate_json,
)
from apps.backend.app.services.ai_task_service import AITaskService
from apps.backend.app.services.bridge_consumer import (
    _pump_agent_sse_to_bridge,
    _spawn_lifecycle_consumer,
    consume_task_stream,
    get_shared_bridge,
)
from apps.backend.app.services.chat_session import ChatSessionService
from apps.backend.app.services.finance_coach_cache import SKILL_TTL
from apps.backend.app.services.subscriber_registry import tracked_sse_stream
from packages.core.path_manager import PathManager

router = APIRouter(prefix="/ai/report", tags=["ai-report"])
logger = logging.getLogger(__name__)


class MarkdownResponse(BaseModel):
    """Markdown report file content response."""

    content: str
    filename: str
    generated_at: datetime
    file_size: int

    @field_serializer("generated_at")
    def _serialize_generated_at(self, v: datetime) -> str:
        if v.tzinfo is None:
            v = v.replace(tzinfo=UTC)
        return v.isoformat()


def _latest_report(family_id: int, db: Session) -> AIReport | None:
    from apps.backend.app.services.finance_coach_cache import latest_by_skill

    return latest_by_skill(db, family_id, "report")


# U4 step 6: report cache TTL. A trigger within this window returns the cached
# AIReport as non-streaming JSON (200) unless ?force=true. Cached report_json
# re-validation (plan P2, security-lens #22) is deferred — the fresh-generation
# path runs schema validation on write, and the frontend DOMPurify is the
# render-time mitigation; server-side re-validation on cache hit is tracked
# separately as defense-in-depth.
# Plan A T7: TTL now lives in the skill-scoped map (SKILL_TTL); keep
# REPORT_CACHE_TTL as an alias so the existing `age < REPORT_CACHE_TTL` check
# in trigger_generate_events preserves identical report behavior.
REPORT_CACHE_TTL = SKILL_TTL["report"]  # keep existing report behavior


@router.get("")
def get_report(
    current_user: User = Depends(require_adult),
    db: Session = Depends(get_db),
):
    """获取家庭最新体检报告。"""
    report = _latest_report(current_user.family_id, db)
    if not report:
        return {"report": None}
    return {
        "report": report.report_json,
        "generated_at": ensure_utc(report.generated_at).isoformat(),
    }


@router.post("/generate/events")
async def trigger_generate_events(
    request: Request,
    force: bool = False,
    current_user: User = Depends(require_adult),
    _ai: None = Depends(require_ai_enabled),
    _owner: None = Depends(require_owner),
    db: Session = Depends(get_db),
):
    """触发体检报告生成（U5: Redis Stream 订阅替代 HTTP 代理）。

    1h 缓存——入口先查最新 completed AIReport，1h 内且无 force
    直接返回缓存 JSON（200，非流）；force=true 或超 1h 走 stream_run 重新生成。
    后台生成：SSE 连接断开后 agent pipeline 仍继续运行，用户可切离页面。
    """
    blocked_resp = check_circuit_blocked(current_user.family_id, "report", db)
    if blocked_resp is not None:
        return blocked_resp

    # U4 step 6: 8h cache check (before concurrency gating — a cache hit does
    # not create a run, so it must not be blocked by / queue behind a running
    # task). force=true skips the cache and regenerates.
    if not force:
        cached = _latest_report(current_user.family_id, db)
        if cached is not None and cached.generated_at is not None:
            # Dynamic TTL from family settings, fallback to REPORT_CACHE_TTL
            from apps.backend.app.services.config_registry import (
                FAMILY_SETTING_DEFINITIONS,
            )
            from apps.backend.app.services.config_service import (
                get_family_setting_cached,
            )

            _report_ttl = REPORT_CACHE_TTL
            if "ai_cache_ttl_report" in FAMILY_SETTING_DEFINITIONS:
                with contextlib.suppress(Exception):
                    _report_ttl = timedelta(
                        minutes=get_family_setting_cached(
                            int(current_user.family_id), "ai_cache_ttl_report"
                        )
                    )

            age = datetime.now(UTC).replace(tzinfo=None) - cached.generated_at
            if age < _report_ttl:
                # security-lens Open Question #22 (P2, defense-in-depth): the
                # cached report_json was validated on first write, but re-serving
                # it bypasses fresh-generation output sanitization. Re-validate
                # against the same report schema + markdown-table check before
                # returning; a stale/corrupted cache falls through to regen.
                cached_json = cached.report_json
                if (
                    isinstance(cached_json, dict)
                    and _validate_json(cached_json, "report")
                    and not _contains_markdown_table(cached_json)
                ):
                    return JSONResponse(
                        status_code=200,
                        content={
                            "status": "cached",
                            "generated_at": ensure_utc(cached.generated_at).isoformat(),
                            "report": cached_json,
                        },
                    )
                logger.info(
                    "[trigger_generate_events] cached report failed re-validation, "
                    "regenerating family=%s",
                    current_user.family_id,
                )

    # Check if there's already a running task.
    existing = AITaskService.get_running_task(current_user.family_id, "report", db)
    if existing and not force:
        # 已有运行中任务 — 直接接续，不重复创建
        task = existing
        # Clear stale run_id so that bridge_consumer's DB lookup sees NULL
        # and retries until the pump's _on_run_id callback sets the fresh
        # value.  Without this, consume_task_stream (which starts after a
        # brief wait) may read the old task's run_id from a previous agent
        # run, subscribe to the bridge with that stale key, and immediately
        # replay old events → the frontend sees "completed" with the
        # previous report's data.
        if task.run_id:
            task.run_id = None
            db.commit()
        session_id = str(task.session_id) if task.session_id else str(task.id)
        session = (
            db.query(AIChatSession)
            .filter_by(id=session_id, family_id=current_user.family_id)
            .first()
        )
        if not session:
            raise AppError(ErrorCode.NOT_FOUND)
    else:
        # force=true: cancel zombie running task so a fresh generation starts.
        if existing and force:
            logger.info(
                "[trigger_generate_events] force=true, cancelling zombie task=%s",
                existing.id,
            )
            AITaskService.cancel_task(current_user.family_id, "report", db)
        # No running task - create new session and task
        session = await ChatSessionService.create_session(
            family_id=current_user.family_id,
            user_id=current_user.id,
            db=db,
        )
        any_running = AITaskService.get_any_running_task(current_user.family_id, db)
        if any_running and not force:
            task = AITaskService.create_queued_task(
                family_id=current_user.family_id,
                skill_id="report",
                session_id=session.id,
                db=db,
            )
            return JSONResponse(
                status_code=202,
                content={
                    "status": "queued",
                    "task_id": str(task.id),
                    "queue_position": task.queue_position,
                },
            )
        task = AITaskService.create_task(
            family_id=current_user.family_id,
            skill_id="report",
            session_id=session.id,
            db=db,
        )
        session_id = str(session.id)

    task_id = str(task.id)
    family_id = current_user.family_id
    user_id = str(current_user.id)

    # Phase 1: Backend-owned buffer (single streaming POST — no double trigger).
    # The agent is triggered once via streaming POST; _pump_agent_sse_to_bridge
    # consumes its SSE response and publishes to the shared bridge.
    # The on_run_id callback spawns the lifecycle consumer as soon as the
    # agent's Content-Location header is available (before body is consumed).
    agent_client = AgentClient(family_id, user_id, timeout=300.0)
    agent_url = f"/internal/gateway/runs/asset-report/{session_id}"
    shared_bridge = get_shared_bridge()
    agent_trigger_body = {
        "family_id": str(family_id),
        "user_id": str(user_id),
        "language": current_user.language,
        "on_disconnect": "continue",
    }

    # Track lifecycle consumer spawn state.
    # ``lifecycle_spawned``: whether the lifecycle consumer has been spawned.
    # ``lifecycle_task``: the spawned task (for cancellation if run_id changes).
    # ``cl_bare_run_id``: Content-Location run_id (for fallback if metadata never arrives).
    lifecycle_spawned = asyncio.Event()
    lifecycle_task: asyncio.Task[None] | None = None
    cl_bare_run_id: str | None = None

    def _on_run_id(cl_url: str) -> None:
        """Called when Content-Location header arrives. Persist to DB only."""
        nonlocal cl_bare_run_id
        # Content-Location is a URL path like
        # /internal/gateway/runs/asset-report/{thread_id}/{run_id}.
        # Extract the trailing UUID.
        cl_bare_run_id = cl_url.rstrip("/").rsplit("/", 1)[-1]
        AITaskService.extract_and_attach_run_id(
            task_id, cl_url, family_id
        )

    def _on_authoritative_run_id(meta_run_id: str) -> None:
        """Called when metadata event arrives with the authoritative run_id.

        The metadata run_id may differ from Content-Location when the agent's
        interrupt strategy fires a second run. Spawn the lifecycle consumer
        with this run_id so it subscribes to the correct stream.
        """
        nonlocal lifecycle_task
        # Update DB with the authoritative run_id.
        AITaskService.extract_and_attach_run_id(
            task_id, meta_run_id, family_id
        )
        # Cancel old lifecycle consumer (if spawned with wrong run_id).
        if lifecycle_task is not None and not lifecycle_task.done():
            lifecycle_task.cancel()
        lifecycle_task = _spawn_lifecycle_consumer(
            task_id=task_id,
            family_id=family_id,
            run_id=meta_run_id,
            bridge=shared_bridge,
        )
        lifecycle_spawned.set()

    # Spawn background pump: one streaming POST → shared bridge.
    # (Keep a reference so the task is not garbage-collected mid-flight.)
    _pump_task = asyncio.create_task(
        _pump_agent_sse_to_bridge(
            agent_client=agent_client,
            agent_url=agent_url,
            json_body=agent_trigger_body,
            bridge=shared_bridge,
            run_id="",  # resolved from Content-Location inside the pump
            task_id=task_id,
            on_run_id=_on_run_id,
            on_authoritative_run_id=_on_authoritative_run_id,
        )
    )

    # Wait for pump to resolve run_id (either Content-Location or metadata).
    # Give the pump up to 3 seconds — metadata may arrive slightly later than
    # Content-Location. If neither arrives, fall back to run_id=None.
    try:
        await asyncio.wait_for(lifecycle_spawned.wait(), timeout=3.0)
    except TimeoutError:
        logger.warning(
            "[asset-report] pump did not resolve authoritative run_id within 3s, using fallback task=%s",
            task_id,
        )

    if not lifecycle_spawned.is_set():
        # Fallback: spawn with Content-Location run_id (if available) or None.
        lifecycle_task = _spawn_lifecycle_consumer(
            task_id=task_id,
            family_id=family_id,
            run_id=cl_bare_run_id,
            bridge=shared_bridge,
        )

    # SSE forwarder: subscribes to shared bridge, yields SSE text to frontend.
    last_event_id = request.headers.get("Last-Event-ID")
    stream_gen = consume_task_stream(
        task_id=task_id,
        family_id=family_id,
        last_event_id=last_event_id,
        run_id=None,  # resolved from AITask table by bridge_consumer
        bridge=shared_bridge,
    )

    return StreamingResponse(
        tracked_sse_stream(task_id, stream_gen),
        media_type="text/event-stream",
        headers={"X-Accel-Buffering": "no"},
    )


@router.get("/markdown")
def get_report_markdown(
    current_user: User = Depends(require_adult),
    db: Session = Depends(get_db),
) -> MarkdownResponse:
    """获取markdown报告文件内容。

    返回最新报告的markdown源文件内容，供前端预览使用。
    """
    report = _latest_report(current_user.family_id, db)
    if not report:
        raise AppError(ErrorCode.AI_REPORT_NOT_FOUND)
    if not report.markdown_file_path:
        raise AppError(ErrorCode.AI_REPORT_MARKDOWN_NOT_FOUND)

    # Read markdown file via PathManager
    pm = PathManager()
    filename = report.markdown_file_path.split("/")[-1]
    try:
        file_path = pm.tenant_report_file(int(current_user.family_id), filename)
    except Exception as e:
        logger.warning(
            f"Invalid markdown file path for family {current_user.family_id}: {e}"
        )
        raise AppError(ErrorCode.AI_REPORT_MARKDOWN_NOT_FOUND) from None

    if not file_path.exists():
        raise AppError(ErrorCode.AI_REPORT_MARKDOWN_NOT_FOUND)

    content = file_path.read_text(encoding="utf-8")
    return MarkdownResponse(
        content=content,
        filename=filename,
        generated_at=report.generated_at,
        file_size=len(content),
    )
