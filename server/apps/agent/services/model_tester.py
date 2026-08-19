"""Stateless model capability tests for POST /test/model."""

import base64
import time

from apps.agent.core.llm import get_llm_client
from apps.agent.services.vision_test_image import (
    get_expected_ocr_text,
    get_test_image_data_url,
)


def _extract_error_detail(exc: Exception) -> dict:
    """Extract structured error detail from an LLM/API exception.

    Returns a dict with status_code, error_type, and error_body for
    API errors, or a minimal dict with just error_type for other errors.
    """
    detail: dict = {"error_type": type(exc).__name__}
    status = getattr(exc, "status_code", None)
    if isinstance(status, int):
        detail["status_code"] = status
    body = getattr(exc, "body", None)
    if body is not None:
        try:
            if hasattr(body, "model_dump"):
                detail["error_body"] = body.model_dump()
            elif isinstance(body, dict):
                detail["error_body"] = body
            else:
                detail["error_body"] = {"raw": str(body)}
        except Exception:
            detail["error_body"] = {"raw": str(body)}
    return detail


def _make_client(provider, api_key, model_id, base_url, vision_model_id, timeout):
    return get_llm_client(
        provider=provider,
        api_key=api_key,
        model_id=model_id,
        vision_model_id=vision_model_id,
        base_url=base_url,
        timeout=timeout,
    )


async def test_connection(provider, api_key, model_id, base_url=None):
    """Test main model connectivity (30s timeout)."""
    start = time.monotonic()
    try:
        client = _make_client(provider, api_key, model_id, base_url, None, 30.0)
        # max_tokens=10 (not 1): DeepSeek models have intrinsic reasoning
        # that consumes the token budget for ThinkingBlock before producing
        # TextBlock. With max_tokens=1, all tokens go to thinking and the
        # response contains no text block, causing a false connection
        # failure. 10 tokens leaves enough budget for both.
        await client.complete("hi", max_tokens=10)
        latency = int((time.monotonic() - start) * 1000)
        return {"connected": True, "message": "主模型连接成功", "latency_ms": latency}
    except Exception as e:
        msg = str(e)
        if "timeout" in msg.lower() or "timed out" in msg.lower():
            return {"connected": False, "message": "主模型连接超时（30秒）", "latency_ms": None}
        return {
            "connected": False,
            "message": f"主模型连接失败: {msg}",
            "latency_ms": None,
            "error_detail": _extract_error_detail(e),
        }


async def test_thinking(provider, api_key, model_id, base_url=None):
    """Test extended thinking capability (120s timeout)."""
    start = time.monotonic()
    try:
        client = _make_client(provider, api_key, model_id, base_url, None, 120.0)
        if provider == "anthropic":
            try:
                has_thinking_block = False
                async for block_type, _chunk in client.stream_with_thinking(
                    "think", max_tokens=1024, thinking_budget=100
                ):
                    if block_type == "thinking":
                        has_thinking_block = True
                        break
                latency = int((time.monotonic() - start) * 1000)
                if has_thinking_block:
                    return {"success": True, "message": "支持思考能力", "latency_ms": latency}
                else:
                    return {"success": True, "message": "主模型可调用（未检测到思考块）", "latency_ms": latency}
            except Exception as inner:
                latency = int((time.monotonic() - start) * 1000)
                msg = str(inner)
                if "invalid_request_error" in msg or "thinking" in msg.lower():
                    return {"success": True, "message": "支持思考能力", "latency_ms": latency}
                return {"success": False, "message": "不支持思考能力", "latency_ms": latency}
        else:
            has_reasoning = False
            has_think_tag = False
            content_buf = ""
            async for block_type, chunk in client.stream_with_thinking("1+1=?", max_tokens=50):
                if block_type == "thinking":
                    has_reasoning = True
                    break
                content_buf += chunk
                if "<think>" in content_buf:
                    has_think_tag = True
                    break
            latency = int((time.monotonic() - start) * 1000)
            if has_reasoning:
                return {"success": True, "message": "支持思考模式 (reasoning_content)", "latency_ms": latency}
            elif has_think_tag:
                return {"success": True, "message": "支持思考模式 (<think> 标签)", "latency_ms": latency}
            else:
                return {"success": True, "message": "模型可用（未检测到思考输出）", "latency_ms": latency}
    except Exception as e:
        msg = str(e)
        if "timeout" in msg.lower() or "timed out" in msg.lower():
            return {"success": False, "message": "思考能力测试超时（120秒）", "latency_ms": None}
        return {"success": False, "message": f"思考能力测试失败: {msg}", "latency_ms": None}


async def test_vision(provider, api_key, vision_model_id, base_url=None):
    """Test vision model connectivity (120s timeout)."""
    start = time.monotonic()
    tiny_png = base64.b64encode(
        bytes.fromhex(
            "89504e470d0a1a0a0000000d494844520000000100000001"
            "08060000001f15c4890000000a49444154789c6260000000"
            "020001e221bc330000000049454e44ae426082"
        )
    ).decode()
    try:
        client = _make_client(provider, api_key, vision_model_id, base_url, vision_model_id, 120.0)
        # max_tokens=10 (not 1): same reasoning as test_connection —
        # DeepSeek's intrinsic thinking may consume the entire budget.
        await client.complete_vision("what", tiny_png, max_tokens=10)
        latency = int((time.monotonic() - start) * 1000)
        return {"success": True, "message": "图像模型连接成功", "latency_ms": latency}
    except Exception as e:
        msg = str(e)
        if "timeout" in msg.lower() or "timed out" in msg.lower():
            return {"success": False, "message": "图像模型连接超时（120秒）", "latency_ms": None}
        if "400" in msg or "invalid_request" in msg.lower():
            latency = int((time.monotonic() - start) * 1000)
            return {"success": True, "message": "图像模型连接成功", "latency_ms": latency}
        return {"success": False, "message": f"图像模型连接失败: {msg}", "latency_ms": None}


def _calculate_ocr_accuracy(recognized, expected):
    """LCS-based OCR accuracy."""
    recognized_clean = recognized.strip()
    expected_clean = expected.strip()
    if not expected_clean:
        return 1.0 if not recognized_clean else 0.0
    if recognized_clean == expected_clean:
        return 1.0
    m, n = len(recognized_clean), len(expected_clean)
    dp = [[0] * (n + 1) for _ in range(m + 1)]
    for i in range(1, m + 1):
        for j in range(1, n + 1):
            if recognized_clean[i - 1] == expected_clean[j - 1]:
                dp[i][j] = dp[i - 1][j - 1] + 1
            else:
                dp[i][j] = max(dp[i - 1][j], dp[i][j - 1])
    return dp[m][n] / n


async def test_vision_ocr(provider, api_key, vision_model_id, base_url=None):
    """Test vision OCR accuracy with embedded test image (120s timeout)."""
    start = time.monotonic()
    test_image_url = get_test_image_data_url()
    expected_text = get_expected_ocr_text()
    image_data = test_image_url.split(",", 1)[-1]
    try:
        client = _make_client(provider, api_key, vision_model_id, base_url, vision_model_id, 120.0)
        recognized = await client.complete_vision("请识别图片中的文字内容", image_data, max_tokens=100)
        latency = int((time.monotonic() - start) * 1000)
        accuracy = _calculate_ocr_accuracy(recognized, expected_text)
        if accuracy >= 0.8:
            return {"success": True, "message": f"OCR 准确度 {accuracy:.0%}", "latency_ms": latency}
        else:
            return {"success": False, "message": f"OCR 准确度 {accuracy:.0%}，低于 80% 阈值", "latency_ms": latency}
    except Exception as e:
        msg = str(e)
        if "timeout" in msg.lower() or "timed out" in msg.lower():
            return {"success": False, "message": "OCR 测试超时（120秒）", "latency_ms": None}
        return {"success": False, "message": f"OCR 测试失败: {msg}", "latency_ms": None}
