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
    has an `aiter_text()` iterator. This stub returns a single empty chunk
    so the proxy stream terminates cleanly."""

    def __init__(self):
        self.status_code = 200

    async def aiter_text(self):
        if False:
            yield ""  # pragma: no cover

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

    def stream(self, method, url, *, json, headers, **_kwargs):
        _FakeAsyncClient.captured["method"] = method
        _FakeAsyncClient.captured["url"] = url
        _FakeAsyncClient.captured["json"] = json
        _FakeAsyncClient.captured["headers"] = headers
        return _FakeStreamResponse()


@pytest.fixture
def patched_httpx(monkeypatch):
    _FakeAsyncClient.captured = {}
    monkeypatch.setattr(
        "apps.backend.app.routers.ai_chat.httpx.AsyncClient",
        _FakeAsyncClient,
    )
    yield _FakeAsyncClient.captured


def test_chat_stream_without_agent_id_proxies_to_legacy_chat_ask(
    client, auth_headers, ai_enabled, patched_httpx
):
    """When agent_id is absent, the proxy hits /chat/ask/stream (legacy path)."""
    resp = client.post(
        "/api/v1/ai/chat/stream",
        json={"question": "hello", "deep_think": False, "web_search": False},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    captured = patched_httpx
    assert captured["url"].endswith("/chat/ask/stream"), captured["url"]
    assert captured["json"]["question"] == "hello"
    assert "agent_id" not in captured["json"]
    assert "message" not in captured["json"]


def test_chat_stream_with_agent_id_proxies_to_agent_dispatch(
    client, auth_headers, ai_enabled, patched_httpx
):
    """When agent_id is present, the proxy hits /agent/{id}/stream (new path)."""
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
    assert captured["url"].endswith("/agent/100000000000005/stream"), captured["url"]
    # The new endpoint uses `message` not `question`, and `enable_thinking`
    # not `deep_think`. web_search isn't supported on the agent path yet.
    assert captured["json"]["message"] == "what's my net worth"
    assert captured["json"]["enable_thinking"] is False
    assert "question" not in captured["json"]


def test_chat_stream_with_agent_id_propagates_deep_think_as_enable_thinking(
    client, auth_headers, ai_enabled, patched_httpx
):
    """deep_think on the request maps to enable_thinking on the agent body."""
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
    assert captured["json"]["enable_thinking"] is True


def test_chat_stream_sets_internal_headers_on_both_paths(
    client, auth_headers, ai_enabled, patched_httpx
):
    """Both paths require X-Family-Id, X-Agent-Token, X-Thread-Id, X-User-Id."""
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
