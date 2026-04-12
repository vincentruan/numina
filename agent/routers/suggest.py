"""智能资产录入助手端点（由 backend 调用）。"""

import json
import logging

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

from config import settings
from services.orchestrator import orchestrator

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
    x_user_id: str = Header(None, alias="X-User-Id"),
):
    if x_agent_token != settings.AGENT_INTERNAL_TOKEN:
        raise HTTPException(status_code=401, detail="invalid token")

    # Pass request fields as free_text JSON so the orchestrator/fallback can use them
    free_text = json.dumps(
        {"name": body.name, "category": body.category, "asset_type": body.asset_type},
        ensure_ascii=False,
    )
    response = await orchestrator.dispatch(
        capability="suggest",
        family_id=x_family_id,
        user_id=x_user_id,
        free_text=free_text,
    )
    return response.model_dump()
