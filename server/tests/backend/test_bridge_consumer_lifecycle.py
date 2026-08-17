"""Tests for _spawn_lifecycle_consumer — verifies F1 fix.

The lifecycle consumer must call complete_task/fail_task regardless of
whether an SSE client is connected. This is the core F1 fix: previously,
complete_task was inside the SSE async generator, so client disconnect
left tasks stuck in 'running'.
"""

import asyncio
from unittest.mock import patch

import pytest


class TestLifecycleConsumer:
    """Test _spawn_lifecycle_consumer completes task lifecycle independently."""

    def test_complete_task_called_on_normal_end(self, db, family_id):
        """When bridge stream ends normally, complete_task must be called."""
        from apps.backend.app.services.ai_task_service import AITaskService
        from apps.backend.app.services.bridge_consumer import _spawn_lifecycle_consumer

        task = AITaskService.create_task(
            family_id=family_id,
            skill_id="narrative",
            session_id=None,
            db=db,
        )

        async def mock_bridge_consumer(*_args, **_kwargs):
            yield {"event": "custom", "data": {"type": "reasoning_delta", "content": "test"}}
            yield {"event": "end", "data": None}

        with patch(
            "apps.backend.app.services.bridge_consumer.bridge_consumer",
            side_effect=mock_bridge_consumer,
        ):
            lifecycle_task = _spawn_lifecycle_consumer(
                task_id=task.id,
                family_id=family_id,
                run_id="test-run-id",
            )
            # Wait for the lifecycle consumer to complete
            asyncio.get_event_loop().run_until_complete(lifecycle_task)

        # Verify task was completed
        db.refresh(task)
        assert task.status == "completed"

    def test_fail_task_called_on_exception(self, db, family_id):
        """When bridge stream raises an exception, fail_task must be called."""
        from apps.backend.app.services.ai_task_service import AITaskService
        from apps.backend.app.services.bridge_consumer import _spawn_lifecycle_consumer

        task = AITaskService.create_task(
            family_id=family_id,
            skill_id="narrative",
            session_id=None,
            db=db,
        )

        async def mock_bridge_consumer(*_args, **_kwargs):
            yield {"event": "custom", "data": {"type": "reasoning_delta", "content": "test"}}
            raise RuntimeError("Bridge connection lost")

        with patch(
            "apps.backend.app.services.bridge_consumer.bridge_consumer",
            side_effect=mock_bridge_consumer,
        ):
            lifecycle_task = _spawn_lifecycle_consumer(
                task_id=task.id,
                family_id=family_id,
                run_id="test-run-id",
            )
            asyncio.get_event_loop().run_until_complete(lifecycle_task)

        # Verify task was failed with safe error message
        db.refresh(task)
        assert task.status == "failed"
        assert task.error_message == "服务异常"

    def test_fail_task_called_on_gap(self, db, family_id):
        """When bridge stream yields a gap event, fail_task must be called."""
        from apps.backend.app.services.ai_task_service import AITaskService
        from apps.backend.app.services.bridge_consumer import _spawn_lifecycle_consumer

        task = AITaskService.create_task(
            family_id=family_id,
            skill_id="narrative",
            session_id=None,
            db=db,
        )

        async def mock_bridge_consumer(*_args, **_kwargs):
            yield {"event": "custom", "data": {"type": "reasoning_delta", "content": "test"}}
            yield {"event": "gap", "data": {"code": "stream_replay_gap"}}

        with patch(
            "apps.backend.app.services.bridge_consumer.bridge_consumer",
            side_effect=mock_bridge_consumer,
        ):
            lifecycle_task = _spawn_lifecycle_consumer(
                task_id=task.id,
                family_id=family_id,
                run_id="test-run-id",
            )
            asyncio.get_event_loop().run_until_complete(lifecycle_task)

        # Verify task was failed with gap-specific message
        db.refresh(task)
        assert task.status == "failed"
        assert "间断" in task.error_message

    def test_on_result_callback_invoked(self, db, family_id):
        """When on_result callback is provided, it must be called for custom events."""
        from apps.backend.app.services.ai_task_service import AITaskService
        from apps.backend.app.services.bridge_consumer import _spawn_lifecycle_consumer

        task = AITaskService.create_task(
            family_id=family_id,
            skill_id="narrative",
            session_id=None,
            db=db,
        )

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
                task_id=task.id,
                family_id=family_id,
                run_id="test-run-id",
                on_result=mock_on_result,
            )
            asyncio.get_event_loop().run_until_complete(lifecycle_task)

        # Verify callback was invoked
        assert len(callback_invocations) == 1
        assert callback_invocations[0][0] == "custom"
        assert callback_invocations[0][1]["type"] == "narrative.result"

        # Verify task was still completed
        db.refresh(task)
        assert task.status == "completed"

    def test_lifecycle_consumer_survives_without_subscribers(self, db, family_id):
        """The lifecycle consumer must complete the task even if no SSE client subscribes.

        This is the core F1 scenario: client disconnects before task completes,
        but the lifecycle consumer (running as an independent asyncio.Task)
        must still call complete_task.
        """
        from apps.backend.app.services.ai_task_service import AITaskService
        from apps.backend.app.services.bridge_consumer import _spawn_lifecycle_consumer

        task = AITaskService.create_task(
            family_id=family_id,
            skill_id="narrative",
            session_id=None,
            db=db,
        )

        async def mock_bridge_consumer(*_args, **_kwargs):
            # Simulate a long-running task that eventually completes
            yield {"event": "custom", "data": {"type": "reasoning_delta", "content": "step 1"}}
            yield {"event": "custom", "data": {"type": "reasoning_delta", "content": "step 2"}}
            yield {"event": "end", "data": None}

        with patch(
            "apps.backend.app.services.bridge_consumer.bridge_consumer",
            side_effect=mock_bridge_consumer,
        ):
            # Spawn lifecycle consumer (simulates what happens when SSE client disconnects)
            lifecycle_task = _spawn_lifecycle_consumer(
                task_id=task.id,
                family_id=family_id,
                run_id="test-run-id",
            )
            # No SSE client subscribes — but lifecycle consumer still runs
            asyncio.get_event_loop().run_until_complete(lifecycle_task)

        # Verify task was completed despite no SSE client
        db.refresh(task)
        assert task.status == "completed"


@pytest.fixture
def family_id(auth_headers, client):
    """Get the family_id for the test user."""
    resp = client.get("/api/v1/auth/me", headers=auth_headers)
    return resp.json()["data"]["family_id"]
