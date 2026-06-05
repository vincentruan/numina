"""Test LLM-based suggestion generation."""

import pytest
from unittest.mock import AsyncMock, patch

from apps.agent.services.orchestrator import Orchestrator


@pytest.mark.asyncio
async def test_generate_suggestions_returns_list():
    """_generate_suggestions should return a list of suggestion strings."""
    o = Orchestrator.__new__(Orchestrator)
    ai_config = {
        "ai_provider": "openai",
        "api_key": "test-key",
        "ai_model_id": "gpt-4",
        "ai_base_url": None,
    }
    with patch("apps.agent.core.llm.LLMClient") as mock_llm_cls:
        mock_llm = AsyncMock()
        mock_llm.complete.return_value = "查看资产配置\n分析净资产趋势\n对比上月变化"
        mock_llm_cls.return_value = mock_llm
        result = await o._generate_suggestions(
            answer_text="您的净资产为100万元，房产占比60%。",
            ai_config=ai_config,
        )
    assert isinstance(result, list)
    assert len(result) == 3
    assert "查看资产配置" in result


@pytest.mark.asyncio
async def test_generate_suggestions_handles_llm_failure():
    """_generate_suggestions should return empty list on LLM failure."""
    o = Orchestrator.__new__(Orchestrator)
    ai_config = {
        "ai_provider": "openai",
        "api_key": "test-key",
        "ai_model_id": "gpt-4",
        "ai_base_url": None,
    }
    with patch("apps.agent.core.llm.LLMClient") as mock_llm_cls:
        mock_llm = AsyncMock()
        mock_llm.complete.side_effect = Exception("timeout")
        mock_llm_cls.return_value = mock_llm
        result = await o._generate_suggestions(
            answer_text="test answer",
            ai_config=ai_config,
        )
    assert result == []


@pytest.mark.asyncio
async def test_generate_suggestions_missing_config():
    """_generate_suggestions returns empty list when ai_config is incomplete."""
    o = Orchestrator.__new__(Orchestrator)
    ai_config = {"ai_provider": "", "api_key": "", "ai_model_id": ""}
    result = await o._generate_suggestions(
        answer_text="test", ai_config=ai_config
    )
    assert result == []


@pytest.mark.asyncio
async def test_generate_suggestions_truncates_to_max():
    """_generate_suggestions respects max_suggestions limit."""
    o = Orchestrator.__new__(Orchestrator)
    ai_config = {
        "ai_provider": "openai",
        "api_key": "test-key",
        "ai_model_id": "gpt-4",
        "ai_base_url": None,
    }
    with patch("apps.agent.core.llm.LLMClient") as mock_llm_cls:
        mock_llm = AsyncMock()
        mock_llm.complete.return_value = "一\n二\n三\n四\n五"
        mock_llm_cls.return_value = mock_llm
        result = await o._generate_suggestions(
            answer_text="test",
            ai_config=ai_config,
            max_suggestions=2,
        )
    assert len(result) == 2
