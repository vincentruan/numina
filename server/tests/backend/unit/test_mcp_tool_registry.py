"""Tests for MCP tool registry — metadata SSOT for all MCP tools."""

from dataclasses import FrozenInstanceError
from unittest.mock import patch

import pytest

from apps.backend.app.services.mcp_tool_registry import (
    MCPToolMeta,
    _REGISTRY,
    get_tool,
    list_tools_for_role,
    validate_registry,
)


class TestRegistryContents:
    def test_registry_contains_all_five_legacy_tools(self):
        expected_names = {
            "get_family_overview",
            "get_assets",
            "get_liabilities",
            "get_members",
            "get_recent_alerts",
        }
        assert set(_REGISTRY.keys()) == expected_names

    def test_each_tool_has_name_description_input_schema(self):
        for name, meta in _REGISTRY.items():
            assert meta.name == name
            assert meta.description
            assert isinstance(meta.input_schema, dict)
            assert "type" in meta.input_schema

    def test_registry_meta_immutable(self):
        meta = _REGISTRY["get_family_overview"]
        with pytest.raises(FrozenInstanceError):
            meta.name = "hacked"  # type: ignore[misc]


class TestGetTool:
    def test_get_existing_tool(self):
        meta = get_tool("get_assets")
        assert meta is not None
        assert meta.name == "get_assets"

    def test_get_nonexistent_tool_returns_none(self):
        assert get_tool("nonexistent_tool") is None


class TestListToolsForRole:
    def test_list_tools_for_role_owner(self):
        tools = list_tools_for_role("owner")
        assert len(tools) == 5
        assert all(isinstance(t, MCPToolMeta) for t in tools)

    def test_list_tools_for_role_member(self):
        tools = list_tools_for_role("member")
        assert len(tools) == 5

    def test_list_tools_for_role_child(self):
        tools = list_tools_for_role("child")
        assert tools == []

    def test_list_tools_for_role_unknown(self):
        tools = list_tools_for_role("admin")
        assert tools == []


class TestValidateRegistry:
    def test_validate_registry_passes_for_current(self):
        validate_registry()

    def test_validate_registry_raises_when_allowed_roles_empty(self):
        broken = MCPToolMeta(
            name="broken_tool",
            description="test",
            input_schema={"type": "object", "properties": {}, "required": []},
            allowed_roles=frozenset(),
            requires_write=False,
        )
        with patch.dict(_REGISTRY, {"broken_tool": broken}):
            with pytest.raises(RuntimeError, match="empty allowed_roles"):
                validate_registry()

    def test_validate_registry_raises_on_unknown_role(self):
        broken = MCPToolMeta(
            name="broken_tool",
            description="test",
            input_schema={"type": "object", "properties": {}, "required": []},
            allowed_roles=frozenset({"admin"}),
            requires_write=False,
        )
        with patch.dict(_REGISTRY, {"broken_tool": broken}):
            with pytest.raises(RuntimeError, match="unknown roles"):
                validate_registry()
