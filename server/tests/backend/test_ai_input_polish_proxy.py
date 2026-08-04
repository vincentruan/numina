"""Regression: POST /api/input-polish proxies to agent /input-polish.

Pre-fix the frontend called /api/input-polish but neither the dev Vite proxy
(Vite routes /api → backend 8000, which had no such route) nor the backend
itself exposed it, so the composer always hit 404 → "优化输入失败". This test
pins the contract that the backend now owns /api/input-polish and forwards it
to the agent with the family-isolation headers, mirroring /api/threads.
"""

import httpx
import pytest

from apps.backend.app.models.user import User


@pytest.fixture
def ai_enabled(db, auth_headers):
    """require_ai_enabled gates the endpoint — enable the family-level AI switch."""
    user = db.query(User).filter_by(username="testuser").first()
    assert user is not None
    from apps.backend.app.models.family import Family
    family = db.query(Family).filter_by(id=user.family_id).first()
    assert family is not None
    family.ai_enabled = True
    db.commit()


class _FakeResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("err", request=None, response=self)

    def json(self):
        return self._payload


class _FakeAsyncClient:
    """Captures the (url, json, headers) of client.post() so the test can assert
    the proxy forwarded to agent /input-polish with X-Family-Id attached."""

    captured: dict = {}

    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return None

    async def post(self, url, json=None, data=None, headers=None, **kwargs):
        _FakeAsyncClient.captured["url"] = url
        _FakeAsyncClient.captured["json"] = json
        _FakeAsyncClient.captured["headers"] = headers
        return _FakeResponse(
            {"rewritten_text": "改写后的内容", "changed": True}
        )


@pytest.fixture
def patched_httpx(monkeypatch):
    _FakeAsyncClient.captured = {}
    monkeypatch.setattr(
        "apps.backend.app.services.agent_client.httpx.AsyncClient",
        _FakeAsyncClient,
    )
    yield _FakeAsyncClient.captured


def test_input_polish_proxies_to_agent(client, auth_headers, ai_enabled, patched_httpx):
    # auth_headers carry the access_token cookie (set by the login fixture)
    resp = client.post(
        "/api/input-polish",
        json={"text": "帮我看看资产"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json() == {"rewritten_text": "改写后的内容", "changed": True}
    # Forwarded to agent's /input-polish (root mount, no /api prefix)
    assert patched_httpx["url"].endswith("/input-polish")
    assert patched_httpx["json"] == {
        "text": "帮我看看资产",
        "locale": None,
        "thread_id": None,
    }
    # Tenant isolation header injected by AgentClient
    assert "X-Family-Id" in patched_httpx["headers"]
    # JWT forwarded so agent's verify_family_token (JWT-based, NOT X-Agent-Token)
    # authenticates the proxied call. Without this the agent returns 401 → 503.
    forwarded = patched_httpx["headers"]
    assert forwarded.get("Authorization", "").startswith("Bearer ")
    assert "access_token=" in forwarded.get("Cookie", "")
