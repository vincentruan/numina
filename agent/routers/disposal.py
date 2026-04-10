"""处置建议 agent 路由。"""

import logging

from fastapi import APIRouter, Header, HTTPException

from config import settings
from core.llm import LLMClient
from services.disposal_advisor import scan_disposal_suggestions

router = APIRouter(prefix="/disposal", tags=["disposal"])
logger = logging.getLogger(__name__)


@router.post("/scan")
async def scan_disposal(
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
    suggestions = await scan_disposal_suggestions(family_id=x_family_id, llm=llm)
    return {"suggestions": suggestions}
