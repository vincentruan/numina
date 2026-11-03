"""Tests for SubagentLimit and ToolProgress config injection (U3)."""

from __future__ import annotations


class TestSubagentLimitInjection:
    """SubagentLimitMiddleware config injection."""

    def test_inject_when_enabled(self) -> None:
        """subagent_limit.enabled=True → config block written."""
        from apps.agent.services.deerflow_adapter.family_adapter_cache import (
            _inject_subagent_limit,
        )

        config: dict = {}
        ai_config = {"subagent_limit": {"enabled": True, "max_concurrent": 5}}
        _inject_subagent_limit(config, ai_config)

        assert config["subagent_limit"]["enabled"] is True
        assert config["subagent_limit"]["max_concurrent"] == 5

    def test_skip_when_disabled(self) -> None:
        """subagent_limit.enabled=False → no config block."""
        from apps.agent.services.deerflow_adapter.family_adapter_cache import (
            _inject_subagent_limit,
        )

        config: dict = {}
        ai_config = {"subagent_limit": {"enabled": False}}
        _inject_subagent_limit(config, ai_config)

        assert "subagent_limit" not in config

    def test_skip_when_absent(self) -> None:
        """No subagent_limit in ai_config → no config block."""
        from apps.agent.services.deerflow_adapter.family_adapter_cache import (
            _inject_subagent_limit,
        )

        config: dict = {}
        _inject_subagent_limit(config, {})

        assert "subagent_limit" not in config

    def test_default_max_concurrent_from_settings(self) -> None:
        """No max_concurrent override → uses AgentSettings default."""
        from apps.agent.services.deerflow_adapter.family_adapter_cache import (
            _inject_subagent_limit,
        )

        config: dict = {}
        ai_config = {"subagent_limit": {"enabled": True}}
        _inject_subagent_limit(config, ai_config)

        # Default from AgentSettings.SUBAGENT_MAX_CONCURRENT = 3
        assert config["subagent_limit"]["max_concurrent"] == 3


class TestToolProgressInjection:
    """ToolProgressMiddleware config injection."""

    def test_inject_when_enabled(self) -> None:
        """tool_progress.enabled=True → config block written."""
        from apps.agent.services.deerflow_adapter.family_adapter_cache import (
            _inject_tool_progress,
        )

        config: dict = {}
        ai_config = {
            "tool_progress": {
                "enabled": True,
                "warn_threshold_seconds": 15.0,
                "hard_stop_threshold_seconds": 60.0,
            }
        }
        _inject_tool_progress(config, ai_config)

        assert config["tool_progress"]["enabled"] is True
        assert config["tool_progress"]["warn_threshold_seconds"] == 15.0
        assert config["tool_progress"]["hard_stop_threshold_seconds"] == 60.0

    def test_skip_when_disabled(self) -> None:
        """tool_progress.enabled=False → no config block."""
        from apps.agent.services.deerflow_adapter.family_adapter_cache import (
            _inject_tool_progress,
        )

        config: dict = {}
        ai_config = {"tool_progress": {"enabled": False}}
        _inject_tool_progress(config, ai_config)

        assert "tool_progress" not in config

    def test_skip_when_absent(self) -> None:
        """No tool_progress in ai_config → no config block."""
        from apps.agent.services.deerflow_adapter.family_adapter_cache import (
            _inject_tool_progress,
        )

        config: dict = {}
        _inject_tool_progress(config, {})

        assert "tool_progress" not in config

    def test_default_thresholds(self) -> None:
        """No threshold overrides → uses defaults (30s / 120s)."""
        from apps.agent.services.deerflow_adapter.family_adapter_cache import (
            _inject_tool_progress,
        )

        config: dict = {}
        ai_config = {"tool_progress": {"enabled": True}}
        _inject_tool_progress(config, ai_config)

        assert config["tool_progress"]["warn_threshold_seconds"] == 30.0
        assert config["tool_progress"]["hard_stop_threshold_seconds"] == 120.0
