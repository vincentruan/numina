"""Unit tests for core/llm.py — Bug fix: SDK client singleton."""

import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from core.llm import LLMClient, get_llm_client


class TestLLMClientSingleton:
    def test_anthropic_client_created_at_init(self):
        with patch("anthropic.AsyncAnthropic") as mock_cls:
            mock_cls.return_value = MagicMock()
            client = LLMClient("anthropic", "test-key", "claude-3-5-sonnet-20241022")
            mock_cls.assert_called_once_with(api_key="test-key", timeout=60.0)
            assert client._anthropic_client is not None

    def test_openai_client_created_at_init(self):
        with patch("openai.AsyncOpenAI") as mock_cls:
            mock_cls.return_value = MagicMock()
            client = LLMClient("openai", "test-key", "gpt-4o")
            mock_cls.assert_called_once_with(api_key="test-key", timeout=60.0)
            assert client._openai_client is not None

    def test_anthropic_client_reused_across_calls(self):
        with patch("anthropic.AsyncAnthropic") as mock_cls:
            mock_cls.return_value = MagicMock()
            client = LLMClient("anthropic", "test-key", "claude-3-5-sonnet-20241022")
            first = client._anthropic_client
            second = client._anthropic_client
            assert first is second
            # Constructor called only once (at __init__)
            assert mock_cls.call_count == 1

    def test_openai_client_reused_across_calls(self):
        with patch("openai.AsyncOpenAI") as mock_cls:
            mock_cls.return_value = MagicMock()
            LLMClient("openai", "test-key", "gpt-4o")
            assert mock_cls.call_count == 1

    def test_unsupported_provider_raises(self):
        import pytest
        with pytest.raises(ValueError, match="不支持的 LLM Provider"):
            client = LLMClient("gemini", "test-key", "gemini-pro")
            import asyncio
            asyncio.run(client.complete("hello"))

    def test_get_llm_client_factory(self):
        with patch("anthropic.AsyncAnthropic") as mock_cls:
            mock_cls.return_value = MagicMock()
            client = get_llm_client("anthropic", "key", "claude-3-5-sonnet-20241022")
            assert isinstance(client, LLMClient)
            assert client.provider == "anthropic"


class TestOpenAICompatibleThinkingControl:
    async def test_stream_text_disables_provider_thinking(self):
        class FakeDelta:
            content = "answer"

        class FakeChoice:
            delta = FakeDelta()

        class FakeChunk:
            choices = [FakeChoice()]

        async def fake_stream():
            yield FakeChunk()

        with patch("openai.AsyncOpenAI") as mock_cls:
            mock_client = MagicMock()
            mock_client.chat.completions.create = AsyncMock(return_value=fake_stream())
            mock_cls.return_value = mock_client
            client = LLMClient("openai", "test-key", "glm-5")

            chunks = [chunk async for chunk in client.stream_text("hello")]

        assert chunks == ["answer"]
        call_kwargs = mock_client.chat.completions.create.call_args.kwargs
        assert call_kwargs["extra_body"]["enable_thinking"] is False


class TestJSONFenceStripping:
    """Regression tests for health_report JSON extraction logic."""

    def _extract_json(self, raw: str) -> str:
        import re
        fence_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', raw)
        if fence_match:
            return fence_match.group(1)
        start = raw.find("{")
        end = raw.rfind("}") + 1
        return raw[start:end]

    def test_plain_json_extracted(self):
        import json
        raw = '{"score": 4, "narrative": "good"}'
        result = json.loads(self._extract_json(raw))
        assert result["score"] == 4

    def test_json_in_code_fence_extracted(self):
        import json
        raw = '```json\n{"score": 4}\n```'
        result = json.loads(self._extract_json(raw))
        assert result["score"] == 4

    def test_json_in_plain_fence_extracted(self):
        import json
        raw = '```\n{"score": 3}\n```'
        result = json.loads(self._extract_json(raw))
        assert result["score"] == 3

    def test_json_with_surrounding_text(self):
        import json
        raw = 'Here is the result:\n{"score": 5}\nEnd.'
        result = json.loads(self._extract_json(raw))
        assert result["score"] == 5

    def test_fenced_json_takes_priority_over_brace_search(self):
        import json
        # If both fence and braces exist, fence wins
        raw = 'outer {bad} ```json\n{"score": 2}\n```'
        result = json.loads(self._extract_json(raw))
        assert result["score"] == 2
