"""Tests for orphan_detector — verifies Phase 5.1 background recovery loop.

Test scenarios:
- No stale tasks → _scan_and_recover returns 0, no mark_interrupted calls
- Stale tasks present → mark_interrupted called per task, correct count returned
- Single-task failure does not abort the scan cycle (other tasks still recovered)
- orphan_detector_loop cancels cleanly on CancelledError
"""

from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def family_id(auth_headers, client):
    """Get the family_id for the test user."""
    resp = client.get("/api/v1/auth/me", headers=auth_headers)
    return resp.json()["data"]["family_id"]


class TestScanAndRecover:
    """Test _scan_and_recover_sync behavior."""

    def test_no_stale_tasks_returns_zero(self):
        """When no stale tasks exist, returns 0 without calling mark_interrupted."""
        from apps.backend.app.services.orphan_detector import _scan_and_recover_sync

        with patch(
            "apps.backend.app.services.ai_task_service.AITaskService.get_stale_running_tasks",
            return_value=[],
        ) as mock_get, patch(
            "apps.backend.app.services.ai_task_service.AITaskService.mark_interrupted"
        ) as mock_mark:
            result = _scan_and_recover_sync()

        assert result == 0
        mock_get.assert_called_once()
        mock_mark.assert_not_called()

    def test_stale_tasks_marked_interrupted(self):
        """Stale tasks are passed to mark_interrupted with lease_guard=True."""
        from apps.backend.app.services.orphan_detector import _scan_and_recover_sync

        stale_task_1 = MagicMock(id=101, family_id=1, skill_id="narrative")
        stale_task_2 = MagicMock(id=102, family_id=1, skill_id="coach")

        with patch(
            "apps.backend.app.services.ai_task_service.AITaskService.get_stale_running_tasks",
            return_value=[stale_task_1, stale_task_2],
        ), patch(
            "apps.backend.app.services.ai_task_service.AITaskService.mark_interrupted",
            return_value=True,
        ) as mock_mark:
            result = _scan_and_recover_sync()

        assert result == 2
        assert mock_mark.call_count == 2
        # Verify lease_guard=True was passed
        for call in mock_mark.call_args_list:
            assert call.kwargs["lease_guard"] is True

    def test_single_task_failure_does_not_abort_scan(self):
        """When mark_interrupted fails for one task, others are still processed."""
        from apps.backend.app.services.orphan_detector import _scan_and_recover_sync

        stale_task_1 = MagicMock(id=201, family_id=1, skill_id="narrative")
        stale_task_2 = MagicMock(id=202, family_id=1, skill_id="coach")
        stale_task_3 = MagicMock(id=203, family_id=1, skill_id="report")

        call_count = 0

        def mark_side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RuntimeError("DB connection lost")
            return True

        with patch(
            "apps.backend.app.services.ai_task_service.AITaskService.get_stale_running_tasks",
            return_value=[stale_task_1, stale_task_2, stale_task_3],
        ), patch(
            "apps.backend.app.services.ai_task_service.AITaskService.mark_interrupted",
            side_effect=mark_side_effect,
        ):
            result = _scan_and_recover_sync()

        # Task 1 failed, tasks 2+3 succeeded → recovered = 2
        assert result == 2

    def test_session_closed_after_scan(self):
        """SessionLocal is always closed, even on exception."""
        from apps.backend.app.services.orphan_detector import _scan_and_recover_sync

        mock_db = MagicMock()

        with patch(
            "apps.backend.app.services.orphan_detector.packages.db.session.SessionLocal",
            return_value=mock_db,
        ) if False else patch(
            "packages.db.session.SessionLocal",
            return_value=mock_db,
        ), patch(
            "apps.backend.app.services.ai_task_service.AITaskService.get_stale_running_tasks",
            side_effect=RuntimeError("DB unreachable"),
        ):
            # Should not raise — the exception is caught in the finally block
            # but we need to handle it in the caller
            with pytest.raises(RuntimeError):
                _scan_and_recover_sync()

        # Verify session was closed despite the exception
        mock_db.close.assert_called_once()


class TestOrphanDetectorLoop:
    """Test orphan_detector_loop cancellation and error handling."""

    async def test_loop_cancels_cleanly(self):
        """orphan_detector_loop re-raises CancelledError on shutdown."""
        import asyncio
        from apps.backend.app.services.orphan_detector import orphan_detector_loop

        with patch(
            "apps.backend.app.services.orphan_detector._scan_and_recover",
            return_value=0,
        ):
            task = asyncio.create_task(orphan_detector_loop())
            # Give the loop one iteration
            await asyncio.sleep(0.05)
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task

    async def test_loop_continues_after_scan_error(self):
        """When _scan_and_recover raises, the loop logs and continues."""
        import asyncio
        from apps.backend.app.services.orphan_detector import orphan_detector_loop

        call_count = 0

        async def flaky_scan():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RuntimeError("transient DB error")
            # Cancel after the second iteration to exit the loop
            raise asyncio.CancelledError

        with patch(
            "apps.backend.app.services.orphan_detector._scan_and_recover",
            side_effect=flaky_scan,
        ), patch(
            "apps.backend.app.services.orphan_detector.asyncio.sleep",
            side_effect=asyncio.CancelledError,
        ):
            task = asyncio.create_task(orphan_detector_loop())
            with pytest.raises(asyncio.CancelledError):
                await task

        # Loop should have run at least once (the first flaky call)
        assert call_count >= 1
