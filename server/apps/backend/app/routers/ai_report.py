"""家庭资产体检报告端点。

- GET  /api/v1/ai/report          — 获取最新报告
- GET  /api/v1/ai/report/markdown — 获取markdown报告文件内容
- POST /api/v1/ai/report/generate/events — 触发生成（SSE 流式推送三步进度，U4）
"""

import asyncio
import contextlib
import json
import logging
from collections.abc import AsyncGenerator
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends
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
from apps.backend.app.services.bridge_consumer import consume_task_stream
from apps.backend.app.services.chat_session import ChatSessionService
from apps.backend.app.services.finance_coach_cache import SKILL_TTL
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


async def _stream_asset_report_sse(
    *,
    family_id: int,
    user_id: str,
    thread_id: str,
    task_id: str,
    language: str | None = None,
) -> AsyncGenerator[bytes, None]:
    """Proxy the agent's asset-report SSE stream to the frontend (U4 step 5).

    Calls the agent's internal ``/internal/gateway/runs/asset-report/{thread_id}``
    endpoint via ``AgentClient`` (which injects ``X-Agent-Token`` for service-
    to-service auth) and forwards the raw SSE bytes. The agent worker
    (``_run_asset_report_pipeline``) emits the 3-step execution frames +
    ``report.step2_json`` custom event; this helper is a pure passthrough.

    On agent error/non-200, yields a single SSE error frame so the frontend
    receives a graceful close rather than a truncated stream.
    """
    agent_client = AgentClient(family_id, user_id, timeout=300.0)
    agent_url = f"/internal/gateway/runs/asset-report/{thread_id}"
    try:
        async with agent_client.stream(
            "POST",
            agent_url,
            json={
                "family_id": str(family_id),
                "user_id": str(user_id),
                "language": language,
                # Background generation: keep the agent pipeline running even if
                # the user navigates away and the SSE connection drops. The
                # AITask record remains the source of truth for completion.
                "on_disconnect": "continue",
            },
        ) as resp:
            if resp.status_code != 200:
                body = await resp.aread()
                logger.warning(
                    "[asset-report] agent stream non-200: status=%s body=%s task=%s",
                    resp.status_code,
                    body[:200],
                    task_id,
                )
                err = json.dumps(
                    {"message": "报告生成服务异常", "name": "AgentError"}
                ).encode()
                yield f"event: error\ndata: {err.decode()}\n\n".encode()
                return
            async for line in resp.aiter_lines():
                # Forward each raw line; aiter_lines strips the trailing newline,
                # so re-add it. Blank lines separate SSE events.
                yield (line + "\n").encode()
    except Exception as exc:
        logger.warning(
            "[asset-report] agent stream failed task=%s err=%s", task_id, exc
        )
        err = json.dumps(
            {"message": "报告生成服务中断", "name": type(exc).__name__}
        ).encode()
        yield f"event: error\ndata: {err.decode()}\n\n".encode()


async def _watch_report_task_completion(
    *, task_id: str, family_id: int
) -> None:
    """Background watcher for report task completion after client disconnect.

    When the SSE client disconnects while the agent pipeline is still running
    (``on_disconnect=continue``), the ``_task_tracking_stream`` finally block
    can no longer see the pipeline's end frame. This watcher polls the
    ``ai_reports`` table for up to 5 minutes, looking for a row matching this
    family. When the pipeline persists its report, the watcher completes the
    AITask so the frontend can discover it on revisit.

    If the report never appears (pipeline failed without persisting), the task
    is marked failed after the timeout.
    """
    POLL_INTERVAL = 15  # seconds between checks
    MAX_WAIT = 300  # 5 minutes max

    try:
        for _ in range(MAX_WAIT // POLL_INTERVAL):
            await asyncio.sleep(POLL_INTERVAL)

            from apps.backend.app.database import SessionLocal
            from apps.backend.app.models.ai_report import AIReport

            db = SessionLocal()
            try:
                # Check if the report was persisted by the pipeline
                report_exists = (
                    db.query(AIReport)
                    .filter(AIReport.family_id == int(family_id))
                    .first()
                    is not None
                )
                if report_exists:
                    AITaskService.complete_task(task_id, db)
                    logger.info(
                        "[report-watcher] task %s completed (report found)", task_id
                    )
                    return

                # Check if the task is still running
                task = AITaskService.get_task_by_id(task_id, family_id, db)
                if task and task.status == "completed":
                    return  # Already completed by another path
                if task and task.status not in ("running", "post_processing", "queued"):
                    return  # Terminal state reached by another path
            finally:
                db.close()

        # Timeout — pipeline didn't produce a report within the window
        from apps.backend.app.database import SessionLocal

        db = SessionLocal()
        try:
            AITaskService.fail_task(
                task_id, "report generation timed out after client disconnect", db
            )
            logger.warning(
                "[report-watcher] task %s timed out (no report after %ds)",
                task_id,
                MAX_WAIT,
            )
        finally:
            db.close()
    except Exception as exc:
        logger.warning(
            "[report-watcher] watcher failed task=%s err=%s", task_id, exc
        )


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

    # Check if there's already a running task - resume it instead of 409
    existing = AITaskService.get_running_task(current_user.family_id, "report", db)
    if existing:
        # 已有运行中任务 — 直接接续，不重复创建
        task = existing
        session_id = str(task.session_id) if task.session_id else str(task.id)
        session = (
            db.query(AIChatSession)
            .filter_by(id=session_id, family_id=current_user.family_id)
            .first()
        )
        if not session:
            raise AppError(ErrorCode.NOT_FOUND)
    else:
        # No running task - create new session and task
        session = await ChatSessionService.create_session(
            family_id=current_user.family_id,
            user_id=current_user.id,
            db=db,
        )
        any_running = AITaskService.get_any_running_task(current_user.family_id, db)
        if any_running:
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
                    "task_id": task.id,
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

    # U5: Trigger agent via HTTP, then subscribe to Redis stream via bridge_consumer
    # The agent writes events to Redis stream; backend consumes via bridge_consumer
    # This enables cross-process reconnection and removes direct HTTP proxy dependency
    agent_client = AgentClient(family_id, user_id, timeout=300.0)
    agent_url = f"/internal/gateway/runs/asset-report/{session_id}"

    # P0 Fix: Use non-streaming POST to trigger the agent task
    # We're not reading the response body (just triggering), so use post() not stream()
    # This prevents the connection from closing immediately and triggering disconnect_watcher
    try:
        resp = await agent_client.post(
            agent_url,
            json={
                "family_id": str(family_id),
                "user_id": str(user_id),
                "language": current_user.language,
                "on_disconnect": "continue",
            },
        )
        if resp.status_code != 200:
            logger.warning(
                "[asset-report] agent trigger failed: status=%s body=%s task=%s",
                resp.status_code,
                resp.text[:200],
                task_id,
            )
            err = json.dumps(
                {"message": "报告生成服务异常", "name": "AgentError"}
            ).encode()
            return StreamingResponse(
                iter([f"event: error\ndata: {err.decode()}\n\n".encode()]),
                media_type="text/event-stream",
            )
    except Exception as exc:
        logger.warning(
            "[asset-report] agent trigger failed task=%s err=%s", task_id, exc
        )
        err = json.dumps(
            {"message": "报告生成服务中断", "name": type(exc).__name__}
        ).encode()
        return StreamingResponse(
            iter([f"event: error\ndata: {err.decode()}\n\n".encode()]),
            media_type="text/event-stream",
        )

    # U5: Subscribe to Redis stream via bridge_consumer (replaces HTTP proxy)
    # bridge_consumer handles:
    # - Last-Event-ID reconnection
    # - StreamGap detection and recovery
    # - Heartbeat sentinels
    # - Task status updates (complete/fail on end/error)
    # U6: Extract Last-Event-ID from request headers for reconnection
    last_event_id = request.headers.get("Last-Event-ID")
    stream_gen = consume_task_stream(
        task_id=task_id,
        family_id=family_id,
        last_event_id=last_event_id,
    )

    async def _sse_stream() -> AsyncGenerator[bytes, None]:
        """Wrap bridge_consumer output as SSE bytes."""
        async for sse_text in stream_gen:
            yield sse_text.encode("utf-8")

    return StreamingResponse(
        _sse_stream(),
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
