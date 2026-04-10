"""Agent 侧体检报告路由。

由 backend WebSocket handler 调用，不直接暴露给前端。
"""

import logging

from fastapi import APIRouter, Header, HTTPException

from config import settings
from core.llm import LLMClient
from services.health_report import generate_health_report

router = APIRouter(prefix="/report", tags=["report"])
logger = logging.getLogger(__name__)


@router.post("/generate")
async def generate_report(
    x_family_id: str = Header(..., alias="X-Family-Id"),
    x_agent_token: str = Header(..., alias="X-Agent-Token"),
):
    """生成家庭资产体检报告（由 backend 调用）。"""
    if x_agent_token != settings.AGENT_INTERNAL_TOKEN:
        raise HTTPException(status_code=401, detail="invalid token")

    # Fetch family AI config from backend to get API key
    from core.backend_client import BackendClient
    client = BackendClient(family_id=x_family_id)
    try:
        ai_config = await client.get_family_ai_config()
    except Exception as e:
        logger.error(f"获取 AI 配置失败: {e}")
        raise HTTPException(status_code=503, detail="无法获取 AI 配置")

    if not ai_config.get("ai_enabled"):
        raise HTTPException(status_code=403, detail="AI 功能未启用")

    provider = ai_config.get("ai_provider")
    api_key = ai_config.get("api_key")
    if not provider or not api_key:
        raise HTTPException(status_code=422, detail="AI 服务商或 API Key 未配置")

    llm = LLMClient(provider=provider, api_key=api_key)
    try:
        report = await generate_health_report(family_id=x_family_id, llm=llm)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.error(f"报告生成失败 family={x_family_id}: {e}")
        raise HTTPException(status_code=500, detail="报告生成失败，请稍后重试")

    return report
