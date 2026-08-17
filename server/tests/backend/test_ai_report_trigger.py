"""U5: backend asset-report trigger -> agent HTTP trigger + Redis bridge subscription.

Verifies ``POST /api/v1/ai/report/generate/events``:
- Enforces owner + ai_enabled + per-family concurrency (existing gate, unchanged).
- Calls the agent's ``/internal/gateway/runs/asset-report/{thread_id}`` via
  ``AgentClient.post`` (X-Agent-Token injected automatically) to trigger the task,
  then subscribes to the Redis stream via bridge_consumer for SSE delivery.
- Returns ``text/event-stream``.

Ported from the former apps/backend/tests/test_ai_report_trigger.py. These cover
the trigger + bridge-consumer path; the 8h cache path is exercised by
``tests/backend/test_ai_report.py``.
"""

from __future__ import annotations

import json
from contextlib import asynccontextmanager
from datetime import UTC
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient


def _fake_agent_trigger(status_code: int = 200, body: dict | None = None) -> Any:
    """Build a fake AgentClient.post response (non-streaming trigger)."""

    class _FakeResp:
        def __init__(self) -> None:
            self.status_code = status_code
            self.text = json.dumps(body or {"status": "started"})
            self.headers = {"Content-Location": "/internal/gateway/runs/asset-report/t/run-123"}

    return _FakeResp()


def _fake_bridge_stream(frames: list[tuple[str, dict]]) -> Any:
    """Build a fake consume_task_stream async generator yielding SSE text."""

    async def _stream(task_id: str, family_id: int, last_event_id: str | None = None, run_id: str | None = None):
        for event, data in frames:
            yield f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
        yield "event: end\ndata: null\n\n"

    return _stream


@pytest.fixture()
def client(monkeypatch):
    """TestClient with agent trigger + bridge consumer stubbed + auth gates bypassed."""
    with (
        patch("apps.backend.app.routers.ai_report.AgentClient") as mock_agent_cls,
        patch("apps.backend.app.routers.ai_report.check_circuit_blocked", return_value=None),
        patch("apps.backend.app.routers.ai_report.AITaskService.get_running_task", return_value=None),
        patch("apps.backend.app.routers.ai_report.AITaskService.get_any_running_task", return_value=None),
        patch("apps.backend.app.routers.ai_report.AITaskService.create_task", return_value=type("T", (), {"id": 1})()),
        patch("apps.backend.app.routers.ai_report.ChatSessionService.create_session", new_callable=AsyncMock, return_value=type("S", (), {"id": "session-1"})()),
        # Default: no cached report (cache-miss -> stream). Cache-hit tests override
        # _latest_report locally.
        patch("apps.backend.app.routers.ai_report._latest_report", return_value=None),
    ):
        mock_agent_cls.return_value.post = AsyncMock(return_value=_fake_agent_trigger())
        mock_agent_cls.return_value.stream = AsyncMock()  # legacy; not used anymore
        from apps.backend.app.auth.ai_deps import require_ai_enabled
        from apps.backend.app.auth.deps import require_adult, require_owner
        from apps.backend.app.main import app

        _fake_user = type("U", (), {"id": 1, "family_id": "family-1", "role": "owner", "language": "zh-CN"})()
        app.dependency_overrides[require_adult] = lambda: _fake_user
        app.dependency_overrides[require_ai_enabled] = lambda: None
        app.dependency_overrides[require_owner] = lambda: _fake_user
        try:
            with TestClient(app) as test_client:
                yield test_client
        finally:
            app.dependency_overrides.clear()


def test_trigger_streams_agent_sse(client):
    """trigger -> 200 text/event-stream with bridge consumer's report.step2_json forwarded."""
    with patch(
        "apps.backend.app.routers.ai_report.consume_task_stream",
        _fake_bridge_stream([("custom", {"type": "report.step2_json", "payload": {"overall_score": 77}})]),
    ):
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


def test_trigger_passes_family_id_as_string_to_agent(client):
    """Regression: family_id/user_id must be sent as strings in the agent
    request body - AssetReportRunRequest.family_id is pydantic ``str``, so an
    int Snowflake value 422s at the agent gateway.
    """
    captured: dict = {}

    async def _capturing_post(endpoint, json=None, **kwargs):
        captured["json"] = json
        captured["endpoint"] = endpoint
        return _fake_agent_trigger()

    with patch("apps.backend.app.routers.ai_report.AgentClient") as mock_cls, patch(
        "apps.backend.app.routers.ai_report.consume_task_stream",
        _fake_bridge_stream([("custom", {"type": "report.step2_json", "payload": {"overall_score": 1}})]),
    ):
        mock_cls.return_value.post = _capturing_post
        response = client.post("/api/v1/ai/report/generate/events?force=true")
    assert response.status_code == 200
    assert captured["json"]["family_id"] == "family-1"
    assert captured["json"]["user_id"] == "1"
    assert isinstance(captured["json"]["family_id"], str)


def _fresh_cached_report():
    """An AIReport-like object generated < 1h ago (cache hit), with a valid
    report_json matching the report schema (overall_score + 3 indicators)."""
    from datetime import datetime, timedelta

    return type(
        "R",
        (),
        {
            "report_json": {
                "overall_score": 80,
                "indicators": [
                    {"key": "a", "label": "A", "score": 4, "narrative": "ok"},
                    {"key": "b", "label": "B", "score": 4, "narrative": "ok"},
                    {"key": "c", "label": "C", "score": 4, "narrative": "ok"},
                ],
            },
            "generated_at": datetime.now(UTC).replace(tzinfo=None) - timedelta(minutes=5),
        },
    )()


def test_trigger_cache_hit_returns_json_not_stream(client):
    """Cached report (fresh, valid) -> 200 JSON with status=cached, no agent call."""
    with (
        patch("apps.backend.app.routers.ai_report._latest_report", return_value=_fresh_cached_report()),
        patch("apps.backend.app.routers.ai_report.consume_task_stream") as mock_stream,
    ):
        response = client.post("/api/v1/ai/report/generate/events")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")
    body = response.json()
    assert body["status"] == "cached"
    assert body["report"]["overall_score"] == 80
    mock_stream.assert_not_called()


def test_trigger_force_bypasses_cache(client):
    """force=true -> skips the cache and goes straight to trigger + stream."""
    with (
        patch("apps.backend.app.routers.ai_report._latest_report", return_value=_fresh_cached_report()),
        patch(
            "apps.backend.app.routers.ai_report.consume_task_stream",
            side_effect=_fake_bridge_stream([("custom", {"type": "report.step2_json", "payload": {"overall_score": 1}})]),
        ) as mock_stream,
    ):
        response = client.post("/api/v1/ai/report/generate/events?force=true")
    assert response.status_code == 200
    assert "text/event-stream" in response.headers.get("content-type", "")
    mock_stream.assert_called_once()


def test_trigger_stale_cache_misses(client):
    """Cache older than 1h -> regenerated via trigger + stream (not served stale)."""
    from datetime import datetime, timedelta

    stale = type(
        "R",
        (),
        {
            "report_json": {"overall_score": 80},
            "generated_at": datetime.now(UTC).replace(tzinfo=None) - timedelta(hours=2),
        },
    )()
    with (
        patch("apps.backend.app.routers.ai_report._latest_report", return_value=stale),
        patch(
            "apps.backend.app.routers.ai_report.consume_task_stream",
            _fake_bridge_stream([("custom", {"type": "report.step2_json", "payload": {"overall_score": 1}})]),
        ),
    ):
        response = client.post("/api/v1/ai/report/generate/events")
    assert response.status_code == 200
    assert "text/event-stream" in response.headers.get("content-type", "")


def test_trigger_corrupted_cache_revalidates_and_regenerates(client):
    """Cached report failing schema re-validation falls through to regeneration."""
    corrupted = type(
        "R",
        (),
        {
            "report_json": {"invalid": "structure"},
            "generated_at": datetime.now(UTC).replace(tzinfo=None) - timedelta(minutes=5),
        },
    )()
    with (
        patch("apps.backend.app.routers.ai_report._latest_report", return_value=corrupted),
        patch(
            "apps.backend.app.routers.ai_report.consume_task_stream",
            _fake_bridge_stream([("custom", {"type": "report.step2_json", "payload": {"overall_score": 1}})]),
        ),
    ):
        response = client.post("/api/v1/ai/report/generate/events")
    assert response.status_code == 200
    assert "text/event-stream" in response.headers.get("content-type", "")


from datetime import datetime, timedelta  # noqa: E402  (used by cache fixtures)
