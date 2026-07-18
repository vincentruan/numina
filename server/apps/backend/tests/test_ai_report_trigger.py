"""U4 step 5: backend asset-report trigger → agent gateway SSE passthrough.

Verifies ``POST /api/v1/ai/report/generate/events``:
- Enforces owner + ai_enabled + per-family concurrency (existing gate, unchanged).
- Calls the agent's ``/internal/gateway/runs/asset-report/{thread_id}`` via
  ``AgentClient`` (X-Agent-Token injected automatically) and streams the SSE
  response through unchanged.
- Returns ``text/event-stream`` (replaces the legacy NDJSON proxy_report_events).
"""

from __future__ import annotations

import json
from contextlib import asynccontextmanager
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient


def _fake_agent_sse_stream(frames: list[tuple[str, dict]]) -> Any:
    """Build a fake AgentClient.stream async context manager yielding SSE lines."""

    class _FakeResp:
        def __init__(self, frames: list[tuple[str, dict]]) -> None:
            self.status_code = 200
            self._lines: list[str] = []
            for event, data in frames:
                self._lines.append(f"event: {event}")
                self._lines.append(f"data: {json.dumps(data, ensure_ascii=False)}")
                self._lines.append("")
            self._lines.append("event: end")
            self._lines.append("data: null")
            self._lines.append("")

        async def aiter_lines(self):
            for line in self._lines:
                yield line

        async def aread(self) -> bytes:
            return b""

    @asynccontextmanager
    async def _stream(method, endpoint, **kwargs):
        yield _FakeResp(frames)

    return _stream


@pytest.fixture()
def client(monkeypatch):
    """TestClient with AgentClient.stream stubbed + auth/ai-config gates bypassed."""
    monkeypatch.setenv("AGENT_INTERNAL_TOKEN", "test-token")
    with (
        patch("apps.backend.app.routers.ai_report.AgentClient") as mock_agent_cls,
        patch("apps.backend.app.routers.ai_report.check_circuit_blocked", return_value=None),
        patch("apps.backend.app.routers.ai_report.AITaskService.get_running_task", return_value=None),
        patch("apps.backend.app.routers.ai_report.AITaskService.get_any_running_task", return_value=None),
        patch("apps.backend.app.routers.ai_report.AITaskService.create_task", return_value=type("T", (), {"id": 1})()),
        patch("apps.backend.app.routers.ai_report.ChatSessionService.create_session", new_callable=AsyncMock, return_value=type("S", (), {"id": "session-1"})()),
    ):
        mock_agent_cls.return_value.stream = _fake_agent_sse_stream(
            [("custom", {"type": "report.step2_json", "payload": {"overall_score": 77}})]
        )
        from apps.backend.app.auth.ai_deps import require_ai_enabled, require_owner
        from apps.backend.app.auth.deps import require_adult
        from apps.backend.app.main import app

        _fake_user = type("U", (), {"id": 1, "family_id": "family-1", "role": "owner"})()
        app.dependency_overrides[require_adult] = lambda: _fake_user
        app.dependency_overrides[require_ai_enabled] = lambda: None
        app.dependency_overrides[require_owner] = lambda: _fake_user
        try:
            with TestClient(app) as test_client:
                yield test_client
        finally:
            app.dependency_overrides.clear()


def test_trigger_streams_agent_sse(client):
    """trigger → 200 text/event-stream with agent's report.step2_json forwarded."""
    response = client.post("/api/v1/ai/report/generate/events")
    assert response.status_code == 200
    assert "text/event-stream" in response.headers.get("content-type", "")
    events: list[dict] = []
    cur_event = None
    for line in response.text.split("\n"):
        if line.startswith("event:"):
            cur_event = line[len("event:"):].strip()
        elif line.startswith("data:") and cur_event:
            data = line[len("data:"):].strip()
            events.append({"event": cur_event, "data": json.loads(data) if data and data != "null" else None})
            cur_event = None
    step2 = [e for e in events if e["event"] == "custom" and isinstance(e["data"], dict) and e["data"].get("type") == "report.step2_json"]
    assert len(step2) == 1, f"expected forwarded report.step2_json, got {events}"
    assert step2[0]["data"]["payload"] == {"overall_score": 77}
