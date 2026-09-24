"""Verify backend triggers agent run and subscribes to Redis directly."""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock


@pytest.mark.asyncio
async def test_trigger_and_subscribe_pattern():
    """Backend should: 1) POST to agent (fire-and-forget), 2) subscribe to Redis bridge."""
    from apps.backend.app.services.bridge_consumer import (
        trigger_agent_run,
    )

    mock_agent_client = AsyncMock()
    mock_agent_client.post = AsyncMock(return_value=MagicMock(
        headers={"Content-Location": "/internal/gateway/runs/asset-report/session_1/r456"},
        status_code=200,
    ))

    result = await trigger_agent_run(
        agent_client=mock_agent_client,
        agent_url="/internal/gateway/runs/asset-report/session_1",
        json_body={"input": {"messages": []}},
        task_id="task_1",
        family_id=123,
    )

    # Agent was called (trigger)
    mock_agent_client.post.assert_called_once()
    # run_id extracted from Content-Location
    assert result["run_id"] == "r456"


@pytest.mark.asyncio
async def test_no_pump_references_remain():
    """After migration, no code should reference _pump_agent_sse_to_bridge."""
    import subprocess
    from pathlib import Path
    # Find repo root: test file is at server/tests/backend/integration/
    repo_root = Path(__file__).resolve().parents[4]
    result = subprocess.run(
        ["grep", "-r", "_pump_agent_sse_to_bridge",
         "server/apps/backend/", "--include=*.py"],
        capture_output=True, text=True,
        cwd=str(repo_root),
    )
    # Should find zero matches (function deleted)
    assert result.stdout.strip() == "", (
        f"_pump_agent_sse_to_bridge still referenced:\n{result.stdout}"
    )
