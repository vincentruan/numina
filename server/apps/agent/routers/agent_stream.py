"""Agent-first stream router."""

import hmac
from typing import Literal

from fastapi import APIRouter, Header, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from apps.agent.app.config import settings
from apps.agent.services.agent_dispatch import stream_agent_dispatch

router = APIRouter(prefix="/agent", tags=["agent-stream"])


class AgentStreamRequest(BaseModel):
    message: str
    thread_id: str | None = None
    enable_thinking: bool = False
    web_search: bool = False
    reasoning_effort: Literal["low", "medium", "high"] = "medium"
    # DeerFlow execution mode parameters (Phase 2)
    is_plan_mode: bool = False
    subagent_enabled: bool = False


@router.post("/{agent_id}/stream")
async def stream_agent(
    agent_id: int,
    body: AgentStreamRequest,
    x_family_id: str = Header(..., alias="X-Family-Id"),
    x_user_id: str = Header(..., alias="X-User-Id"),
    x_agent_token: str = Header(..., alias="X-Agent-Token"),
    x_thread_id: str = Header(None, alias="X-Thread-Id"),
) -> StreamingResponse:
    if not settings.AGENT_INTERNAL_TOKEN or not hmac.compare_digest(
        x_agent_token, settings.AGENT_INTERNAL_TOKEN
    ):
        raise HTTPException(status_code=401, detail="invalid token")

    thread_id = body.thread_id or x_thread_id

    return StreamingResponse(
        stream_agent_dispatch(
            agent_id=agent_id,
            family_id=x_family_id,
            user_id=x_user_id,
            thread_id=thread_id,
            message=body.message,
            enable_thinking=body.enable_thinking,
            web_search=body.web_search,
            reasoning_effort=body.reasoning_effort,
            # DeerFlow execution mode parameters (Phase 2)
            is_plan_mode=body.is_plan_mode,
            subagent_enabled=body.subagent_enabled,
        ),
        media_type="application/x-ndjson",
    )