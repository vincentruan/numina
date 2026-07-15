"""Tests for run_extras.sync_title_from_checkpoint - title resolution pipeline.

Regression guard: the thread title must end up as a proper LLM-generated
summary in the ``ai_chat_sessions`` row. DeerFlow's ``TitleMiddleware`` writes
to the LangGraph checkpoint, but Numina's adapter runs the sync ``stream()``
path - so the sync ``after_model`` hook fires and only writes a local fallback
(the raw ``[SKILL:chat]`` prompt wrapper), never an LLM summary.
``sync_title_from_checkpoint`` must detect that fallback and generate a real
title via the family's AI provider, falling back to the user's message text
if the LLM call fails.
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from apps.agent.services.runtime.run_extras import sync_title_from_checkpoint


def _checkpoint_with_title(title: str | None) -> SimpleNamespace:
    """Build a fake CheckpointTuple whose .checkpoint.channel_values has title."""
    return SimpleNamespace(checkpoint={"channel_values": {"title": title}})


async def test_sync_title_from_checkpoint_persists_title_from_checkpoint():
    """A proper checkpoint title (async middleware path) is persisted as-is."""
    with (
        patch(
            "apps.agent.services.deerflow_adapter.family_adapter_cache._get_shared_checkpointer"
        ) as mock_get_ckpt,
        patch("apps.agent.services.session_store.AiSessionRepository") as MockRepo,
    ):
        checkpointer = mock_get_ckpt.return_value
        checkpointer.aget_tuple = AsyncMock(
            return_value=_checkpoint_with_title("家庭资产总览")
        )

        repo = MockRepo.return_value
        repo.get_session = AsyncMock(return_value={"title": None})
        repo.update_summary = AsyncMock()

        await sync_title_from_checkpoint("thread-1", "family-1")

    # The checkpoint title is persisted via the session repo - proves the
    # sync reads from channel_values["title"] and writes to the session row.
    repo.update_summary.assert_awaited_once()
    kwargs = repo.update_summary.call_args.kwargs
    assert kwargs["session_id"] == "thread-1"
    assert kwargs["family_id"] == "family-1"
    assert kwargs["title"] == "家庭资产总览"


async def test_sync_title_skips_when_session_already_titled():
    """An existing non-fallback title is not overwritten (user may have renamed)."""
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

        await sync_title_from_checkpoint("thread-1", "family-1")

    repo.update_summary.assert_not_called()


async def test_sync_title_overwrites_fallback_via_llm():
    """When the checkpoint title is a [SKILL:chat] fallback, an LLM title is generated."""
    fallback_title = '[SKILL:chat]\n{"free_text": "家庭资产负债现金流"}'
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
            return_value=_checkpoint_with_title(fallback_title)
        )

        repo = MockRepo.return_value
        repo.get_session = AsyncMock(return_value={"title": None})
        repo.update_summary = AsyncMock()

        await sync_title_from_checkpoint(
            "thread-1",
            "family-1",
            ai_config={"ai_provider": "openai", "ai_model_id": "gpt-4o-mini"},
            user_message="家庭资产负债现金流",
            ai_response="这是您的家庭资产负债...",
        )

    mock_llm.assert_awaited_once()
    repo.update_summary.assert_awaited_once()
    assert repo.update_summary.call_args.kwargs["title"] == "家庭资产负债现金流分析"


async def test_sync_title_falls_back_to_user_text_when_llm_fails():
    """If the LLM call fails/returns None, the user message is truncated as the title."""
    fallback_title = '[SKILL:chat]\n{"free_text": "家庭资产负债现金流"}'
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
            return_value=_checkpoint_with_title(fallback_title)
        )

        repo = MockRepo.return_value
        repo.get_session = AsyncMock(return_value={"title": None})
        repo.update_summary = AsyncMock()

        await sync_title_from_checkpoint(
            "thread-1",
            "family-1",
            ai_config={"ai_provider": "openai"},
            user_message="家庭资产负债现金流",
            ai_response="...",
        )

    # LLM returned None -> fallback to the user's actual text (NOT the [SKILL:] wrapper)
    repo.update_summary.assert_awaited_once()
    assert repo.update_summary.call_args.kwargs["title"] == "家庭资产负债现金流"


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

        await sync_title_from_checkpoint("thread-1", "family-1")

    repo.update_summary.assert_not_called()
