"""Test child-scoped MCP tool access (root cause fix for D1/D2).

Verifies:
- CHILD_LEARNING_TOOLS is non-empty and contains expected tools.
- list_tools() for child callers returns only the whitelist.
- call_tool() self-only enforcement rejects sibling data access.
"""

import json
from unittest.mock import MagicMock, patch

import pytest

from apps.backend.app.services.mcp_session import MCPSession
from apps.backend.app.services.mcp_tool_registry import (
    CHILD_LEARNING_TOOLS,
    TOOL_REGISTRY,
    get_tool,
    validate_registry,
)


class TestChildLearningTools:
    """CHILD_LEARNING_TOOLS whitelist surface."""

    def test_non_empty(self):
        assert len(CHILD_LEARNING_TOOLS) > 0

    def test_all_names_registered(self):
        for name in CHILD_LEARNING_TOOLS:
            assert name in TOOL_REGISTRY, (
                f"{name} in CHILD_LEARNING_TOOLS but not in TOOL_REGISTRY"
            )

    def test_expected_learning_tools_included(self):
        expected = {
            "get_learning_topic",
            "get_child_learning_profile",
            "record_learning_result",
            "get_guided_question",
            "submit_guided_answer",
            "get_knowledge_bridge",
            "get_teacher_persona",
            "record_tutoring_step",
            "record_teach_back_turn",
            "select_adaptive_question",
            "generate_hint",
        }
        assert expected.issubset(CHILD_LEARNING_TOOLS)

    def test_non_learning_tools_excluded(self):
        """Financial tools must never be visible to child."""
        forbidden = {
            "get_family_overview",
            "get_assets",
            "get_liabilities",
            "get_members",
            "get_recent_alerts",
            "import_assets_batch",
            "import_liabilities_batch",
        }
        assert forbidden.isdisjoint(CHILD_LEARNING_TOOLS)

    def test_child_tools_match_skills_allowed_tools(self):
        """Every tool referenced by learning skill SKILL.md must be in
        CHILD_LEARNING_TOOLS OR be a builtin (thread_*)."""
        skill_tools = {
            # learning-tutor
            "get_learning_topic",
            "get_child_learning_profile",
            "record_learning_result",
            # learning-smart-tutor (subset already child-allowed)
            "get_guided_question",
            "submit_guided_answer",
            "get_knowledge_bridge",
            "get_teacher_persona",
            "record_tutoring_step",
            "record_teach_back_turn",
            "select_adaptive_question",
            "generate_hint",
        }
        # All skill tools must either be in CHILD_LEARNING_TOOLS or be a
        # DeerFlow builtin (thread_*) that always passes through.
        builtin_prefixes = ("thread_", "task")
        for t in skill_tools:
            in_whitelist = t in CHILD_LEARNING_TOOLS
            is_builtin = any(t.startswith(p) for p in builtin_prefixes)
            assert in_whitelist or is_builtin, (
                f"{t} is needed by a learning skill but not in CHILD_LEARNING_TOOLS"
            )


@pytest.mark.asyncio
class TestChildListToolsFiltering:
    """MCPSession.list_tools() returns only CHILD_LEARNING_TOOLS for child."""

    async def test_child_sees_only_whitelisted_tools(self):
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

        assert tool_names == CHILD_LEARNING_TOOLS
        assert "get_family_overview" not in tool_names
        assert "get_assets" not in tool_names

    async def test_owner_still_sees_full_set(self):
        """Owner role must not be affected by child whitelist."""
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
        assert "get_learning_topic" in tool_names


@pytest.mark.asyncio
class TestChildSelfOnlyEnforcement:
    """MCPSession.call_tool() enforces self-only scope for child callers."""

    async def _make_session(self, caller_user_id: str = "child1"):
        mock_db = MagicMock()
        session = MCPSession(
            family_id="100",
            caller_user_id=caller_user_id,
            caller_role="child",
        )
        return session, mock_db

    async def test_child_cannot_call_non_learning_tool(self):
        """Child caller trying to invoke get_family_overview → permission_denied."""
        session, mock_db = await self._make_session()

        with patch("apps.backend.app.services.mcp_session.SessionLocal") as mock_sl:
            mock_sl.return_value.__enter__ = MagicMock(return_value=mock_db)
            mock_sl.return_value.__exit__ = MagicMock(return_value=False)

            with patch("apps.backend.app.services.mcp_session._get_caller_user") as mu:
                mu.return_value = MagicMock(id="child1", family_id="100", role="child")

                result = await session.call_tool("get_family_overview", {})
                body = json.loads(result[0].text)
                assert body["error"] == "permission_denied"

    async def test_child_self_only_child_id_mismatch(self):
        """Child calling get_learning_topic with sibling's child_id → denied."""
        session, mock_db = await self._make_session(caller_user_id="child1")

        with patch("apps.backend.app.services.mcp_session.SessionLocal") as mock_sl:
            mock_sl.return_value.__enter__ = MagicMock(return_value=mock_db)
            mock_sl.return_value.__exit__ = MagicMock(return_value=False)

            with patch("apps.backend.app.services.mcp_session._get_caller_user") as mu:
                mu.return_value = MagicMock(id="child1", family_id="100", role="child")

                # Try to read sibling child2's data
                result = await session.call_tool(
                    "get_learning_topic", {"topic_id": "1", "child_id": "child2"}
                )
                body = json.loads(result[0].text)
                assert body["error"] == "permission_denied"

    async def test_child_self_only_child_id_match(self):
        """Child calling get_learning_topic with own child_id proceeds."""
        session, mock_db = await self._make_session(caller_user_id="child1")

        with patch("apps.backend.app.services.mcp_session.SessionLocal") as mock_sl:
            mock_sl.return_value.__enter__ = MagicMock(return_value=mock_db)
            mock_sl.return_value.__exit__ = MagicMock(return_value=False)

            with patch("apps.backend.app.services.mcp_session._get_caller_user") as mu:
                mu.return_value = MagicMock(id="child1", family_id="100", role="child")

                with patch(
                    "apps.backend.app.services.learning.topic_service.get_topic_by_id"
                ) as mock_get:
                    mock_get.return_value = {
                        "id": "1", "name": "test", "description": "test"
                    }
                    result = await session.call_tool(
                        "get_learning_topic", {"topic_id": "1", "child_id": "child1"}
                    )
                    # Handler returns data dict, not error
                    body = json.loads(result[0].text)
                    assert "error" not in body or body.get("error") != "permission_denied"

    async def test_child_session_id_self_only(self):
        """Child calling record_learning_result with sibling's session_id → denied."""
        session, mock_db = await self._make_session(caller_user_id="child1")

        with patch("apps.backend.app.services.mcp_session.SessionLocal") as mock_sl:
            mock_sl.return_value.__enter__ = MagicMock(return_value=mock_db)
            mock_sl.return_value.__exit__ = MagicMock(return_value=False)

            with patch("apps.backend.app.services.mcp_session._get_caller_user") as mu:
                mu.return_value = MagicMock(id="child1", family_id="100", role="child")

                # Mock LearningSession query: session belongs to child2, not child1
                mock_session_obj = MagicMock()
                mock_session_obj.child_id = 999  # different child
                mock_db.query.return_value.filter.return_value.filter.return_value.first.return_value = mock_session_obj

                result = await session.call_tool(
                    "record_learning_result",
                    {"session_id": "999", "evaluation": {"recommendation": "mastered", "overall_score": 0.9, "evidence_results": []}},
                )
                body = json.loads(result[0].text)
                assert body["error"] == "permission_denied"
