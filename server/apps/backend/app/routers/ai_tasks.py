"""AI 任务状态查询端点。

- GET /ai/tasks                      - 查询任务列表（U6 useTaskResume）
- GET /ai/tasks/running              - 查询运行中任务（U6 便捷端点）
- GET /ai/tasks/{skill_id}           - 查询当前 skill_id 的任务状态（向后兼容）
- GET /ai/tasks/{skill_id}/session   - 获取关联的 session_id（向后兼容）
- POST /ai/tasks/{skill_id}/cancel   - 终止当前运行的任务（向后兼容）
- GET /ai/tasks/detail/{task_id}     - 按 ID 查询任务（U10）
- GET /ai/tasks/detail/{task_id}/stream - SSE 重连端点（v3 subscribe-only）
- POST /ai/tasks/detail/{task_id}/cancel - 按 ID 终止任务（U20）
"""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from apps.backend.app.auth.deps import require_adult
from apps.backend.app.database import get_db
from apps.backend.app.errors import AppError, ErrorCode
from apps.backend.app.models.user import User
from apps.backend.app.schemas.base import SnowflakeBase
from apps.backend.app.services.ai_task_service import AITaskService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/ai/tasks", tags=["ai-tasks"])

VALID_SKILL_IDS = {
    "report",
    "alerts",
    "disposal",
    "allocation",
    "spending_leak",
    "liability",
    "time_machine",
    # v2 features (U10)
    "coach",
    "literacy-weekly-report",
    "dashboard-narrative",
    "chat",
}

# Default limit for list endpoints - prevents unbounded queries (P2 fix)
DEFAULT_TASK_LIMIT = 50


class AITaskResponse(SnowflakeBase):
    """AITask response schema with Snowflake ID serialization."""

    id: int
    family_id: int
    skill_id: str
    status: str
    run_id: str | None = None
    worker_id: str | None = None
    started_at: datetime
    completed_at: datetime | None = None
    error_message: str | None = None
    # v2 fields (U10)
    progress: dict | None = None
    lease_expires_at: datetime | None = None
    queue_position: int | None = None
    session_id: int | None = None

    class Config:
        from_attributes = True


@router.get("", response_model=list[AITaskResponse])
async def get_tasks(
    skill_id: str | None = Query(None, description="Filter by skill_id"),
    status: str | None = Query(None, description="Filter by status"),
    session_id: int | None = Query(None, description="Filter by session_id (U10)"),
    limit: int = Query(DEFAULT_TASK_LIMIT, ge=1, le=200, description="Max results"),
    current_user: User = Depends(require_adult),
    db: Session = Depends(get_db),
) -> list[AITaskResponse]:
    """Query AI tasks for the current family.

    Used by frontend useTaskResume hook to check for running tasks on page load.
    Returns tasks filtered by skill_id and/or status, scoped to the user's family.

    Example: GET /api/v1/ai/tasks?skill_id=report&status=running
    """
    from packages.db.models.ai_task import AITask

    query = db.query(AITask).filter(AITask.family_id == current_user.family_id)

    if skill_id:
        query = query.filter(AITask.skill_id == skill_id)

    if status:
        query = query.filter(AITask.status == status)

    if session_id:
        query = query.filter(AITask.session_id == session_id)

    # Order by started_at descending (most recent first), bounded by limit
    query = query.order_by(AITask.started_at.desc()).limit(limit)

    tasks = query.all()
    return [AITaskResponse.model_validate(task) for task in tasks]


@router.get("/running", response_model=list[AITaskResponse])
async def get_running_tasks(
    current_user: User = Depends(require_adult),
    db: Session = Depends(get_db),
) -> list[AITaskResponse]:
    """Get all running tasks for the current family.

    Convenience endpoint for frontend task resume. Returns all running tasks
    (excludes timed-out tasks).
    """
    tasks = AITaskService.get_running_tasks_by_family(current_user.family_id, db)
    return [AITaskResponse.model_validate(task) for task in tasks]


@router.get("/{skill_id}")
def get_task_status(
    skill_id: str,
    current_user: User = Depends(require_adult),
    db: Session = Depends(get_db),
):
    """查询当前 skill_id 的任务状态（含排队状态）。向后兼容端点。"""
    if skill_id not in VALID_SKILL_IDS:
        return {"status": "idle"}

    # Check running task for this skill_id
    task = AITaskService.get_running_task(current_user.family_id, skill_id, db)
    if task is not None:
        return {
            "status": task.status,
            "task_id": str(task.id),
            "session_id": str(task.session_id) if task.session_id else None,
            "started_at": task.started_at.isoformat() + "+00:00",
            "queue_position": None,
        }

    # Check queued task for this skill_id (position computed dynamically)
    queued = AITaskService.get_queued_task(current_user.family_id, skill_id, db)
    if queued is not None:
        return {
            "status": "queued",
            "task_id": str(queued.id),
            "session_id": str(queued.session_id) if queued.session_id else None,
            "started_at": queued.started_at.isoformat() + "+00:00",
            "queue_position": queued.queue_position,
        }

    return {"status": "idle"}


@router.get("/{skill_id}/session")
def get_task_session(
    skill_id: str,
    current_user: User = Depends(require_adult),
    db: Session = Depends(get_db),
):
    """获取当前 running 任务关联的 session_id（用于前端接续历史消息）。向后兼容端点。"""
    if skill_id not in VALID_SKILL_IDS:
        return {"session_id": None}

    task = AITaskService.get_running_task(current_user.family_id, skill_id, db)
    if task is None:
        return {"session_id": None}

    return {"session_id": str(task.session_id) if task.session_id else None, "task_id": str(task.id)}


@router.post("/{skill_id}/cancel")
def cancel_task(
    skill_id: str,
    current_user: User = Depends(require_adult),
    db: Session = Depends(get_db),
):
    """终止当前运行或排队的任务。向后兼容端点。"""
    if skill_id not in VALID_SKILL_IDS:
        return {"ok": False, "message": "invalid_skill_id"}

    cancelled = AITaskService.cancel_task(current_user.family_id, skill_id, db)
    if cancelled:
        return {"ok": True, "status": "cancelled"}
    return {"ok": False, "message": "no_running_task"}


# ---------------------------------------------------------------------------
# v2 endpoints (U10 + U20)
# ---------------------------------------------------------------------------


@router.get("/detail/{task_id}", response_model=AITaskResponse)
async def get_task_by_id(
    task_id: int,
    current_user: User = Depends(require_adult),
    db: Session = Depends(get_db),
) -> AITaskResponse:
    """Get a single task by ID with full progress data (U10).

    Used by frontend useTaskPolling composable for task state recovery.
    Returns 404 if task not found or belongs to different family.
    """
    task = AITaskService.get_task_by_id(task_id, current_user.family_id, db)
    if not task:
        raise AppError(ErrorCode.NOT_FOUND, "任务不存在")
    return AITaskResponse.model_validate(task)


@router.post("/detail/{task_id}/cancel")
async def cancel_task_by_id(
    task_id: int,
    current_user: User = Depends(require_adult),
    db: Session = Depends(get_db),
):
    """User-initiated task cancellation by task_id (U20).

    1. Verify task belongs to this family (tenant isolation)
    2. If task has run_id → notify Agent to cancel (fire-and-forget)
    3. Mark AITask.status = cancelled
    4. Idempotent: already-cancelled/completed tasks return current status
    """
    task = AITaskService.get_task_by_id(task_id, current_user.family_id, db)
    if not task:
        raise AppError(ErrorCode.NOT_FOUND, "任务不存在")

    # Idempotent: if already terminal, return current status
    if task.status in ("completed", "failed", "cancelled", "timeout"):
        return {"ok": True, "status": task.status, "task_id": str(task.id)}

    # Notify Agent if task has run_id (fire-and-forget)
    if task.run_id:
        import asyncio

        from apps.backend.app.services.agent_client import AgentClient

        # session_id is the thread_id for Agent
        thread_id = task.session_id
        if thread_id is None:
            # Fallback: use family_id as default thread
            thread_id = current_user.family_id

        async def _notify_agent():
            try:
                agent_client = AgentClient(
                    current_user.family_id, current_user.id, timeout=5.0
                )
                await agent_client.post(
                    f"/api/threads/{thread_id}/runs/{task.run_id}/cancel",
                    json={},
                )
            except Exception as e:
                logger.warning(
                    "[task-cancel] agent notification failed task=%s run=%s err=%s",
                    task_id, task.run_id, e,
                )

        asyncio.create_task(_notify_agent())

    # Mark as cancelled
    task.status = "cancelled"
    task.completed_at = datetime.now(UTC)
    db.commit()

    return {"ok": True, "status": "cancelled", "task_id": str(task.id)}


# ---------------------------------------------------------------------------
# v3 SSE reconnect endpoint (subscribe-only)
# ---------------------------------------------------------------------------

# F7: Per-family concurrent SSE connection cap (prevents DoS)
_MAX_SSE_CONNECTIONS_PER_FAMILY = 3
_active_sse_connections: dict[int, int] = {}


def _load_scenario_result(task, db: Session) -> dict:
    """Load cached scenario result for a terminal task.

    Maps ``task.skill_id`` (scenario identifier) to the corresponding result
    storage and returns a dict suitable for SSE ``event: result`` data.
    """
    scenario = task.skill_id

    if scenario in ("narrative", "coach"):
        from apps.backend.app.services.finance_coach_cache import latest_by_skill

        skill_key = "narrative" if scenario == "narrative" else "finance_coach"
        cached = latest_by_skill(db, task.family_id, skill_key)
        if not cached:
            return {"error": "结果未找到"}
        if scenario == "narrative":
            report_data = cached.report_json
            narrative_text = (
                report_data.get("narrative", "")
                if isinstance(report_data, dict)
                else str(report_data)
            )
            return {"narrative": narrative_text}
        else:
            return cached.report_json if isinstance(cached.report_json, dict) else {"data": cached.report_json}

    elif scenario == "literacy":
        from packages.db.models.literacy_report import LiteracyWeeklyReport

        # LiteracyWeeklyReport has no family_id column - resolve through the
        # child's family (users.family_id) for tenant isolation.
        report = (
            db.query(LiteracyWeeklyReport)
            .join(User, LiteracyWeeklyReport.child_id == User.id)
            .filter(User.family_id == task.family_id)
            .order_by(LiteracyWeeklyReport.generated_at.desc())
            .first()
        )
        if not report:
            return {"error": "报告未找到"}
        return {
            "report": {
                "id": str(report.id),
                "child_id": str(report.child_id),
                "week_start": report.week_start.isoformat() if report.week_start else None,
                "narrative": report.narrative,
                "report_json": report.report_json,
                "generated_at": report.generated_at.isoformat() if report.generated_at else None,
            }
        }

    elif scenario == "report":
        from apps.backend.app.services.finance_coach_cache import latest_by_skill

        cached = latest_by_skill(db, task.family_id, "report")
        if not cached:
            return {"error": "报告未找到"}
        return {"report": cached.report_json}

    else:
        return {"error": f"未知场景: {scenario}"}


async def _emit_scenario_result(task, db: Session) -> AsyncIterator[str]:
    """Emit cached scenario result for terminal tasks, then close."""
    if task.status == "completed":
        result = _load_scenario_result(task, db)
        yield f"event: result\ndata: {json.dumps(result, default=str)}\n\n"
    elif task.status in ("failed", "cancelled", "timeout", "interrupted"):
        yield f"event: error\ndata: {json.dumps({'error': task.error_message or '任务异常终止'})}\n\n"
    yield "event: end\ndata: null\n\n"


@router.get("/detail/{task_id}/stream")
async def stream_task_events(
    task_id: int,
    request: Request,
    current_user: User = Depends(require_adult),
    db: Session = Depends(get_db),
):
    """Subscribe-only SSE endpoint for task stream reconnection (v3).

    Does NOT trigger a new task. Subscribes to the existing task's
    bridge buffer and replays events from Last-Event-ID (if provided).

    Behavior matrix:
    - running/queued/post_processing + buffer exists → 200 SSE stream
    - running/queued/post_processing + buffer gap → 200 SSE with gap event
    - completed → 200 SSE with cached result + end
    - failed/cancelled/timeout → 200 SSE with error + end
    - not found / wrong family → 404
    """
    from apps.backend.app.services.bridge_consumer import consume_task_stream

    task = AITaskService.get_task_by_id(task_id, current_user.family_id, db)
    if not task:
        raise AppError(ErrorCode.NOT_FOUND, "任务不存在")

    # Connection cap (F7)
    family_id = current_user.family_id
    current_count = _active_sse_connections.get(family_id, 0)
    if current_count >= _MAX_SSE_CONNECTIONS_PER_FAMILY:
        raise AppError(ErrorCode.RATE_LIMITED, "SSE 连接数已达上限")

    # Terminal states: emit cached result and close
    if task.status in ("completed", "failed", "cancelled", "timeout", "interrupted"):
        return StreamingResponse(
            _emit_scenario_result(task, db),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    # Active task: subscribe to bridge buffer
    if not task.run_id:
        raise AppError(ErrorCode.NOT_FOUND, "任务尚未分配 run_id")

    last_event_id = request.headers.get("Last-Event-ID")

    async def _tracked_stream() -> AsyncIterator[str]:
        _active_sse_connections[family_id] = _active_sse_connections.get(family_id, 0) + 1
        try:
            async for chunk in consume_task_stream(
                task_id=str(task.id),
                family_id=family_id,
                last_event_id=last_event_id,
                run_id=task.run_id,
            ):
                yield chunk
        finally:
            _active_sse_connections[family_id] = max(0, _active_sse_connections.get(family_id, 1) - 1)

    return StreamingResponse(
        _tracked_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )
