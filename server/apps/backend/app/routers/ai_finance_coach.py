"""finance_coach trigger endpoint (Plan A T8 + U13 AITask tracking).

- POST /api/v1/ai/finance-coach/generate?force=false
    8h skill-cache check -> cached JSON 200 (non-stream) OR AITask-tracked
    bridge consumer SSE via agent gateway. Mirrors ai_report.py pattern (U13).
"""
import asyncio
import json
import logging

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy.orm import Session

from apps.backend.app.auth.ai_deps import require_ai_enabled
from apps.backend.app.auth.deps import require_adult, require_owner
from apps.backend.app.database import get_db
from apps.backend.app.errors import AppError, ErrorCode
from apps.backend.app.models.ai_chat_session import AIChatSession
from apps.backend.app.models.user import User
from apps.backend.app.routers._ai_events_helper import check_circuit_blocked
from apps.backend.app.schemas.base import ensure_utc
from apps.backend.app.services.agent_client import AgentClient
from apps.backend.app.services.ai_task_service import AITaskService
from apps.backend.app.services.bridge_consumer import (
    _pump_agent_sse_to_bridge,
    _spawn_lifecycle_consumer,
    consume_task_stream,
    get_shared_bridge,
)
from apps.backend.app.services.chat_session import ChatSessionService
from apps.backend.app.services.finance_coach_cache import (
    is_cache_fresh,
    latest_by_skill,
    upsert_skill_result,
)
from apps.backend.app.services.finance_coach_snapshot import (
    build_family_finance_snapshot,
)
from apps.backend.app.services.subscriber_registry import tracked_sse_stream

router = APIRouter(prefix="/ai/finance-coach", tags=["ai-finance-coach"])
logger = logging.getLogger(__name__)

# skill_id for AITask tracking (matches VALID_SKILL_IDS in ai_tasks.py)
SKILL_ID = "coach"


@router.post("/generate")
async def trigger_finance_coach(
    request: Request,
    force: bool = False,
    current_user: User = Depends(require_adult),
    _ai: None = Depends(require_ai_enabled),
    _owner: None = Depends(require_owner),
    db: Session = Depends(get_db),
):
    """Trigger finance_coach generation (8h skill-cache + AITask-tracked SSE).

    U13: Mirrors trigger_generate_events (ai_report.py) — circuit breaker ->
    8h cache check (force skips) -> AITask tracking + bridge consumer SSE.
    Cache hit returns JSON 200 (non-stream).
    """
    blocked_resp = check_circuit_blocked(current_user.family_id, "finance_coach", db)
    if blocked_resp is not None:
        return blocked_resp

    # 8h skill-cache check (before streaming). force=true regenerates.
    if not force:
        cached = latest_by_skill(db, current_user.family_id, "finance_coach")
        if is_cache_fresh(cached, "finance_coach", family_id=current_user.family_id) and cached is not None:
            return JSONResponse(
                status_code=200,
                content={
                    "status": "cached",
                    "generated_at": ensure_utc(cached.generated_at).isoformat() if cached.generated_at else None,
                    "report": cached.report_json,
                },
            )

    # Check if there's already a running task - resume it instead of 409
    existing = AITaskService.get_running_task(current_user.family_id, SKILL_ID, db)
    if existing:
        # Already running — resume via bridge consumer
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
                skill_id=SKILL_ID,
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
            skill_id=SKILL_ID,
            session_id=session.id,
            db=db,
        )
        session_id = str(session.id)

    task_id = str(task.id)
    family_id = current_user.family_id
    user_id = str(current_user.id)

    # Build the PII-minimized snapshot (spec §7.1) — injected as input payload
    snapshot = build_family_finance_snapshot(db, current_user)

    # Phase 1: Backend-owned buffer (single streaming POST — no double trigger).
    agent_client = AgentClient(family_id, user_id, timeout=300.0)
    agent_url = f"/internal/gateway/runs/finance-coach/{session_id}"
    shared_bridge = get_shared_bridge()

    # Lifecycle result callback — persists coach output to cache on completion.
    async def _persist_coach_result(_event_type: str, data: dict) -> None:
        if isinstance(data, dict) and data.get("type") == "finance_coach.result":
            payload = data.get("payload")
            if payload:
                from apps.backend.app.database import SessionLocal

                _db = SessionLocal()
                try:
                    upsert_skill_result(_db, family_id, "finance_coach", payload)
                    _db.commit()
                finally:
                    _db.close()

    agent_trigger_body = {
        "family_id": str(family_id),
        "user_id": user_id,
        "language": current_user.language,
        "on_disconnect": "continue",
        "task_id": task_id,
        "input": {"messages": [{"role": "user", "content": json.dumps(snapshot, ensure_ascii=False)}]},
    }

    # Track whether the lifecycle consumer was spawned via the callback.
    lifecycle_spawned = [False]

    def _on_run_id(cl_run_id: str) -> None:
        resolved = AITaskService.extract_and_attach_run_id(
            task_id, cl_run_id, family_id
        )
        if resolved and not lifecycle_spawned[0]:
            lifecycle_spawned[0] = True
            _spawn_lifecycle_consumer(
                task_id=task_id,
                family_id=family_id,
                run_id=resolved,
                on_result=_persist_coach_result,
                bridge=shared_bridge,
            )

    # Spawn background pump: one streaming POST → shared bridge.
    asyncio.create_task(
        _pump_agent_sse_to_bridge(
            agent_client=agent_client,
            agent_url=agent_url,
            json_body=agent_trigger_body,
            bridge=shared_bridge,
            run_id="",
            task_id=task_id,
            on_run_id=_on_run_id,
        )
    )

    # Fallback: lifecycle consumer without run_id if agent omits Content-Location.
    if not lifecycle_spawned[0]:
        _spawn_lifecycle_consumer(
            task_id=task_id,
            family_id=family_id,
            run_id=None,
            on_result=_persist_coach_result,
            bridge=shared_bridge,
        )

    # SSE forwarder: subscribes to shared bridge, yields SSE text to frontend.
    last_event_id = request.headers.get("Last-Event-ID")
    stream_gen = consume_task_stream(
        task_id=task_id,
        family_id=family_id,
        last_event_id=last_event_id,
        run_id=None,
        bridge=shared_bridge,
    )

    return StreamingResponse(
        tracked_sse_stream(task_id, stream_gen),
        media_type="text/event-stream",
        headers={"X-Accel-Buffering": "no"},
    )
