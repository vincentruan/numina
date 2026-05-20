"""老化预警 agent 路由。"""

import hmac
import logging
import re

from fastapi import APIRouter, Header, HTTPException
from fastapi.responses import StreamingResponse

from apps.agent.app.config import settings
from apps.agent.services.orchestrator import orchestrator

router = APIRouter(prefix="/alerts", tags=["alerts"])
logger = logging.getLogger(__name__)

_ID_RE = re.compile(r"^\d+$")


def _validate_id(value: str, name: str) -> None:
    if not _ID_RE.match(value):
        raise HTTPException(status_code=400, detail=f"invalid {name}")


@router.post("/aging")
async def generate_aging_alerts(
    x_family_id: str = Header(..., alias="X-Family-Id"),
    x_agent_token: str = Header(..., alias="X-Agent-Token"),
    x_user_id: str = Header(None, alias="X-User-Id"),
):
    if not settings.AGENT_INTERNAL_TOKEN or not hmac.compare_digest(x_agent_token, settings.AGENT_INTERNAL_TOKEN):
        raise HTTPException(status_code=401, detail="invalid token")

    response = await orchestrator.dispatch(
        capability="alerts",
        family_id=x_family_id,
        user_id=x_user_id,
    )
    return response.model_dump()


@router.post("/stream")
async def generate_alerts_stream(
    x_family_id: str = Header(..., alias="X-Family-Id"),
    x_agent_token: str = Header(..., alias="X-Agent-Token"),
    x_task_id: str = Header(..., alias="X-Task-Id"),
    x_thread_id: str = Header(..., alias="X-Thread-Id"),
    x_user_id: str | None = Header(None, alias="X-User-Id"),
):
    """流式生成老化预警（由 backend 调用）。已废弃，请使用 /events。"""
    if not settings.AGENT_INTERNAL_TOKEN or not hmac.compare_digest(x_agent_token, settings.AGENT_INTERNAL_TOKEN):
        raise HTTPException(status_code=401, detail="invalid token")
    _validate_id(x_task_id, "X-Task-Id")
    _validate_id(x_thread_id, "X-Thread-Id")
    logger.warning("Deprecated endpoint /alerts/stream called; migrate to /alerts/events")

    async def event_stream():
        async for chunk in orchestrator.stream_dispatch(
            capability="alerts",
            family_id=x_family_id,
            task_id=x_task_id,
            thread_id=x_thread_id,
            user_id=x_user_id,
        ):
            yield chunk.encode("utf-8")

    return StreamingResponse(event_stream(), media_type="text/plain; charset=utf-8")


@router.post("/events")
async def generate_alerts_events(
    x_family_id: str = Header(..., alias="X-Family-Id"),
    x_agent_token: str = Header(..., alias="X-Agent-Token"),
    x_task_id: str = Header(..., alias="X-Task-Id"),
    x_thread_id: str = Header(..., alias="X-Thread-Id"),
    x_user_id: str | None = Header(None, alias="X-User-Id"),
):
    """NDJSON 事件流（由 backend 调用）。"""
    if not settings.AGENT_INTERNAL_TOKEN or not hmac.compare_digest(x_agent_token, settings.AGENT_INTERNAL_TOKEN):
        raise HTTPException(status_code=401, detail="invalid token")
    _validate_id(x_task_id, "X-Task-Id")
    _validate_id(x_thread_id, "X-Thread-Id")

    async def event_stream():
        async for line in orchestrator.stream_dispatch_events(
            capability="alerts",
            family_id=x_family_id,
            task_id=x_task_id,
            thread_id=x_thread_id,
            user_id=x_user_id,
        ):
            yield line.encode("utf-8")

    return StreamingResponse(event_stream(), media_type="application/x-ndjson")
