"""Tests for RunPipeline checkpoint capture (_capture_checkpoint_id).

Verifies:
- Checkpoint ID is captured and reported to backend after __aexit__
- Checkpointer read failure is non-fatal (does not affect run outcome)
- Missing task_id in metadata skips the report (no crash)
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from deerflow.runtime import RunManager, RunRecord, RunStatus, StreamBridge


def _make_record(run_id: str = "run-1", task_id: str = "12345") -> RunRecord:
    record = MagicMock(spec=RunRecord)
    record.run_id = run_id
    record.status = RunStatus.running
    record.abort_event = asyncio.Event()
    record.metadata = {"app": "finance-coach", "task_id": task_id}
    return record


def _make_bridge() -> MagicMock:
    bridge = MagicMock(spec=StreamBridge)
    bridge.publish = AsyncMock()
    bridge.publish_end = AsyncMock()
    bridge.cleanup = AsyncMock()
    return bridge


def _make_run_manager() -> MagicMock:
    rm = MagicMock(spec=RunManager)
    rm.set_status = AsyncMock()
    return rm


@pytest.fixture(autouse=True)
def _mock_mcp_context_assert():
    with patch(
        "apps.agent.services.runtime.sandbox_provider.assert_mcp_context_complete",
    ):
        yield


class TestCaptureCheckpointId:
    """Tests for RunPipeline._capture_checkpoint_id."""

    @pytest.mark.asyncio
    async def test_captures_and_reports_checkpoint(self):
        """Checkpoint ID is captured and reported to backend."""
        from apps.agent.services.runtime.run_pipeline import RunPipeline

        record = _make_record(task_id="99999")
        bridge = _make_bridge()
        run_manager = _make_run_manager()

        pipeline = RunPipeline(
            app_name="finance-coach",
            family_id="1001",
            user_id="user-1",
            thread_id="thread-abc",
            record=record,
            bridge=bridge,
            run_manager=run_manager,
        )

        # Mock checkpointer
        mock_checkpoint = {"id": "ckpt-xyz-789"}
        mock_tuple = MagicMock()
        mock_tuple.checkpoint = mock_checkpoint
        mock_checkpointer = AsyncMock()
        mock_checkpointer.aget_tuple = AsyncMock(return_value=mock_tuple)

        # Mock BackendClient
        mock_backend_client = AsyncMock()
        mock_backend_client.report_checkpoint_id = AsyncMock()

        with (
            patch(
                "apps.agent.services.deerflow_adapter.family_adapter_cache._get_shared_checkpointer",
                return_value=mock_checkpointer,
            ),
            patch(
                "apps.agent.services.runtime.run_pipeline.BackendClient",
                return_value=mock_backend_client,
            ),
        ):
            await pipeline._capture_checkpoint_id()

        mock_checkpointer.aget_tuple.assert_awaited_once_with(
            {"configurable": {"thread_id": "thread-abc"}}
        )
        mock_backend_client.report_checkpoint_id.assert_awaited_once_with(
            task_id=99999,
            checkpoint_id="ckpt-xyz-789",
        )

    @pytest.mark.asyncio
    async def test_checkpointer_failure_is_non_fatal(self):
        """Checkpointer read failure does not raise."""
        from apps.agent.services.runtime.run_pipeline import RunPipeline

        record = _make_record()
        bridge = _make_bridge()
        run_manager = _make_run_manager()

        pipeline = RunPipeline(
            app_name="finance-coach",
            family_id="1001",
            user_id="user-1",
            thread_id="thread-abc",
            record=record,
            bridge=bridge,
            run_manager=run_manager,
        )

        mock_checkpointer = AsyncMock()
        mock_checkpointer.aget_tuple = AsyncMock(
            side_effect=RuntimeError("checkpointer unavailable")
        )

        with (
            patch(
                "apps.agent.services.deerflow_adapter.family_adapter_cache._get_shared_checkpointer",
                return_value=mock_checkpointer,
            ),
        ):
            # Should not raise
            await pipeline._capture_checkpoint_id()

    @pytest.mark.asyncio
    async def test_no_task_id_skips_report(self):
        """When task_id is not in metadata, report is skipped."""
        from apps.agent.services.runtime.run_pipeline import RunPipeline

        record = _make_record()
        record.metadata = {"app": "finance-coach"}  # no task_id
        bridge = _make_bridge()
        run_manager = _make_run_manager()

        pipeline = RunPipeline(
            app_name="finance-coach",
            family_id="1001",
            user_id="user-1",
            thread_id="thread-abc",
            record=record,
            bridge=bridge,
            run_manager=run_manager,
        )

        mock_checkpoint = {"id": "ckpt-no-task"}
        mock_tuple = MagicMock()
        mock_tuple.checkpoint = mock_checkpoint
        mock_checkpointer = AsyncMock()
        mock_checkpointer.aget_tuple = AsyncMock(return_value=mock_tuple)

        mock_backend_client = AsyncMock()
        mock_backend_client.report_checkpoint_id = AsyncMock()

        with (
            patch(
                "apps.agent.services.deerflow_adapter.family_adapter_cache._get_shared_checkpointer",
                return_value=mock_checkpointer,
            ),
            patch(
                "apps.agent.services.runtime.run_pipeline.BackendClient",
                return_value=mock_backend_client,
            ),
        ):
            await pipeline._capture_checkpoint_id()

        # report_checkpoint_id should NOT have been called
        mock_backend_client.report_checkpoint_id.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_none_checkpoint_skips_report(self):
        """When checkpointer returns None, report is skipped."""
        from apps.agent.services.runtime.run_pipeline import RunPipeline

        record = _make_record()
        bridge = _make_bridge()
        run_manager = _make_run_manager()

        pipeline = RunPipeline(
            app_name="finance-coach",
            family_id="1001",
            user_id="user-1",
            thread_id="thread-abc",
            record=record,
            bridge=bridge,
            run_manager=run_manager,
        )

        mock_checkpointer = AsyncMock()
        mock_checkpointer.aget_tuple = AsyncMock(return_value=None)

        mock_backend_client = AsyncMock()
        mock_backend_client.report_checkpoint_id = AsyncMock()

        with (
            patch(
                "apps.agent.services.deerflow_adapter.family_adapter_cache._get_shared_checkpointer",
                return_value=mock_checkpointer,
            ),
            patch(
                "apps.agent.services.runtime.run_pipeline.BackendClient",
                return_value=mock_backend_client,
            ),
        ):
            await pipeline._capture_checkpoint_id()

        mock_backend_client.report_checkpoint_id.assert_not_awaited()
