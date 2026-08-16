"""U12: heartbeat loop + run_id extraction unit tests."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def test_extract_task_id_from_metadata():
    """_extract_task_id pulls int task_id from run metadata."""
    from apps.agent.services.runtime.worker import _extract_task_id

    assert _extract_task_id({"task_id": 123}) == 123
    assert _extract_task_id({"task_id": "456"}) == 456
    assert _extract_task_id({"task_id": "not-an-int"}) is None
    assert _extract_task_id({"other": "field"}) is None
    assert _extract_task_id(None) is None


@pytest.mark.asyncio
async def test_run_agent_starts_heartbeat_when_task_id_present():
    """run_agent starts _heartbeat_loop when metadata carries task_id."""
    from apps.agent.services.runtime.worker import run_agent

    mock_bridge = AsyncMock()
    mock_run_manager = AsyncMock()
    mock_record = MagicMock()
    mock_record.metadata = {"app": "finance-coach", "task_id": 777}
    mock_record.run_id = "run-xyz"

    with (
        patch(
            "apps.agent.services.runtime.worker._run_finance_coach_agent",
            new_callable=AsyncMock,
        ) as mock_runner,
        patch(
            "apps.agent.services.runtime.worker._heartbeat_loop",
            new_callable=AsyncMock,
        ) as mock_heartbeat,
    ):
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
        mock_heartbeat.assert_called_once()
        # task_id and family_id passed positionally
        call_args = mock_heartbeat.call_args
        assert call_args[0][0] == 777
        assert call_args[0][1] == "123"
        # stop_event passed as kwarg
        assert call_args[1].get("stop_event") is not None


@pytest.mark.asyncio
async def test_run_agent_skips_heartbeat_without_task_id():
    """run_agent does NOT start heartbeat when metadata lacks task_id."""
    from apps.agent.services.runtime.worker import run_agent

    mock_bridge = AsyncMock()
    mock_run_manager = AsyncMock()
    mock_record = MagicMock()
    mock_record.metadata = {"app": "finance-coach"}  # no task_id
    mock_record.run_id = "run-xyz"

    with (
        patch(
            "apps.agent.services.runtime.worker._run_finance_coach_agent",
            new_callable=AsyncMock,
        ) as mock_runner,
        patch(
            "apps.agent.services.runtime.worker._heartbeat_loop",
            new_callable=AsyncMock,
        ) as mock_heartbeat,
    ):
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
        mock_heartbeat.assert_not_called()
