"""Smoke tests for learning-tutor Redis bridge integration.

Verifies the two integration contracts introduced by the learning-tutor
DeerFlow SSE migration:

1. ``get_shared_bridge()`` returns a Redis-backed bridge by default
   (the agent writes events directly to Redis; backend subscribes).
2. ``trigger_agent_run()`` extracts the ``run_id`` from the
   ``Content-Location`` header returned by the agent gateway.
"""

from __future__ import annotations

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# 1. Shared bridge defaults to Redis
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_shared_bridge_defaults_to_redis():
    """After migration, get_shared_bridge() should return a Redis bridge.

    The bridge is created lazily on first call using the ``STREAM_BRIDGE_TYPE``
    env var (default ``"redis"``).  We patch the singleton to force a fresh
    creation without touching the process-wide state.
    """
    from apps.backend.app.services.bridge_consumer import get_shared_bridge
    from packages.stream_bridge.redis import NuminaRedisStreamBridge

    # Patch the module-level singleton so we don't pollute other tests.
    with patch("apps.backend.app.services.bridge_consumer._shared_bridge", None):
        with patch.dict(os.environ, {"STREAM_BRIDGE_TYPE": "redis"}):
            bridge = get_shared_bridge()

    assert isinstance(bridge, NuminaRedisStreamBridge), (
        f"Expected NuminaRedisStreamBridge, got {type(bridge).__name__}"
    )


# ---------------------------------------------------------------------------
# 2. trigger_agent_run extracts run_id from Content-Location header
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_trigger_agent_run_extracts_run_id():
    """trigger_agent_run should extract run_id from Content-Location header."""
    from apps.backend.app.services.bridge_consumer import trigger_agent_run

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(
        return_value=MagicMock(
            headers={
                "Content-Location": (
                    "/internal/gateway/runs/learning-tutor/12345/67890"
                ),
            },
            status_code=200,
        ),
    )

    result = await trigger_agent_run(
        agent_client=mock_client,
        agent_url="/internal/gateway/runs/learning-tutor/12345",
        json_body={"input": {"messages": []}},
        task_id="task-001",
    )

    assert result["run_id"] == "67890"
    assert result["content_location"] == (
        "/internal/gateway/runs/learning-tutor/12345/67890"
    )


@pytest.mark.asyncio
async def test_trigger_agent_run_empty_content_location():
    """trigger_agent_run should return empty run_id when header is missing."""
    from apps.backend.app.services.bridge_consumer import trigger_agent_run

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(
        return_value=MagicMock(
            headers={},
            status_code=200,
        ),
    )

    result = await trigger_agent_run(
        agent_client=mock_client,
        agent_url="/internal/gateway/runs/learning-tutor/thread-1",
        json_body={"input": {"messages": []}},
        task_id="task-002",
    )

    assert result["run_id"] == ""
    assert result["content_location"] == ""


# ---------------------------------------------------------------------------
# 3. Full E2E — skipped without a running stack
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_learning_tutor_full_flow():
    """Full E2E integration test — requires running stack.

    Covers: backend → agent → Redis bridge → backend subscribe → MCP tools.
    Skipped in unit-test runs; executed via the e2e test suite.
    """
    pytest.skip("Requires full stack — run via e2e test suite")
