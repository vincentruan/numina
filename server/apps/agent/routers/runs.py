"""Runs endpoints — create and stream agent runs.

Implements the LangGraph Platform runs API specifically for the chat UI.
We use DeerFlowAdapter.raw_stream_dispatch to yield standard LangGraph SSE frames
while maintaining Numina's tenant isolation (family_id).
"""

from __future__ import annotations

import json
import logging
from typing import Any, Literal
import uuid

from fastapi import APIRouter, Header, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from apps.agent.services.deerflow_adapter.adapter import create_family_adapter
from apps.agent.schemas.context import FamilyContext, RedactedContext
from apps.agent.services.pii_redactor import pii_redactor
from apps.agent.core.backend_client import BackendClient
from apps.agent.services.session_store import AiSessionRepository
import asyncio
logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/threads", tags=["runs"])

# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------

class RunCreateRequest(BaseModel):
    assistant_id: str | None = Field(default=None, description="Agent / assistant to use")
    input: dict[str, Any] | None = Field(default=None, description="Graph input (e.g. {messages: [...]})")
    command: dict[str, Any] | None = Field(default=None, description="LangGraph Command")
    metadata: dict[str, Any] | None = Field(default=None, description="Run metadata")
    config: dict[str, Any] | None = Field(default=None, description="RunnableConfig overrides")
    context: dict[str, Any] | None = Field(default=None, description="DeerFlow context overrides")
    stream_mode: list[str] | str | None = Field(default=None, description="Stream mode(s)")

def format_sse(event: str, data: Any, *, event_id: str | None = None) -> str:
    payload = json.dumps(data, default=str, ensure_ascii=False)
    parts = [f"event: {event}", f"data: {payload}"]
    if event_id:
        parts.append(f"id: {event_id}")
    parts.append("")
    parts.append("")
    return "\n".join(parts)

# ---------------------------------------------------------------------------
# Background Tasks
# ---------------------------------------------------------------------------

async def _generate_and_save_title(thread_id: str, family_id: str, user_message: str, ai_config: dict[str, Any]):
    """Generate a short title for the thread in the background."""
    if not user_message:
        return
        
    try:
        from langchain_openai import ChatOpenAI
        from langchain_core.messages import SystemMessage, HumanMessage
        
        # Determine model
        model = ai_config.get("ai_model_id") or "gpt-4o-mini"
        api_key = ai_config.get("api_key") or "dummy"
        base_url = ai_config.get("base_url")
        
        llm = ChatOpenAI(
            model=model,
            api_key=api_key,
            base_url=base_url,
            temperature=0.3,
            max_tokens=30,
        )
        
        prompt = SystemMessage(content="You are a helpful assistant that generates a concise 2-4 word title for a chat conversation based on the user's first message. Respond ONLY with the title. Do not use quotes or punctuation.")
        human = HumanMessage(content=user_message)
        
        response = await llm.ainvoke([prompt, human])
        title = response.content.strip().strip('"').strip("'")
        
        if title:
            repo = AiSessionRepository(family_id)
            # Only update if the session exists
            session = await repo.get_session(thread_id)
            if session and (not session.get("title") or session.get("title") == "New Chat"):
                await repo.update_summary(session_id=thread_id, family_id=family_id, summary=None, title=title)
                logger.info(f"[runs] Generated title '{title}' for thread {thread_id}")
    except Exception as e:
        logger.error(f"[runs] Failed to generate title for thread {thread_id}: {e}")

# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/{thread_id}/runs/stream")
async def stream_run(
    thread_id: str,
    body: RunCreateRequest,
    request: Request,
    x_family_id: str = Header(..., alias="X-Family-Id"),
    x_user_id: str = Header(None, alias="X-User-Id")
) -> StreamingResponse:
    """Create a run and stream events via SSE.
    
    This replaces the complex background task and RunManager from DeerFlow,
    but yields the same LangGraph SSE format expected by the frontend's useStream hook.
    """
    try:
        client = BackendClient(family_id=x_family_id)
        ai_config = await client.get_family_ai_config()
    except Exception as e:
        logger.error("[runs] fetch ai_config failed family=%s: %s", x_family_id, e)
        raise HTTPException(status_code=500, detail="Failed to fetch AI config")

    # In LangGraph SDK, input is typically {"messages": [{"role": "user", "content": "..."}]}
    user_message = ""
    if body.input and "messages" in body.input:
        messages = body.input["messages"]
        if isinstance(messages, list) and messages:
            last_msg = messages[-1]
            if isinstance(last_msg, dict) and last_msg.get("role") in ("user", "human"):
                user_message = last_msg.get("content", "")

    context = FamilyContext(family_id=x_family_id, free_text=user_message)
    redacted_context = pii_redactor.redact(context)

    # In chat, capability is effectively 'chat'.
    # For Numina wrapper, we map 'assistant_id' to capability or just use 'chat'.
    capability = "chat"
    if body.assistant_id and body.assistant_id != "lead_agent":
        capability = body.assistant_id

    adapter = create_family_adapter(
        x_family_id, 
        ai_config, 
        timeout_seconds=240,
        subagent_enabled=True,
        plan_mode=False
    )
    
    run_id = str(uuid.uuid4())

    async def _sse_generator():
        try:
            async for event in adapter.raw_stream_dispatch(
                skill_name=capability,
                context=redacted_context,
                thread_id=thread_id,
                enable_thinking=True
            ):
                if hasattr(event, "type") and hasattr(event, "data"):
                    yield format_sse(event.type, event.data)
        except Exception as e:
            logger.error("[runs] Stream failed: %s", e)
            # Send an error event in LangGraph format
            yield format_sse("error", {"error": str(e)})
        finally:
            # Fire background task for title generation
            asyncio.create_task(_generate_and_save_title(thread_id, x_family_id, user_message, ai_config))
            
            # Yield end sentinel
            yield format_sse("end", None)

    return StreamingResponse(
        _sse_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            "Content-Location": f"/api/threads/{thread_id}/runs/{run_id}",
        },
    )

@router.get("/{thread_id}/messages")
async def list_thread_messages(
    thread_id: str,
    request: Request,
    x_family_id: str = Header(..., alias="X-Family-Id")
) -> list[dict]:
    """Return displayable messages for a thread."""
    from apps.agent.services.deerflow_adapter.family_adapter_cache import _get_shared_checkpointer
    checkpointer = _get_shared_checkpointer(None)
    
    config = {"configurable": {"thread_id": thread_id, "checkpoint_ns": ""}}
    checkpoint_tuple = await checkpointer.aget_tuple(config)

    if checkpoint_tuple is None:
        return []

    checkpoint = getattr(checkpoint_tuple, "checkpoint", {}) or {}
    channel_values = checkpoint.get("channel_values", {})
    messages = channel_values.get("messages", [])

    result = []
    from langchain_core.messages import BaseMessage
    for idx, msg in enumerate(messages):
        if isinstance(msg, BaseMessage):
            # Try to format as standard DeerFlow UI message
            evt_type = "human_message" if msg.type in ("human", "user") else "ai_message" if msg.type == "ai" else "tool_message"
            result.append({
                "id": msg.id or str(idx),
                "run_id": "latest",
                "event_type": evt_type,
                "content": msg.content,
                "additional_kwargs": msg.additional_kwargs,
            })
    return result

