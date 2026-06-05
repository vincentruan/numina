"""处置建议 agent 路由。"""

import hmac
import logging
import re

from fastapi import APIRouter, Header, HTTPException
from fastapi.responses import StreamingResponse

from apps.agent.app.config import settings
from apps.agent.services.orchestrator import orchestrator

router = APIRouter(prefix="/disposal", tags=["disposal"])
logger = logging.getLogger(__name__)

_ID_RE = re.compile(r"^\d+$")


def _validate_id(value: str, name: str) -> None:
    if not _ID_RE.match(value):
        raise HTTPException(status_code=400, detail=f"invalid {name}")


@router.post("/scan")
async def scan_disposal(
    x_family_id: str = Header(..., alias="X-Family-Id"),
    x_agent_token: str = Header(..., alias="X-Agent-Token"),
    x_user_id: str = Header(None, alias="X-User-Id"),
):
    if not settings.AGENT_INTERNAL_TOKEN or not hmac.compare_digest(x_agent_token, settings.AGENT_INTERNAL_TOKEN):
        raise HTTPException(status_code=401, detail="invalid token")

    response = await orchestrator.dispatch(
        capability="disposal",
        family_id=x_family_id,
        user_id=x_user_id,
    )
    return response.model_dump()


@router.post("/events")
async def scan_disposal_events(
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
        async for line in orchestrator.stream_dispatch(
            capability="disposal",
            family_id=x_family_id,
            task_id=x_task_id,
            thread_id=x_thread_id,
            user_id=x_user_id,
        ):
            yield line.encode("utf-8")

    return StreamingResponse(event_stream(), media_type="application/x-ndjson")
