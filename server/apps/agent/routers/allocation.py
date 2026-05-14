"""配置漂移检测 agent 路由。"""

import hmac
import json
import logging
import re

from fastapi import APIRouter, Header, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from apps.agent.app.config import settings
from apps.agent.services.orchestrator import orchestrator

router = APIRouter(prefix="/allocation", tags=["allocation"])
logger = logging.getLogger(__name__)

_UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.IGNORECASE)


def _validate_uuid(value: str, name: str) -> None:
    if not _UUID_RE.match(value):
        raise HTTPException(status_code=400, detail=f"invalid {name}")


class DriftRequest(BaseModel):
    targets: dict[str, float]
    threshold: float = 10.0


@router.post("/drift")
async def check_drift(
    body: DriftRequest,
    x_family_id: str = Header(..., alias="X-Family-Id"),
    x_agent_token: str = Header(..., alias="X-Agent-Token"),
    x_user_id: str = Header(None, alias="X-User-Id"),
):
    if not settings.AGENT_INTERNAL_TOKEN or not hmac.compare_digest(x_agent_token, settings.AGENT_INTERNAL_TOKEN):
        raise HTTPException(status_code=401, detail="invalid token")

    free_text = json.dumps(
        {"targets": body.targets, "threshold": body.threshold},
        ensure_ascii=False,
    )
    response = await orchestrator.dispatch(
        capability="allocation",
        family_id=x_family_id,
        user_id=x_user_id,
        free_text=free_text,
    )
    return response.model_dump()


@router.post("/stream")
async def check_allocation_stream(
    x_family_id: str = Header(..., alias="X-Family-Id"),
    x_agent_token: str = Header(..., alias="X-Agent-Token"),
    x_task_id: str = Header(..., alias="X-Task-Id"),
    x_thread_id: str = Header(..., alias="X-Thread-Id"),
    x_user_id: str | None = Header(None, alias="X-User-Id"),
):
    """流式生成配置漂移分析（由 backend 调用）。已废弃，请使用 /events。"""
    if not settings.AGENT_INTERNAL_TOKEN or not hmac.compare_digest(x_agent_token, settings.AGENT_INTERNAL_TOKEN):
        raise HTTPException(status_code=401, detail="invalid token")
    _validate_uuid(x_task_id, "X-Task-Id")
    _validate_uuid(x_thread_id, "X-Thread-Id")
    logger.warning("Deprecated endpoint /allocation/stream called; migrate to /allocation/events")

    async def event_stream():
        async for chunk in orchestrator.stream_dispatch(
            capability="allocation",
            family_id=x_family_id,
            task_id=x_task_id,
            thread_id=x_thread_id,
            user_id=x_user_id,
        ):
            yield chunk.encode("utf-8")

    return StreamingResponse(event_stream(), media_type="text/plain; charset=utf-8")


@router.post("/events")
async def check_allocation_events(
    x_family_id: str = Header(..., alias="X-Family-Id"),
    x_agent_token: str = Header(..., alias="X-Agent-Token"),
    x_task_id: str = Header(..., alias="X-Task-Id"),
    x_thread_id: str = Header(..., alias="X-Thread-Id"),
    x_user_id: str | None = Header(None, alias="X-User-Id"),
):
    """NDJSON 事件流（由 backend 调用）。"""
    if not settings.AGENT_INTERNAL_TOKEN or not hmac.compare_digest(x_agent_token, settings.AGENT_INTERNAL_TOKEN):
        raise HTTPException(status_code=401, detail="invalid token")
    _validate_uuid(x_task_id, "X-Task-Id")
    _validate_uuid(x_thread_id, "X-Thread-Id")

    async def event_stream():
        async for line in orchestrator.stream_dispatch_events(
            capability="allocation",
            family_id=x_family_id,
            task_id=x_task_id,
            thread_id=x_thread_id,
            user_id=x_user_id,
        ):
            yield line.encode("utf-8")

    return StreamingResponse(event_stream(), media_type="application/x-ndjson")
