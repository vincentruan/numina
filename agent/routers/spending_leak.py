"""消费漏洞检测 agent 路由。"""

import logging

from fastapi import APIRouter, Header, HTTPException
from fastapi.responses import StreamingResponse

from app.config import settings
from services.orchestrator import orchestrator

router = APIRouter(prefix="/spending-leak", tags=["spending-leak"])
logger = logging.getLogger(__name__)


@router.post("")
async def analyze_spending_leaks(
    x_family_id: str = Header(..., alias="X-Family-Id"),
    x_agent_token: str = Header(..., alias="X-Agent-Token"),
    x_user_id: str = Header(None, alias="X-User-Id"),
):
    """分析家庭消费漏洞（由 backend 调用）。"""
    if x_agent_token != settings.AGENT_INTERNAL_TOKEN:
        raise HTTPException(status_code=401, detail="invalid token")

    response = await orchestrator.dispatch(
        capability="spending_leak",
        family_id=x_family_id,
        user_id=x_user_id,
    )
    return response.model_dump()


@router.post("/stream")
async def analyze_spending_leaks_stream(
    x_family_id: str = Header(..., alias="X-Family-Id"),
    x_agent_token: str = Header(..., alias="X-Agent-Token"),
    x_task_id: str = Header(..., alias="X-Task-Id"),
    x_thread_id: str = Header(..., alias="X-Thread-Id"),
    x_user_id: str | None = Header(None, alias="X-User-Id"),
):
    """流式分析家庭消费漏洞（由 backend 调用）。"""
    if x_agent_token != settings.AGENT_INTERNAL_TOKEN:
        raise HTTPException(status_code=401, detail="invalid token")

    async def event_stream():
        async for chunk in orchestrator.stream_dispatch(
            capability="spending_leak",
            family_id=x_family_id,
            task_id=x_task_id,
            thread_id=x_thread_id,
            user_id=x_user_id,
        ):
            yield chunk.encode("utf-8")

    return StreamingResponse(event_stream(), media_type="text/plain; charset=utf-8")
