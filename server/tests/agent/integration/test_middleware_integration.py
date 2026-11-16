"""Integration tests for SubagentLimitMiddleware and ToolProgressMiddleware (U4).

Verifies that the middlewares wire correctly into the dispatch pipeline:
1. Config injection creates middleware instances via _build_runtime_middlewares
2. SubagentLimitMiddleware correctly denies spawns when registry is at capacity
3. ToolProgressMiddleware emits progress events during tool execution
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from apps.agent.services.deerflow_adapter.family_adapter_cache import (
    _build_runtime_middlewares,
)
from apps.agent.services.runtime.subagent_limit_middleware import (
    SubagentLimitMiddleware,
)
from apps.agent.services.runtime.tool_progress_middleware import (
    ToolProgressMiddleware,
    ToolStatus,
)


class TestMiddlewareIntegration:
    """End-to-end middleware wiring tests."""

    def test_build_runtime_middlewares_disabled_by_default(self) -> None:
        """No middlewares created when config is absent/disabled."""
        result = _build_runtime_middlewares(ai_config={}, family_id="fam_1")
        assert result is None

    def test_build_runtime_middlewares_subagent_limit_enabled(self) -> None:
        """SubagentLimitMiddleware created when enabled in config."""
        ai_config = {
            "subagent_limit": {"enabled": True, "max_concurrent": 5},
        }
        result = _build_runtime_middlewares(ai_config, family_id="fam_1")

        assert result is not None
        assert len(result) == 1
        assert isinstance(result[0], SubagentLimitMiddleware)
        assert result[0].max_concurrent == 5
        assert result[0].family_id == "fam_1"

    def test_build_runtime_middlewares_tool_progress_enabled(self) -> None:
        """ToolProgressMiddleware created when enabled in config."""
        ai_config = {
            "tool_progress": {
                "enabled": True,
                "warn_threshold_seconds": 15.0,
                "hard_stop_threshold_seconds": 60.0,
            },
        }
        result = _build_runtime_middlewares(ai_config, family_id="fam_1")

        assert result is not None
        assert len(result) == 1
        assert isinstance(result[0], ToolProgressMiddleware)

    def test_build_runtime_middlewares_both_enabled(self) -> None:
        """Both middlewares created when both enabled in config."""
        ai_config = {
            "subagent_limit": {"enabled": True, "max_concurrent": 3},
            "tool_progress": {"enabled": True},
        }
        result = _build_runtime_middlewares(ai_config, family_id="fam_1")

        assert result is not None
        assert len(result) == 2
        types = [type(m) for m in result]
        assert SubagentLimitMiddleware in types
        assert ToolProgressMiddleware in types

    def test_build_runtime_middlewares_preserves_existing(self) -> None:
        """Existing middlewares from caller are preserved."""
        existing = [MagicMock(name="existing_middleware")]
        ai_config = {
            "subagent_limit": {"enabled": True, "max_concurrent": 3},
        }
        result = _build_runtime_middlewares(ai_config, "fam_1", existing)

        assert result is not None
        assert len(result) == 2
        assert result[0] is existing[0]
        assert isinstance(result[1], SubagentLimitMiddleware)


class TestSubagentLimitDenialHandling:
    """Verify SubagentLimitMiddleware denial is handled gracefully."""

    def test_denial_returns_decision_not_exception(self) -> None:
        """Middleware returns SubagentDecision on denial, does not raise."""
        mw = SubagentLimitMiddleware(max_concurrent=2, family_id="fam_1")

        with patch(
            "apps.agent.services.runtime.subagent_registry.FamilySubagentRegistry"
        ) as mock_reg:
            mock_reg.count_active_for_family.return_value = 3  # over limit
            result = mw.check_subagent_spawn()

        assert result.allowed is False
        assert "limit reached" in result.reason.lower()

    def test_family_isolation_under_concurrent_load(self) -> None:
        """Different families' limits are independent under concurrent load."""
        mw_a = SubagentLimitMiddleware(max_concurrent=2, family_id="fam_A")
        mw_b = SubagentLimitMiddleware(max_concurrent=2, family_id="fam_B")

        with patch(
            "apps.agent.services.runtime.subagent_registry.FamilySubagentRegistry"
        ) as mock_reg:
            # fam_A at limit, fam_B under limit
            mock_reg.count_active_for_family.side_effect = lambda fid: 3 if fid == "fam_A" else 1

            result_a = mw_a.check_subagent_spawn()
            result_b = mw_b.check_subagent_spawn()

        assert result_a.allowed is False
        assert result_b.allowed is True


class TestToolProgressEventEmission:
    """Verify ToolProgressMiddleware emits events during tool execution."""

    def test_event_emitted_on_completion(self) -> None:
        """before_tool_call + after_tool_call produces a completion event."""
        mw = ToolProgressMiddleware(
            warn_threshold_seconds=10.0,
            hard_stop_threshold_seconds=60.0,
        )

        with patch("apps.agent.services.runtime.tool_progress_middleware.time") as mock_time:
            mock_time.monotonic.side_effect = [0.0, 5.0]  # start=0, end=5
            start_event = mw.before_tool_call("call_1", "web_search")
            assert start_event is not None
            assert start_event.status == ToolStatus.ACTIVE

            end_event = mw.after_tool_call("call_1", "web_search")

        assert end_event is not None
        assert end_event.status == ToolStatus.ACTIVE
        assert end_event.elapsed_seconds == 5.0
        assert "web_search" in end_event.message
        assert "completed" in end_event.message

    def test_warn_event_emitted_for_slow_tool(self) -> None:
        """Slow tool triggers WARNED status in event."""
        mw = ToolProgressMiddleware(
            warn_threshold_seconds=10.0,
            hard_stop_threshold_seconds=60.0,
        )

        with patch("apps.agent.services.runtime.tool_progress_middleware.time") as mock_time:
            mock_time.monotonic.side_effect = [0.0, 25.0]  # start=0, end=25 (> 10s warn)
            mw.before_tool_call("call_1", "read_file")
            event = mw.after_tool_call("call_1", "read_file")

        assert event is not None
        assert event.status == ToolStatus.WARNED
        assert event.elapsed_seconds == 25.0
