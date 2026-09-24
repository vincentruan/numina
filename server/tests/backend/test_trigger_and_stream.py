"""Tests for the trigger_and_stream() helper in bridge_consumer.py."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.fixture
def mock_agent_client():
    """Mock AgentClient that returns a canned trigger response."""
    client = AsyncMock()
    resp = MagicMock()
    resp.headers = {"Content-Location": "/api/threads/t1/runs/run-123"}
    resp.raise_for_status = MagicMock()
    client.post = AsyncMock(return_value=resp)
    return client


@pytest.fixture
def patched_helpers():
    """Patch all downstream dependencies of trigger_and_stream."""
    with (
        patch(
            "apps.backend.app.services.bridge_consumer.AITaskService"
        ) as mock_task_svc,
        patch(
            "apps.backend.app.services.bridge_consumer._lease_heartbeat",
            new_callable=AsyncMock,
        ) as mock_hb,
        patch(
            "apps.backend.app.services.bridge_consumer._spawn_lifecycle_consumer",
        ) as mock_lifecycle,
        patch(
            "apps.backend.app.services.bridge_consumer.consume_task_stream",
        ) as mock_consume,
        patch(
            "apps.backend.app.services.bridge_consumer.get_shared_bridge",
        ) as mock_bridge,
        patch(
            "apps.backend.app.services.bridge_consumer.tracked_sse_stream",
        ) as mock_tracked,
    ):
        mock_task_svc.extract_and_attach_run_id = MagicMock()

        async def fake_stream(**kwargs):
            yield 'event: metadata\ndata: {"task_id": "t1"}\n\n'
            yield 'event: end\ndata: {"status": "success"}\n\n'

        mock_consume.side_effect = fake_stream
        mock_tracked.side_effect = lambda task_id, gen: gen

        async def fake_heartbeat(task_id, family_id, stop_event):
            await stop_event.wait()

        mock_hb.side_effect = fake_heartbeat

        yield {
            "task_svc": mock_task_svc,
            "heartbeat": mock_hb,
            "lifecycle": mock_lifecycle,
            "consume": mock_consume,
            "bridge": mock_bridge,
            "tracked": mock_tracked,
        }


class TestTriggerAndStream:
    """Verify trigger_and_stream encapsulates the full SSE lifecycle."""

    async def test_returns_streaming_response(self, mock_agent_client, patched_helpers):
        from apps.backend.app.services.bridge_consumer import trigger_and_stream

        result = await trigger_and_stream(
            agent_client=mock_agent_client,
            agent_url="/internal/gateway/runs/asset-report/session-1",
            json_body={"family_id": "123"},
            task_id="task-1",
            family_id=123,
            session_id="session-1",
        )
        assert result.media_type == "text/event-stream"

    async def test_attaches_run_id_to_task(self, mock_agent_client, patched_helpers):
        from apps.backend.app.services.bridge_consumer import trigger_and_stream

        await trigger_and_stream(
            agent_client=mock_agent_client,
            agent_url="/internal/gateway/runs/asset-report/session-1",
            json_body={"family_id": "123"},
            task_id="task-1",
            family_id=123,
            session_id="session-1",
        )
        patched_helpers["task_svc"].extract_and_attach_run_id.assert_called_once_with(
            "task-1", "/api/threads/t1/runs/run-123", 123
        )

    async def test_spawns_lifecycle_consumer(self, mock_agent_client, patched_helpers):
        from apps.backend.app.services.bridge_consumer import trigger_and_stream

        await trigger_and_stream(
            agent_client=mock_agent_client,
            agent_url="/internal/gateway/runs/asset-report/session-1",
            json_body={"family_id": "123"},
            task_id="task-1",
            family_id=123,
            session_id="session-1",
        )
        patched_helpers["lifecycle"].assert_called_once()
        call_kwargs = patched_helpers["lifecycle"].call_args.kwargs
        assert call_kwargs["task_id"] == "task-1"
        assert call_kwargs["family_id"] == 123
        assert call_kwargs["run_id"] == "run-123"

    async def test_passes_on_result_callback(self, mock_agent_client, patched_helpers):
        from apps.backend.app.services.bridge_consumer import trigger_and_stream

        on_result = AsyncMock()
        await trigger_and_stream(
            agent_client=mock_agent_client,
            agent_url="/internal/gateway/runs/finance-coach/session-1",
            json_body={"family_id": "123"},
            task_id="task-1",
            family_id=123,
            session_id="session-1",
            on_result=on_result,
        )
        call_kwargs = patched_helpers["lifecycle"].call_args.kwargs
        assert call_kwargs.get("on_result") is on_result

    async def test_passes_thread_id_to_lifecycle(
        self, mock_agent_client, patched_helpers
    ):
        from apps.backend.app.services.bridge_consumer import trigger_and_stream

        await trigger_and_stream(
            agent_client=mock_agent_client,
            agent_url="/internal/gateway/runs/asset-report/session-1",
            json_body={"family_id": "123"},
            task_id="task-1",
            family_id=123,
            session_id="session-1",
            thread_id="custom-thread-id",
        )
        call_kwargs = patched_helpers["lifecycle"].call_args.kwargs
        assert call_kwargs.get("thread_id") == "custom-thread-id"

    async def test_default_thread_id_is_session_id(
        self, mock_agent_client, patched_helpers
    ):
        from apps.backend.app.services.bridge_consumer import trigger_and_stream

        await trigger_and_stream(
            agent_client=mock_agent_client,
            agent_url="/internal/gateway/runs/asset-report/session-1",
            json_body={"family_id": "123"},
            task_id="task-1",
            family_id=123,
            session_id="session-1",
        )
        call_kwargs = patched_helpers["lifecycle"].call_args.kwargs
        assert call_kwargs.get("thread_id") == "session-1"

    async def test_passes_last_event_id_to_consume(
        self, mock_agent_client, patched_helpers
    ):
        from apps.backend.app.services.bridge_consumer import trigger_and_stream

        await trigger_and_stream(
            agent_client=mock_agent_client,
            agent_url="/internal/gateway/runs/asset-report/session-1",
            json_body={"family_id": "123"},
            task_id="task-1",
            family_id=123,
            session_id="session-1",
            last_event_id="evt-42",
        )
        call_kwargs = patched_helpers["consume"].call_args.kwargs
        assert call_kwargs.get("last_event_id") == "evt-42"

    async def test_sets_x_accel_buffering_header(
        self, mock_agent_client, patched_helpers
    ):
        from apps.backend.app.services.bridge_consumer import trigger_and_stream

        result = await trigger_and_stream(
            agent_client=mock_agent_client,
            agent_url="/internal/gateway/runs/asset-report/session-1",
            json_body={"family_id": "123"},
            task_id="task-1",
            family_id=123,
            session_id="session-1",
        )
        assert result.headers.get("X-Accel-Buffering") == "no"

    async def test_propagates_trigger_failure(self, mock_agent_client, patched_helpers):
        """Agent trigger failure should propagate to the caller."""
        from apps.backend.app.services.bridge_consumer import trigger_and_stream

        mock_agent_client.post = AsyncMock(side_effect=Exception("Agent unavailable"))
        with pytest.raises(Exception, match="Agent unavailable"):
            await trigger_and_stream(
                agent_client=mock_agent_client,
                agent_url="/internal/gateway/runs/asset-report/session-1",
                json_body={"family_id": "123"},
                task_id="task-1",
                family_id=123,
                session_id="session-1",
            )
