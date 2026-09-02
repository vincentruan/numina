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
# must be replaced by a proper LLM-generated title. (Legacy checkpoints only;
# the [SKILL:] prefix was removed, but old titles persist in the checkpointer DB.)
_SKILL_PROMPT_PREFIX = "[SKILL:"

# Title generation limits. Mirrors DeerFlow ``TitleConfig`` defaults.
_TITLE_MAX_WORDS = 6
_TITLE_MAX_CHARS = 60


# Language-instruction prefixes used by the frontend (useThreadChat.ts) and
# backend runners. Stripped from user-visible outputs (titles, suggestions)
# so the internal language directive doesn't leak into the UI.
_LANGUAGE_PREFIXES: tuple[str, ...] = (
    "[LANGUAGE REQUIREMENT] Output language: English.",
    "[语言要求] 输出语言：中文。",
)


def strip_language_prefix(text: str) -> str:
    """Remove a leading language-instruction prefix from *text*.

    The frontend prepends ``[LANGUAGE REQUIREMENT]...`` / ``[语言要求]...`` to
    every user message so the LLM responds in the correct language. That prefix
    must stay in the prompt sent to the LLM but must **not** appear in
    user-facing outputs like the session title or follow-up suggestions.
    """
    for prefix in _LANGUAGE_PREFIXES:
        if text.startswith(prefix):
            remainder = text[len(prefix):]
            # Consume leading newlines / whitespace that may follow the prefix.
            return remainder.lstrip("\n").lstrip()
    return text


def _strip_thinking_from_text(text: str) -> str:
    """Remove ``<think>...</think>`` blocks from text (reasoning model output)."""
    import re
    # Standard <think>...</think> blocks
    text = re.sub(r"<think>[\s\S]*?</think>", "", text, flags=re.IGNORECASE).strip()
    # Collapse blank lines left by removal
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _extract_text_from_content_blocks(content: Any) -> str:
    """Extract only text portions from structured LLM output.

    Models with thinking (Claude extended thinking, Qwen3, etc.) may return
    ``response.content`` as a list of dicts:
    ``[{"type": "thinking", "thinking": "..."}, {"type": "text", "text": "..."}]``.

    When ``str()`` is called on such a list, the result is a Python repr like
    ``[{'signature': '', 'thinking': '...'}]`` which is NOT valid JSON.

    Returns the concatenated text from ``text``/``content`` blocks only.
    Falls back to ``str(content)`` for plain strings.
    """
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, dict):
                block_type = block.get("type", "")
                if block_type == "thinking":
                    continue  # skip thinking blocks entirely
                text_val = block.get("text") or block.get("content")
                if isinstance(text_val, str) and text_val.strip():
                    parts.append(text_val.strip())
        return " ".join(parts) if parts else str(content)
    return str(content)


async def generate_suggestions(ai_response: str, user_message: str, ai_config: dict[str, Any]) -> list[str]:
    """Generate 3 follow-up question suggestions based on the conversation.

    Includes validate→retry cycle: if the LLM returns malformed JSON or
    invalid suggestions, retries up to 2 times with error feedback.
    """
    if not ai_response or len(ai_response.strip()) < 20:
        return []

    from apps.agent.services.runtime.llm_json_repair import validate_suggestions

    # Strip thinking blocks from the AI response so the suggestion LLM
    # doesn't get confused by internal reasoning content.
    cleaned_response = _strip_thinking_from_text(ai_response)
    if len(cleaned_response.strip()) < 20:
        return []

    max_attempts = 3
    failure_reasons: list[str] = []

    for attempt in range(max_attempts):
        try:
            llm = _create_lightweight_llm(ai_config, temperature=0.7, max_tokens=200)
            from langchain_core.messages import HumanMessage, SystemMessage

            # Build feedback-aware prompt
            feedback_hint = ""
            if failure_reasons:
                feedback_hint = (
                    f"\n\nPrevious attempt failed: {'; '.join(failure_reasons[:2])}. "
                    "Please ensure the output is a valid JSON array of 3 short strings."
                )

            system = SystemMessage(content=(
                "You are a helpful assistant that suggests 3 concise follow-up questions "
                "the user might ask next, based on the AI's response. "
                "Respond with a JSON array of exactly 3 short strings (each under 15 words). "
                "No explanation, no markdown - only the JSON array."
                f"{feedback_hint}"
            ))
            human = HumanMessage(content=(
                f"User asked: {user_message}\n\n"
                f"AI responded: {cleaned_response[:500]}\n\n"
                "Suggest 3 follow-up questions as a JSON array."
            ))

            response = await llm.ainvoke([system, human])
            # Handle structured output (list of dicts with thinking blocks)
            raw_content = _extract_text_from_content_blocks(response.content)
            content = raw_content.strip()
            # Strip markdown code fences if present
            if content.startswith("```"):
                content = content.split("\n", 1)[-1] if "\n" in content else content[3:]
                if content.endswith("```"):
                    content = content[:-3]
                content = content.strip()

            # Use json_repair for tolerant parsing
            from json_repair import repair_json

            parsed = repair_json(content, return_objects=True)
            suggestions = parsed if isinstance(parsed, list) else None
            if suggestions is None and isinstance(parsed, dict) and "suggestions" in parsed:
                suggestions = parsed["suggestions"]

            if suggestions is None:
                failure_reasons.append("无法解析为 JSON 数组")
                continue

            # Validate
            errors = validate_suggestions(suggestions)
            if not errors:
                return [str(s) for s in suggestions[:3]]
            failure_reasons.extend(errors[:2])
        except Exception as e:
            failure_reasons.append(f"LLM 调用失败: {type(e).__name__}")
            logger.warning("[run_extras] Failed to generate suggestions (attempt %d): %s", attempt + 1, e)

    logger.warning("[run_extras] Suggestions failed after %d attempts: %s", max_attempts, failure_reasons[:3])
    return []


def _is_fallback_title(title: str | None) -> bool:
    """Return True if the title is empty, the placeholder, or a raw prompt wrapper.

    A "raw prompt wrapper" is the context JSON the adapter sends as the user
    message (``_build_prompt`` output) — either the legacy ``[SKILL:chat]``-prefixed
    form or the current bare-JSON form (``{"free_text": ..., "family_id": ...}``).
    These are NOT real summaries and must be replaced by an LLM-generated title.

    Also detects Python list-literal repr of structured LLM output (thinking
    blocks): ``[{'signature': '', 'thinking': '...'}]``. This leaks when the
    model returns content as a list of dicts and ``str()`` is called on it.
    """
    if not title or not str(title).strip():
        return True
    t = str(title).strip()
    if t == "New Chat" or t.startswith(_SKILL_PROMPT_PREFIX):
        return True
    # Python list-literal repr of structured model output (thinking blocks).
    # e.g. ``[{'signature': '', 'thinking': '用户希望为一段对话生成一个简洁的标题...'}]``
    # This is NOT a real summary — it's the raw repr of a list[dict] response.content.
    if t.startswith("[{") and ("thinking" in t or "signature" in t or "type" in t):
        return True
    # Bare-JSON context wrapper (current _build_prompt output). Detect by parsing;
    # a real summary is never a JSON object of context fields.
    if t.startswith("{"):
        # Substring check first: the TitleMiddleware / DB column may truncate
        # the raw context JSON mid-string (e.g. ``{"family_id": "...", "free_tex``),
        # which makes json.loads fail with UnterminatedString. Such a truncated
        # blob still leaking ``family_id``/``free_text`` keys is unambiguously a
        # fallback wrapper, not a real summary — detect it without full parse.
        if '"family_id"' in t or '"free_text"' in t:
            return True
        try:
            parsed = json.loads(t)
        except json.JSONDecodeError:
            return False
        if isinstance(parsed, dict) and any(k in parsed for k in ("free_text", "family_id")):
            return True
    return False


def _message_type(message: object) -> str | None:
    """Normalize a checkpoint message to a canonical role.

    Mirrors ``TitleMiddleware._message_type`` so title-gating logic stays
    consistent with DeerFlow. Accepts both LangChain message objects and the
    dict form stored in checkpoints.
    """
    message_type = getattr(message, "type", None)
    if message_type is None and isinstance(message, dict):
        message_type = message.get("type") or message.get("role")
    if message_type == "user":
        return "human"
    if message_type == "assistant":
        return "ai"
    return message_type if isinstance(message_type, str) else None


def _message_content(message: object) -> object:
    """Return the content payload of a checkpoint message."""
    if isinstance(message, dict):
        return message.get("content", "")
    return getattr(message, "content", "")


def _is_user_message_for_title(message: object) -> bool:
    """Return True for real human messages (excluding hidden system reminders)."""
    if _message_type(message) != "human":
        return False
    # ``dynamic_context_reminder`` (a hidden MemoryMiddleware context reminder)
    # is NOT a real user turn and must not count toward the first-exchange gate.
    # The checkpointer stores LangChain ``HumanMessage`` OBJECTS whose
    # ``additional_kwargs`` carries this flag; the old code only inspected the
    # dict form, so for objects the reminder was counted as a second user
    # message → ``len(user_messages)==2`` → ``_should_generate_title`` returned
    # ``False`` → ``sync_title_from_checkpoint`` returned ``None`` → no session
    # title was ever generated. Mirror DeerFlow's ``_is_dynamic_context_reminder_message``
    # by inspecting ``additional_kwargs`` for BOTH object and dict forms.
    if isinstance(message, dict):
        additional_kwargs = message.get("additional_kwargs") or {}
    else:
        additional_kwargs = getattr(message, "additional_kwargs", None) or {}
    return not (
        isinstance(additional_kwargs, dict)
        and bool(additional_kwargs.get("dynamic_context_reminder"))
    )


def _should_generate_title(
    channel_values: dict[str, Any] | None,
    *,
    allow_partial_exchange: bool = False,
) -> bool:
    """DeerFlow-style gate: title is generated once, after the first exchange.

    Mirrors ``TitleMiddleware._should_generate_title``:
    - Skip if the checkpoint already carries a real title.
    - Skip if we are past the first complete exchange (>1 real user messages).
    - Generate when there is exactly one real user message plus at least one
      assistant response.
    - For interrupted first turns, ``allow_partial_exchange=True`` accepts a
      lone user message so the thread still gets a sidebar title.
    """
    if not channel_values:
        return False

    # If the checkpoint already has a proper title, never overwrite it.
    existing_title = channel_values.get("title")
    if existing_title and not _is_fallback_title(existing_title):
        return False

    messages = channel_values.get("messages") or []
    if not isinstance(messages, list):
        return False

    min_messages = 1 if allow_partial_exchange else 2
    if len(messages) < min_messages:
        return False

    user_messages = [m for m in messages if _is_user_message_for_title(m)]
    assistant_messages = [m for m in messages if _message_type(m) == "ai"]

    # Normal path: title only after first complete exchange. Interrupted path
    # accepts a lone first-turn user message.
    return len(user_messages) == 1 and (len(assistant_messages) >= 1 or allow_partial_exchange)


def _normalize_content(content: object) -> str:
    """Normalize message content into plain text (lists/dicts/strings)."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = [_normalize_content(item) for item in content]
        return "\n".join(part for part in parts if part)
    if isinstance(content, dict):
        text_value = content.get("text")
        if isinstance(text_value, str):
            return text_value
        nested_content = content.get("content")
        if nested_content is not None:
            return _normalize_content(nested_content)
    return ""


def _text_fallback_title(text: str, max_chars: int = _TITLE_MAX_CHARS) -> str:
    """Return a display-safe fallback title, mirroring DeerFlow's local path.

    DeerFlow returns the user message truncated to ``max_chars`` (reserving room
    for the ellipsis). When the input is empty, returns ``"New Chat"`` so the
    sidebar never shows a blank title.
    """
    text = (text or "").strip()
    if not text:
        return "New Chat"
    fallback_chars = min(max_chars, 50)
    if len(text) > fallback_chars:
        ellipsis = "..."
        body = min(fallback_chars, max_chars - len(ellipsis))
        return text[:body].rstrip() + ellipsis
    return text


def _parse_title_content(content: Any) -> str:
    """Normalise raw LLM output into a clean title string.

    Handles three forms:
    - Plain string (most models).
    - List of content-block dicts (Anthropic Claude, some OpenAI-compatible
      models with thinking): extract only ``text`` blocks, skip ``thinking``.
    - Fallback ``str()`` for anything else.
    """
    if isinstance(content, list):
        # Structured output: list of content-block dicts (e.g. from Claude
        # with extended thinking, or Qwen3 with thinking blocks).
        # Extract only the text portions — thinking blocks are NOT titles.
        parts: list[str] = []
        for block in content:
            if isinstance(block, dict):
                block_type = block.get("type", "")
                if block_type == "thinking":
                    continue  # skip thinking blocks entirely (mirrors
                              # _extract_text_from_content_blocks, line 92)
                # Standard content block: {"type": "text", "text": "..."}
                text_val = block.get("text")
                if isinstance(text_val, str) and text_val.strip():
                    parts.append(text_val.strip())
                # Fallback for blocks that use "content" key instead of "text"
                # (some provider quirks). Thinking blocks already skipped above.
                elif not text_val:
                    content_val = block.get("content")
                    if isinstance(content_val, str) and content_val.strip():
                        parts.append(content_val.strip())
        title = " ".join(parts).strip().strip('`"\'').strip()
    else:
        text = content if isinstance(content, str) else str(content)
        title = text.strip().strip('`"\'').strip()
    if title.startswith("```"):
        title = title.split("\n", 1)[-1] if "\n" in title else title[3:]
        if title.endswith("```"):
            title = title[:-3]
        title = title.strip()
    return title


def _create_lightweight_llm(
    ai_config: dict[str, Any],
    *,
    temperature: float = 0.3,
    max_tokens: int = 60,
    timeout: int = 30,
):
    """Build a lightweight chat model for short LLM calls (titles, suggestions).

    Shared by ``generate_suggestions`` and ``_generate_title_via_llm`` so both
    honour the family's ``ai_provider`` (Anthropic vs OpenAI-compatible) and
    the ``enable_thinking: False`` flag for reasoning models. Uses
    ``ai_base_url`` with a ``base_url`` fallback for OpenAI-compatible gateways.
    """
    provider = (ai_config.get("ai_provider") or "openai").lower()
    model = ai_config.get("ai_model_id") or "gpt-4o-mini"
    api_key = ai_config.get("api_key") or "dummy"
    base_url = ai_config.get("ai_base_url") or ai_config.get("base_url")

    if provider == "anthropic":
        try:
            from langchain_anthropic import ChatAnthropic

            kwargs: dict[str, Any] = {
                "model": model,
                "api_key": api_key,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "timeout": timeout,
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
        "temperature": temperature,
        "max_tokens": max_tokens,
        "timeout": timeout,
        # Qwen3 (and similar reasoning models) consume the entire token budget
        # on reasoning tokens, leaving content empty. Disable thinking for this
        # lightweight call - the title doesn't need chain-of-thought.
        "extra_body": {"enable_thinking": False},
    }
    if base_url:
        kwargs["base_url"] = base_url
    return ChatOpenAI(**kwargs)


def _build_title_prompt(
    user_message: str, ai_response: str, target_language: str = "English"
) -> tuple[str, str]:
    """Build the LLM title prompt and return the trimmed user message.

    Mirrors DeerFlow's default ``TitleConfig.prompt_template`` and strips
    ``<think>...</think>`` blocks from the assistant response before including
    it in the prompt.

    ``target_language`` controls the output language of the generated title so
    that a Chinese user message with an English locale still produces an
    English title (LLM handles the cross-language generation natively).
    """
    user_msg = user_message.strip()[:500]
    assistant_msg = _strip_thinking_from_text(ai_response)[:500]
    prompt = (
        f"Generate a concise title (max {_TITLE_MAX_WORDS} words) for this conversation.\n"
        f"The title MUST be written in {target_language}.\n"
        f"User: {user_msg}\n"
        f"Assistant: {assistant_msg}\n\n"
        "Return ONLY the title, no quotes, no explanation."
    )
    return prompt, user_msg


async def _generate_title_via_llm(
    user_message: str,
    ai_response: str,
    ai_config: dict[str, Any],
    target_language: str = "English",
) -> str | None:
    """Generate a concise conversation title via the family's AI provider.

    Mirrors the ``generate_suggestions`` LLM-call pattern (single ``ainvoke``,
    best-effort) but uses a tighter prompt and lower ``max_tokens``. Returns
    ``None`` on any failure so the caller can fall back to the user message.
    """
    if not user_message or len(user_message.strip()) < 2:
        return None
    try:
        from langchain_core.messages import SystemMessage

        llm = _create_lightweight_llm(ai_config, temperature=0.3, max_tokens=60)
        prompt, _ = _build_title_prompt(user_message, ai_response, target_language)

        system = SystemMessage(content=prompt)
        response = await llm.ainvoke([system])
        title = _parse_title_content(response.content)
        return title[:_TITLE_MAX_CHARS] if title else None
    except Exception as e:
        logger.warning("[run_extras] LLM title generation failed: %s", e)
        return None


async def _read_checkpoint(thread_id: str) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    """Read the latest checkpoint tuple and its channel_values for a thread."""
    try:
        from apps.agent.services.deerflow_adapter.family_adapter_cache import (
            _get_shared_checkpointer,
        )

        checkpointer = _get_shared_checkpointer(None)
        config = {"configurable": {"thread_id": thread_id, "checkpoint_ns": ""}}
        checkpoint_tuple = await checkpointer.aget_tuple(config)
        if checkpoint_tuple is None:
            return None, None
        checkpoint = getattr(checkpoint_tuple, "checkpoint", {}) or {}
        channel_values = checkpoint.get("channel_values") or {}
        return checkpoint, channel_values
    except Exception:
        return None, None


async def sync_title_from_checkpoint(
    thread_id: str,
    family_id: str,
    ai_config: dict[str, Any] | None = None,
    user_message: str = "",
    ai_response: str = "",
    *,
    allow_partial_exchange: bool = False,
    target_language: str = "English",
) -> str | None:
    """Persist a proper conversation title into the ``ai_chat_sessions`` row.

    DeerFlow's ``TitleMiddleware`` writes to the checkpoint's
    ``channel_values["title"]``. When the agent runs via the async path
    (``astream``) that title is an LLM-generated summary; but Numina's adapter
    uses the sync ``stream()`` path, so the sync ``after_model`` hook runs and
    only writes a local fallback (the raw prompt wrapper JSON). This function
    bridges that gap.

    **Design (v2 — simplified):** For new sessions the worker already carries
    ``user_message`` and ``ai_response`` directly, so we generate the title
    from those without depending on the checkpointer. The checkpoint is only
    consulted as a fallback source for the user message (e.g. when the worker
    didn't receive one) and to detect an existing proper title that should be
    preserved. This eliminates the class of bugs where a checkpointer read
    failure or unexpected checkpoint state silently prevents title generation.

    Returns the newly persisted title string so the worker can publish it to the
    frontend, or ``None`` when no new title was written.
    """
    try:
        from apps.agent.services.session_store import AiSessionRepository

        repo = AiSessionRepository(family_id)

        # 1. Skip if the DB row already has a proper title (user rename or prior gen).
        session = await repo.get_session(thread_id)
        db_title = session.get("title") if session else None
        logger.info(
            "[run_extras][title] step1: thread=%s session_exists=%s db_title=%r is_fallback=%s",
            thread_id,
            session is not None,
            db_title,
            _is_fallback_title(db_title) if db_title else None,
        )
        if db_title and not _is_fallback_title(db_title):
            logger.info("[run_extras][title] step1 SKIP: DB already has proper title")
            return None

        # 2. Attempt to read the checkpoint — used ONLY to detect an existing
        #    proper title that should be preserved (not to gate generation).
        #    Checkpoint failures are non-fatal: we still generate a title from
        #    the user message.
        _, channel_values = await _read_checkpoint(thread_id)
        ckpt_title = None
        if channel_values:
            ckpt_title = channel_values.get("title")
            # If the checkpoint already carries a proper (non-fallback) title
            # from the async middleware path, persist it and return.
            if ckpt_title and not _is_fallback_title(ckpt_title):
                title = str(ckpt_title).strip()
                await repo.update_summary(
                    session_id=thread_id,
                    family_id=family_id,
                    summary=None,
                    title=title,
                )
                logger.info("[run_extras] Synced title '%s' for thread %s", title, thread_id)
                return title
            # Gate: only generate a title on the first exchange. If the
            # checkpoint has real messages AND the gate says no, respect it —
            # unless the DB/checkpoint carries a fallback that needs replacing.
            ckpt_messages = channel_values.get("messages") or []
            if len(ckpt_messages) >= 1:
                gate_allows = _should_generate_title(
                    channel_values, allow_partial_exchange=allow_partial_exchange,
                )
                db_has_fallback = db_title and _is_fallback_title(db_title)
                ckpt_has_fallback = ckpt_title and _is_fallback_title(ckpt_title)
                if not gate_allows and not db_has_fallback and not ckpt_has_fallback:
                    logger.info(
                        "[run_extras][title] gate SKIP: thread=%s gate=%s db_fb=%s ckpt_fb=%s",
                        thread_id, gate_allows, db_has_fallback, ckpt_has_fallback,
                    )
                    return None

        # 3. Generate title via LLM from the worker's user_message + ai_response.
        #    This is the PRIMARY path for new sessions — does NOT depend on the
        #    checkpointer returning useful data.
        generated_title: str | None = None
        if ai_config and user_message:
            logger.info(
                "[run_extras][title] step3 LLM: thread=%s user_msg=%r ai_resp_len=%d lang=%s",
                thread_id, user_message[:60], len(ai_response), target_language,
            )
            generated_title = await _generate_title_via_llm(
                user_message, ai_response, ai_config, target_language,
            )
            logger.info("[run_extras][title] step3 LLM result: %r", generated_title)

        # 4. Final fallback: truncated user message. Even ``_text_fallback_title("")``
        #    returns "New Chat" so the sidebar is never blank.
        if not generated_title:
            generated_title = _text_fallback_title(user_message)
            logger.info("[run_extras][title] step4 fallback: %r", generated_title)

        if generated_title and generated_title.strip():
            title = generated_title.strip()
            await repo.update_summary(
                session_id=thread_id,
                family_id=family_id,
                summary=None,
                title=title,
            )
            logger.info("[run_extras] Generated title '%s' for thread %s", title, thread_id)
            return title
        logger.info("[run_extras][title] FINAL: generated_title empty, returning None")
        return None
    except Exception as e:
        logger.warning("[run_extras] Failed to sync title for thread %s: %s", thread_id, e)
        return None
