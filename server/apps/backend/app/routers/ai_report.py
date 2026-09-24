"""家庭资产体检报告端点。

- GET  /api/v1/ai/report          — 获取最新报告
- GET  /api/v1/ai/report/markdown — 获取markdown报告文件内容
- POST /api/v1/ai/report/generate/events — 触发生成（SSE 流式推送三步进度，U4）
"""

import contextlib
import json
import logging
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, field_serializer
from sqlalchemy.orm import Session

from apps.backend.app.auth.deps import require_adult, require_owner
from apps.backend.app.database import SessionLocal, get_db
from apps.backend.app.errors import AppError, ErrorCode
from apps.backend.app.models.ai_chat_session import AIChatSession
from apps.backend.app.models.ai_report import AIReport
from apps.backend.app.models.family import Family
from apps.backend.app.models.user import User
from apps.backend.app.routers._ai_events_helper import check_circuit_blocked
from apps.backend.app.services.agent_client import AgentClient
from apps.backend.app.services.ai_result_parser import (
    _contains_markdown_table,
    _validate_json,
)
from apps.backend.app.services.ai_task_service import AITaskService
from apps.backend.app.services.bridge_consumer import trigger_and_stream
from apps.backend.app.services.chat_session import ChatSessionService
from apps.backend.app.services.finance_coach_cache import SKILL_TTL
from apps.backend.app.services.subscriber_registry import tracked_sse_stream
from packages.core.path_manager import PathManager

router = APIRouter(prefix="/ai/report", tags=["ai-report"])
logger = logging.getLogger(__name__)


def _check_ai_enabled(db: Session, family_id: int) -> None:
    """Raise AI_NOT_ENABLED when the family's AI master switch is off."""
    family = db.query(Family).filter(Family.id == family_id).first()
    if not family or not family.ai_enabled:
        raise AppError(ErrorCode.AI_NOT_ENABLED)


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

    return latest_by_skill(db, family_id, "asset-report")


def _get_last_checkpoint_for_resume(
    family_id: int, skill_id: str, db: Session
) -> str | None:
    """Find the last_checkpoint_id from the most recent failed/interrupted task.

    Returns the checkpoint_id if a failed task with one exists, None otherwise.
    """
    from packages.db.models.ai_task import AITask

    task = (
        db.query(AITask)
        .filter(
            AITask.family_id == family_id,
            AITask.skill_id == skill_id,
            AITask.status.in_(["failed", "interrupted"]),
            AITask.last_checkpoint_id.isnot(None),
        )
        .order_by(AITask.started_at.desc())
        .first()
    )
    return task.last_checkpoint_id if task else None


# U4 step 6: report cache TTL. A trigger within this window returns the cached
# AIReport as non-streaming JSON (200) unless ?force=true. Cached report_json
# re-validation (plan P2, security-lens #22) is deferred — the fresh-generation
# path runs schema validation on write, and the frontend DOMPurify is the
# render-time mitigation; server-side re-validation on cache hit is tracked
# separately as defense-in-depth.
# Plan A T7: TTL now lives in the skill-scoped map (SKILL_TTL); keep
# REPORT_CACHE_TTL as an alias so the existing `age < REPORT_CACHE_TTL` check
# in trigger_generate_events preserves identical report behavior.
REPORT_CACHE_TTL = SKILL_TTL["asset-report"]  # keep existing report behavior


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
        "generated_at": report.generated_at.isoformat(),
    }


@router.post("/generate/events")
async def trigger_generate_events(
    request: Request,
    force: bool = False,
    resume: bool = False,
    current_user: User = Depends(require_adult),
    _owner: None = Depends(require_owner),
    db: Session = Depends(get_db),
):
    """触发体检报告生成（U5: Redis Stream 订阅替代 HTTP 代理）。

    1h 缓存——入口先查最新 completed AIReport，1h 内且无 force
    直接返回缓存 JSON（200，非流）；force=true 或超 1h 走 stream_run 重新生成。
    后台生成：SSE 连接断开后 agent pipeline 仍继续运行，用户可切离页面。
    """
    blocked_resp = check_circuit_blocked(current_user.family_id, "asset-report", db)
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

            age = datetime.now(UTC) - cached.generated_at
            if age < _report_ttl:
                # security-lens Open Question #22 (P2, defense-in-depth): the
                # cached report_json was validated on first write, but re-serving
                # it bypasses fresh-generation output sanitization. Re-validate
                # against the same report schema + markdown-table check before
                # returning; a stale/corrupted cache falls through to regen.
                cached_json = cached.report_json
                if (
                    isinstance(cached_json, dict)
                    and _validate_json(cached_json, "asset-report")
                    and not _contains_markdown_table(cached_json)
                ):
                    return JSONResponse(
                        status_code=200,
                        content={
                            "status": "cached",
                            "generated_at": cached.generated_at.isoformat(),
                            "report": cached_json,
                        },
                    )
                logger.info(
                    "[trigger_generate_events] cached report failed re-validation, "
                    "regenerating family=%s",
                    current_user.family_id,
                )

    # Check if there's already a running task.
    existing = AITaskService.get_running_task(
        current_user.family_id, "asset-report", db
    )
    if existing and not force:
        # 已有运行中任务 — 直接接续，不重复创建
        task = existing
        # Clear stale run_id so that bridge_consumer's DB lookup sees NULL
        # and retries until the run_id callback sets the fresh
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
        # AI-enabled gate (only enforced on generation path, not cache reads).
        _check_ai_enabled(db, current_user.family_id)
        # force=true: cancel zombie running task so a fresh generation starts.
        if existing and force:
            logger.info(
                "[trigger_generate_events] force=true, cancelling zombie task=%s",
                existing.id,
            )
            AITaskService.cancel_task(current_user.family_id, "asset-report", db)
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
                skill_id="asset-report",
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
            skill_id="asset-report",
            session_id=session.id,
            db=db,
        )
        session_id = str(session.id)

    task_id = str(task.id)
    family_id = current_user.family_id
    user_id = str(current_user.id)

    # Phase 2: Trigger agent (writes to Redis) and subscribe via bridge.
    agent_client = AgentClient(family_id, user_id, timeout=300.0)
    agent_url = f"/internal/gateway/runs/asset-report/{session_id}"
    agent_trigger_body = {
        "family_id": str(family_id),
        "user_id": str(user_id),
        "language": current_user.language,
        "on_disconnect": "continue",
    }

    # Checkpoint resume: when resume=true, inject the last checkpoint_id
    # from the most recent failed task so the agent forks from that checkpoint.
    if resume:
        last_checkpoint = _get_last_checkpoint_for_resume(
            current_user.family_id, "asset-report", db
        )
        if not last_checkpoint:
            raise AppError(
                ErrorCode.NOT_FOUND,
                "无可恢复的断点（任务未失败或无 checkpoint）",
            )
        agent_trigger_body.setdefault("config", {})["configurable"] = {
            "checkpoint_id": last_checkpoint,
        }

    # Trigger agent and stream SSE lifecycle
    try:
        return await trigger_and_stream(
            agent_client=agent_client,
            agent_url=agent_url,
            json_body=agent_trigger_body,
            task_id=str(task_id),
            family_id=family_id,
            session_id=session_id,
            last_event_id=request.headers.get("Last-Event-ID"),
            thread_id=session_id,
        )
    except Exception as e:
        logger.warning(
            "[asset-report] trigger failed task=%s err=%s", task_id, e, exc_info=True
        )
        _fdb = SessionLocal()
        try:
            AITaskService.fail_task(
                task_id, f"agent trigger failed: {type(e).__name__}", _fdb
            )
        finally:
            _fdb.close()

        async def _error_stream():
            yield f"event: error\ndata: {json.dumps({'error': '报告生成服务异常'})}\n\n"
            yield "event: end\ndata: null\n\n"

        return StreamingResponse(
            tracked_sse_stream(task_id, _error_stream()),
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
