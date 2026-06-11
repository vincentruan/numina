"""Agent 侧体检报告路由。

由 backend 调用，不直接暴露给前端。
"""

import logging

from fastapi import APIRouter, Header, HTTPException
from fastapi.responses import StreamingResponse

from apps.agent.app.config import settings
from apps.agent.services.orchestrator import orchestrator

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


@router.post("/events")
async def generate_report_events(
    x_family_id: str = Header(..., alias="X-Family-Id"),
    x_agent_token: str = Header(..., alias="X-Agent-Token"),
    x_task_id: str = Header(..., alias="X-Task-Id"),
    x_thread_id: str = Header(..., alias="X-Thread-Id"),
    x_user_id: str | None = Header(None, alias="X-User-Id"),
):
    """NDJSON 事件流生成体检报告（由 backend 调用）。"""
    if x_agent_token != settings.AGENT_INTERNAL_TOKEN:
        raise HTTPException(status_code=401, detail="invalid token")

    async def event_stream():
        async for line in orchestrator.stream_dispatch(
            capability="report",
            family_id=x_family_id,
            task_id=x_task_id,
            thread_id=x_thread_id,
            user_id=x_user_id,
        ):
            yield line.encode("utf-8")

    return StreamingResponse(event_stream(), media_type="application/x-ndjson")


@router.post("/generate/events")
async def generate_markdown_events(
    x_family_id: str = Header(..., alias="X-Family-Id"),
    x_agent_token: str = Header(..., alias="X-Agent-Token"),
    x_task_id: str = Header(..., alias="X-Task-Id"),
    x_thread_id: str = Header(..., alias="X-Thread-Id"),
    x_user_id: str | None = Header(None, alias="X-User-Id"),
):
    """Phase 1: 生成 markdown 报告文件（由 backend proxy_report_events 调用）。"""
    if x_agent_token != settings.AGENT_INTERNAL_TOKEN:
        raise HTTPException(status_code=401, detail="invalid token")

    async def event_stream():
        async for line in orchestrator.stream_dispatch(
            capability="report_generate",
            family_id=x_family_id,
            task_id=x_task_id,
            thread_id=x_thread_id,
            user_id=x_user_id,
        ):
            yield line.encode("utf-8")

    return StreamingResponse(event_stream(), media_type="application/x-ndjson")


@router.post("/structured/events")
async def structured_conversion_events(
    x_family_id: str = Header(..., alias="X-Family-Id"),
    x_agent_token: str = Header(..., alias="X-Agent-Token"),
    x_task_id: str = Header(..., alias="X-Task-Id"),
    x_thread_id: str = Header(..., alias="X-Thread-Id"),
    x_user_id: str | None = Header(None, alias="X-User-Id"),
    x_markdown_path: str | None = Header(None, alias="X-Markdown-Path"),
):
    """Phase 2: 将 markdown 转换为结构化 JSON（由 backend proxy_report_events 调用）。

    读取指定的 markdown 文件，转换为 indicators 格式的 JSON。
    """
    if x_agent_token != settings.AGENT_INTERNAL_TOKEN:
        raise HTTPException(status_code=401, detail="invalid token")

    # Pass markdown path in trigger message for the skill
    trigger_message = "将报告转换为结构化JSON格式"
    if x_markdown_path:
        trigger_message = f"读取文件 {x_markdown_path} 并转换为结构化JSON格式"

    async def event_stream():
        async for line in orchestrator.stream_dispatch(
            capability="report_structured",
            family_id=x_family_id,
            task_id=x_task_id,
            thread_id=x_thread_id,
            user_id=x_user_id,
            free_text=trigger_message,
        ):
            yield line.encode("utf-8")

    return StreamingResponse(event_stream(), media_type="application/x-ndjson")
