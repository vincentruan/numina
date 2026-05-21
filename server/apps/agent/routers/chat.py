"""问答助手 agent 路由。"""

import logging
import uuid

from fastapi import APIRouter, Header, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from apps.agent.app.config import settings
from apps.agent.services.orchestrator import orchestrator
from apps.agent.services.stream_events import EventStreamBuilder

router = APIRouter(prefix="/chat", tags=["chat"])
logger = logging.getLogger(__name__)


class ChatRequest(BaseModel):
    question: str


class ChatStreamRequest(BaseModel):
    question: str
    deep_think: bool = False
    web_search: bool = False


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


@router.post("/ask/stream")
async def ask_stream(
    body: ChatStreamRequest,
    x_family_id: str = Header(..., alias="X-Family-Id"),
    x_agent_token: str = Header(..., alias="X-Agent-Token"),
    x_user_id: str = Header(None, alias="X-User-Id"),
    x_thread_id: str = Header(None, alias="X-Thread-Id"),
):
    """流式问答，输出 NDJSON 事件流。"""
    if x_agent_token != settings.AGENT_INTERNAL_TOKEN:
        raise HTTPException(status_code=401, detail="invalid token")

    async def generate():
        task_id = str(uuid.uuid4())
        event_builder = EventStreamBuilder(capability_id="chat", task_id=task_id)
        try:
            async for event_line in orchestrator.stream_dispatch_events(
                capability="chat",
                family_id=x_family_id,
                task_id=task_id,
                user_id=x_user_id,
                thread_id=x_thread_id,
                free_text=body.question,
                enable_thinking_override=body.deep_think,
                web_search=body.web_search,
            ):
                yield event_line

        except Exception as e:
            logger.error(f"[chat/stream] unhandled error: {e}")
            yield event_builder.error(
                "抱歉，AI 服务暂时不可用，请稍后重试。",
                code="chat_stream_error",
            ).to_ndjson()

    return StreamingResponse(generate(), media_type="application/x-ndjson; charset=utf-8")
