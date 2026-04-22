"""处置建议 agent 路由。"""

import logging

from fastapi import APIRouter, Header, HTTPException

from app.config import settings
from services.orchestrator import orchestrator

router = APIRouter(prefix="/disposal", tags=["disposal"])
logger = logging.getLogger(__name__)


@router.post("/scan")
async def scan_disposal(
    x_family_id: str = Header(..., alias="X-Family-Id"),
    x_agent_token: str = Header(..., alias="X-Agent-Token"),
    x_user_id: str = Header(None, alias="X-User-Id"),
):
    if x_agent_token != settings.AGENT_INTERNAL_TOKEN:
        raise HTTPException(status_code=401, detail="invalid token")

    response = await orchestrator.dispatch(
        capability="disposal",
        family_id=x_family_id,
        user_id=x_user_id,
    )
    return response.model_dump()
