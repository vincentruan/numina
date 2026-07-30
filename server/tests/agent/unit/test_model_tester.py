"""Unit tests for services/model_tester.py."""

import importlib
import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

# Import via importlib to prevent pytest from collecting test_* functions
# in services/model_tester.py as test cases.
_mod = importlib.import_module("apps.agent.services.model_tester")
_calculate_ocr_accuracy = _mod._calculate_ocr_accuracy
_test_connection = _mod.test_connection
_test_thinking = _mod.test_thinking
_test_vision = _mod.test_vision
_test_vision_ocr = _mod.test_vision_ocr


class TestCalculateOcrAccuracy:
    def test_exact_match(self):
        assert _calculate_ocr_accuracy("abc", "abc") == 1.0

    def test_empty_expected_empty_recognized(self):
        assert _calculate_ocr_accuracy("", "") == 1.0

    def test_empty_expected_nonempty_recognized(self):
        assert _calculate_ocr_accuracy("abc", "") == 0.0

    def test_partial_match(self):
        # LCS("ab", "abc") = 2, expected len = 3 → 2/3
        acc = _calculate_ocr_accuracy("ab", "abc")
        assert abs(acc - 2 / 3) < 0.001

    def test_no_match(self):
        assert _calculate_ocr_accuracy("xyz", "abc") == 0.0

    def test_whitespace_stripped(self):
        assert _calculate_ocr_accuracy("  abc  ", "abc") == 1.0


class TestTestConnection:
    async def test_success(self):
        with patch("apps.agent.services.model_tester.get_llm_client") as mock_factory:
            mock_client = MagicMock()
            mock_client.complete = AsyncMock(return_value="hi")
            mock_factory.return_value = mock_client

            result = await _test_connection("anthropic", "sk-test", "claude-3-5-haiku-20241022")

        assert result["connected"] is True
        assert result["latency_ms"] is not None

    async def test_timeout(self):
        with patch("apps.agent.services.model_tester.get_llm_client") as mock_factory:
            mock_client = MagicMock()
            mock_client.complete = AsyncMock(side_effect=Exception("Request timed out"))
            mock_factory.return_value = mock_client

            result = await _test_connection("anthropic", "sk-test", "claude-3-5-haiku-20241022")

        assert result["connected"] is False
        assert "超时" in result["message"]
        assert result["latency_ms"] is None

    async def test_generic_failure(self):
        with patch("apps.agent.services.model_tester.get_llm_client") as mock_factory:
            mock_client = MagicMock()
            mock_client.complete = AsyncMock(side_effect=Exception("401 Unauthorized"))
            mock_factory.return_value = mock_client

            result = await _test_connection("anthropic", "bad-key", "claude-3-5-haiku-20241022")

        assert result["connected"] is False
        assert "401" in result["message"]


class TestTestThinking:
    async def test_anthropic_with_thinking_block(self):
        async def fake_stream(*args, **kwargs):
            yield ("thinking", "some thought")
            yield ("text", "answer")

        with patch("apps.agent.services.model_tester.get_llm_client") as mock_factory:
            mock_client = MagicMock()
            mock_client.stream_with_thinking = fake_stream
            mock_factory.return_value = mock_client

            result = await _test_thinking("anthropic", "sk-test", "claude-opus-4-7")

        assert result["success"] is True
        assert "支持思考能力" in result["message"]

    async def test_anthropic_no_thinking_block(self):
        async def fake_stream(*args, **kwargs):
            yield ("text", "answer only")

        with patch("apps.agent.services.model_tester.get_llm_client") as mock_factory:
            mock_client = MagicMock()
            mock_client.stream_with_thinking = fake_stream
            mock_factory.return_value = mock_client

            result = await _test_thinking("anthropic", "sk-test", "claude-opus-4-7")

        assert result["success"] is True
        # Actual message: "主模型可调用（未检测到思考块）"
        assert "未检测到思考块" in result["message"]

    async def test_openai_reasoning_content(self):
        async def fake_stream(*args, **kwargs):
            yield ("thinking", "reasoning here")

        with patch("apps.agent.services.model_tester.get_llm_client") as mock_factory:
            mock_client = MagicMock()
            mock_client.stream_with_thinking = fake_stream
            mock_factory.return_value = mock_client

            result = await _test_thinking("openai", "sk-test", "deepseek-r1")

        assert result["success"] is True
        # Actual message: "支持思考模式 (reasoning_content)"
        assert "reasoning_content" in result["message"]

    async def test_timeout(self):
        with patch("apps.agent.services.model_tester.get_llm_client") as mock_factory:
            mock_client = MagicMock()

            async def timeout_stream(*args, **kwargs):
                raise Exception("Request timed out")
                yield  # make it an async generator

            mock_client.stream_with_thinking = timeout_stream
            mock_factory.return_value = mock_client

            result = await _test_thinking("anthropic", "sk-test", "claude-opus-4-7")

        assert result["success"] is False
        # The inner except catches this (not outer), so latency_ms is computed, not None
        assert result["latency_ms"] is not None
        assert "不支持思考能力" in result["message"]


class TestTestVision:
    async def test_success(self):
        with patch("apps.agent.services.model_tester.get_llm_client") as mock_factory:
            mock_client = MagicMock()
            mock_client.complete_vision = AsyncMock(return_value="image description")
            mock_factory.return_value = mock_client

            result = await _test_vision("anthropic", "sk-test", "claude-opus-4-7")

        assert result["success"] is True

    async def test_400_treated_as_success(self):
        with patch("apps.agent.services.model_tester.get_llm_client") as mock_factory:
            mock_client = MagicMock()
            mock_client.complete_vision = AsyncMock(
                side_effect=Exception("400 invalid_request")
            )
            mock_factory.return_value = mock_client

            result = await _test_vision("anthropic", "sk-test", "claude-opus-4-7")

        assert result["success"] is True

    async def test_timeout(self):
        with patch("apps.agent.services.model_tester.get_llm_client") as mock_factory:
            mock_client = MagicMock()
            mock_client.complete_vision = AsyncMock(
                side_effect=Exception("timed out after 120s")
            )
            mock_factory.return_value = mock_client

            result = await _test_vision("anthropic", "sk-test", "claude-opus-4-7")

        assert result["success"] is False
        assert result["latency_ms"] is None


class TestTestVisionOcr:
    async def test_high_accuracy(self):
        with patch("apps.agent.services.model_tester.get_llm_client") as mock_factory:
            mock_client = MagicMock()
            # Return exact expected text → 100% accuracy
            mock_client.complete_vision = AsyncMock(return_value="这是一个测试文本~")
            mock_factory.return_value = mock_client

            result = await _test_vision_ocr("anthropic", "sk-test", "claude-opus-4-7")

        assert result["success"] is True
        assert "100%" in result["message"]

    async def test_low_accuracy(self):
        with patch("apps.agent.services.model_tester.get_llm_client") as mock_factory:
            mock_client = MagicMock()
            # Return text with ~11% LCS accuracy against "这是一个测试文本~"
            mock_client.complete_vision = AsyncMock(return_value="完全不同的文字内容xyz")
            mock_factory.return_value = mock_client

            result = await _test_vision_ocr("anthropic", "sk-test", "claude-opus-4-7")

        assert result["success"] is False
        assert "80%" in result["message"]

    async def test_timeout(self):
        with patch("apps.agent.services.model_tester.get_llm_client") as mock_factory:
            mock_client = MagicMock()
            mock_client.complete_vision = AsyncMock(
                side_effect=Exception("timed out")
            )
            mock_factory.return_value = mock_client

            result = await _test_vision_ocr("anthropic", "sk-test", "claude-opus-4-7")

        assert result["success"] is False
        assert result["latency_ms"] is None
