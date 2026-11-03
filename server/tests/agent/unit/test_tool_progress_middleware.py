"""Tests for ToolProgressMiddleware."""

from __future__ import annotations

import threading
from unittest.mock import patch

from apps.agent.services.runtime.tool_progress_middleware import (
    ToolProgressMiddleware,
    ToolStatus,
)


class TestToolProgressMiddleware:
    """Unit tests for the tool execution health tracker."""

    def test_before_tool_call_returns_active_event(self) -> None:
        """before_tool_call emits an ACTIVE event."""
        mw = ToolProgressMiddleware()
        event = mw.before_tool_call("call_1", "web_search")

        assert event is not None
        assert event.tool_call_id == "call_1"
        assert event.tool_name == "web_search"
        assert event.status == ToolStatus.ACTIVE
        assert event.elapsed_seconds == 0.0

    def test_after_tool_call_within_threshold(self) -> None:
        """Tool completes within warn_threshold -> ACTIVE status."""
        mw = ToolProgressMiddleware(warn_threshold_seconds=30.0)
        mw.before_tool_call("call_1", "web_search")

        event = mw.after_tool_call("call_1", "web_search")
        assert event is not None
        assert event.status == ToolStatus.ACTIVE
        assert "completed" in event.message
        assert mw.active_count == 0  # cleaned up

    def test_after_tool_call_exceeds_warn_threshold(self) -> None:
        """Tool exceeds warn_threshold -> WARNED status (deterministic time)."""
        mw = ToolProgressMiddleware(
            warn_threshold_seconds=10.0,
            hard_stop_threshold_seconds=60.0,
        )
        # Use mocked time to avoid flaky real sleeps
        with patch("apps.agent.services.runtime.tool_progress_middleware.time") as mock_time:
            mock_time.monotonic.side_effect = [0.0, 15.0]  # start=0, end=15 (>10s warn)
            mw.before_tool_call("call_1", "web_search")
            event = mw.after_tool_call("call_1", "web_search")

        assert event is not None
        assert event.status == ToolStatus.WARNED
        assert "warn" in event.message.lower()
        assert mw.active_count == 0

    def test_after_tool_call_exceeds_hard_stop(self) -> None:
        """Tool exceeds hard_stop_threshold -> BLOCKED status (deterministic time)."""
        mw = ToolProgressMiddleware(
            warn_threshold_seconds=5.0,
            hard_stop_threshold_seconds=10.0,
        )
        with patch("apps.agent.services.runtime.tool_progress_middleware.time") as mock_time:
            mock_time.monotonic.side_effect = [0.0, 15.0]  # start=0, end=15 (>10s hard stop)
            mw.before_tool_call("call_1", "read_file")
            event = mw.after_tool_call("call_1", "read_file")

        assert event is not None
        assert event.status == ToolStatus.BLOCKED
        assert "hard stop" in event.message.lower()

    def test_after_tool_call_unknown_id(self) -> None:
        """after_tool_call with unknown call_id -> returns None."""
        mw = ToolProgressMiddleware()
        result = mw.after_tool_call("unknown_id", "web_search")
        assert result is None

    def test_concurrent_tools_tracked_independently(self) -> None:
        """Two tools running concurrently have independent state."""
        mw = ToolProgressMiddleware(
            warn_threshold_seconds=10.0,
            hard_stop_threshold_seconds=60.0,
        )
        with patch("apps.agent.services.runtime.tool_progress_middleware.time") as mock_time:
            # Start both tools at t=0
            mock_time.monotonic.side_effect = [0.0, 0.0]
            mw.before_tool_call("call_1", "web_search")
            mw.before_tool_call("call_2", "read_file")
            assert mw.active_count == 2

            # Complete fast tool at t=1 (within threshold)
            mock_time.monotonic.side_effect = [1.0]
            event_2 = mw.after_tool_call("call_2", "read_file")
            assert event_2 is not None
            assert event_2.status == ToolStatus.ACTIVE
            assert mw.active_count == 1

            # Complete slow tool at t=15 (exceeds warn threshold)
            mock_time.monotonic.side_effect = [15.0]
            event_1 = mw.after_tool_call("call_1", "web_search")
            assert event_1 is not None
            assert event_1.status == ToolStatus.WARNED
            assert mw.active_count == 0

    def test_get_active_tools_snapshot(self) -> None:
        """get_active_tools returns a snapshot of tracked tools."""
        mw = ToolProgressMiddleware()
        mw.before_tool_call("call_1", "web_search")
        mw.before_tool_call("call_2", "read_file")

        snapshot = mw.get_active_tools()
        assert len(snapshot) == 2
        names = {s["tool_name"] for s in snapshot}
        assert names == {"web_search", "read_file"}
        for s in snapshot:
            assert s["status"] == "active"
            assert s["elapsed_seconds"] >= 0.0

    def test_after_failed_tool_call(self) -> None:
        """after_tool_call with success=False -> message says 'failed'."""
        mw = ToolProgressMiddleware()
        mw.before_tool_call("call_1", "web_search")

        event = mw.after_tool_call("call_1", "web_search", success=False)
        assert event is not None
        assert "failed" in event.message

    def test_tool_status_enum_values(self) -> None:
        """ToolStatus enum has expected values."""
        assert ToolStatus.ACTIVE.value == "active"
        assert ToolStatus.WARNED.value == "warned"
        assert ToolStatus.BLOCKED.value == "blocked"

    def test_elapsed_seconds_in_event(self) -> None:
        """Event includes accurate elapsed_seconds (deterministic time)."""
        mw = ToolProgressMiddleware()
        with patch("apps.agent.services.runtime.tool_progress_middleware.time") as mock_time:
            mock_time.monotonic.side_effect = [0.0, 0.5]  # 0.5s elapsed
            mw.before_tool_call("call_1", "web_search")
            event = mw.after_tool_call("call_1", "web_search")

        assert event is not None
        assert event.elapsed_seconds == 0.5

    def test_concurrent_thread_access(self) -> None:
        """Thread safety: concurrent before/after calls don't corrupt state."""
        mw = ToolProgressMiddleware(
            warn_threshold_seconds=10.0,
            hard_stop_threshold_seconds=60.0,
        )
        errors: list[Exception] = []
        num_threads = 10

        def worker(thread_id: int) -> None:
            try:
                call_id = f"call_{thread_id}"
                mw.before_tool_call(call_id, f"tool_{thread_id}")
                # Small yield to increase interleaving chance
                threading.Event().wait(0.001)
                event = mw.after_tool_call(call_id, f"tool_{thread_id}")
                assert event is not None
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(num_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5.0)

        assert not errors, f"Thread safety errors: {errors}"
        assert mw.active_count == 0  # All tools completed
