"""Unit test: chat router forwards web_search to orchestrator."""
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from apps.agent.app.config import settings
from apps.agent.app.main import app


def test_ask_stream_forwards_web_search(monkeypatch):
    monkeypatch.setattr(settings, "AGENT_INTERNAL_TOKEN", "tok")
    captured = {}

    async def fake_stream(**kwargs):
        captured.update(kwargs)
        yield '{"type":"capability.end"}\n'

    with patch("apps.agent.routers.chat.orchestrator") as mock_orch:
        mock_orch.stream_dispatch_events = fake_stream
        client = TestClient(app)
        resp = client.post(
            "/chat/ask/stream",
            json={"question": "hi", "deep_think": True, "web_search": True},
            headers={
                "X-Family-Id": "100",
                "X-Agent-Token": "tok",
                "X-User-Id": "u1",
                "X-Thread-Id": "t1",
            },
        )
        assert resp.status_code == 200
    assert captured.get("web_search") is True
