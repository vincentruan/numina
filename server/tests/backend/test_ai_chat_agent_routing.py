"""ADV-001 backend regression: /chat/stream proxy branches on agent_id.

Pins the contract that POST /api/v1/ai/chat/stream routes to the agent-dispatch
endpoint (/agent/{agent_id}/stream) when agent_id is in the body, and falls
back to the legacy chat_adapter (/chat/ask/stream) otherwise. Pre-fix the
proxy always hit /chat/ask/stream regardless of which agent the frontend
selected, so _resolve_skills was unreachable from production traffic.
"""

import pytest

from apps.backend.app.models.ai_provider_config import AIProviderConfig
from apps.backend.app.models.user import User


@pytest.fixture
def ai_enabled(db, auth_headers):
    """require_ai_enabled gates the chat endpoint — seed a provider config so
    the family registers as AI-enabled."""
    user = db.query(User).filter_by(username="testuser").first()
    assert user is not None
    db.add(
        AIProviderConfig(
            family_id=user.family_id,
            name="测试配置",
            provider="anthropic",
            api_key_encrypted="test_encrypted_key",
            model_id="claude-3-5-sonnet-20241022",
            is_active=True,
        )
    )
    db.commit()


class _FakeStreamResponse:
    """httpx.AsyncClient.stream() returns an async context manager whose value
    has `aiter_lines()`, `aiter_text()`, and `aiter_bytes()` iterators.
    This stub returns a single SSE end event so the proxy stream terminates."""

    def __init__(self):
        self.status_code = 200

    async def aiter_text(self):
        if False:
            yield ""  # pragma: no cover

    async def aiter_bytes(self):
        yield b"event: end\ndata: null\n\n"

    async def aiter_lines(self):
        yield '{"type":"capability.end","result":{"summary":""}}'

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return None


class _FakeAsyncClient:
    """Stand-in for httpx.AsyncClient. Captures the (url, body) of the .stream
    call so tests can assert which path the proxy took."""

    captured: dict = {}

    def __init__(self, *_args, **_kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return None

    def build_request(self, method, url, **kwargs):
        """AgentClient.stream() calls build_request before stream()."""
        from unittest.mock import MagicMock
        req = MagicMock()
        req.method = method
        req.url = url
        req.content = kwargs.pop("content", None)
        req.headers = kwargs.pop("headers", {})
        # Preserve remaining kwargs (json, etc.) for capture
        self._build_kwargs = kwargs
        return req

    def stream(self, method, url, *, content, headers, **kwargs):
        _FakeAsyncClient.captured["method"] = method
        _FakeAsyncClient.captured["url"] = url
        _FakeAsyncClient.captured["headers"] = headers
        # Merge kwargs captured from build_request
        if hasattr(self, "_build_kwargs"):
            _FakeAsyncClient.captured["json"] = self._build_kwargs.get("json")
            _FakeAsyncClient.captured["content"] = self._build_kwargs.get("content")
        else:
            _FakeAsyncClient.captured["json"] = kwargs.get("json")
        return _FakeStreamResponse()


@pytest.fixture
def patched_httpx(monkeypatch):
    _FakeAsyncClient.captured = {}
    monkeypatch.setattr(
        "apps.backend.app.services.agent_client.httpx.AsyncClient",
        _FakeAsyncClient,
    )
    yield _FakeAsyncClient.captured


def test_chat_stream_without_agent_id_proxies_to_runs_stream_with_numina_fallback(
    client, auth_headers, ai_enabled, patched_httpx
):
    """When agent_id is absent, the proxy hits /runs/stream with NUMINA_AGENT_ID."""
    resp = client.post(
        "/api/v1/ai/chat/stream",
        json={"question": "hello", "deep_think": False, "web_search": False},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    captured = patched_httpx
    assert "/runs/stream" in captured["url"], captured["url"]
    assert captured["json"]["assistant_id"] == "100000000000005"
    assert captured["json"]["input"]["messages"][0]["content"] == "hello"
    assert "agent_id" not in captured["json"]
    assert "message" not in captured["json"]


def test_chat_stream_with_agent_id_proxies_to_runs_stream(
    client, auth_headers, ai_enabled, patched_httpx
):
    """When agent_id is present, the proxy hits the runs stream endpoint."""
    resp = client.post(
        "/api/v1/ai/chat/stream",
        json={
            "question": "what's my net worth",
            "deep_think": False,
            "web_search": False,
            "agent_id": "100000000000005",
        },
        headers=auth_headers,
    )
    assert resp.status_code == 200
    captured = patched_httpx
    assert "/runs/stream" in captured["url"], captured["url"]
    assert captured["json"]["assistant_id"] == "100000000000005"
    assert captured["json"]["input"]["messages"][0]["content"] == "what's my net worth"
    assert "question" not in captured["json"]


def test_chat_stream_with_agent_id_propagates_deep_think_metadata(
    client, auth_headers, ai_enabled, patched_httpx
):
    """deep_think on the request maps to deep_think under metadata in the agent payload."""
    resp = client.post(
        "/api/v1/ai/chat/stream",
        json={
            "question": "trace the allocation drift",
            "deep_think": True,
            "web_search": False,
            "agent_id": "100000000000005",
        },
        headers=auth_headers,
    )
    assert resp.status_code == 200
    captured = patched_httpx
    assert captured["json"]["metadata"]["deep_think"] is True


def test_chat_stream_sets_internal_headers(
    client, auth_headers, ai_enabled, patched_httpx
):
    """All proxy paths require X-Family-Id, X-Agent-Token, X-Thread-Id, X-User-Id."""
    client.post(
        "/api/v1/ai/chat/stream",
        json={"question": "hi", "agent_id": "100000000000005"},
        headers=auth_headers,
    )
    captured = patched_httpx
    assert "X-Family-Id" in captured["headers"]
    assert "X-Agent-Token" in captured["headers"]
    assert "X-Thread-Id" in captured["headers"]
    assert "X-User-Id" in captured["headers"]
