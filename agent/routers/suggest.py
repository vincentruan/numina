"""智能资产录入助手端点（由 backend 调用）。"""

import logging

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

from config import settings
from core.llm import LLMClient
from services.asset_suggest import suggest_asset_fields

router = APIRouter(prefix="/suggest", tags=["suggest"])
logger = logging.getLogger(__name__)


class AssetSuggestRequest(BaseModel):
    name: str
    category: str
    asset_type: str = "physical"


@router.post("/asset")
async def suggest_asset(
    body: AssetSuggestRequest,
    x_family_id: str = Header(..., alias="X-Family-Id"),
    x_agent_token: str = Header(..., alias="X-Agent-Token"),
):
    if x_agent_token != settings.AGENT_INTERNAL_TOKEN:
        raise HTTPException(status_code=401, detail="invalid token")

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
    result = await suggest_asset_fields(
        name=body.name,
        category=body.category,
        asset_type=body.asset_type,
        llm=llm,
    )
    return result
