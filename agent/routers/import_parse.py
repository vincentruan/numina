"""金融文档持仓解析端点（由 backend 调用）。"""

import json
import logging

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

from app.config import settings
from services.orchestrator import orchestrator

router = APIRouter(prefix="/import", tags=["import"])
logger = logging.getLogger(__name__)


class ImportParseRequest(BaseModel):
    text: str


@router.post("/parse")
async def parse_import(
    body: ImportParseRequest,
    x_family_id: str = Header(..., alias="X-Family-Id"),
    x_agent_token: str = Header(..., alias="X-Agent-Token"),
    x_user_id: str = Header(None, alias="X-User-Id"),
):
    """解析金融文档文本，提取持仓快照（由 backend 调用）。"""
    if x_agent_token != settings.AGENT_INTERNAL_TOKEN:
        raise HTTPException(status_code=401, detail="invalid token")

    free_text = json.dumps({"text": body.text}, ensure_ascii=False)
    response = await orchestrator.dispatch(
        capability="import_parse",
        family_id=x_family_id,
        user_id=x_user_id,
        free_text=free_text,
    )
    return response.model_dump()
