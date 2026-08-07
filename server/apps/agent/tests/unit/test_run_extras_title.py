"""Tests for run_extras.sync_title_from_checkpoint - title resolution pipeline.

Regression guard: the thread title must end up as a proper LLM-generated
summary in the ``ai_chat_sessions`` row. DeerFlow's ``TitleMiddleware`` writes
to the LangGraph checkpoint, but Numina's adapter runs the sync ``stream()``
path - so the sync ``after_model`` hook fires and only writes a local fallback
(the raw ``[SKILL:chat]`` prompt wrapper), never an LLM summary.
``sync_title_from_checkpoint`` must detect that fallback and generate a real
title via the family's AI provider, falling back to the user's message text
if the LLM call fails.

Title generation is gated like DeerFlow's ``TitleMiddleware``: only the first
complete exchange produces a title; follow-up exchanges must return ``None``
so the worker does not re-publish the title to the frontend.
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from apps.agent.services.runtime.run_extras import (
    _is_fallback_title,
    _should_generate_title,
    sync_title_from_checkpoint,
)


def _checkpoint_with_title(title: str | None, messages: list | None = None) -> SimpleNamespace:
    """Build a fake CheckpointTuple whose .checkpoint.channel_values has title."""
    channel_values: dict = {"title": title}
    if messages is not None:
        channel_values["messages"] = messages
    return SimpleNamespace(checkpoint={"channel_values": channel_values})


async def test_sync_title_from_checkpoint_persists_title_from_checkpoint():
    """A proper checkpoint title (async middleware path) is persisted as-is."""
    messages = [
        {"role": "user", "content": "家庭资产总览"},
        {"role": "assistant", "content": "这是您的资产情况"},
    ]
    with (
        patch(
            "apps.agent.services.deerflow_adapter.family_adapter_cache._get_shared_checkpointer"
        ) as mock_get_ckpt,
        patch("apps.agent.services.session_store.AiSessionRepository") as MockRepo,
    ):
        checkpointer = mock_get_ckpt.return_value
        checkpointer.aget_tuple = AsyncMock(
            return_value=_checkpoint_with_title("家庭资产总览", messages)
        )

        repo = MockRepo.return_value
        repo.get_session = AsyncMock(return_value={"title": None})
        repo.update_summary = AsyncMock()

        result = await sync_title_from_checkpoint("thread-1", "family-1")

    # The checkpoint title is persisted via the session repo - proves the
    # sync reads from channel_values["title"] and writes to the session row.
    repo.update_summary.assert_awaited_once()
    kwargs = repo.update_summary.call_args.kwargs
    assert kwargs["session_id"] == "thread-1"
    assert kwargs["family_id"] == "family-1"
    assert kwargs["title"] == "家庭资产总览"
    # Returns the newly-persisted title so the worker publishes it to the frontend.
    assert result == "家庭资产总览"


async def test_sync_title_skips_when_session_already_titled():
    """An existing non-fallback title is not overwritten (user may have renamed).

    Return value must be None (not the existing title) so the worker does NOT
    re-publish the title to the frontend on follow-up messages — DeerFlow
    ``TitleMiddleware._should_generate_title`` pattern: title only on the first
    complete exchange, never again.
    """
    with (
        patch(
            "apps.agent.services.deerflow_adapter.family_adapter_cache._get_shared_checkpointer"
        ) as mock_get_ckpt,
        patch("apps.agent.services.session_store.AiSessionRepository") as MockRepo,
    ):
        checkpointer = mock_get_ckpt.return_value
        checkpointer.aget_tuple = AsyncMock(
            return_value=_checkpoint_with_title("新标题")
        )

        repo = MockRepo.return_value
        repo.get_session = AsyncMock(return_value={"title": "已有标题"})
        repo.update_summary = AsyncMock()

        result = await sync_title_from_checkpoint("thread-1", "family-1")

    repo.update_summary.assert_not_called()
    # Returns None (not the existing title) so the worker does NOT publish a
    # values event — the sidebar title stays stable across follow-up messages.
    assert result is None


async def test_sync_title_skips_on_second_exchange():
    """Follow-up messages must NOT regenerate or re-publish the title.

    Even when the DB title is missing/fallback, the checkpoint now contains two
    real user messages, so DeerFlow's first-exchange gate returns False.
    """
    messages = [
        {"role": "user", "content": "第一问"},
        {"role": "assistant", "content": "第一答"},
        {"role": "user", "content": "第二问"},
        {"role": "assistant", "content": "第二答"},
    ]
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
        checkpointer = mock_get_ckpt.return_value
        checkpointer.aget_tuple = AsyncMock(
            return_value=_checkpoint_with_title(None, messages)
        )

        repo = MockRepo.return_value
        repo.get_session = AsyncMock(return_value={"title": None})
        repo.update_summary = AsyncMock()

        result = await sync_title_from_checkpoint(
            "thread-1",
            "family-1",
            ai_config={"ai_provider": "openai", "ai_model_id": "gpt-4o-mini"},
            user_message="第二问",
            ai_response="第二答",
        )

    # No LLM call, no DB write, no frontend publish on follow-up.
    mock_llm.assert_not_awaited()
    repo.update_summary.assert_not_called()
    assert result is None


async def test_sync_title_overwrites_fallback_via_llm():
    """When the checkpoint title is a [SKILL:chat] fallback, an LLM title is generated."""
    fallback_title = '[SKILL:chat]\n{"free_text": "家庭资产负债现金流"}'
    messages = [
        {"role": "user", "content": "家庭资产负债现金流"},
        {"role": "assistant", "content": "这是您的家庭资产负债..."},
    ]
    with (
        patch(
            "apps.agent.services.deerflow_adapter.family_adapter_cache._get_shared_checkpointer"
        ) as mock_get_ckpt,
        patch("apps.agent.services.session_store.AiSessionRepository") as MockRepo,
        patch(
            "apps.agent.services.runtime.run_extras._generate_title_via_llm",
            new_callable=AsyncMock,
            return_value="家庭资产负债现金流分析",
        ) as mock_llm,
    ):
        checkpointer = mock_get_ckpt.return_value
        checkpointer.aget_tuple = AsyncMock(
            return_value=_checkpoint_with_title(fallback_title, messages)
        )

        repo = MockRepo.return_value
        repo.get_session = AsyncMock(return_value={"title": None})
        repo.update_summary = AsyncMock()

        result = await sync_title_from_checkpoint(
            "thread-1",
            "family-1",
            ai_config={"ai_provider": "openai", "ai_model_id": "gpt-4o-mini"},
            user_message="家庭资产负债现金流",
            ai_response="这是您的家庭资产负债...",
        )

    mock_llm.assert_awaited_once()
    repo.update_summary.assert_awaited_once()
    assert repo.update_summary.call_args.kwargs["title"] == "家庭资产负债现金流分析"
    # Returns the newly-generated LLM title so the worker publishes it.
    assert result == "家庭资产负债现金流分析"


async def test_sync_title_falls_back_to_user_text_when_llm_fails():
    """If the LLM call fails/returns None, the user message is truncated as the title."""
    fallback_title = '[SKILL:chat]\n{"free_text": "家庭资产负债现金流"}'
    messages = [
        {"role": "user", "content": "家庭资产负债现金流"},
        {"role": "assistant", "content": "..."},
    ]
    with (
        patch(
            "apps.agent.services.deerflow_adapter.family_adapter_cache._get_shared_checkpointer"
        ) as mock_get_ckpt,
        patch("apps.agent.services.session_store.AiSessionRepository") as MockRepo,
        patch(
            "apps.agent.services.runtime.run_extras._generate_title_via_llm",
            new_callable=AsyncMock,
            return_value=None,
        ),
    ):
        checkpointer = mock_get_ckpt.return_value
        checkpointer.aget_tuple = AsyncMock(
            return_value=_checkpoint_with_title(fallback_title, messages)
        )

        repo = MockRepo.return_value
        repo.get_session = AsyncMock(return_value={"title": None})
        repo.update_summary = AsyncMock()

        result = await sync_title_from_checkpoint(
            "thread-1",
            "family-1",
            ai_config={"ai_provider": "openai"},
            user_message="家庭资产负债现金流",
            ai_response="...",
        )

    # LLM returned None -> fallback to the user's actual text (NOT the [SKILL:] wrapper)
    repo.update_summary.assert_awaited_once()
    assert repo.update_summary.call_args.kwargs["title"] == "家庭资产负债现金流"
    # Returns the fallback title so the worker publishes it.
    assert result == "家庭资产负债现金流"


async def test_sync_title_allows_partial_exchange_for_interrupted_run():
    """Interrupted first turns may produce a fallback title from a lone user message.

    Mirrors DeerFlow's ``_ensure_interrupted_title`` / ``allow_partial_exchange``.
    """
    messages = [{"role": "user", "content": "家庭资产负债现金流"}]
    with (
        patch(
            "apps.agent.services.deerflow_adapter.family_adapter_cache._get_shared_checkpointer"
        ) as mock_get_ckpt,
        patch("apps.agent.services.session_store.AiSessionRepository") as MockRepo,
        patch(
            "apps.agent.services.runtime.run_extras._generate_title_via_llm",
            new_callable=AsyncMock,
            return_value=None,
        ),
    ):
        checkpointer = mock_get_ckpt.return_value
        checkpointer.aget_tuple = AsyncMock(
            return_value=_checkpoint_with_title(None, messages)
        )

        repo = MockRepo.return_value
        repo.get_session = AsyncMock(return_value={"title": None})
        repo.update_summary = AsyncMock()

        result = await sync_title_from_checkpoint(
            "thread-1",
            "family-1",
            ai_config={"ai_provider": "openai"},
            user_message="家庭资产负债现金流",
            ai_response="",
            allow_partial_exchange=True,
        )

    repo.update_summary.assert_awaited_once()
    assert repo.update_summary.call_args.kwargs["title"] == "家庭资产负债现金流"
    assert result == "家庭资产负债现金流"


async def test_sync_title_no_save_without_checkpoint_or_message():
    """No save when checkpoint is absent and no user_message is provided."""
    with (
        patch(
            "apps.agent.services.deerflow_adapter.family_adapter_cache._get_shared_checkpointer"
        ) as mock_get_ckpt,
        patch("apps.agent.services.session_store.AiSessionRepository") as MockRepo,
    ):
        checkpointer = mock_get_ckpt.return_value
        checkpointer.aget_tuple = AsyncMock(return_value=None)

        repo = MockRepo.return_value
        repo.get_session = AsyncMock(return_value={"title": None})
        repo.update_summary = AsyncMock()

        result = await sync_title_from_checkpoint("thread-1", "family-1")

    repo.update_summary.assert_not_called()
    # No title source available — returns None, worker will not publish.
    assert result is None


def test_is_fallback_title_detects_truncated_context_json():
    """A truncated raw-context JSON (TitleMiddleware/DB column cut mid-string)
    must still be detected as a fallback.

    Regression: the e2e chat title leaked ``family_id`` because the DB stored a
    truncated ``{"family_id": "...", "free_tex`` (unterminated string). The old
    json.loads-based check raised JSONDecodeError → returned False → the title
    was kept instead of being replaced by an LLM-generated one. The substring
    guard (``"family_id" in t or "free_text" in t``) catches this without parse.
    """
    truncated = '{\n  "family_id": "321210384289632256",\n  "free_tex'
    assert _is_fallback_title(truncated) is True
    # Full (un-truncated) raw context JSON still detected.
    assert _is_fallback_title('{"family_id": "123", "free_text": "帮我看看资产"}') is True
    # Real titles and LLM JSON without context keys must NOT be flagged.
    assert _is_fallback_title("家庭资产总览分析") is False
    assert _is_fallback_title('{"summary": "资产配置建议"}') is False


def test_is_fallback_title_detects_thinking_block_repr():
    """A Python list-literal repr of structured model output (thinking blocks)
    must be detected as a fallback title.

    Regression: when the model returns content as a list of dicts
    (e.g. Claude extended thinking, Qwen3 thinking blocks), calling ``str()``
    on ``response.content`` produces a Python repr like
    ``[{'signature': '', 'thinking': '用户希望为一段对话生成一个简洁的标题...'}]``
    which is NOT a real summary. The old check only detected ``[SKILL:`` prefix
    and JSON objects — list-literal repr slipped through.
    """
    # Full thinking block repr (Python list of dicts)
    thinking_title = "[{'signature': '', 'thinking': '用户希望为一段对话生成一个简洁的标题。\\n对话内容：用户问了关于家庭资产的问题'}]"
    assert _is_fallback_title(thinking_title) is True
    # Truncated thinking block repr
    truncated_thinking = "[{'signature': '', 'thinking': '用户希望为一段对话"
    assert _is_fallback_title(truncated_thinking) is True
    # Thinking block with 'type' key instead of 'signature'
    typed_thinking = "[{'type': 'thinking', 'thinking': '生成标题...'}, {'type': 'text', 'text': '家庭资产总览'}]"
    assert _is_fallback_title(typed_thinking) is True
    # Real titles must NOT be flagged
    assert _is_fallback_title("家庭资产总览分析") is False
    assert _is_fallback_title("保险配置建议") is False


def test_should_generate_title_first_exchange():
    """DeerFlow gate: generate title only after the first complete exchange."""
    messages = [
        {"role": "user", "content": "问"},
        {"role": "assistant", "content": "答"},
    ]
    assert _should_generate_title({"messages": messages}) is True


def test_should_generate_title_requires_assistant_for_complete_exchange():
    """A lone user message on the first turn does NOT generate a title normally."""
    messages = [{"role": "user", "content": "问"}]
    assert _should_generate_title({"messages": messages}) is False
    # Interrupted-run path allows a partial exchange.
    assert _should_generate_title({"messages": messages}, allow_partial_exchange=True) is True


def test_should_generate_title_skips_second_exchange():
    """Two complete exchanges means we are past the first turn — skip title."""
    messages = [
        {"role": "user", "content": "第一问"},
        {"role": "assistant", "content": "第一答"},
        {"role": "user", "content": "第二问"},
        {"role": "assistant", "content": "第二答"},
    ]
    assert _should_generate_title({"messages": messages}) is False


def test_should_generate_title_skips_when_title_exists():
    """An existing proper checkpoint title blocks regeneration."""
    messages = [
        {"role": "user", "content": "问"},
        {"role": "assistant", "content": "答"},
    ]
    assert _should_generate_title({"messages": messages, "title": "已有标题"}) is False
    # A fallback title does NOT block regeneration.
    assert _should_generate_title({"messages": messages, "title": "New Chat"}) is True


def test_should_generate_title_handles_langchain_objects():
    """Messages may be LangChain message objects, not just dicts."""
    from langchain_core.messages import AIMessage, HumanMessage

    messages = [HumanMessage(content="问"), AIMessage(content="答")]
    assert _should_generate_title({"messages": messages}) is True


def test_should_generate_title_ignores_dynamic_context_reminders():
    """Hidden memory reminders are not counted as user turns."""
    messages = [
        {
            "role": "user",
            "content": "<memory>User prefers concise titles.</memory>",
            "additional_kwargs": {"dynamic_context_reminder": True},
        },
        {"role": "user", "content": "请帮我写测试"},
        {"role": "assistant", "content": "好的"},
    ]
    assert _should_generate_title({"messages": messages}) is True


def test_text_fallback_title_empty_returns_new_chat():
    """DeerFlow-style: blank user messages fall back to 'New Chat', not ''."""
    from apps.agent.services.runtime.run_extras import _text_fallback_title

    assert _text_fallback_title("") == "New Chat"
    assert _text_fallback_title("   ") == "New Chat"


def test_text_fallback_title_truncation():
    """Long user messages are truncated with ellipsis, never exceeding max_chars."""
    from apps.agent.services.runtime.run_extras import _text_fallback_title

    long_text = "x" * 200
    title = _text_fallback_title(long_text, max_chars=60)
    assert len(title) <= 60
    assert title.endswith("...")
    # Default DeerFlow max_chars=60 leaves room for a 50-char body + ellipsis.
    assert title == "x" * 50 + "..."
