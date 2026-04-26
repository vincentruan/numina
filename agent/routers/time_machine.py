"""时光机 LLM 解读 agent 路由。"""

import json
import logging
from typing import Literal

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

from app.config import settings
from services.orchestrator import orchestrator

router = APIRouter(prefix="/time-machine", tags=["time-machine"])
logger = logging.getLogger(__name__)


class InterpretRequest(BaseModel):
    type: Literal["whatif", "projection"]
    data: dict
    family_context: dict | None = None


@router.post("/interpret")
async def interpret_time_machine(
    body: InterpretRequest,
    x_family_id: str = Header(..., alias="X-Family-Id"),
    x_agent_token: str = Header(..., alias="X-Agent-Token"),
):
    if x_agent_token != settings.AGENT_INTERNAL_TOKEN:
        raise HTTPException(status_code=401, detail="invalid token")

    try:
        family_id = int(x_family_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="invalid X-Family-Id header")

    free_text = json.dumps(
        {"type": body.type, "data": body.data, "family_context": body.family_context},
        ensure_ascii=False,
    )

    response = await orchestrator.dispatch(
        capability="time_machine",
        family_id=family_id,
        free_text=free_text,
    )
    return {"summary": response.summary}
