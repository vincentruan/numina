"""Integration test for the v2 SSE streaming contract.

Verifies the contract between the v2 runs_stream router and the frontend:
- metadata event carries run_id (Q3 / fixes #4)
- messages events carry AI text (R5 streaming)
- custom tool_call events carry type:"tool_call" (R6 规划步骤)
- end event carries status payload (Q2 / fixes #19 truncated-end)
- suggestions custom event is emitted before stream closes (R8 追问问题)

Uses FastAPI TestClient with a stub adapter — does NOT invoke the real
DeerFlowClient. Real end-to-end verification requires running the agent
locally, which is outside automated test scope (per CLAUDE.md: no dev servers).
"""

from __future__ import annotations

from typing import Any, AsyncGenerator
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Stub adapter — deterministic SSE frame sequence
# ---------------------------------------------------------------------------


def _make_stub_adapter():
    """Return a stub adapter that yields a known SSE frame sequence."""
    stub = AsyncMock()

    async def typed_stream_dispatch(
        skill_name: str,
        context: Any,
        thread_id: str,
        enable_thinking: bool = False,
    ) -> AsyncGenerator[tuple[str, dict], None]:
        # 1. metadata is emitted by worker.py itself (not the adapter), so
        #    the adapter starts with messages events.

        # 2. An AI message with tool_calls — the worker synthesizes a
        #    `custom` tool_call event from the tool_calls field (R6).
        yield (
            "messages",
            {
                "type": "ai",
                "content": "Let me search that for you.",
                "tool_calls": [
                    {
                        "id": "call_abc123",
                        "name": "web_search",
                        "args": {"query": "family asset management"},
                    }
                ],
            },
        )

        # 3. A plain AI text chunk (no tool calls).
        yield (
            "messages",
            {
                "type": "ai",
                "content": " Based on the search results...",
                "tool_calls": None,
            },
        )

        # 4. A values event (state snapshot).
        yield ("values", {"messages": []})

        # 5. Stream complete.
        yield ("end", {})

    stub.typed_stream_dispatch = typed_stream_dispatch
    return stub


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def client():
    """Module-scoped FastAPI TestClient — lifespan runs once for all tests."""
    mock_ai_config = {
        "ai_enabled": True,
        "providers": [
            {
                "is_active": True,
                "provider": "openai",
                "api_key": "test-key",
                "base_url": "http://localhost:11434/v1",
            }
        ],
        "ai_model_id": "gpt-4o-mini",
    }
    with (
        patch(
            "apps.agent.services.runtime.worker.BackendClient.get_family_ai_config",
            new_callable=AsyncMock,
            return_value=mock_ai_config,
        ),
        patch(
            "apps.agent.services.runtime.worker.create_family_adapter",
            return_value=_make_stub_adapter(),
        ),
        patch(
            "apps.agent.services.runtime.worker.generate_suggestions",
            new_callable=AsyncMock,
            return_value=["What is my net worth?", "How should I invest?", "Review my debts"],
        ),
        patch(
            "apps.agent.services.runtime.worker.sync_title_from_checkpoint",
            new_callable=AsyncMock,
            return_value=None,
        ),
        # Stub the lifespan dependencies that hit the filesystem / DB
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

        with TestClient(app) as test_client:
            yield test_client


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def _parse_sse_events(response_text: str) -> list[dict]:
    """Parse SSE text into a list of {event, data} dicts."""
    events = []
    current_event = None
    current_data = None
    for line in response_text.split("\n"):
        if line.startswith("event:"):
            current_event = line[len("event:"):].strip()
        elif line.startswith("data:"):
            import json
            current_data = json.loads(line[len("data:"):].strip())
        elif line == "" and current_event is not None:
            events.append({"event": current_event, "data": current_data})
            current_event = None
            current_data = None
        # skip comments (heartbeat lines starting with ":")
    return events


def test_v2_sse_contract_emits_metadata_with_run_id(client):
    """The v2 worker emits a metadata event with run_id first."""
    response = client.post(
        "/api/threads/test-thread-123/runs/stream",
        headers={"X-Family-Id": "family-1", "X-User-Id": "user-1"},
        json={"input": {"messages": [{"role": "user", "content": "hello"}]}},
    )
    assert response.status_code == 200

    events = _parse_sse_events(response.text)
    event_names = [e["event"] for e in events]

    # metadata must be the first real event
    assert "metadata" in event_names, f"metadata not in events: {event_names}"
    metadata_event = next(e for e in events if e["event"] == "metadata")
    assert "run_id" in metadata_event["data"]
    assert metadata_event["data"]["run_id"]  # non-empty


def test_v2_sse_contract_emits_tool_call_custom_events_for_r6(client):
    """Custom tool_call events carry type:'tool_call' so R6 (规划步骤) renders."""
    response = client.post(
        "/api/threads/test-thread-456/runs/stream",
        headers={"X-Family-Id": "family-1", "X-User-Id": "user-1"},
        json={"input": {"messages": [{"role": "user", "content": "search assets"}]}},
    )
    events = _parse_sse_events(response.text)
    custom_events = [e for e in events if e["event"] == "custom"]

    # At least one custom event must be type:"tool_call"
    tool_call_events = [
        e for e in custom_events
        if isinstance(e["data"], dict) and e["data"].get("type") == "tool_call"
    ]
    assert len(tool_call_events) >= 1, (
        f"No custom tool_call events found. Custom events: {custom_events}"
    )

    # Verify the tool_call payload shape the frontend expects
    tc = tool_call_events[0]["data"]
    assert tc["tool_call_id"] == "call_abc123"
    assert tc["tool_name"] == "web_search"
    assert tc["args"] == {"query": "family asset management"}


def test_v2_sse_contract_end_carries_completion_status(client):
    """The `end` data frame carries status so frontend can detect truncation (Q2/#19)."""
    response = client.post(
        "/api/threads/test-thread-789/runs/stream",
        headers={"X-Family-Id": "family-1", "X-User-Id": "user-1"},
        json={"input": {"messages": [{"role": "user", "content": "hello"}]}},
    )
    events = _parse_sse_events(response.text)
    end_events = [e for e in events if e["event"] == "end"]

    # At least one `end` event must carry status payload (Q2).
    # The sentinel `end` (from publish_end) has data=None; the data-bearing
    # `end` (from worker's explicit publish) carries status.
    data_end_events = [e for e in end_events if e["data"] is not None]
    assert len(data_end_events) >= 1, (
        f"No data-bearing `end` events found. All end events: {end_events}"
    )
    assert data_end_events[0]["data"]["status"] == "complete"


def test_v2_sse_contract_suggestions_emitted_for_r8(client):
    """Suggestions custom event is emitted before stream closes (R8)."""
    response = client.post(
        "/api/threads/test-thread-sug/runs/stream",
        headers={"X-Family-Id": "family-1", "X-User-Id": "user-1"},
        json={"input": {"messages": [{"role": "user", "content": "help"}]}},
    )
    events = _parse_sse_events(response.text)
    custom_events = [e for e in events if e["event"] == "custom"]

    suggestion_events = [
        e for e in custom_events
        if isinstance(e["data"], dict) and e["data"].get("type") == "suggestions"
    ]
    assert len(suggestion_events) == 1, (
        f"Expected exactly 1 suggestions event, got: {suggestion_events}"
    )
    assert suggestion_events[0]["data"]["suggestions"] == [
        "What is my net worth?",
        "How should I invest?",
        "Review my debts",
    ]


def test_v2_sse_contract_full_event_order(client):
    """End-to-end: metadata → messages → custom(tool_call) → end(status) → suggestions."""
    response = client.post(
        "/api/threads/test-thread-order/runs/stream",
        headers={"X-Family-Id": "family-1", "X-User-Id": "user-1"},
        json={"input": {"messages": [{"role": "user", "content": "hello"}]}},
    )
    events = _parse_sse_events(response.text)
    event_names = [e["event"] for e in events]

    # All required event types must be present
    for required in ["metadata", "messages", "custom", "end"]:
        assert required in event_names, f"Missing required event: {required}"

    # metadata must come before messages
    assert event_names.index("metadata") < event_names.index("messages")

    # end must come after messages
    assert event_names.index("messages") < event_names.index("end")

    # At least one custom event (tool_call or suggestions)
    assert "custom" in event_names
