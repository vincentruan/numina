"""Post-stream extras: follow-up suggestions and thread title sync.

Extracted from the legacy ``routers/runs.py`` so the v2 ``runs_stream`` worker
can reuse them without duplicating the LLM calls. Both are best-effort and
swallow their own errors — a failure here must never break the stream.

# [Extracted from routers/runs.py] — suggestions preserved verbatim; title
# now synced from the DeerFlow TitleMiddleware checkpoint instead of a
# separate LLM call.
"""

from __future__ import annotations

import json
import logging
from typing import Any

logger = logging.getLogger(__name__)


async def generate_suggestions(ai_response: str, user_message: str, ai_config: dict[str, Any]) -> list[str]:
    """Generate 3 follow-up question suggestions based on the conversation."""
    if not ai_response or len(ai_response.strip()) < 20:
        return []

    try:
        from langchain_core.messages import HumanMessage, SystemMessage
        from langchain_openai import ChatOpenAI

        model = ai_config.get("ai_model_id") or "gpt-4o-mini"
        api_key = ai_config.get("api_key") or "dummy"
        base_url = ai_config.get("ai_base_url")

        llm = ChatOpenAI(
            model=model,
            api_key=api_key,
            base_url=base_url,
            temperature=0.7,
            max_tokens=200,
        )

        system = SystemMessage(content=(
            "You are a helpful assistant that suggests 3 concise follow-up questions "
            "the user might ask next, based on the AI's response. "
            "Respond with a JSON array of exactly 3 short strings (each under 15 words). "
            "No explanation, no markdown — only the JSON array."
        ))
        human = HumanMessage(content=(
            f"User asked: {user_message}\n\n"
            f"AI responded: {ai_response[:500]}\n\n"
            "Suggest 3 follow-up questions as a JSON array."
        ))

        response = await llm.ainvoke([system, human])
        content = response.content.strip()
        # Strip markdown code fences if present
        if content.startswith("```"):
            content = content.split("\n", 1)[-1] if "\n" in content else content[3:]
            if content.endswith("```"):
                content = content[:-3]
            content = content.strip()
        suggestions = json.loads(content)
        if isinstance(suggestions, list):
            return [str(s) for s in suggestions[:3]]
    except Exception as e:
        logger.warning("[run_extras] Failed to generate suggestions: %s", e)
    return []


async def sync_title_from_checkpoint(thread_id: str, family_id: str) -> None:
    """Sync the thread title from the LangGraph checkpoint into the session row.

    DeerFlow's ``TitleMiddleware`` (already active in the chat path via
    ``_build_middlewares``) generates a title during the stream and writes it
    to the checkpoint's ``channel_values["title"]``. The frontend, however,
    reads the title from the persistent ``ai_chat_sessions`` record (via
    ``getThread`` → ``get_thread``). This bridges that gap by reading the
    checkpoint title and persisting it — reusing the DeerFlow-generated title
    instead of making a second LLM call.

    Best-effort: any failure is logged and swallowed. Only writes when the
    session exists and is still untitled (``None`` or ``"New Chat"``), so a
    user-renamed title is never clobbered.
    """
    try:
        from apps.agent.services.deerflow_adapter.family_adapter_cache import (
            _get_shared_checkpointer,
        )
        from apps.agent.services.session_store import AiSessionRepository

        checkpointer = _get_shared_checkpointer(None)
        config = {"configurable": {"thread_id": thread_id, "checkpoint_ns": ""}}
        checkpoint_tuple = await checkpointer.aget_tuple(config)
        if checkpoint_tuple is None:
            return

        checkpoint = getattr(checkpoint_tuple, "checkpoint", {}) or {}
        title = (checkpoint.get("channel_values", {}) or {}).get("title")
        if not title or not str(title).strip():
            return

        repo = AiSessionRepository(family_id)
        session = await repo.get_session(thread_id)
        # Only set the title on a freshly-created, still-untitled session —
        # never overwrite a title the user has already renamed.
        if session and (not session.get("title") or session.get("title") == "New Chat"):
            await repo.update_summary(
                session_id=thread_id,
                family_id=family_id,
                summary=None,
                title=str(title).strip(),
            )
            logger.info("[run_extras] Synced title '%s' for thread %s", title, thread_id)
    except Exception as e:
        logger.warning("[run_extras] Failed to sync title for thread %s: %s", thread_id, e)
