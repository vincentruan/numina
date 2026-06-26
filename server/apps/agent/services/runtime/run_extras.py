"""Post-stream extras: follow-up suggestions and thread title generation.

Extracted from the legacy ``routers/runs.py`` so the v2 ``runs_stream`` worker
can reuse them without duplicating the LLM calls. Both are best-effort and
swallow their own errors — a failure here must never break the stream.

# [Extracted from routers/runs.py] — preserved verbatim, only relocated.
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
        base_url = ai_config.get("base_url")

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


async def generate_and_save_title(thread_id: str, family_id: str, user_message: str, ai_config: dict[str, Any]) -> None:
    """Generate a short title for the thread in the background."""
    if not user_message:
        return

    try:
        from langchain_core.messages import HumanMessage, SystemMessage
        from langchain_openai import ChatOpenAI

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
            from apps.agent.services.session_store import AiSessionRepository

            repo = AiSessionRepository(family_id)
            # Only update if the session exists
            session = await repo.get_session(thread_id)
            if session and (not session.get("title") or session.get("title") == "New Chat"):
                await repo.update_summary(session_id=thread_id, family_id=family_id, summary=None, title=title)
                logger.info("[run_extras] Generated title '%s' for thread %s", title, thread_id)
    except Exception as e:
        logger.error("[run_extras] Failed to generate title for thread %s: %s", thread_id, e)
