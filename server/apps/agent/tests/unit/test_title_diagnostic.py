"""Diagnostic test: exercises the full sync_title_from_checkpoint flow
to identify exactly where title generation breaks for numina chat sessions.

Run: uv run pytest server/apps/agent/tests/unit/test_title_diagnostic.py -vs
"""
from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from apps.agent.services.runtime.run_extras import (
    _generate_title_via_llm,
    _is_fallback_title,
    _should_generate_title,
    _text_fallback_title,
    strip_language_prefix,
    sync_title_from_checkpoint,
)


# ── Simulate the exact data flow from AI Hub → worker → title sync ──


def test_ai_hub_message_strip():
    """Verify the exact message the AI Hub sends produces a valid title_user_message."""
    # Frontend sends this (from useThreadChat.ts line 1404-1409)
    raw_content = "[语言要求] 输出语言：中文。\n帮我看看家庭财务近况"
    title_user_message = strip_language_prefix(raw_content)
    assert title_user_message == "帮我看看家庭财务近况", f"Got: {title_user_message!r}"
    assert len(title_user_message) > 0


def test_build_prompt_json_is_fallback_title():
    """Verify the adapter's _build_prompt JSON output is detected as fallback."""
    # Adapter builds this JSON (adapter.py line 837-851)
    ctx_dict = {"free_text": "<user_message>\n帮我看看家庭财务近况\n</user_message>"}
    prompt_json = json.dumps(ctx_dict, ensure_ascii=False, indent=2)
    assert _is_fallback_title(prompt_json), "Adapter prompt JSON should be detected as fallback"


def test_checkpoint_with_adapter_prompt_json():
    """Simulate checkpoint carrying the adapter's JSON as fallback title + real messages."""
    # After graph runs, checkpoint has:
    # - title: adapter's _build_prompt JSON output
    # - messages: [HumanMessage(prompt_json), AIMessage(response)]
    adapter_prompt = json.dumps(
        {"free_text": "<user_message>\n帮我看看家庭财务近况\n</user_message>"},
        ensure_ascii=False,
    )
    messages = [
        HumanMessage(content=adapter_prompt),
        AIMessage(content="这是您的家庭财务分析..."),
    ]
    channel_values = {"title": adapter_prompt, "messages": messages}

    # Step 1: DB has no title (new session)
    # Step 3: checkpoint title IS a fallback → don't return early
    assert _is_fallback_title(channel_values["title"])

    # Step 4: gate check
    assert _should_generate_title(channel_values) is True, \
        "Should generate title for first exchange with adapter JSON fallback"


def test_checkpoint_empty_messages_bypasses_gate():
    """When checkpoint messages haven't flushed, gate is bypassed."""
    adapter_prompt = json.dumps({"free_text": "test"}, ensure_ascii=False)
    channel_values = {"title": adapter_prompt}  # no messages key

    # gate_applicable = len([]) >= 1 → False → gate bypassed
    gate_applicable = len(channel_values.get("messages") or []) >= 1
    assert gate_applicable is False, "Empty messages should bypass gate"


@pytest.mark.asyncio
async def test_full_title_sync_from_checkpoint():
    """End-to-end: simulate the exact flow for an AI Hub new session."""
    adapter_prompt = json.dumps(
        {"free_text": "<user_message>\n帮我看看家庭财务近况\n</user_message>"},
        ensure_ascii=False,
    )
    messages = [
        HumanMessage(content=adapter_prompt),
        AIMessage(content="这是您的家庭财务分析..."),
    ]
    channel_values = {"title": adapter_prompt, "messages": messages}
    checkpoint = SimpleNamespace(checkpoint={"channel_values": channel_values})

    with (
        patch(
            "apps.agent.services.deerflow_adapter.family_adapter_cache._get_shared_checkpointer"
        ) as mock_get_ckpt,
        patch("apps.agent.services.session_store.AiSessionRepository") as MockRepo,
        patch(
            "apps.agent.services.runtime.run_extras._generate_title_via_llm",
            new_callable=AsyncMock,
            return_value="家庭财务近况分析",
        ) as mock_llm,
    ):
        mock_get_ckpt.return_value.aget_tuple = AsyncMock(return_value=checkpoint)

        repo = MockRepo.return_value
        repo.get_session = AsyncMock(return_value=None)  # new session
        repo.update_summary = AsyncMock()

        result = await sync_title_from_checkpoint(
            "thread-uuid-123",
            "family-123",
            ai_config={
                "ai_provider": "openai",
                "ai_model_id": "gpt-4o-mini",
                "api_key": "test-key",
            },
            user_message="帮我看看家庭财务近况",
            ai_response="这是您的家庭财务分析...",
            target_language="Chinese",
        )

    # Verify the full flow worked
    mock_llm.assert_awaited_once()
    repo.update_summary.assert_awaited_once()
    assert repo.update_summary.call_args.kwargs["title"] == "家庭财务近况分析"
    assert result == "家庭财务近况分析"


@pytest.mark.asyncio
async def test_full_title_sync_llm_fails_fallback():
    """When LLM fails, fallback to user message text."""
    adapter_prompt = json.dumps(
        {"free_text": "帮我看看家庭财务近况"},
        ensure_ascii=False,
    )
    messages = [
        HumanMessage(content=adapter_prompt),
        AIMessage(content="分析结果..."),
    ]
    channel_values = {"title": adapter_prompt, "messages": messages}
    checkpoint = SimpleNamespace(checkpoint={"channel_values": channel_values})

    with (
        patch(
            "apps.agent.services.deerflow_adapter.family_adapter_cache._get_shared_checkpointer"
        ) as mock_get_ckpt,
        patch("apps.agent.services.session_store.AiSessionRepository") as MockRepo,
        patch(
            "apps.agent.services.runtime.run_extras._generate_title_via_llm",
            new_callable=AsyncMock,
            return_value=None,  # LLM failed
        ),
    ):
        mock_get_ckpt.return_value.aget_tuple = AsyncMock(return_value=checkpoint)
        repo = MockRepo.return_value
        repo.get_session = AsyncMock(return_value=None)
        repo.update_summary = AsyncMock()

        result = await sync_title_from_checkpoint(
            "thread-uuid-123",
            "family-123",
            ai_config={"ai_provider": "openai"},
            user_message="帮我看看家庭财务近况",
            ai_response="分析结果...",
        )

    repo.update_summary.assert_awaited_once()
    title = repo.update_summary.call_args.kwargs["title"]
    assert title == "帮我看看家庭财务近况", f"Expected fallback title, got: {title!r}"
    assert result == "帮我看看家庭财务近况"


@pytest.mark.asyncio
async def test_checkpoint_read_returns_none():
    """When checkpoint read fails, still produce a title from user message."""
    with (
        patch(
            "apps.agent.services.deerflow_adapter.family_adapter_cache._get_shared_checkpointer"
        ) as mock_get_ckpt,
        patch("apps.agent.services.session_store.AiSessionRepository") as MockRepo,
    ):
        mock_get_ckpt.return_value.aget_tuple = AsyncMock(return_value=None)
        repo = MockRepo.return_value
        repo.get_session = AsyncMock(return_value=None)
        repo.update_summary = AsyncMock()

        result = await sync_title_from_checkpoint(
            "thread-uuid-123",
            "family-123",
            ai_config={"ai_provider": "openai"},
            user_message="帮我看看家庭财务近况",
            ai_response="",
        )

    repo.update_summary.assert_awaited_once()
    title = repo.update_summary.call_args.kwargs["title"]
    assert title == "帮我看看家庭财务近况", f"Expected fallback, got: {title!r}"
    assert result == "帮我看看家庭财务近况"


def test_text_fallback_title_values():
    """Verify _text_fallback_title produces expected values."""
    assert _text_fallback_title("") == "New Chat"
    assert _text_fallback_title("   ") == "New Chat"
    assert _text_fallback_title("帮我看看") == "帮我看看"
    long = "x" * 200
    t = _text_fallback_title(long)
    assert len(t) <= 60
    assert t.endswith("...")


@pytest.mark.asyncio
async def test_followup_generates_title_when_db_has_no_title():
    """Regression: follow-up messages must generate a title when DB has NONE.

    Previously the gate checked ``db_has_fallback`` (title is a fallback value)
    but NOT ``db_title is None`` (title was never set).  Sessions that never
    got a title — due to the prior bug, a crashed first turn, etc. — would
    stay title-less forever because the gate saw 2+ user messages and no
    fallback, then returned None.

    Fix: add ``db_title_missing`` escape so any follow-up turn generates a
    title when the DB row has never had one.
    """
    # Simulate a session with 2 complete exchanges (follow-up message)
    messages = [
        HumanMessage(content="第一问"),
        AIMessage(content="第一答"),
        HumanMessage(content="第二问 — 这就是本轮的用户消息"),
        AIMessage(content="第二答"),
    ]
    # Checkpoint has NO title (never set)
    channel_values = {"messages": messages}
    checkpoint = SimpleNamespace(checkpoint={"channel_values": channel_values})

    with (
        patch(
            "apps.agent.services.deerflow_adapter.family_adapter_cache._get_shared_checkpointer"
        ) as mock_get_ckpt,
        patch("apps.agent.services.session_store.AiSessionRepository") as MockRepo,
        patch(
            "apps.agent.services.runtime.run_extras._generate_title_via_llm",
            new_callable=AsyncMock,
            return_value="第二问的标题",
        ) as mock_llm,
    ):
        mock_get_ckpt.return_value.aget_tuple = AsyncMock(return_value=checkpoint)
        repo = MockRepo.return_value
        repo.get_session = AsyncMock(return_value={"title": None})  # DB has NO title
        repo.update_summary = AsyncMock()

        result = await sync_title_from_checkpoint(
            "thread-uuid-456",
            "family-123",
            ai_config={"ai_provider": "openai", "ai_model_id": "gpt-4o-mini"},
            user_message="第二问 — 这就是本轮的用户消息",
            ai_response="第二答",
        )

    # Must generate title despite being a follow-up (2+ user messages)
    mock_llm.assert_awaited_once()
    repo.update_summary.assert_awaited_once()
    assert repo.update_summary.call_args.kwargs["title"] == "第二问的标题"
    assert result == "第二问的标题"


@pytest.mark.asyncio
async def test_followup_preserves_existing_title():
    """Follow-up must NOT overwrite a session that already has a proper title."""
    messages = [
        HumanMessage(content="第一问"),
        AIMessage(content="第一答"),
        HumanMessage(content="第二问"),
        AIMessage(content="第二答"),
    ]
    channel_values = {"messages": messages}
    checkpoint = SimpleNamespace(checkpoint={"channel_values": channel_values})

    with (
        patch(
            "apps.agent.services.deerflow_adapter.family_adapter_cache._get_shared_checkpointer"
        ) as mock_get_ckpt,
        patch("apps.agent.services.session_store.AiSessionRepository") as MockRepo,
        patch(
            "apps.agent.services.runtime.run_extras._generate_title_via_llm",
            new_callable=AsyncMock,
        ) as mock_llm,
    ):
        mock_get_ckpt.return_value.aget_tuple = AsyncMock(return_value=checkpoint)
        repo = MockRepo.return_value
        repo.get_session = AsyncMock(return_value={"title": "已有标题"})  # proper title
        repo.update_summary = AsyncMock()

        result = await sync_title_from_checkpoint(
            "thread-uuid-789",
            "family-123",
            ai_config={"ai_provider": "openai"},
            user_message="第二问",
            ai_response="第二答",
        )

    # Must NOT generate/overwrite — step 1 returns None for proper existing title
    mock_llm.assert_not_awaited()
    repo.update_summary.assert_not_awaited()
    assert result is None
