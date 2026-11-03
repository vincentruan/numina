"""Tests for _inject_tool_search config injection (T24)."""

from __future__ import annotations


def _make_mcp_servers(n: int) -> list[dict]:
    return [{"name": f"srv_{i}", "client_id": f"c{i}"} for i in range(n)]


class TestToolSearchThreshold:
    """Threshold-based activation (R3, R6)."""

    def test_below_threshold_1_server(self) -> None:
        """1 MCP server, no override → enabled=false (AE1)."""
        from apps.agent.services.deerflow_adapter.family_adapter_cache import (
            _inject_tool_search,
        )

        config: dict = {
            "tool_search": {"enabled": False, "mcp_server_threshold": 3},
            "mcp_servers": _make_mcp_servers(1),
        }
        _inject_tool_search(config, {})

        assert config["tool_search"]["enabled"] is False

    def test_at_threshold_3_servers(self) -> None:
        """3 MCP servers == threshold 3 → enabled=true (AE2)."""
        from apps.agent.services.deerflow_adapter.family_adapter_cache import (
            _inject_tool_search,
        )

        config: dict = {
            "tool_search": {"enabled": False, "mcp_server_threshold": 3},
            "mcp_servers": _make_mcp_servers(3),
        }
        _inject_tool_search(config, {})

        assert config["tool_search"]["enabled"] is True

    def test_above_threshold_5_servers(self) -> None:
        """5 MCP servers > threshold 3 → enabled=true."""
        from apps.agent.services.deerflow_adapter.family_adapter_cache import (
            _inject_tool_search,
        )

        config: dict = {
            "tool_search": {"enabled": False, "mcp_server_threshold": 3},
            "mcp_servers": _make_mcp_servers(5),
        }
        _inject_tool_search(config, {})

        assert config["tool_search"]["enabled"] is True

    def test_zero_servers_none(self) -> None:
        """mcp_servers=None → enabled=false."""
        from apps.agent.services.deerflow_adapter.family_adapter_cache import (
            _inject_tool_search,
        )

        config: dict = {
            "tool_search": {"enabled": False, "mcp_server_threshold": 3},
            "mcp_servers": None,
        }
        _inject_tool_search(config, {})

        assert config["tool_search"]["enabled"] is False

    def test_zero_servers_empty_list(self) -> None:
        """mcp_servers=[] → enabled=false."""
        from apps.agent.services.deerflow_adapter.family_adapter_cache import (
            _inject_tool_search,
        )

        config: dict = {
            "tool_search": {"enabled": False, "mcp_server_threshold": 3},
            "mcp_servers": [],
        }
        _inject_tool_search(config, {})

        assert config["tool_search"]["enabled"] is False


class TestToolSearchExplicitOverride:
    """Per-family ai_config override (R4)."""

    def test_explicit_true_below_threshold(self) -> None:
        """1 server + ai_config.tool_search.enabled=true → true (override wins)."""
        from apps.agent.services.deerflow_adapter.family_adapter_cache import (
            _inject_tool_search,
        )

        config: dict = {
            "tool_search": {"enabled": False, "mcp_server_threshold": 3},
            "mcp_servers": _make_mcp_servers(1),
        }
        ai_config = {"tool_search": {"enabled": True}}
        _inject_tool_search(config, ai_config)

        assert config["tool_search"]["enabled"] is True

    def test_explicit_false_above_threshold(self) -> None:
        """5 servers + ai_config.tool_search.enabled=false → false (AE3)."""
        from apps.agent.services.deerflow_adapter.family_adapter_cache import (
            _inject_tool_search,
        )

        config: dict = {
            "tool_search": {"enabled": False, "mcp_server_threshold": 3},
            "mcp_servers": _make_mcp_servers(5),
        }
        ai_config = {"tool_search": {"enabled": False}}
        _inject_tool_search(config, ai_config)

        assert config["tool_search"]["enabled"] is False


class TestToolSearchCustomThreshold:
    """Custom threshold values."""

    def test_custom_threshold_not_met(self) -> None:
        """threshold=5, 3 servers → false."""
        from apps.agent.services.deerflow_adapter.family_adapter_cache import (
            _inject_tool_search,
        )

        config: dict = {
            "tool_search": {"enabled": False, "mcp_server_threshold": 5},
            "mcp_servers": _make_mcp_servers(3),
        }
        _inject_tool_search(config, {})

        assert config["tool_search"]["enabled"] is False

    def test_custom_threshold_met(self) -> None:
        """threshold=5, 5 servers → true."""
        from apps.agent.services.deerflow_adapter.family_adapter_cache import (
            _inject_tool_search,
        )

        config: dict = {
            "tool_search": {"enabled": False, "mcp_server_threshold": 5},
            "mcp_servers": _make_mcp_servers(5),
        }
        _inject_tool_search(config, {})

        assert config["tool_search"]["enabled"] is True

    def test_per_family_threshold_override(self) -> None:
        """ai_config.tool_search.mcp_server_threshold=2, 2 servers → true."""
        from apps.agent.services.deerflow_adapter.family_adapter_cache import (
            _inject_tool_search,
        )

        config: dict = {
            "tool_search": {"enabled": False, "mcp_server_threshold": 3},
            "mcp_servers": _make_mcp_servers(2),
        }
        ai_config = {"tool_search": {"mcp_server_threshold": 2}}
        _inject_tool_search(config, ai_config)

        assert config["tool_search"]["enabled"] is True
        assert config["tool_search"]["mcp_server_threshold"] == 2


class TestToolSearchDefaults:
    """Fallback when config has no tool_search block."""

    def test_missing_tool_search_in_base_config(self) -> None:
        """No tool_search key in config → defaults applied, still resolves."""
        from apps.agent.services.deerflow_adapter.family_adapter_cache import (
            _inject_tool_search,
        )

        config: dict = {"mcp_servers": _make_mcp_servers(3)}
        _inject_tool_search(config, {})

        assert config["tool_search"]["enabled"] is True
        assert config["tool_search"]["mcp_server_threshold"] == 3
