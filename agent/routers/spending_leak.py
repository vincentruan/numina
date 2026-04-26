"""消费漏洞检测 agent 路由。"""

import logging

from fastapi import APIRouter, Header, HTTPException

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
