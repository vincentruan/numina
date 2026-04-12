"""Agent 侧体检报告路由。

由 backend 调用，不直接暴露给前端。
"""

import logging

from fastapi import APIRouter, Header, HTTPException

from config import settings
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
