"""Agent-first stream router."""

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


@router.post("/{agent_id}/stream")
async def stream_agent(
    agent_id: int,
    body: AgentStreamRequest,
    x_family_id: str = Header(..., alias="X-Family-Id"),
    x_agent_token: str = Header(..., alias="X-Agent-Token"),
    x_thread_id: str = Header(None, alias="X-Thread-Id"),
) -> StreamingResponse:
    if x_agent_token != settings.AGENT_INTERNAL_TOKEN:
        raise HTTPException(status_code=401, detail="invalid token")

    thread_id = body.thread_id or x_thread_id

    return StreamingResponse(
        stream_agent_dispatch(
            agent_id=agent_id,
            family_id=x_family_id,
            thread_id=thread_id,
            message=body.message,
            enable_thinking=body.enable_thinking,
        ),
        media_type="application/x-ndjson",
    )