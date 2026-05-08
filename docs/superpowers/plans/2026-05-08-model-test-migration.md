# Model Test Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Migrate LLM model-test logic from backend `ai_config.py` into a new stateless agent endpoint `POST /test/model`, so all LLM interactions live in the agent module.

**Architecture:** Backend reads AI config from DB, decrypts the API key, then calls `POST {AGENT_BASE_URL}/test/model` with raw credentials. Agent runs the four tests using a temporary `LLMClient` instance and returns results. Backend persists results to `AIProviderTestResult` and returns the same `AIConfigTestResult` JSON to the frontend as before.

**Tech Stack:** Python 3.11, FastAPI, Pydantic v2, httpx, Anthropic SDK, OpenAI SDK

---

## File Map

| Action | Path |
|--------|------|
| Create | `agent/schemas/model_test.py` |
| Create | `agent/services/model_tester.py` |
| Create | `agent/routers/model_test.py` |
| Modify | `agent/app/main.py` |
| Create | `agent/tests/unit/test_model_tester.py` |
| Modify | `backend/app/routers/ai_config.py` |
| Create | `backend/app/services/vision_test_image.py` → already exists, no change needed |

---

### Task 1: Agent schemas

**Files:**
- Create: `agent/schemas/model_test.py`

- [ ] **Step 1: Create the file**

```python
"""Schemas for POST /test/model endpoint."""

from pydantic import BaseModel


class ModelTestRequest(BaseModel):
    provider: str                       # "anthropic" | "openai"
    api_key: str                        # plaintext, decrypted by backend before sending
    model_id: str
    base_url: str | None = None
    vision_model_id: str | None = None
    test_types: list[str]               # subset of ["connection","thinking","vision","vision_ocr"]


class ModelTestResult(BaseModel):
    connected: bool
    message: str
    latency_ms: int | None = None
    thinking_success: bool | None = None
    thinking_message: str | None = None
    thinking_latency_ms: int | None = None
    vision_success: bool | None = None
    vision_message: str | None = None
    vision_latency_ms: int | None = None
    vision_text_success: bool | None = None
    vision_text_message: str | None = None
    vision_text_latency_ms: int | None = None
```

- [ ] **Step 2: Verify import works**

```bash
cd /Users/vincentruan/geek_space/github/numina/agent
uv run python -c "from schemas.model_test import ModelTestRequest, ModelTestResult; print('ok')"
```

Expected: `ok`

- [ ] **Step 3: Commit**

```bash
git add agent/schemas/model_test.py
git commit -m "feat(agent): add ModelTestRequest/ModelTestResult schemas"
```


---

### Task 2: Agent model_tester service

**Files:**
- Create: `agent/services/model_tester.py`

This file migrates the four `_test_*` functions from `backend/app/routers/ai_config.py`. Key differences from the backend version:
- Uses `LLMClient` (from `core/llm.py`) instead of raw httpx calls
- Accepts plain parameters instead of a `_CfgProxy` object
- The OCR image data comes from a copy of `backend/app/services/vision_test_image.py` placed at `agent/services/vision_test_image.py`

- [ ] **Step 1: Copy vision_test_image helper into agent**

```bash
cp backend/app/services/vision_test_image.py agent/services/vision_test_image.py
```

- [ ] **Step 2: Create `agent/services/model_tester.py`**

```python
"""Stateless model capability tests for POST /test/model."""

import json
import time

from core.llm import LLMClient, get_llm_client
from services.vision_test_image import get_expected_ocr_text, get_test_image_data_url


def _make_client(
    provider: str,
    api_key: str,
    model_id: str,
    base_url: str | None,
    vision_model_id: str | None,
    timeout: float,
) -> LLMClient:
    return get_llm_client(
        provider=provider,
        api_key=api_key,
        model_id=model_id,
        vision_model_id=vision_model_id,
        base_url=base_url,
        timeout=timeout,
    )


async def test_connection(
    provider: str,
    api_key: str,
    model_id: str,
    base_url: str | None = None,
) -> dict:
    """Test main model connectivity (30s timeout)."""
    start = time.monotonic()
    try:
        client = _make_client(provider, api_key, model_id, base_url, None, 30.0)
        await client.complete("hi", max_tokens=1)
        latency = int((time.monotonic() - start) * 1000)
        return {"connected": True, "message": "主模型连接成功", "latency_ms": latency}
    except Exception as e:
        msg = str(e)
        if "timeout" in msg.lower() or "timed out" in msg.lower():
            return {"connected": False, "message": "主模型连接超时（30秒）", "latency_ms": None}
        return {"connected": False, "message": f"主模型连接失败: {msg}", "latency_ms": None}


async def test_thinking(
    provider: str,
    api_key: str,
    model_id: str,
    base_url: str | None = None,
) -> dict:
    """Test extended thinking capability (120s timeout)."""
    start = time.monotonic()
    try:
        client = _make_client(provider, api_key, model_id, base_url, None, 120.0)
        if provider == "anthropic":
            # Collect stream; any response (including 400 invalid_request) means thinking is wired
            chunks = []
            try:
                async for block_type, chunk in client.stream_with_thinking(
                    "think", max_tokens=1024, thinking_budget=100
                ):
                    chunks.append((block_type, chunk))
                latency = int((time.monotonic() - start) * 1000)
                return {"success": True, "message": "支持思考能力", "latency_ms": latency}
            except Exception as inner:
                latency = int((time.monotonic() - start) * 1000)
                msg = str(inner)
                # invalid_request_error means API accepted the thinking param
                if "invalid_request_error" in msg or "thinking" in msg.lower():
                    return {"success": True, "message": "支持思考能力", "latency_ms": latency}
                return {"success": False, "message": "不支持思考能力", "latency_ms": latency}
        else:
            # OpenAI-compatible: stream and detect reasoning_content or <think> tags
            has_reasoning = False
            has_think_tag = False
            content_buf = ""
            async for block_type, chunk in client.stream_with_thinking(
                "1+1=?", max_tokens=50
            ):
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


async def test_vision(
    provider: str,
    api_key: str,
    vision_model_id: str,
    base_url: str | None = None,
) -> dict:
    """Test vision model connectivity (120s timeout)."""
    start = time.monotonic()
    try:
        client = _make_client(provider, api_key, vision_model_id, base_url, vision_model_id, 120.0)
        # Use a minimal base64 1x1 PNG to avoid external URL dependency
        import base64
        tiny_png = base64.b64encode(
            bytes.fromhex(
                "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4"
                "890000000a49444154789c6260000000020001e221bc330000000049454e44ae426082"
            )
        ).decode()
        await client.complete_vision("what", tiny_png, max_tokens=1)
        latency = int((time.monotonic() - start) * 1000)
        return {"success": True, "message": "图像模型连接成功", "latency_ms": latency}
    except Exception as e:
        msg = str(e)
        if "timeout" in msg.lower() or "timed out" in msg.lower():
            return {"success": False, "message": "图像模型连接超时（120秒）", "latency_ms": None}
        # 400 from API means model accepted the vision request format
        if "400" in msg or "invalid_request" in msg.lower():
            latency = int((time.monotonic() - start) * 1000)
            return {"success": True, "message": "图像模型连接成功", "latency_ms": latency}
        return {"success": False, "message": f"图像模型连接失败: {msg}", "latency_ms": None}


def _calculate_ocr_accuracy(recognized: str, expected: str) -> float:
    """LCS-based OCR accuracy (same algorithm as backend)."""
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


async def test_vision_ocr(
    provider: str,
    api_key: str,
    vision_model_id: str,
    base_url: str | None = None,
) -> dict:
    """Test vision OCR accuracy with embedded test image (120s timeout)."""
    start = time.monotonic()
    test_image_url = get_test_image_data_url()
    expected_text = get_expected_ocr_text()
    image_data = test_image_url.replace("data:image/png;base64,", "")
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
```

- [ ] **Step 3: Verify import**

```bash
cd /Users/vincentruan/geek_space/github/numina/agent
uv run python -c "from services.model_tester import test_connection; print('ok')"
```

Expected: `ok`

- [ ] **Step 4: Commit**

```bash
git add agent/services/vision_test_image.py agent/services/model_tester.py
git commit -m "feat(agent): add model_tester service with four LLM test functions"
```


---

### Task 3: Agent router and registration

**Files:**
- Create: `agent/routers/model_test.py`
- Modify: `agent/app/main.py`

- [ ] **Step 1: Create `agent/routers/model_test.py`**

```python
"""POST /test/model — stateless model capability test endpoint."""

import logging

from fastapi import APIRouter, Header, HTTPException

from app.config import settings
from schemas.model_test import ModelTestRequest, ModelTestResult
from services.model_tester import (
    test_connection,
    test_thinking,
    test_vision,
    test_vision_ocr,
)

router = APIRouter(prefix="/test", tags=["model-test"])
logger = logging.getLogger(__name__)


@router.post("/model", response_model=ModelTestResult)
async def run_model_test(
    req: ModelTestRequest,
    x_agent_token: str = Header(..., alias="X-Agent-Token"),
) -> ModelTestResult:
    """Run model capability tests with provided credentials (called by backend)."""
    if x_agent_token != settings.AGENT_INTERNAL_TOKEN:
        raise HTTPException(status_code=401, detail="invalid token")

    vision_model = req.vision_model_id or req.model_id

    # 1. Connection (always)
    conn = await test_connection(req.provider, req.api_key, req.model_id, req.base_url)

    # 2. Thinking (only if connection succeeded)
    think = None
    if "thinking" in req.test_types and conn["connected"]:
        think = await test_thinking(req.provider, req.api_key, req.model_id, req.base_url)

    # 3. Vision (only if vision_model_id differs from model_id)
    vis = None
    if (
        "vision" in req.test_types
        and req.vision_model_id
        and req.vision_model_id != req.model_id
    ):
        vis = await test_vision(req.provider, req.api_key, req.vision_model_id, req.base_url)

    # 4. Vision OCR (always when requested)
    ocr = None
    if "vision_ocr" in req.test_types:
        ocr = await test_vision_ocr(req.provider, req.api_key, vision_model, req.base_url)

    return ModelTestResult(
        connected=conn["connected"],
        message=conn["message"],
        latency_ms=conn.get("latency_ms"),
        thinking_success=think["success"] if think else None,
        thinking_message=think["message"] if think else None,
        thinking_latency_ms=think.get("latency_ms") if think else None,
        vision_success=vis["success"] if vis else None,
        vision_message=vis["message"] if vis else None,
        vision_latency_ms=vis.get("latency_ms") if vis else None,
        vision_text_success=ocr["success"] if ocr else None,
        vision_text_message=ocr["message"] if ocr else None,
        vision_text_latency_ms=ocr.get("latency_ms") if ocr else None,
    )
```

- [ ] **Step 2: Register router in `agent/app/main.py`**

Add after the existing router imports (around line 50):

```python
from routers import model_test as model_test_router
```

Add after the existing `app.include_router(...)` calls (around line 62):

```python
app.include_router(model_test_router.router)
```

- [ ] **Step 3: Verify import**

```bash
cd /Users/vincentruan/geek_space/github/numina/agent
uv run python -c "from routers.model_test import router; print('ok')"
```

Expected: `ok`

- [ ] **Step 4: Commit**

```bash
git add agent/routers/model_test.py agent/app/main.py
git commit -m "feat(agent): add POST /test/model endpoint"
```


---

### Task 4: Agent unit tests

**Files:**
- Create: `agent/tests/unit/test_model_tester.py`

- [ ] **Step 1: Create the test file**

```python
"""Unit tests for services/model_tester.py."""

import sys
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from services.model_tester import (
    _calculate_ocr_accuracy,
    test_connection,
    test_thinking,
    test_vision,
    test_vision_ocr,
)


# ---------------------------------------------------------------------------
# _calculate_ocr_accuracy
# ---------------------------------------------------------------------------

class TestCalculateOcrAccuracy:
    def test_exact_match(self):
        assert _calculate_ocr_accuracy("abc", "abc") == 1.0

    def test_empty_expected(self):
        assert _calculate_ocr_accuracy("", "") == 1.0
        assert _calculate_ocr_accuracy("abc", "") == 0.0

    def test_partial_match(self):
        # LCS("ab", "abc") = 2, expected len = 3 → 2/3
        acc = _calculate_ocr_accuracy("ab", "abc")
        assert abs(acc - 2 / 3) < 0.001

    def test_no_match(self):
        acc = _calculate_ocr_accuracy("xyz", "abc")
        assert acc == 0.0


# ---------------------------------------------------------------------------
# test_connection
# ---------------------------------------------------------------------------

class TestTestConnection:
    @pytest.mark.asyncio
    async def test_success(self):
        with patch("services.model_tester.get_llm_client") as mock_factory:
            mock_client = MagicMock()
            mock_client.complete = AsyncMock(return_value="hi")
            mock_factory.return_value = mock_client

            result = await test_connection("anthropic", "sk-test", "claude-3-5-haiku-20241022")

        assert result["connected"] is True
        assert result["latency_ms"] is not None

    @pytest.mark.asyncio
    async def test_timeout(self):
        with patch("services.model_tester.get_llm_client") as mock_factory:
            mock_client = MagicMock()
            mock_client.complete = AsyncMock(side_effect=Exception("Request timed out"))
            mock_factory.return_value = mock_client

            result = await test_connection("anthropic", "sk-test", "claude-3-5-haiku-20241022")

        assert result["connected"] is False
        assert "超时" in result["message"]
        assert result["latency_ms"] is None

    @pytest.mark.asyncio
    async def test_generic_failure(self):
        with patch("services.model_tester.get_llm_client") as mock_factory:
            mock_client = MagicMock()
            mock_client.complete = AsyncMock(side_effect=Exception("401 Unauthorized"))
            mock_factory.return_value = mock_client

            result = await test_connection("anthropic", "bad-key", "claude-3-5-haiku-20241022")

        assert result["connected"] is False
        assert "401" in result["message"]


# ---------------------------------------------------------------------------
# test_thinking
# ---------------------------------------------------------------------------

class TestTestThinking:
    @pytest.mark.asyncio
    async def test_anthropic_success(self):
        async def fake_stream(*args, **kwargs):
            yield ("thinking", "some thought")
            yield ("text", "answer")

        with patch("services.model_tester.get_llm_client") as mock_factory:
            mock_client = MagicMock()
            mock_client.stream_with_thinking = fake_stream
            mock_factory.return_value = mock_client

            result = await test_thinking("anthropic", "sk-test", "claude-opus-4-7")

        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_openai_reasoning_content(self):
        async def fake_stream(*args, **kwargs):
            yield ("thinking", "reasoning here")

        with patch("services.model_tester.get_llm_client") as mock_factory:
            mock_client = MagicMock()
            mock_client.stream_with_thinking = fake_stream
            mock_factory.return_value = mock_client

            result = await test_thinking("openai", "sk-test", "deepseek-r1")

        assert result["success"] is True
        assert "reasoning_content" in result["message"]

    @pytest.mark.asyncio
    async def test_timeout(self):
        with patch("services.model_tester.get_llm_client") as mock_factory:
            mock_client = MagicMock()

            async def timeout_stream(*args, **kwargs):
                raise Exception("Request timed out")
                yield  # make it a generator

            mock_client.stream_with_thinking = timeout_stream
            mock_factory.return_value = mock_client

            result = await test_thinking("anthropic", "sk-test", "claude-opus-4-7")

        assert result["success"] is False
        assert result["latency_ms"] is None


# ---------------------------------------------------------------------------
# test_vision
# ---------------------------------------------------------------------------

class TestTestVision:
    @pytest.mark.asyncio
    async def test_success(self):
        with patch("services.model_tester.get_llm_client") as mock_factory:
            mock_client = MagicMock()
            mock_client.complete_vision = AsyncMock(return_value="image description")
            mock_factory.return_value = mock_client

            result = await test_vision("anthropic", "sk-test", "claude-opus-4-7")

        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_400_treated_as_success(self):
        with patch("services.model_tester.get_llm_client") as mock_factory:
            mock_client = MagicMock()
            mock_client.complete_vision = AsyncMock(
                side_effect=Exception("400 invalid_request")
            )
            mock_factory.return_value = mock_client

            result = await test_vision("anthropic", "sk-test", "claude-opus-4-7")

        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_timeout(self):
        with patch("services.model_tester.get_llm_client") as mock_factory:
            mock_client = MagicMock()
            mock_client.complete_vision = AsyncMock(
                side_effect=Exception("timed out after 120s")
            )
            mock_factory.return_value = mock_client

            result = await test_vision("anthropic", "sk-test", "claude-opus-4-7")

        assert result["success"] is False
        assert result["latency_ms"] is None


# ---------------------------------------------------------------------------
# test_vision_ocr
# ---------------------------------------------------------------------------

class TestTestVisionOcr:
    @pytest.mark.asyncio
    async def test_high_accuracy(self):
        with patch("services.model_tester.get_llm_client") as mock_factory:
            mock_client = MagicMock()
            mock_client.complete_vision = AsyncMock(return_value="这是一个测试文本~")
            mock_factory.return_value = mock_client

            result = await test_vision_ocr("anthropic", "sk-test", "claude-opus-4-7")

        assert result["success"] is True
        assert "100%" in result["message"]

    @pytest.mark.asyncio
    async def test_low_accuracy(self):
        with patch("services.model_tester.get_llm_client") as mock_factory:
            mock_client = MagicMock()
            mock_client.complete_vision = AsyncMock(return_value="完全不同的文字")
            mock_factory.return_value = mock_client

            result = await test_vision_ocr("anthropic", "sk-test", "claude-opus-4-7")

        assert result["success"] is False
        assert "80%" in result["message"]

    @pytest.mark.asyncio
    async def test_timeout(self):
        with patch("services.model_tester.get_llm_client") as mock_factory:
            mock_client = MagicMock()
            mock_client.complete_vision = AsyncMock(
                side_effect=Exception("timed out")
            )
            mock_factory.return_value = mock_client

            result = await test_vision_ocr("anthropic", "sk-test", "claude-opus-4-7")

        assert result["success"] is False
        assert result["latency_ms"] is None
```

- [ ] **Step 2: Run tests**

```bash
cd /Users/vincentruan/geek_space/github/numina/agent
uv run pytest tests/unit/test_model_tester.py -v
```

Expected: all tests pass.

- [ ] **Step 3: Commit**

```bash
git add agent/tests/unit/test_model_tester.py
git commit -m "test(agent): add unit tests for model_tester service"
```


---

### Task 5: Backend — refactor test_ai_config to call agent

**Files:**
- Modify: `backend/app/routers/ai_config.py`

The goal is to replace the body of `test_ai_config` (lines 258–348) and delete the four private functions `_test_connection`, `_test_thinking`, `_test_vision_model`, `_test_vision_text_ocr`, and `_calculate_ocr_accuracy` (lines 351–731). The `_build_endpoint` helper and the `vision_test_image` imports are no longer needed either.

- [ ] **Step 1: Replace `test_ai_config` body**

Find the function at line 258. Replace the entire function body (keeping the decorator and signature) with:

```python
@router.post("/config/{config_id}/test", response_model=AIConfigTestResult)
async def test_ai_config(
    config_id: int,
    current_user: User = Depends(require_owner),
    db: Session = Depends(get_db),
) -> AIConfigTestResult:
    """测试指定 AI 配置的连通性和模型能力（仅 owner）。"""
    cfg = (
        db.query(AIProviderConfig)
        .filter(
            AIProviderConfig.id == config_id,
            AIProviderConfig.family_id == current_user.family_id,
        )
        .first()
    )
    if not cfg:
        raise AppError(ErrorCode.FAMILY_NOT_FOUND)

    if not cfg.api_key_encrypted:
        return AIConfigTestResult(connected=False, message="未配置 API Key")

    api_key = decrypt_api_key(cfg.api_key_encrypted)
    if not api_key:
        return AIConfigTestResult(connected=False, message="API Key 解密失败，请重新配置")

    api_key = api_key.strip()
    if not cfg.model_id:
        return AIConfigTestResult(connected=False, message="未配置主模型 ID")

    async with httpx.AsyncClient(timeout=300.0) as client:
        try:
            resp = await client.post(
                f"{settings.AGENT_BASE_URL}/test/model",
                headers={
                    "X-Agent-Token": settings.AGENT_INTERNAL_TOKEN,
                    "Content-Type": "application/json",
                },
                json={
                    "provider": cfg.provider,
                    "api_key": api_key,
                    "model_id": cfg.model_id,
                    "base_url": cfg.base_url,
                    "vision_model_id": cfg.vision_model_id,
                    "test_types": ["connection", "thinking", "vision", "vision_ocr"],
                },
            )
            resp.raise_for_status()
            data = resp.json()
        except httpx.HTTPStatusError as e:
            return AIConfigTestResult(
                connected=False,
                message=f"Agent 服务返回错误: HTTP {e.response.status_code}",
            )
        except Exception as e:
            return AIConfigTestResult(connected=False, message=f"无法连接 Agent 服务: {e}")

    def _upsert_test(test_type: str, success: bool | None, message: str, latency_ms: int | None) -> None:
        existing = db.query(AIProviderTestResult).filter_by(config_id=cfg.id, test_type=test_type).first()
        if existing:
            existing.success = success
            existing.message = message
            existing.latency_ms = latency_ms
            existing.tested_at = datetime.utcnow()
        else:
            db.add(AIProviderTestResult(
                config_id=cfg.id,
                test_type=test_type,
                success=success,
                message=message,
                latency_ms=latency_ms,
            ))
        db.commit()

    _upsert_test("main", data["connected"], data["message"], data.get("latency_ms"))
    if data.get("thinking_success") is not None:
        _upsert_test("thinking", data["thinking_success"], data.get("thinking_message", ""), data.get("thinking_latency_ms"))
    if data.get("vision_success") is not None:
        _upsert_test("vision", data["vision_success"], data.get("vision_message", ""), data.get("vision_latency_ms"))
    if data.get("vision_text_success") is not None:
        _upsert_test("vision_text", data["vision_text_success"], data.get("vision_text_message", ""), data.get("vision_text_latency_ms"))

    return AIConfigTestResult(
        connected=data["connected"],
        message=data["message"],
        latency_ms=data.get("latency_ms"),
        thinking_success=data.get("thinking_success"),
        thinking_message=data.get("thinking_message"),
        thinking_latency_ms=data.get("thinking_latency_ms"),
        vision_success=data.get("vision_success"),
        vision_message=data.get("vision_message"),
        vision_latency_ms=data.get("vision_latency_ms"),
        vision_text_success=data.get("vision_text_success"),
        vision_text_message=data.get("vision_text_message"),
        vision_text_latency_ms=data.get("vision_text_latency_ms"),
    )
```

- [ ] **Step 2: Delete the four private test functions and helpers**

Delete from `ai_config.py`:
- `_build_endpoint` function
- `_test_connection` function
- `_test_thinking` function
- `_test_vision_model` function
- `_test_vision_text_ocr` function
- `_calculate_ocr_accuracy` function

Also remove these now-unused imports from the top of the file:
```python
# Remove these lines:
from app.services.vision_test_image import (
    get_expected_ocr_text,
    get_test_image_data_url,
)
```

Keep `import httpx` — it is still used by the new agent call.
Keep `import time` only if used elsewhere in the file; otherwise remove it.

- [ ] **Step 3: Lint and type-check**

```bash
cd /Users/vincentruan/geek_space/github/numina/backend
uv run ruff check app/routers/ai_config.py --fix
uv run mypy app/routers/ai_config.py
```

Expected: no errors.

- [ ] **Step 4: Run backend tests**

```bash
cd /Users/vincentruan/geek_space/github/numina/backend
uv run pytest tests/ -v -k "ai_config"
```

Expected: all pass (or no tests exist for this router yet — that is acceptable).

- [ ] **Step 5: Commit**

```bash
git add backend/app/routers/ai_config.py
git commit -m "refactor(backend): delegate model tests to agent, remove direct LLM calls"
```


---

### Task 6: Final verification

- [ ] **Step 1: Run all agent tests**

```bash
cd /Users/vincentruan/geek_space/github/numina/agent
uv run pytest tests/ -v
```

Expected: all pass.

- [ ] **Step 2: Run agent type check**

```bash
cd /Users/vincentruan/geek_space/github/numina/agent
uv run mypy . --exclude vendor
```

Expected: no new errors.

- [ ] **Step 3: Run all backend tests**

```bash
cd /Users/vincentruan/geek_space/github/numina/backend
uv run pytest tests/ -v
```

Expected: all pass.

- [ ] **Step 4: Run backend type check**

```bash
cd /Users/vincentruan/geek_space/github/numina/backend
uv run mypy app/
```

Expected: no new errors.

- [ ] **Step 5: Verify response schema parity**

Confirm `ModelTestResult` fields in `agent/schemas/model_test.py` match `AIConfigTestResult` fields in `backend/app/schemas/ai_config.py` exactly (same field names, same types, same nullability).

- [ ] **Step 6: Final commit if any loose files**

```bash
git status
# Stage and commit any remaining changes
```

