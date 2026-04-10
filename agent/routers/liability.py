"""负债顾问 agent 路由。"""

import logging

from fastapi import APIRouter, Header, HTTPException

from config import settings
from core.llm import LLMClient
from services.liability_advisor import analyze_liabilities

router = APIRouter(prefix="/liability", tags=["liability"])
logger = logging.getLogger(__name__)


@router.post("/analyze")
async def analyze_liability(
    x_family_id: str = Header(..., alias="X-Family-Id"),
    x_agent_token: str = Header(..., alias="X-Agent-Token"),
):
    if x_agent_token != settings.AGENT_INTERNAL_TOKEN:
        raise HTTPException(status_code=401, detail="invalid token")

    from core.backend_client import BackendClient
    client = BackendClient(family_id=x_family_id)
    ai_config = await client.get_family_ai_config()
    if not ai_config.get("ai_enabled"):
        raise HTTPException(status_code=403, detail="AI 功能未启用")

    llm = LLMClient(provider=ai_config["ai_provider"], api_key=ai_config["api_key"])
    result = await analyze_liabilities(family_id=x_family_id, llm=llm)
    return result
