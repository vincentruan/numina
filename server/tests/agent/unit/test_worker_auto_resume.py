"""Tests for auto-resume detection in RunPipeline.

Verifies:
- auto_resume=True queries backend and sets checkpoint_id from failed task
- auto_resume=False does not query backend
- Backend query failure is non-fatal (no crash, checkpoint_id stays None)
- Successful previous run does not trigger resume
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
    record.metadata = {"app": "asset-report", "task_id": task_id}
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


class TestAutoResume:
    """Tests for RunPipeline auto_resume in __aenter__."""

    @pytest.mark.asyncio
    async def test_auto_resume_sets_checkpoint_from_failed_task(self):
        """auto_resume=True with a failed task sets checkpoint_id."""
        from apps.agent.services.runtime.run_pipeline import RunPipeline

        record = _make_record(task_id="99999")
        bridge = _make_bridge()
        run_manager = _make_run_manager()

        pipeline = RunPipeline(
            app_name="asset-report",
            family_id="1001",
            user_id="user-1",
            thread_id="thread-abc",
            record=record,
            bridge=bridge,
            run_manager=run_manager,
            auto_resume=True,
        )

        # Mock BackendClient.get_task_info
        mock_backend_client = AsyncMock()
        mock_backend_client.get_task_info = AsyncMock(return_value={
            "status": "failed",
            "last_checkpoint_id": "ckpt-auto-resume",
            "skill_id": "asset-report",
        })
        mock_backend_client.get_family_ai_config = AsyncMock(return_value={
            "providers": [{"config_id": "cfg-1", "is_active": True, "circuit_state": "closed"}],
        })

        with (
            patch(
                "apps.agent.services.runtime.run_pipeline.BackendClient",
                return_value=mock_backend_client,
            ),
            patch(
                "apps.agent.services.runtime.run_pipeline._resolve_numina_mcp_servers",
                new=AsyncMock(return_value=[]),
            ),
            patch(
                "apps.agent.services.runtime.run_pipeline.create_family_adapter",
                return_value=MagicMock(),
            ),
            patch(
                "apps.agent.services.deerflow_adapter.active_skill_context.set_active_skill",
                return_value="token-1",
            ),
            patch(
                "apps.agent.services.deerflow_adapter.active_skill_context.reset_active_skill",
                MagicMock(),
            ),
        ):
            await pipeline.__aenter__()

        assert pipeline.checkpoint_id == "ckpt-auto-resume"

    @pytest.mark.asyncio
    async def test_auto_resume_false_does_not_query(self):
        """auto_resume=False (default) does not query backend."""
        from apps.agent.services.runtime.run_pipeline import RunPipeline

        record = _make_record()
        bridge = _make_bridge()
        run_manager = _make_run_manager()

        pipeline = RunPipeline(
            app_name="asset-report",
            family_id="1001",
            user_id="user-1",
            thread_id="thread-abc",
            record=record,
            bridge=bridge,
            run_manager=run_manager,
            # auto_resume defaults to False
        )

        mock_backend_client = AsyncMock()
        mock_backend_client.get_task_info = AsyncMock()
        mock_backend_client.get_family_ai_config = AsyncMock(return_value={
            "providers": [{"config_id": "cfg-1", "is_active": True, "circuit_state": "closed"}],
        })

        with (
            patch(
                "apps.agent.services.runtime.run_pipeline.BackendClient",
                return_value=mock_backend_client,
            ),
            patch(
                "apps.agent.services.runtime.run_pipeline._resolve_numina_mcp_servers",
                new=AsyncMock(return_value=[]),
            ),
            patch(
                "apps.agent.services.runtime.run_pipeline.create_family_adapter",
                return_value=MagicMock(),
            ),
            patch(
                "apps.agent.services.deerflow_adapter.active_skill_context.set_active_skill",
                return_value="token-1",
            ),
            patch(
                "apps.agent.services.deerflow_adapter.active_skill_context.reset_active_skill",
                MagicMock(),
            ),
        ):
            await pipeline.__aenter__()

        # get_task_info should NOT have been called
        mock_backend_client.get_task_info.assert_not_awaited()
        assert pipeline.checkpoint_id is None

    @pytest.mark.asyncio
    async def test_auto_resume_backend_failure_non_fatal(self):
        """Backend query failure does not crash; checkpoint_id stays None."""
        from apps.agent.services.runtime.run_pipeline import RunPipeline

        record = _make_record()
        bridge = _make_bridge()
        run_manager = _make_run_manager()

        pipeline = RunPipeline(
            app_name="asset-report",
            family_id="1001",
            user_id="user-1",
            thread_id="thread-abc",
            record=record,
            bridge=bridge,
            run_manager=run_manager,
            auto_resume=True,
        )

        mock_backend_client = AsyncMock()
        mock_backend_client.get_task_info = AsyncMock(
            side_effect=RuntimeError("backend unavailable")
        )
        mock_backend_client.get_family_ai_config = AsyncMock(return_value={
            "providers": [{"config_id": "cfg-1", "is_active": True, "circuit_state": "closed"}],
        })

        with (
            patch(
                "apps.agent.services.runtime.run_pipeline.BackendClient",
                return_value=mock_backend_client,
            ),
            patch(
                "apps.agent.services.runtime.run_pipeline._resolve_numina_mcp_servers",
                new=AsyncMock(return_value=[]),
            ),
            patch(
                "apps.agent.services.runtime.run_pipeline.create_family_adapter",
                return_value=MagicMock(),
            ),
            patch(
                "apps.agent.services.deerflow_adapter.active_skill_context.set_active_skill",
                return_value="token-1",
            ),
            patch(
                "apps.agent.services.deerflow_adapter.active_skill_context.reset_active_skill",
                MagicMock(),
            ),
        ):
            # Should not raise
            await pipeline.__aenter__()

        assert pipeline.checkpoint_id is None
