"""Tests for MCP tool registry — metadata SSOT for all MCP tools."""

from dataclasses import FrozenInstanceError
from unittest.mock import patch

import pytest

from apps.backend.app.services.mcp_tool_registry import (
    TOOL_REGISTRY,
    MCPToolMeta,
    get_tool,
    list_tools_for_role,
    validate_registry,
)


class TestRegistryContents:
    def test_registry_contains_all_tools(self):
        # Resolved-3 (U5 cleanup): write_numina_report / read_numina_report
        # deleted — asset-report uses DeerFlow native sandbox tools now.
        # #11 (U8 follow-up): 3 import_*_batch write tools added.
        # Task 1: literacy weekly report tools added
        # Travel module: 3 travel tools added
        # Task 4 SDD: 3 learning-tutor tools added
        expected_names = {
            "get_family_overview",
            "get_assets",
            "get_liabilities",
            "get_members",
            "get_recent_alerts",
            "import_assets_batch",
            "import_liabilities_batch",
            "import_credit_cards_batch",
            "get_child_literacy_profile",
            "get_literacy_weekly_data",
            "get_travel_trips",
            "get_travel_expenses",
            "get_travel_split_balances",
            "get_learning_topic",
            "get_child_learning_profile",
            "record_learning_result",
            # Issue #190: learning-topic-generator tools
            "get_child_weak_points",
            "get_taxonomy_topic",
            "list_taxonomy_topics",
            "get_taxonomy_dependencies",
            "validate_question",
            # Issue #191: smart-tutor tools
            "get_guided_question",
            "submit_guided_answer",
            "get_knowledge_bridge",
            "get_teacher_persona",
            "record_tutoring_step",
            # Issue #191: adaptive question selection + hint generation
            "select_adaptive_question",
            "generate_hint",
            # Issue #216: teach-back tool
            "record_teach_back_turn",
        }
        assert set(TOOL_REGISTRY.keys()) == expected_names

    def test_each_tool_has_name_description_input_schema(self):
        for name, meta in TOOL_REGISTRY.items():
            assert meta.name == name
            assert meta.description
            assert isinstance(meta.input_schema, dict)
            assert "type" in meta.input_schema

    def test_registry_meta_immutable(self):
        meta = TOOL_REGISTRY["get_family_overview"]
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
        # 10 existing + 3 travel + 3 learning + 5 topic-generator + 5 smart-tutor + 2 adaptive + 1 teach-back tools
        assert len(tools) == 29
        assert all(isinstance(t, MCPToolMeta) for t in tools)

    def test_list_tools_for_role_member(self):
        tools = list_tools_for_role("member")
        assert len(tools) == 29

    def test_list_tools_for_role_child(self):
        tools = list_tools_for_role("child")
        # Smart tutor tools (Issue #191) are accessible to children:
        # 4 core + select_adaptive_question + generate_hint (both read-only)
        assert len(tools) == 6
        child_tool_names = {t.name for t in tools}
        assert child_tool_names == {
            "get_guided_question",
            "submit_guided_answer",
            "get_knowledge_bridge",
            "get_teacher_persona",
            "select_adaptive_question",
            "generate_hint",
        }

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
            child_scope="none",
        )
        with (
            patch.dict(TOOL_REGISTRY, {"broken_tool": broken}),
            pytest.raises(RuntimeError, match="empty allowed_roles"),
        ):
            validate_registry()

    def test_validate_registry_raises_on_unknown_role(self):
        broken = MCPToolMeta(
            name="broken_tool",
            description="test",
            input_schema={"type": "object", "properties": {}, "required": []},
            allowed_roles=frozenset({"admin"}),
            requires_write=False,
            child_scope="none",
        )
        with (
            patch.dict(TOOL_REGISTRY, {"broken_tool": broken}),
            pytest.raises(RuntimeError, match="unknown roles"),
        ):
            validate_registry()


def test_literacy_tools_registered():
    """Literacy MCP tools are registered with correct metadata."""
    from apps.backend.app.services.mcp_tool_registry import get_tool

    profile_tool = get_tool("get_child_literacy_profile")
    assert profile_tool is not None
    assert profile_tool.requires_write is False
    assert "owner" in profile_tool.allowed_roles
    assert "member" in profile_tool.allowed_roles
    assert "child" not in profile_tool.allowed_roles

    data_tool = get_tool("get_literacy_weekly_data")
    assert data_tool is not None
    assert data_tool.requires_write is False
    assert "child_id" in data_tool.input_schema["properties"]


# ---------------------------------------------------------------------------
# child_scope declaration
# ---------------------------------------------------------------------------


class TestChildScopeDeclaration:
    """Every tool declares which per-child handle it takes, and the
    declaration must agree with its input_schema."""

    def test_every_tool_declares_a_valid_child_scope(self):
        from apps.backend.app.services.mcp_tool_registry import VALID_CHILD_SCOPES

        for name, meta in TOOL_REGISTRY.items():
            assert meta.child_scope in VALID_CHILD_SCOPES, (
                f"{name} declares unknown child_scope {meta.child_scope!r}"
            )

    def test_child_scope_matches_schema_handles(self):
        expected_handles = {
            "none": (False, False),
            "child": (True, False),
            "child_optional": (True, False),
            "session": (False, True),
            "session_child": (True, True),
            "session_unscoped": (False, True),
        }
        for name, meta in TOOL_REGISTRY.items():
            props = meta.input_schema.get("properties", {})
            actual = ("child_id" in props, "session_id" in props)
            assert expected_handles[meta.child_scope] == actual, (
                f"{name}: child_scope={meta.child_scope!r} implies handles "
                f"{expected_handles[meta.child_scope]} but schema has child_id/session_id={actual}"
            )

    def test_child_open_tools_are_self_scoped(self):
        """A tool a child may call must gate its child_id / session_id."""
        for name, meta in TOOL_REGISTRY.items():
            if "child" not in meta.allowed_roles:
                continue
            props = meta.input_schema.get("properties", {})
            if "child_id" in props or "session_id" in props:
                assert meta.child_scope != "none", f"{name} is child-open but declares none"
                assert meta.child_scope != "session_unscoped", (
                    f"{name} is child-open but leaves its session unscoped"
                )

    def test_child_open_tool_without_handle_may_declare_none(self):
        """The branch no real tool exercises: a child-open tool carrying no
        per-child handle is legitimately `none`."""
        synthetic = MCPToolMeta(
            name="synthetic_child_open",
            description="test",
            input_schema={"type": "object", "properties": {}, "required": []},
            allowed_roles=frozenset({"child"}),
            requires_write=False,
            child_scope="none",
        )
        with patch.dict(TOOL_REGISTRY, {"synthetic_child_open": synthetic}):
            validate_registry()

    def test_validate_registry_rejects_child_id_tool_declared_none(self):
        broken = MCPToolMeta(
            name="broken_tool",
            description="test",
            input_schema={
                "type": "object",
                "properties": {"child_id": {"type": "integer"}},
                "required": [],
            },
            allowed_roles=frozenset({"owner"}),
            requires_write=False,
            child_scope="none",
        )
        with (
            patch.dict(TOOL_REGISTRY, {"broken_tool": broken}),
            pytest.raises(RuntimeError, match="child_scope"),
        ):
            validate_registry()

    def test_validate_registry_rejects_child_scope_without_child_id(self):
        broken = MCPToolMeta(
            name="broken_tool",
            description="test",
            input_schema={"type": "object", "properties": {}, "required": []},
            allowed_roles=frozenset({"owner"}),
            requires_write=False,
            child_scope="child",
        )
        with (
            patch.dict(TOOL_REGISTRY, {"broken_tool": broken}),
            pytest.raises(RuntimeError, match="child_scope"),
        ):
            validate_registry()

    def test_validate_registry_rejects_session_scope_without_session_id(self):
        broken = MCPToolMeta(
            name="broken_tool",
            description="test",
            input_schema={
                "type": "object",
                "properties": {"child_id": {"type": "integer"}},
                "required": [],
            },
            allowed_roles=frozenset({"owner"}),
            requires_write=False,
            child_scope="session_child",
        )
        with (
            patch.dict(TOOL_REGISTRY, {"broken_tool": broken}),
            pytest.raises(RuntimeError, match="child_scope"),
        ):
            validate_registry()

    def test_validate_registry_rejects_child_open_session_unscoped(self):
        broken = MCPToolMeta(
            name="broken_tool",
            description="test",
            input_schema={
                "type": "object",
                "properties": {"session_id": {"type": "integer"}},
                "required": [],
            },
            allowed_roles=frozenset({"child"}),
            requires_write=False,
            child_scope="session_unscoped",
        )
        with (
            patch.dict(TOOL_REGISTRY, {"broken_tool": broken}),
            pytest.raises(RuntimeError, match="child_scope"),
        ):
            validate_registry()
