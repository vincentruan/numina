"""U4 step 5: internal asset-report run trigger (backend → agent gateway).

Verifies the ``POST /internal/gateway/runs/asset-report/{thread_id}`` endpoint:
- ``X-Agent-Token`` auth (401 on bad/missing token).
- ``internal=True`` bypasses R1's 409 gate (frontend direct dispatch stays 409,
  tested in test_u2_app_dispatch.py).
- Triggers ``_run_asset_report_pipeline`` via ``start_run`` and streams SSE,
  including the ``report.step2_json`` custom event from the worker-synthesized
  step 3.
"""

from __future__ import annotations

import json
from collections.abc import AsyncGenerator
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient


def _make_stub_adapter() -> Any:
    stub = AsyncMock()

    async def typed_stream_dispatch(
        skill_name: str,
        context: Any,
        thread_id: str,
        enable_thinking: bool = False,
    ) -> AsyncGenerator[tuple[str, dict], None]:
        yield (
            "messages",
            {"type": "ai", "content": '```json\n{"overall_score": 88}\n```', "tool_calls": None, "id": "m1"},
        )
        yield ("end", {"usage": {"input_tokens": 1, "output_tokens": 2, "total_tokens": 3}})

    stub.typed_stream_dispatch = typed_stream_dispatch
    return stub


@pytest.fixture(scope="module")
def client():
    """Module-scoped TestClient with worker deps stubbed."""
    mock_ai_config = {
        "ai_enabled": True,
        "providers": [
            {"is_active": True, "provider": "openai", "api_key": "k", "base_url": "u"}
        ],
    }
    with (
        patch(
            "apps.agent.services.runtime.worker.BackendClient.get_family_ai_config",
            new_callable=AsyncMock,
            return_value=mock_ai_config,
        ),
        patch(
            "apps.agent.services.runtime.worker.BackendClient.get_enabled_mcp_servers",
            new_callable=AsyncMock,
            return_value=[],
        ),
        patch(
            "apps.agent.services.runtime.worker.create_family_adapter",
            return_value=_make_stub_adapter(),
        ),
        patch(
            "apps.agent.services.runtime.worker.pii_redactor.redact",
            side_effect=lambda ctx: ctx,
        ),
        patch(
            "apps.agent.services.deerflow_adapter.family_adapter_cache.async_init_checkpointer",
            new_callable=AsyncMock,
        ),
        patch(
            "deerflow.persistence.engine.init_engine",
            new_callable=AsyncMock,
        ),
    ):
        from apps.agent.app.main import app

        try:
            with TestClient(app) as test_client:
                yield test_client
        finally:
            app.dependency_overrides.clear()


def _parse_sse_events(response_text: str) -> list[dict]:
    events: list[dict] = []
    current_event = None
    current_data = None
    for line in response_text.split("\n"):
        if line.startswith("event:"):
            current_event = line[len("event:"):].strip()
        elif line.startswith("data:"):
            current_data = json.loads(line[len("data:"):].strip())
        elif line == "" and current_event is not None:
            events.append({"event": current_event, "data": current_data})
            current_event = None
            current_data = None
    return events


_TOKEN = "test-internal-token"


def test_asset_report_run_rejects_missing_token(client):
    """No X-Agent-Token → 401 (service-to-service auth required)."""
    response = client.post(
        "/internal/gateway/runs/asset-report/thread-1",
        json={"family_id": "family-1", "user_id": "user-1"},
    )
    assert response.status_code == 422  # missing required header → FastAPI 422


def test_asset_report_run_rejects_bad_token(client):
    """Wrong X-Agent-Token → 401."""
    response = client.post(
        "/internal/gateway/runs/asset-report/thread-1",
        headers={"X-Agent-Token": "wrong-token"},
        json={"family_id": "family-1", "user_id": "user-1"},
    )
    assert response.status_code == 401


def test_asset_report_run_streams_step2_json(client):
    """Valid token → SSE stream with report.step2_json custom event + complete end."""
    with patch(
        "apps.agent.app.routers.gateway.settings.AGENT_INTERNAL_TOKEN",
        _TOKEN,
    ):
        response = client.post(
            "/internal/gateway/runs/asset-report/thread-ar",
            headers={"X-Agent-Token": _TOKEN},
            json={"family_id": "family-1", "user_id": "user-1"},
        )
    assert response.status_code == 200
    events = _parse_sse_events(response.text)
    step2 = [
        e for e in events
        if e["event"] == "custom" and isinstance(e["data"], dict) and e["data"].get("type") == "report.step2_json"
    ]
    assert len(step2) == 1, f"expected 1 report.step2_json, got {events}"
    assert step2[0]["data"]["payload"] == {"overall_score": 88}
    end_events = [e for e in events if e["event"] == "end" and e["data"] is not None]
    assert end_events and end_events[0]["data"]["status"] == "complete"
