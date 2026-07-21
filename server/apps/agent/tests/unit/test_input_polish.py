"""Tests for input_polish.polish_draft (D3 DeerFlow-synced lightweight LLM call).

Same shape as ``asset_suggest`` (``_create_lightweight_llm`` + ``llm.ainvoke``).
Verifies:
- system prompt is a rewrite instruction (not an answerer) + preserves slash prefix intent
- ``changed=False`` on empty / overlong / no-op / LLM-failure → original returned unchanged
- ``<think>`` blocks and stray ``` fences are stripped from the rewritten text
- prompt-injection defense (user draft wrapped in <draft> XML delimiter)
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from apps.agent.services.input_polish import polish_draft


class _FakeLLMResponse:
    """Mimic langchain AIMessage.content for llm.ainvoke()."""

    def __init__(self, content: str) -> None:
        self.content = content


def _provider_config() -> dict:
    """A representative active-provider dict (keys _create_lightweight_llm reads)."""
    return {
        "ai_provider": "openai",
        "ai_model_id": "qwen-plus",
        "api_key": "sk-test",
        "ai_base_url": "http://localhost:8000/v1",
    }


@pytest.mark.asyncio
async def test_polish_rewrites_and_marks_changed():
    """A rough draft is rewritten into a clearer instruction; changed=True."""
    captured: dict = {}

    async def _fake_ainvoke(messages):
        captured["messages"] = messages
        return _FakeLLMResponse("请帮我全面分析一下目前的家庭资产配置情况，并指出集中度风险。")

    with patch("apps.agent.services.input_polish._create_lightweight_llm") as mock_factory:
        mock_factory.return_value.ainvoke = AsyncMock(side_effect=_fake_ainvoke)
        rewritten, changed = await polish_draft("帮我看看资产", _provider_config())

    assert changed is True
    assert rewritten == "请帮我全面分析一下目前的家庭资产配置情况，并指出集中度风险。"
    # System prompt is a rewriter, not an answerer.
    system_content = captured["messages"][0].content
    assert "改写" in system_content
    assert "不要回答任务本身" in system_content
    # User draft is wrapped in <draft> delimiter (injection defense).
    human_content = captured["messages"][1].content
    assert "<draft>" in human_content
    assert "帮我看看资产" in human_content


@pytest.mark.asyncio
async def test_polish_strips_think_blocks_and_fences():
    """Reasoning-model <think> blocks and stray ``` fences are removed."""
    async def _fake_ainvoke(messages):
        return _FakeLLMResponse(
            "<think>internal reasoning</think>\n```text\n改写后的清晰提问\n```"
        )

    with patch("apps.agent.services.input_polish._create_lightweight_llm") as mock_factory:
        mock_factory.return_value.ainvoke = AsyncMock(side_effect=_fake_ainvoke)
        rewritten, changed = await polish_draft("draft", _provider_config())

    assert changed is True
    assert rewritten == "改写后的清晰提问"
    assert "<think>" not in rewritten
    assert "```" not in rewritten


@pytest.mark.asyncio
async def test_polish_unchanged_when_llm_returns_original():
    """changed=False when the rewrite equals the original (no-op)."""
    async def _fake_ainvoke(messages):
        return _FakeLLMResponse("same text")

    with patch("apps.agent.services.input_polish._create_lightweight_llm") as mock_factory:
        mock_factory.return_value.ainvoke = AsyncMock(side_effect=_fake_ainvoke)
        rewritten, changed = await polish_draft("same text", _provider_config())

    assert changed is False
    assert rewritten == "same text"


@pytest.mark.asyncio
async def test_polish_empty_returns_unchanged_without_llm_call():
    """Empty/whitespace draft short-circuits before any LLM call."""
    with patch("apps.agent.services.input_polish._create_lightweight_llm") as mock_factory:
        rewritten, changed = await polish_draft("   ", _provider_config())
        mock_factory.assert_not_called()

    assert changed is False
    assert rewritten == ""


@pytest.mark.asyncio
async def test_polish_overlong_returns_unchanged_without_llm_call():
    """Drafts over the 4000-char cap short-circuit before the LLM call."""
    with patch("apps.agent.services.input_polish._create_lightweight_llm") as mock_factory:
        rewritten, changed = await polish_draft("x" * 4001, _provider_config())
        mock_factory.assert_not_called()

    assert changed is False
    assert len(rewritten) == 4001


@pytest.mark.asyncio
async def test_polish_llm_failure_returns_original_unchanged():
    """An LLM exception surfaces as changed=False + original text (no throw)."""
    with patch("apps.agent.services.input_polish._create_lightweight_llm") as mock_factory:
        mock_factory.return_value.ainvoke = AsyncMock(side_effect=RuntimeError("llm down"))
        rewritten, changed = await polish_draft("帮我看看资产", _provider_config())

    assert changed is False
    assert rewritten == "帮我看看资产"


@pytest.mark.asyncio
async def test_polish_empty_llm_output_returns_unchanged():
    """An empty/whitespace LLM response is treated as no-op (changed=False)."""
    async def _fake_ainvoke(messages):
        return _FakeLLMResponse("   ")

    with patch("apps.agent.services.input_polish._create_lightweight_llm") as mock_factory:
        mock_factory.return_value.ainvoke = AsyncMock(side_effect=_fake_ainvoke)
        rewritten, changed = await polish_draft("draft", _provider_config())

    assert changed is False
    assert rewritten == "draft"
