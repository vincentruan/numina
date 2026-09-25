"""Tests for agent-side topic translation service."""

import json

import pytest

from apps.agent.services.topic_translate import (
    TRANSLATION_SYSTEM_PROMPT,
    translate_topic,
)


def _make_ai_config(
    provider: str = "openai_compatible",
    model: str = "qwen-plus",
    api_key: str = "test-key",
    base_url: str = "https://example.com/v1",
) -> dict:
    return {
        "ai_provider": provider,
        "ai_model_id": model,
        "api_key": api_key,
        "ai_base_url": base_url,
    }


@pytest.mark.asyncio
async def test_translate_topic_returns_all_keys(monkeypatch):
    """translate_topic returns all four _zh keys from LLM JSON response."""
    expected = {
        "name_zh": "加法",
        "description_zh": "学习基本加法运算",
        "evidence_zh": ["能正确计算", "理解进位概念"],
        "assessment_prompt_zh": "请计算以下题目",
    }

    async def mock_complete_json(self, prompt, max_tokens=4000, system=None):
        return json.dumps(expected, ensure_ascii=False)

    from apps.agent.core.llm import LLMClient

    monkeypatch.setattr(LLMClient, "complete_json", mock_complete_json)

    topic = {
        "name": "Addition",
        "description": "Learn basic addition",
        "evidence": ["Can compute correctly", "Understands carrying"],
        "assessment_prompt": "Calculate the following",
    }
    result = await translate_topic(topic, _make_ai_config())
    assert result == expected


@pytest.mark.asyncio
async def test_translate_topic_truncates_long_description(monkeypatch):
    """Description is truncated to _MAX_DESCRIPTION_CHARS before sending to LLM."""
    captured_prompt = {}

    async def mock_complete_json(self, prompt, max_tokens=4000, system=None):
        captured_prompt["value"] = prompt
        return json.dumps({
            "name_zh": "X", "description_zh": "Y",
            "evidence_zh": [], "assessment_prompt_zh": "Z",
        })

    from apps.agent.core.llm import LLMClient

    monkeypatch.setattr(LLMClient, "complete_json", mock_complete_json)

    topic = {
        "name": "Test",
        "description": "A" * 5000,
        "evidence": [],
        "assessment_prompt": "",
    }
    await translate_topic(topic, _make_ai_config())
    # The prompt should NOT contain the full 5000-char description
    assert len(captured_prompt["value"]) < 5000


@pytest.mark.asyncio
async def test_translate_topic_missing_key_raises():
    """LLM response missing a required key raises ValueError."""
    from unittest.mock import AsyncMock, patch

    from apps.agent.core.llm import LLMClient

    with patch.object(
        LLMClient, "complete_json",
        new_callable=AsyncMock,
        return_value=json.dumps({"name_zh": "X"}),  # missing other keys
    ):
        with pytest.raises(ValueError, match="missing required key"):
            await translate_topic(
                {"name": "T", "description": "D", "evidence": [], "assessment_prompt": ""},
                _make_ai_config(),
            )


@pytest.mark.asyncio
async def test_translate_topic_malformed_json_raises():
    """Non-JSON LLM response raises ValueError."""
    from unittest.mock import AsyncMock, patch

    from apps.agent.core.llm import LLMClient

    with patch.object(
        LLMClient, "complete_json",
        new_callable=AsyncMock,
        return_value="not json at all",
    ):
        with pytest.raises(ValueError, match="malformed|JSON|json"):
            await translate_topic(
                {"name": "T", "description": "D", "evidence": [], "assessment_prompt": ""},
                _make_ai_config(),
            )


@pytest.mark.asyncio
async def test_translate_topic_empty_api_key_raises():
    """Missing api_key in ai_config raises ValueError."""
    with pytest.raises(ValueError, match="API key|api_key"):
        await translate_topic(
            {"name": "T", "description": "D", "evidence": [], "assessment_prompt": ""},
            {"ai_provider": "openai", "ai_model_id": "gpt-4", "api_key": ""},
        )
