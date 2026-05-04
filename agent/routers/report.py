"""Agent 侧体检报告路由。

由 backend 调用，不直接暴露给前端。
"""

import logging

from fastapi import APIRouter, Header, HTTPException
from fastapi.responses import StreamingResponse

from app.config import settings
from services.orchestrator import orchestrator

router = APIRouter(prefix="/report", tags=["report"])
logger = logging.getLogger(__name__)


@router.post("/generate")
async def generate_report(
    x_family_id: str = Header(..., alias="X-Family-Id"),
    x_agent_token: str = Header(..., alias="X-Agent-Token"),
    x_user_id: str = Header(None, alias="X-User-Id"),
):
    """生成家庭资产体检报告（由 backend 调用）。"""
    if x_agent_token != settings.AGENT_INTERNAL_TOKEN:
        raise HTTPException(status_code=401, detail="invalid token")

    response = await orchestrator.dispatch(
        capability="report",
        family_id=x_family_id,
        user_id=x_user_id,
    )
    return response.model_dump()


@router.post("/generate/stream")
async def generate_report_stream(
    x_family_id: str = Header(..., alias="X-Family-Id"),
    x_agent_token: str = Header(..., alias="X-Agent-Token"),
    x_task_id: str = Header(..., alias="X-Task-Id"),
    x_thread_id: str = Header(..., alias="X-Thread-Id"),
    x_user_id: str | None = Header(None, alias="X-User-Id"),
):
    """流式生成体检报告（由 backend 调用）。"""
    if x_agent_token != settings.AGENT_INTERNAL_TOKEN:
        raise HTTPException(status_code=401, detail="invalid token")

    async def event_stream():
        async for chunk in orchestrator.stream_dispatch(
            capability="report",
            family_id=x_family_id,
            task_id=x_task_id,
            thread_id=x_thread_id,
            user_id=x_user_id,
        ):
            yield chunk.encode("utf-8")

    return StreamingResponse(event_stream(), media_type="text/plain; charset=utf-8")
