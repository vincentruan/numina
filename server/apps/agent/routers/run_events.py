"""Run event query endpoints (T12).

Exposes the persisted run event stream for debugging and audit. Query by
``thread_id`` (a single conversation) or ``family_id`` (all runs for a family).

Authentication: ``X-Agent-Token`` (same as other internal agent routers).
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Query

from apps.agent.services.run_event_store import RunEvent, _get_event_store
from packages.core.logging import get_logger
from packages.security.service_auth.agent_token_verify import verify_service_token

router = APIRouter(prefix="/run-events", tags=["run-events"])
logger = get_logger(__name__)


@router.get("")
async def query_run_events(
    thread_id: str | None = Query(None, description="Filter by thread ID"),
    family_id: str | None = Query(None, description="Filter by family ID"),
    limit: int = Query(100, ge=1, le=1000, description="Max events to return"),
    offset: int = Query(0, ge=0, description="Events to skip"),
    x_family_id: str = Header(..., alias="X-Family-Id"),
    _token_family: str = Depends(verify_service_token),
) -> list[dict[str, Any]]:
    """Return recorded run events, newest-last, ordered by timestamp.

    Exactly one of ``thread_id`` or ``family_id`` must be supplied. The
    ``family_id`` query parameter must match the ``X-Family-Id`` header
    (tenant isolation); ``thread_id`` queries are scoped to the caller's
    family automatically.
    """
    if not thread_id and not family_id:
        raise HTTPException(
            status_code=400,
            detail="须提供 thread_id 或 family_id 之一",
        )

    if family_id and family_id != x_family_id:
        raise HTTPException(status_code=403, detail="无权访问其他家庭的事件")

    store = _get_event_store()
    try:
        if thread_id:
            events: list[RunEvent] = store.query_by_thread(
                thread_id, family_id=x_family_id
            )
            events = events[offset : offset + limit]
        else:
            events = store.query_by_family(x_family_id, limit=limit, offset=offset)
    except Exception:
        logger.exception("run-events query failed")
        raise HTTPException(status_code=500, detail="事件查询失败") from None

    return [e.model_dump() for e in events]
