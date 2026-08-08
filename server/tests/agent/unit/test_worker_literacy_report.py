"""Test literacy-weekly-report worker dispatch branch."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.mark.asyncio
async def test_worker_dispatches_literacy_weekly_report():
    """worker.run_agent routes app='literacy-weekly-report' to the correct runner."""
    from apps.agent.services.runtime.worker import run_agent

    mock_bridge = AsyncMock()
    mock_run_manager = AsyncMock()
    mock_record = MagicMock()
    mock_record.metadata = {"app": "literacy-weekly-report"}
    mock_record.run_id = "test-run-id"

    with patch(
        "apps.agent.services.runtime.worker._run_literacy_weekly_report_agent",
        new_callable=AsyncMock,
    ) as mock_runner:
        await run_agent(
            bridge=mock_bridge,
            run_manager=mock_run_manager,
            record=mock_record,
            family_id="123",
            user_id="456",
            thread_id="thread-abc",
            graph_input=None,
            config={},
        )
        mock_runner.assert_called_once()


@pytest.mark.asyncio
async def test_extract_backend_user_message_with_valid_input():
    """_extract_backend_user_message pulls content from last user message."""
    from apps.agent.services.runtime.worker import _extract_backend_user_message

    graph_input = {
        "messages": [
            {"role": "user", "content": '{"child_id": "123", "week": "2026-W30"}'},
        ]
    }
    result = _extract_backend_user_message(graph_input)
    assert result == '{"child_id": "123", "week": "2026-W30"}'


@pytest.mark.asyncio
async def test_extract_backend_user_message_empty():
    """_extract_backend_user_message returns None for empty/missing input."""
    from apps.agent.services.runtime.worker import _extract_backend_user_message

    assert _extract_backend_user_message(None) is None
    assert _extract_backend_user_message({}) is None
    assert _extract_backend_user_message({"messages": []}) is None
