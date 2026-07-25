"""finance_coach trigger endpoint (Plan A T8).

- POST /api/v1/ai/finance-coach/generate?force=false
    8h skill-cache check -> cached JSON 200 (non-stream) OR stream_run via
    the agent gateway /internal/gateway/runs/finance-coach/{thread_id} (Task 5).
    Mirrors ai_report.trigger_generate_events but skill_id='finance_coach'.
"""
import json
import logging
import uuid
from collections.abc import AsyncGenerator

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy.orm import Session

from apps.backend.app.auth.ai_deps import require_ai_enabled, require_owner
from apps.backend.app.auth.deps import require_adult
from apps.backend.app.database import get_db
from apps.backend.app.models.user import User
from apps.backend.app.routers._ai_events_helper import check_circuit_blocked
from apps.backend.app.services.agent_client import AgentClient
from apps.backend.app.services.finance_coach_cache import (
    is_cache_fresh,
    latest_by_skill,
    upsert_skill_result,
)
from apps.backend.app.services.finance_coach_snapshot import (
    build_family_finance_snapshot,
)

router = APIRouter(prefix="/ai/finance-coach", tags=["ai-finance-coach"])
logger = logging.getLogger(__name__)


async def _stream_finance_coach_sse(
    *,
    family_id: str,
    user_id: str,
    thread_id: str,
    snapshot: dict,
) -> AsyncGenerator[bytes, None]:
    """Proxy the agent's finance-coach SSE stream (mirrors _stream_asset_report_sse).

    Calls the agent's /internal/gateway/runs/finance-coach/{thread_id} endpoint
    via AgentClient (X-Agent-Token service-to-service auth) and forwards raw SSE
    bytes. The worker (_run_finance_coach_agent) emits a finance_coach.result
    custom event; this helper is a pure passthrough. On stream end the caller
    persists the result to ai_reports (skill_id='finance_coach').
    """
    agent_client = AgentClient(family_id, user_id, timeout=300.0)
    agent_url = f"/internal/gateway/runs/finance-coach/{thread_id}"
    try:
        async with agent_client.stream(
            "POST",
            agent_url,
            json={
                "family_id": str(family_id),
                "user_id": str(user_id),
                # Inject the snapshot as the run's user message so the worker
                # (_extract_finance_coach_snapshot) picks it up.
                "input": {"messages": [{"role": "user", "content": json.dumps(snapshot, ensure_ascii=False)}]},
            },
        ) as resp:
            if resp.status_code != 200:
                body = await resp.aread()
                logger.warning(
                    "[finance-coach] agent stream non-200: status=%s body=%s",
                    resp.status_code, body[:200],
                )
                err = json.dumps({"message": "财务建议服务异常", "name": "AgentError"}).encode()
                yield f"event: error\ndata: {err.decode()}\n\n".encode()
                return
            collected = b""
            async for line in resp.aiter_lines():
                yield (line + "\n").encode()
                collected += (line + "\n").encode()
            # Persist the finance_coach.result payload to the skill cache.
            # The worker emits exactly one `event: custom` frame with
            # data.type == "finance_coach.result". Parse it out of the collected bytes.
            _persist_finance_coach_result(family_id, collected)
    except Exception as exc:
        logger.warning("[finance-coach] agent stream failed err=%s", type(exc).__name__)
        err = json.dumps({"message": "财务建议服务中断", "name": type(exc).__name__}).encode()
        yield f"event: error\ndata: {err.decode()}\n\n".encode()


def _persist_finance_coach_result(family_id: str, collected_sse: bytes) -> None:
    """Extract the finance_coach.result payload from the SSE bytes and cache it.

    Called after a successful stream. Opens a short-lived session (separate from
    the request's read-only db) to write the result row. Silently no-ops if the
    result frame is missing (advice baseline: wrong/absent output is dropped, not
    displayed — spec §7.1).
    """
    try:
        text = collected_sse.decode("utf-8", errors="replace")
        # SSE frames look like: event: custom\ndata: {"type":"finance_coach.result","payload":{...}}\n\n
        payload = None
        for block in text.split("\n\n"):
            if "finance_coach.result" not in block:
                continue
            for line in block.split("\n"):
                if line.startswith("data: "):
                    try:
                        data = json.loads(line[len("data: "):])
                        if data.get("type") == "finance_coach.result":
                            payload = data.get("payload")
                    except json.JSONDecodeError:
                        continue
        if payload is None:
            logger.info("[finance-coach] no finance_coach.result frame in stream — not caching")
            return
        from apps.backend.app.database import SessionLocal
        with SessionLocal() as db:
            upsert_skill_result(db, family_id, "finance_coach", payload)
            db.commit()
    except Exception as exc:
        logger.warning("[finance-coach] persist result failed err=%s", type(exc).__name__)


@router.post("/generate")
async def trigger_finance_coach(
    force: bool = False,
    current_user: User = Depends(require_adult),
    _ai: None = Depends(require_ai_enabled),
    _owner: None = Depends(require_owner),
    db: Session = Depends(get_db),
):
    """Trigger finance_coach generation (8h skill-cache + SSE stream).

    Mirrors trigger_generate_events: circuit breaker -> 8h cache check (force
    skips) -> stream_run via agent gateway. Cache hit returns JSON 200 (non-stream).
    """
    blocked_resp = check_circuit_blocked(current_user.family_id, "finance_coach", db)
    if blocked_resp is not None:
        return blocked_resp

    # 8h skill-cache check (before streaming). force=true regenerates.
    if not force:
        cached = latest_by_skill(db, current_user.family_id, "finance_coach")
        if is_cache_fresh(cached, "finance_coach") and cached is not None:
            return JSONResponse(
                status_code=200,
                content={
                    "status": "cached",
                    "generated_at": cached.generated_at.isoformat() if cached.generated_at else None,
                    "report": cached.report_json,
                },
            )

    # Build the PII-minimized snapshot (spec §7.1) and stream.
    snapshot = build_family_finance_snapshot(db, current_user.family_id)
    thread_id = f"finance-coach-{current_user.family_id}-{uuid.uuid4().hex[:8]}"

    return StreamingResponse(
        _stream_finance_coach_sse(
            family_id=str(current_user.family_id),
            user_id=str(current_user.id),
            thread_id=thread_id,
            snapshot=snapshot,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
