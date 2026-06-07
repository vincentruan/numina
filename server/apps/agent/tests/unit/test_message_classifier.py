"""Tests for message_classifier.py — tool registry and suffix matching."""
import pytest
from apps.agent.services.message_classifier import resolve_tool_metadata


class TestResolveToolMetadata:
    """Tests for resolve_tool_metadata function."""

    def test_exact_match_returns_registry_entry(self) -> None:
        """Exact tool name matches should return the registry entry."""
        tool_type, display_name, icon = resolve_tool_metadata("execute_code")
        assert tool_type == "execution"
        assert display_name == "执行分析代码"
        assert icon == "⚙️"

    def test_exact_match_mcp_tool(self) -> None:
        """MCP tools with hyphen namespace prefix should match exactly."""
        tool_type, display_name, icon = resolve_tool_metadata(
            "numina-family-data_get_assets"
        )
        assert tool_type == "data_collect"
        assert display_name == "查询资产数据"
        assert icon == "💰"

    def test_suffix_match_whitelisted_bash(self) -> None:
        """Namespaced variants of whitelisted DeerFlow tools should match."""
        tool_type, display_name, icon = resolve_tool_metadata("some_namespace_bash")
        assert tool_type == "execution"
        assert display_name == "执行命令"
        assert icon == "⚙️"

    def test_suffix_match_whitelisted_write(self) -> None:
        """Suffix match for write should work."""
        tool_type, display_name, icon = resolve_tool_metadata("custom_write")
        assert tool_type == "execution"
        assert display_name == "写入结果"
        assert icon == "📝"

    def test_suffix_match_blocked_for_non_whitelisted(self) -> None:
        """Suffixes not in whitelist should NOT match, even if in registry."""
        # "get_assets" is in registry but NOT in whitelist
        tool_type, display_name, icon = resolve_tool_metadata("audit_log_get_assets")
        assert tool_type == "unknown"
        assert display_name == "audit_log_get_assets"
        assert icon == "tool"

    def test_suffix_match_blocked_for_non_whitelisted_suffix(self) -> None:
        """Suffixes NOT in whitelist should NOT match even if derived from registry tool."""
        # "compose_summary" is in registry but "summary" suffix is NOT in whitelist
        # So namespaced variants should NOT match it
        tool_type, display_name, icon = resolve_tool_metadata("audit_log_compose_summary")
        assert tool_type == "unknown"
        assert display_name == "audit_log_compose_summary"
        assert icon == "tool"

    def test_unknown_tool_returns_fallback(self) -> None:
        """Unknown tools should return unknown tuple with raw name."""
        tool_type, display_name, icon = resolve_tool_metadata("unknown_tool_xyz")
        assert tool_type == "unknown"
        assert display_name == "unknown_tool_xyz"
        assert icon == "tool"

    def test_no_underscore_skips_suffix_match(self) -> None:
        """Tools without underscore skip suffix matching entirely."""
        tool_type, display_name, icon = resolve_tool_metadata("unknownsingleword")
        assert tool_type == "unknown"
        assert display_name == "unknownsingleword"
        assert icon == "tool"

    def test_multiple_underscores_matches_last_segment(self) -> None:
        """Suffix match should use last underscore segment."""
        tool_type, display_name, icon = resolve_tool_metadata(
            "deeply_nested_namespace_bash"
        )
        assert tool_type == "execution"
        assert display_name == "执行命令"
        assert icon == "⚙️"