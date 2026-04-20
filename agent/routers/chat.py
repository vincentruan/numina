"""问答助手 agent 路由。"""

import logging

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

from config import settings
from services.orchestrator import orchestrator

router = APIRouter(prefix="/chat", tags=["chat"])
logger = logging.getLogger(__name__)


class ChatRequest(BaseModel):
    question: str


@router.post("/ask")
async def ask(
    body: ChatRequest,
    x_family_id: str = Header(..., alias="X-Family-Id"),
    x_agent_token: str = Header(..., alias="X-Agent-Token"),
    x_user_id: str = Header(None, alias="X-User-Id"),
    x_thread_id: str = Header(None, alias="X-Thread-Id"),
):
    if x_agent_token != settings.AGENT_INTERNAL_TOKEN:
        raise HTTPException(status_code=401, detail="invalid token")

    response = await orchestrator.dispatch(
        capability="chat",
        family_id=x_family_id,
        user_id=x_user_id,
        free_text=body.question,
        thread_id=x_thread_id,
    )
    return response.model_dump()
