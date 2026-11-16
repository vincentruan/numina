"""Tests for _inject_task_continuity config injection (T25 U3)."""

from __future__ import annotations


class TestTaskContinuityDefault:
    """Default behavior from base config."""

    def test_base_enabled_true_no_override(self) -> None:
        """Base config enabled=true, no ai_config override → true."""
        from apps.agent.services.deerflow_adapter.family_adapter_cache import (
            _inject_task_continuity,
        )

        config: dict = {"task_continuity": {"enabled": True}}
        _inject_task_continuity(config, {})

        assert config["task_continuity"]["enabled"] is True

    def test_base_enabled_false_no_override(self) -> None:
        """Base config enabled=false, no ai_config override → false."""
        from apps.agent.services.deerflow_adapter.family_adapter_cache import (
            _inject_task_continuity,
        )

        config: dict = {"task_continuity": {"enabled": False}}
        _inject_task_continuity(config, {})

        assert config["task_continuity"]["enabled"] is False

    def test_no_base_block_no_override(self) -> None:
        """No task_continuity key in base config, no override → false (default)."""
        from apps.agent.services.deerflow_adapter.family_adapter_cache import (
            _inject_task_continuity,
        )

        config: dict = {}
        _inject_task_continuity(config, {})

        assert config["task_continuity"]["enabled"] is False


class TestTaskContinuityExplicitOverride:
    """Per-family ai_config override."""

    def test_explicit_true_base_false(self) -> None:
        """Base false + ai_config.enabled=true → true (override wins)."""
        from apps.agent.services.deerflow_adapter.family_adapter_cache import (
            _inject_task_continuity,
        )

        config: dict = {"task_continuity": {"enabled": False}}
        ai_config = {"task_continuity": {"enabled": True}}
        _inject_task_continuity(config, ai_config)

        assert config["task_continuity"]["enabled"] is True

    def test_explicit_false_base_true(self) -> None:
        """Base true + ai_config.enabled=false → false (override wins)."""
        from apps.agent.services.deerflow_adapter.family_adapter_cache import (
            _inject_task_continuity,
        )

        config: dict = {"task_continuity": {"enabled": True}}
        ai_config = {"task_continuity": {"enabled": False}}
        _inject_task_continuity(config, ai_config)

        assert config["task_continuity"]["enabled"] is False

    def test_explicit_true_base_missing(self) -> None:
        """No base block + ai_config.enabled=true → true."""
        from apps.agent.services.deerflow_adapter.family_adapter_cache import (
            _inject_task_continuity,
        )

        config: dict = {}
        ai_config = {"task_continuity": {"enabled": True}}
        _inject_task_continuity(config, ai_config)

        assert config["task_continuity"]["enabled"] is True


class TestTaskContinuityCoexistence:
    """No regression when called alongside other _inject_* functions."""

    def test_tool_search_block_untouched(self) -> None:
        """task_continuity injection does not modify tool_search."""
        from apps.agent.services.deerflow_adapter.family_adapter_cache import (
            _inject_task_continuity,
        )

        config: dict = {
            "task_continuity": {"enabled": True},
            "tool_search": {"enabled": True, "mcp_server_threshold": 3},
        }
        _inject_task_continuity(config, {})

        assert config["tool_search"]["enabled"] is True
        assert config["tool_search"]["mcp_server_threshold"] == 3
        assert config["task_continuity"]["enabled"] is True
