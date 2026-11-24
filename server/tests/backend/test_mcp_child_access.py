"""Test child-scoped MCP tool access.

The child scoping rule lives in `MCPToolMeta.allowed_roles`, not in a
separate whitelist constant — child callers see exactly the tools whose
`allowed_roles` contains "child".

Verifies:
- The child-visible set is non-empty and contains the guided-tutoring tools.
- No financial tool is ever visible to a child.
- list_tools() for a child returns only that set; owner is unaffected.
- call_tool() self-only enforcement rejects sibling data access.
"""

import json
from unittest.mock import MagicMock, patch

import pytest

from apps.backend.app.services.mcp_session import MCPSession
from apps.backend.app.services.mcp_tool_registry import (
    TOOL_REGISTRY,
    get_tool,
    list_tools_for_role,
    validate_registry,
)


def child_tool_names() -> frozenset[str]:
    """The tools a child caller may see — derived from allowed_roles."""
    return frozenset(meta.name for meta in list_tools_for_role("child"))


class TestChildToolSurface:
    """The child-visible tool set and what it must never contain."""

    def test_non_empty(self):
        assert len(child_tool_names()) > 0

    def test_all_names_registered(self):
        for name in child_tool_names():
            assert name in TOOL_REGISTRY, (
                f"{name} is visible to child but not in TOOL_REGISTRY"
            )

    def test_expected_guided_tutoring_tools_included(self):
        """The in-session Socratic tutoring surface must stay open to child."""
        expected = {
            "get_guided_question",
            "submit_guided_answer",
            "get_knowledge_bridge",
            "get_teacher_persona",
            "select_adaptive_question",
            "generate_hint",
        }
        assert expected.issubset(child_tool_names())

    def test_financial_tools_never_visible_to_child(self):
        """Financial tools and family-wide reads must never reach a child."""
        forbidden = {
            "get_family_overview",
            "get_assets",
            "get_liabilities",
            "get_members",
            "get_recent_alerts",
            "import_assets_batch",
            "import_liabilities_batch",
        }
        assert forbidden.isdisjoint(child_tool_names())

    def test_registry_is_valid(self):
        validate_registry()

    def test_get_tool_unknown_returns_none(self):
        assert get_tool("no_such_tool") is None


@pytest.mark.asyncio
class TestChildListToolsFiltering:
    """MCPSession.list_tools() honours allowed_roles for the child caller."""

    async def test_child_sees_only_child_allowed_tools(self):
        mock_db = MagicMock()
        session = MCPSession(
            family_id="100",
            caller_user_id="child1",
            caller_role="child",
        )

        with patch("apps.backend.app.services.mcp_session.SessionLocal") as mock_sl:
            mock_sl.return_value.__enter__ = MagicMock(return_value=mock_db)
            mock_sl.return_value.__exit__ = MagicMock(return_value=False)

            tools = await session.list_tools()
            tool_names = {t.name for t in tools}

        assert tool_names == child_tool_names()
        assert "get_family_overview" not in tool_names
        assert "get_assets" not in tool_names

    async def test_owner_sees_full_set(self):
        """Owner role must not be affected by child scoping."""
        mock_db = MagicMock()
        session = MCPSession(
            family_id="100",
            caller_user_id="owner1",
            caller_role="owner",
        )

        with patch("apps.backend.app.services.mcp_session.SessionLocal") as mock_sl:
            mock_sl.return_value.__enter__ = MagicMock(return_value=mock_db)
            mock_sl.return_value.__exit__ = MagicMock(return_value=False)

            tools = await session.list_tools()
            tool_names = {t.name for t in tools}

        assert "get_family_overview" in tool_names
        # read-only learning tools stay available to the parent side
        assert "get_learning_topic" in tool_names


@pytest.mark.asyncio
class TestChildSelfOnlyEnforcement:
    """MCPSession.call_tool() enforces self-only scope for child callers."""

    async def _make_session(self, caller_user_id: str = "child1"):
        session = MCPSession(
            family_id="100",
            caller_user_id=caller_user_id,
            caller_role="child",
        )
        return session

    async def _call_as_child(self, tool: str, args: dict) -> dict:
        mock_db = MagicMock()
        session = await self._make_session()

        with patch("apps.backend.app.services.mcp_session.SessionLocal") as mock_sl:
            mock_sl.return_value.__enter__ = MagicMock(return_value=mock_db)
            mock_sl.return_value.__exit__ = MagicMock(return_value=False)

            with patch("apps.backend.app.services.mcp_session._get_caller_user") as mu:
                mu.return_value = MagicMock(id="child1", family_id="100", role="child")
                result = await session.call_tool(tool, args)

        return json.loads(result[0].text)

    async def test_child_cannot_call_financial_tool(self):
        """Child invoking get_family_overview → permission_denied."""
        body = await self._call_as_child("get_family_overview", {})
        assert body["error"] == "permission_denied"

    async def test_child_cannot_call_asset_import(self):
        """Child invoking a write tool → permission_denied."""
        body = await self._call_as_child("import_assets_batch", {"assets": []})
        assert body["error"] == "permission_denied"

    async def test_child_guided_tool_rejects_non_family_child(self):
        """A sibling outside the family is rejected at the family boundary."""
        mock_db = MagicMock()
        # Family-scope lookup finds no User for child_id 999 -> child_not_in_family
        mock_db.query.return_value.filter.return_value.first.return_value = None
        session = await self._make_session()

        with patch("apps.backend.app.services.mcp_session.SessionLocal") as mock_sl:
            mock_sl.return_value.__enter__ = MagicMock(return_value=mock_db)
            mock_sl.return_value.__exit__ = MagicMock(return_value=False)

            with patch("apps.backend.app.services.mcp_session._get_caller_user") as mu:
                mu.return_value = MagicMock(id="child1", family_id="100", role="child")
                result = await session.call_tool(
                    "get_guided_question",
                    {"question_id": 1, "child_id": 999, "topic_id": 1},
                )

        body = json.loads(result[0].text)
        assert body["error"] == "child_not_in_family"
