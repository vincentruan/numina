"""Tests for _spawn_lifecycle_consumer — verifies F1 fix.

The lifecycle consumer must call complete_task/fail_task regardless of
whether an SSE client is connected. This is the core F1 fix: previously,
complete_task was inside the SSE async generator, so client disconnect
left tasks stuck in 'running'.

These tests verify the *behavior* (which lifecycle transition is triggered
for each bridge event) by patching AITaskService.complete_task/fail_task and
SessionLocal — avoiding cross-session DB coupling between the lifecycle
consumer's own SessionLocal and the test's in-memory StaticPool fixture.
"""

from unittest.mock import MagicMock, patch

import pytest

from apps.backend.app.services.bridge_consumer import _spawn_lifecycle_consumer


@pytest.fixture
def mocked():
    """Patch SessionLocal + AITaskService lifecycle methods to record calls."""
    mock_db = MagicMock()

    completed: list[tuple] = []
    failed: list[tuple] = []

    with patch(
        "apps.backend.app.services.bridge_consumer.SessionLocal",
        return_value=mock_db,
    ), patch(
        "apps.backend.app.services.ai_task_service.AITaskService.complete_task",
        side_effect=lambda tid, db: completed.append((tid, db)),
    ), patch(
        "apps.backend.app.services.ai_task_service.AITaskService.fail_task",
        side_effect=lambda tid, msg, db: failed.append((tid, msg, db)),
    ):
        yield {"db": mock_db, "completed": completed, "failed": failed}


class TestLifecycleConsumer:
    """Test _spawn_lifecycle_consumer lifecycle transitions."""

    async def test_complete_task_called_on_normal_end(self, mocked):
        """When bridge stream ends normally, complete_task must be called."""
        async def mock_bridge_consumer(*_args, **_kwargs):
            yield {"event": "custom", "data": {"type": "reasoning_delta", "content": "test"}}
            yield {"event": "end", "data": None}

        with patch(
            "apps.backend.app.services.bridge_consumer.bridge_consumer",
            side_effect=mock_bridge_consumer,
        ):
            lifecycle_task = _spawn_lifecycle_consumer(
                task_id="task-1",
                family_id=1,
                run_id="run-1",
            )
            await lifecycle_task

        assert len(mocked["completed"]) == 1
        assert mocked["completed"][0][0] == "task-1"
        assert mocked["failed"] == []

    async def test_fail_task_called_on_exception(self, mocked):
        """When bridge stream raises an exception, fail_task must be called."""
        async def mock_bridge_consumer(*_args, **_kwargs):
            yield {"event": "custom", "data": {"type": "reasoning_delta", "content": "test"}}
            raise RuntimeError("Bridge connection lost")

        with patch(
            "apps.backend.app.services.bridge_consumer.bridge_consumer",
            side_effect=mock_bridge_consumer,
        ):
            lifecycle_task = _spawn_lifecycle_consumer(
                task_id="task-1",
                family_id=1,
                run_id="run-1",
            )
            await lifecycle_task

        assert mocked["completed"] == []
        assert len(mocked["failed"]) == 1
        assert mocked["failed"][0][0] == "task-1"
        # Safe message mapping: RuntimeError → "任务执行异常"
        assert mocked["failed"][0][1] == "任务执行异常"

    async def test_fail_task_called_on_gap(self, mocked):
        """When bridge stream yields a gap event, fail_task must be called."""
        async def mock_bridge_consumer(*_args, **_kwargs):
            yield {"event": "custom", "data": {"type": "reasoning_delta", "content": "test"}}
            yield {"event": "gap", "data": {"code": "stream_replay_gap"}}

        with patch(
            "apps.backend.app.services.bridge_consumer.bridge_consumer",
            side_effect=mock_bridge_consumer,
        ):
            lifecycle_task = _spawn_lifecycle_consumer(
                task_id="task-1",
                family_id=1,
                run_id="run-1",
            )
            await lifecycle_task

        assert mocked["completed"] == []
        assert len(mocked["failed"]) == 1
        assert "间断" in mocked["failed"][0][1]

    async def test_on_result_callback_invoked(self, mocked):
        """When on_result callback is provided, it must be called for custom events."""
        callback_invocations = []

        async def mock_on_result(event_type, data):
            callback_invocations.append((event_type, data))

        async def mock_bridge_consumer(*_args, **_kwargs):
            yield {"event": "custom", "data": {"type": "narrative.result", "payload": {"text": "test"}}}
            yield {"event": "end", "data": None}

        with patch(
            "apps.backend.app.services.bridge_consumer.bridge_consumer",
            side_effect=mock_bridge_consumer,
        ):
            lifecycle_task = _spawn_lifecycle_consumer(
                task_id="task-1",
                family_id=1,
                run_id="run-1",
                on_result=mock_on_result,
            )
            await lifecycle_task

        assert len(callback_invocations) == 1
        assert callback_invocations[0][0] == "custom"
        assert callback_invocations[0][1]["type"] == "narrative.result"
        assert len(mocked["completed"]) == 1

    async def test_lifecycle_consumer_survives_without_subscribers(self, mocked):
        """The lifecycle consumer must complete the task even if no SSE client subscribes."""
        async def mock_bridge_consumer(*_args, **_kwargs):
            yield {"event": "custom", "data": {"type": "reasoning_delta", "content": "step 1"}}
            yield {"event": "custom", "data": {"type": "reasoning_delta", "content": "step 2"}}
            yield {"event": "end", "data": None}

        with patch(
            "apps.backend.app.services.bridge_consumer.bridge_consumer",
            side_effect=mock_bridge_consumer,
        ):
            # Spawn lifecycle consumer (simulates what happens when SSE client disconnects)
            lifecycle_task = _spawn_lifecycle_consumer(
                task_id="task-1",
                family_id=1,
                run_id="run-1",
            )
            # No SSE client subscribes — but lifecycle consumer still runs
            await lifecycle_task

        assert len(mocked["completed"]) == 1
        assert mocked["failed"] == []
