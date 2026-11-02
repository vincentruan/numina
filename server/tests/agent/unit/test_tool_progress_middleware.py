"""Tests for ToolProgressMiddleware."""

from __future__ import annotations

import time

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
        """Tool completes within warn_threshold → ACTIVE status."""
        mw = ToolProgressMiddleware(warn_threshold_seconds=30.0)
        mw.before_tool_call("call_1", "web_search")

        event = mw.after_tool_call("call_1", "web_search")
        assert event is not None
        assert event.status == ToolStatus.ACTIVE
        assert "completed" in event.message
        assert mw.active_count == 0  # cleaned up

    def test_after_tool_call_exceeds_warn_threshold(self) -> None:
        """Tool exceeds warn_threshold → WARNED status."""
        mw = ToolProgressMiddleware(
            warn_threshold_seconds=0.1,
            hard_stop_threshold_seconds=10.0,
        )
        mw.before_tool_call("call_1", "web_search")
        time.sleep(0.15)

        event = mw.after_tool_call("call_1", "web_search")
        assert event is not None
        assert event.status == ToolStatus.WARNED
        assert "warn" in event.message.lower()
        assert mw.active_count == 0

    def test_after_tool_call_exceeds_hard_stop(self) -> None:
        """Tool exceeds hard_stop_threshold → BLOCKED status."""
        mw = ToolProgressMiddleware(
            warn_threshold_seconds=0.05,
            hard_stop_threshold_seconds=0.1,
        )
        mw.before_tool_call("call_1", "read_file")
        time.sleep(0.15)

        event = mw.after_tool_call("call_1", "read_file")
        assert event is not None
        assert event.status == ToolStatus.BLOCKED
        assert "hard stop" in event.message.lower()

    def test_after_tool_call_unknown_id(self) -> None:
        """after_tool_call with unknown call_id → returns None."""
        mw = ToolProgressMiddleware()
        result = mw.after_tool_call("unknown_id", "web_search")
        assert result is None

    def test_concurrent_tools_tracked_independently(self) -> None:
        """Two tools running concurrently have independent state."""
        mw = ToolProgressMiddleware(
            warn_threshold_seconds=0.1,
            hard_stop_threshold_seconds=10.0,
        )
        mw.before_tool_call("call_1", "web_search")
        mw.before_tool_call("call_2", "read_file")
        assert mw.active_count == 2

        # Complete the fast tool
        time.sleep(0.01)
        event_2 = mw.after_tool_call("call_2", "read_file")
        assert event_2 is not None
        assert event_2.status == ToolStatus.ACTIVE
        assert mw.active_count == 1

        # Wait and complete the slow tool
        time.sleep(0.15)
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

    def test_check_tool_call_always_allows(self) -> None:
        """check_tool_call is a no-op guardrail hook — always returns True."""
        mw = ToolProgressMiddleware()
        assert mw.check_tool_call("web_search") is True
        assert mw.check_tool_call("bash", tool_args={"cmd": "ls"}) is True

    def test_after_failed_tool_call(self) -> None:
        """after_tool_call with success=False → message says 'failed'."""
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
        """Event includes accurate elapsed_seconds."""
        mw = ToolProgressMiddleware()
        mw.before_tool_call("call_1", "web_search")
        time.sleep(0.05)

        event = mw.after_tool_call("call_1", "web_search")
        assert event is not None
        assert event.elapsed_seconds >= 0.04  # allow small timing variance
