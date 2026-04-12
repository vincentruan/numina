"""老化预警 agent 路由。"""

import logging

from fastapi import APIRouter, Header, HTTPException

from config import settings
from services.orchestrator import orchestrator

router = APIRouter(prefix="/alerts", tags=["alerts"])
logger = logging.getLogger(__name__)


@router.post("/aging")
async def generate_aging_alerts(
    x_family_id: str = Header(..., alias="X-Family-Id"),
    x_agent_token: str = Header(..., alias="X-Agent-Token"),
    x_user_id: str = Header(None, alias="X-User-Id"),
):
    if x_agent_token != settings.AGENT_INTERNAL_TOKEN:
        raise HTTPException(status_code=401, detail="invalid token")

    response = await orchestrator.dispatch(
        capability="alerts",
        family_id=x_family_id,
        user_id=x_user_id,
    )
    return response.model_dump()
