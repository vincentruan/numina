"""Post-stream extras: follow-up suggestions and thread title sync.

Extracted from the legacy ``routers/runs.py`` so the v2 ``runs_stream`` worker
can reuse them without duplicating the LLM calls. Both are best-effort and
swallow their own errors - a failure here must never break the stream.

# Title generation note (2026-07-08):
# DeerFlow's ``TitleMiddleware`` defines BOTH ``after_model`` (sync) and
# ``aafter_model`` (async). The async hook makes an LLM call to summarise the
# conversation; the sync hook only returns a local fallback (truncated user
# message). Numina's adapter runs the agent via the SYNC ``DeerFlowClient.stream()``
# (in a thread executor), so LangGraph dispatches the sync ``after_model`` and
# the LLM title is NEVER generated - the checkpoint title is always the raw
# ``[SKILL:chat]`` prompt wrapper. ``sync_title_from_checkpoint`` bridges that
# gap by generating a proper LLM title when the checkpoint title is a fallback.
"""

from __future__ import annotations

import json
import logging
from typing import Any

logger = logging.getLogger(__name__)

# Titles that start with this were produced by the sync ``after_model`` fallback
# using the raw ``[SKILL:chat]`` prompt wrapper - they are NOT real summaries and
# must be replaced by a proper LLM-generated title.
_SKILL_PROMPT_PREFIX = "[SKILL:"
_FALLBACK_TITLE_MAX_CHARS = 50


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
            extra_body={"enable_thinking": False},
        )

        system = SystemMessage(content=(
            "You are a helpful assistant that suggests 3 concise follow-up questions "
            "the user might ask next, based on the AI's response. "
            "Respond with a JSON array of exactly 3 short strings (each under 15 words). "
            "No explanation, no markdown - only the JSON array."
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


def _is_fallback_title(title: str | None) -> bool:
    """Return True if the title is empty, the default placeholder, or a raw ``[SKILL:`` wrapper."""
    if not title or not str(title).strip():
        return True
    t = str(title).strip()
    return t == "New Chat" or t.startswith(_SKILL_PROMPT_PREFIX)


def _text_fallback_title(text: str) -> str:
    """Truncate the user's message into a display-safe fallback title."""
    text = (text or "").strip()
    if not text:
        return ""
    if len(text) > _FALLBACK_TITLE_MAX_CHARS:
        return text[:_FALLBACK_TITLE_MAX_CHARS].rstrip() + "..."
    return text


def _parse_title_content(content: Any) -> str:
    """Normalise raw LLM output into a clean title string."""
    text = content if isinstance(content, str) else str(content)
    title = text.strip().strip('`"\'').strip()
    if title.startswith("```"):
        title = title.split("\n", 1)[-1] if "\n" in title else title[3:]
        if title.endswith("```"):
            title = title[:-3]
        title = title.strip()
    return title


def _create_title_llm(provider: str, model: str, api_key: str, base_url: str | None):
    """Build a lightweight chat model for title generation, honouring the provider type.

    ``generate_suggestions`` always uses ``ChatOpenAI``; that works for
    OpenAI-compatible gateways but silently 401s on native Anthropic. The title
    path avoids that by dispatching to ``ChatAnthropic`` when ``ai_provider``
    is ``"anthropic"``.
    """
    if provider == "anthropic":
        try:
            from langchain_anthropic import ChatAnthropic

            kwargs: dict[str, Any] = {
                "model": model,
                "api_key": api_key,
                "temperature": 0.3,
                "max_tokens": 60,
            }
            if base_url:
                kwargs["base_url"] = base_url
            return ChatAnthropic(**kwargs)
        except ImportError:
            logger.debug("[run_extras] langchain_anthropic not installed; falling back to ChatOpenAI")
    from langchain_openai import ChatOpenAI

    kwargs = {
        "model": model,
        "api_key": api_key,
        "temperature": 0.3,
        "max_tokens": 60,
        # Qwen3 (and similar reasoning models) consume the entire token budget
        # on reasoning tokens, leaving content empty. Disable thinking for this
        # lightweight call - the title doesn't need chain-of-thought.
        "extra_body": {"enable_thinking": False},
    }
    if base_url:
        kwargs["base_url"] = base_url
    return ChatOpenAI(**kwargs)


async def _generate_title_via_llm(
    user_message: str,
    ai_response: str,
    ai_config: dict[str, Any],
) -> str | None:
    """Generate a concise conversation title via the family's AI provider.

    Mirrors the ``generate_suggestions`` LLM-call pattern (single ``ainvoke``,
    best-effort) but uses a tighter prompt and lower ``max_tokens``. Returns
    ``None`` on any failure so the caller can fall back to the user message.
    """
    if not user_message or len(user_message.strip()) < 2:
        return None
    try:
        from langchain_core.messages import HumanMessage, SystemMessage

        model_name = ai_config.get("ai_model_id") or "gpt-4o-mini"
        api_key = ai_config.get("api_key") or "dummy"
        base_url = ai_config.get("ai_base_url")
        provider = (ai_config.get("ai_provider") or "openai").lower()

        llm = _create_title_llm(provider, model_name, api_key, base_url)

        system = SystemMessage(content=(
            "Generate a concise title (max 6 words, in the user's language) for this conversation. "
            "Return ONLY the title, no quotes, no explanation."
        ))
        human = HumanMessage(content=(
            f"User: {user_message[:300]}\n\n"
            f"Assistant: {ai_response[:300]}\n\n"
            "Title:"
        ))

        response = await llm.ainvoke([system, human])
        title = _parse_title_content(response.content)
        return title[:60] if title else None
    except Exception as e:
        logger.warning("[run_extras] LLM title generation failed: %s", e)
        return None


async def _read_checkpoint_title(thread_id: str) -> str | None:
    """Read ``channel_values["title"]`` from the latest checkpoint (best-effort)."""
    try:
        from apps.agent.services.deerflow_adapter.family_adapter_cache import (
            _get_shared_checkpointer,
        )

        checkpointer = _get_shared_checkpointer(None)
        config = {"configurable": {"thread_id": thread_id, "checkpoint_ns": ""}}
        checkpoint_tuple = await checkpointer.aget_tuple(config)
        if checkpoint_tuple is None:
            return None
        checkpoint = getattr(checkpoint_tuple, "checkpoint", {}) or {}
        return (checkpoint.get("channel_values", {}) or {}).get("title")
    except Exception:
        return None


async def sync_title_from_checkpoint(
    thread_id: str,
    family_id: str,
    ai_config: dict[str, Any] | None = None,
    user_message: str = "",
    ai_response: str = "",
) -> None:
    """Persist a proper conversation title into the ``ai_chat_sessions`` row.

    DeerFlow's ``TitleMiddleware`` writes to the checkpoint's
    ``channel_values["title"]``. When the agent runs via the async path
    (``astream``) that title is an LLM-generated summary; but Numina's adapter
    uses the sync ``stream()`` path, so the sync ``after_model`` hook runs and
    only writes a local fallback (the raw ``[SKILL:chat]`` prompt wrapper). This
    function bridges that gap:

    1. If the session row already has a proper (non-fallback) title, keep it
       (the user may have renamed the thread).
    2. If the checkpoint has a proper title (async middleware path), use it.
    3. Otherwise generate a title via the family's AI provider (the sync stream
       path only produced a fallback).
    4. If the LLM call fails, fall back to a truncated form of the user message.

    Best-effort: any failure is logged and swallowed. Only writes when the
    session is still untitled or the existing title is a recognisable fallback.
    """
    try:
        from apps.agent.services.session_store import AiSessionRepository

        repo = AiSessionRepository(family_id)

        # 1. Skip if the DB row already has a proper title (user rename or prior gen).
        session = await repo.get_session(thread_id)
        db_title = session.get("title") if session else None
        if db_title and not _is_fallback_title(db_title):
            return

        # 2. Prefer a proper title from the checkpoint (async middleware path).
        ckpt_title = await _read_checkpoint_title(thread_id)
        if ckpt_title and not _is_fallback_title(ckpt_title):
            await repo.update_summary(
                session_id=thread_id,
                family_id=family_id,
                summary=None,
                title=str(ckpt_title).strip(),
            )
            logger.info("[run_extras] Synced title '%s' for thread %s", ckpt_title, thread_id)
            return

        # 3. The sync stream() path only wrote a fallback - generate a real title.
        title: str | None = None
        if ai_config and user_message:
            title = await _generate_title_via_llm(user_message, ai_response, ai_config)

        # 4. Final fallback: truncated user message (NOT the raw [SKILL:chat] wrapper).
        if not title:
            title = _text_fallback_title(user_message)

        if title:
            await repo.update_summary(
                session_id=thread_id,
                family_id=family_id,
                summary=None,
                title=title,
            )
            logger.info("[run_extras] Generated title '%s' for thread %s", title, thread_id)
    except Exception as e:
        logger.warning("[run_extras] Failed to sync title for thread %s: %s", thread_id, e)
