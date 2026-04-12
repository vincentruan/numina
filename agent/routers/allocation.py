"""配置漂移检测 agent 路由。"""

import logging
import json

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

from config import settings
from services.orchestrator import orchestrator

router = APIRouter(prefix="/allocation", tags=["allocation"])
logger = logging.getLogger(__name__)


class DriftRequest(BaseModel):
    targets: dict[str, float]
    threshold: float = 10.0


@router.post("/drift")
async def check_drift(
    body: DriftRequest,
    x_family_id: str = Header(..., alias="X-Family-Id"),
    x_agent_token: str = Header(..., alias="X-Agent-Token"),
    x_user_id: str = Header(None, alias="X-User-Id"),
):
    if x_agent_token != settings.AGENT_INTERNAL_TOKEN:
        raise HTTPException(status_code=401, detail="invalid token")

    free_text = json.dumps(
        {"targets": body.targets, "threshold": body.threshold},
        ensure_ascii=False,
    )
    response = await orchestrator.dispatch(
        capability="allocation",
        family_id=x_family_id,
        user_id=x_user_id,
        free_text=free_text,
    )
    return response.model_dump()
