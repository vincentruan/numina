"""Agent-first stream router."""

from fastapi import APIRouter, Header, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, field_validator

from apps.agent.app.config import settings
from apps.agent.services.agent_dispatch import stream_agent_dispatch

router = APIRouter(prefix="/agent", tags=["agent-stream"])


class AgentStreamRequest(BaseModel):
    message: str
    thread_id: str | None = None
    enable_thinking: bool = False
    # U2: reasoning_effort controls thinking depth when enable_thinking=True.
    # Values: "low" (single-step tool calls), "medium" (default), "high" (multi-step).
    reasoning_effort: str | None = None

    @field_validator("reasoning_effort")
    @classmethod
    def validate_reasoning_effort(cls, v: str | None) -> str | None:
        if v is not None and v not in ("low", "medium", "high"):
            raise ValueError("reasoning_effort 必须为 low、medium 或 high")
        return v


@router.post("/{agent_id}/stream")
async def stream_agent(
    agent_id: int,
    body: AgentStreamRequest,
    x_family_id: str = Header(..., alias="X-Family-Id"),
    x_user_id: str = Header(..., alias="X-User-Id"),
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
            user_id=x_user_id,
            thread_id=thread_id,
            message=body.message,
            enable_thinking=body.enable_thinking,
            reasoning_effort=body.reasoning_effort,
        ),
        media_type="application/x-ndjson",
    )