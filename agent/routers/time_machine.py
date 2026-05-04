"""时光机 LLM 解读 agent 路由。"""

import json
import logging
from typing import Literal

from fastapi import APIRouter, Header, HTTPException
from fastapi.responses import StreamingResponse
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


@router.post("/stream")
async def interpret_time_machine_stream(
    x_family_id: str = Header(..., alias="X-Family-Id"),
    x_agent_token: str = Header(..., alias="X-Agent-Token"),
    x_task_id: str = Header(..., alias="X-Task-Id"),
    x_thread_id: str = Header(..., alias="X-Thread-Id"),
    x_user_id: str | None = Header(None, alias="X-User-Id"),
):
    """流式生成时光机解读（由 backend 调用）。"""
    if x_agent_token != settings.AGENT_INTERNAL_TOKEN:
        raise HTTPException(status_code=401, detail="invalid token")

    async def event_stream():
        async for chunk in orchestrator.stream_dispatch(
            capability="time_machine",
            family_id=x_family_id,
            task_id=x_task_id,
            thread_id=x_thread_id,
            user_id=x_user_id,
        ):
            yield chunk.encode("utf-8")

    return StreamingResponse(event_stream(), media_type="text/plain; charset=utf-8")
