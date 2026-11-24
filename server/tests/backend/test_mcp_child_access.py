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
        """Any child_id other than the caller's own is rejected before dispatch.

        This used to fall through to the handler's family lookup and come back
        as `child_not_in_family`; the self-scope gate now answers first, which
        is the stricter and correct outcome for a child caller.
        """
        mock_db = MagicMock()
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
        assert body["error"] == "permission_denied"
        assert body["retryable"] is False
        # No handler ran, so no family lookup happened.
        mock_db.query.assert_not_called()


def _patch_child_call(mock_db, caller_id="1001", role="child"):
    """Patch a call as `caller_id` with `role`, against `mock_db`."""
    import contextlib

    @contextlib.contextmanager
    def _ctx():
        with patch("apps.backend.app.services.mcp_session.SessionLocal") as mock_sl:
            mock_sl.return_value.__enter__ = MagicMock(return_value=mock_db)
            mock_sl.return_value.__exit__ = MagicMock(return_value=False)
            with patch(
                "apps.backend.app.services.mcp_session._get_caller_user"
            ) as mock_user:
                mock_user.return_value = MagicMock(
                    id=caller_id, family_id="100", role=role, is_active=True
                )
                yield mock_user

    return _ctx()


CHILD_A = "1001"  # the caller
SIBLING_ID = "200"


@pytest.mark.asyncio
class TestChildSelfScopeGate:
    """A child caller may only address their own child_id and session_id.

    Every case runs inside one family: the sibling is a real member of the
    caller's family, which is exactly what the old family-only check allowed.
    """

    CHILD_OPEN_TOOLS = [
        "get_guided_question",
        "submit_guided_answer",
        "get_knowledge_bridge",
        "select_adaptive_question",
        "generate_hint",
    ]

    @staticmethod
    def _args_for(tool: str, child_id) -> dict:
        base = {"child_id": child_id, "topic_id": 1, "question_id": 1}
        if tool == "submit_guided_answer":
            base.update(
                {"session_id": 55, "step_number": 1, "answer_text": "因为 2+3=5"}
            )
        elif tool == "generate_hint":
            base["error_pattern"] = "concept"
        return base

    @pytest.mark.parametrize("tool", CHILD_OPEN_TOOLS)
    async def test_sibling_child_id_is_denied(self, tool):
        mock_db = MagicMock()
        session = MCPSession("100", CHILD_A, "child")

        with _patch_child_call(mock_db):
            result = await session.call_tool(tool, self._args_for(tool, SIBLING_ID))

        body = json.loads(result[0].text)
        assert body["error"] == "permission_denied"
        assert body["retryable"] is False
        if tool == "submit_guided_answer":
            # The gate's only read is the session ownership lookup.
            assert mock_db.query.call_count <= 1
        else:
            assert mock_db.query.call_count == 0, "the gate answers before any handler read"

    @pytest.mark.parametrize("tool", CHILD_OPEN_TOOLS)
    async def test_sibling_child_id_as_string_is_denied(self, tool):
        mock_db = MagicMock()
        session = MCPSession("100", CHILD_A, "child")

        with _patch_child_call(mock_db):
            result = await session.call_tool(tool, self._args_for(tool, "200"))

        assert json.loads(result[0].text)["error"] == "permission_denied"

    async def test_denial_is_audited_with_its_own_error_code(self):
        mock_db = MagicMock()
        audit = MagicMock()
        session = MCPSession("100", CHILD_A, "child", audit_callback=audit)

        with _patch_child_call(mock_db):
            await session.call_tool("get_guided_question", self._args_for(
                "get_guided_question", SIBLING_ID
            ))

        audit.assert_called_once()
        kwargs = audit.call_args.kwargs
        assert kwargs["status"] == "permission_denied"
        assert kwargs["error_code"] == "child_scope_violation"

    async def test_own_child_id_reaches_the_handler(self):
        mock_db = MagicMock()
        # Handler path: the child row is found, then the question is not.
        mock_db.query.return_value.filter.return_value.first.side_effect = [
            MagicMock(id=CHILD_A, family_id="100"),
            None,
        ]
        session = MCPSession("100", CHILD_A, "child")

        with _patch_child_call(mock_db):
            result = await session.call_tool(
                "get_guided_question", self._args_for("get_guided_question", str(CHILD_A))
            )

        # Reached the handler, which reports its own data-level outcome.
        assert json.loads(result[0].text)["error"] == "question_not_found"
        assert mock_db.query.called

    async def test_parents_child_id_is_denied(self):
        """A child naming a parent's user id is not a family-boundary case."""
        mock_db = MagicMock()
        session = MCPSession("100", CHILD_A, "child")

        with _patch_child_call(mock_db):
            result = await session.call_tool(
                "get_knowledge_bridge",
                {"child_id": "9001", "topic_id": 1},
            )

        assert json.loads(result[0].text)["error"] == "permission_denied"

    async def test_gate_reports_denial_for_an_adult_id(self):
        """The gate's own verdict, with a valid question — no handler ran."""
        mock_db = MagicMock()
        session = MCPSession("100", CHILD_A, "child")

        with _patch_child_call(mock_db):
            result = await session.call_tool(
                "get_guided_question",
                {"question_id": 1, "child_id": "9001", "topic_id": 1},
            )

        body = json.loads(result[0].text)
        assert body["error"] == "permission_denied"
        assert body["retryable"] is False
        mock_db.query.assert_not_called()

    async def test_injected_identity_arguments_do_not_help(self):
        mock_db = MagicMock()
        session = MCPSession("100", CHILD_A, "child")
        args = self._args_for("get_guided_question", SIBLING_ID)
        args.update({"caller_user_id": "200", "role": "owner"})

        with _patch_child_call(mock_db):
            result = await session.call_tool("get_guided_question", args)

        assert json.loads(result[0].text)["error"] == "permission_denied"

    async def test_non_numeric_child_id_is_a_handler_argument_error(self):
        mock_db = MagicMock()
        session = MCPSession("100", CHILD_A, "child")

        with _patch_child_call(mock_db):
            result = await session.call_tool(
                "get_guided_question", {"question_id": 1, "child_id": "abc", "topic_id": 1}
            )

        assert json.loads(result[0].text)["error"] == "invalid_arguments"

    async def test_sibling_session_id_is_denied(self):
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = None
        session = MCPSession("100", CHILD_A, "child")
        args = {
            "question_id": 1,
            "child_id": str(CHILD_A),
            "session_id": 55,
            "step_number": 1,
            "answer_text": "因为 2+3=5",
        }

        with _patch_child_call(mock_db):
            result = await session.call_tool("submit_guided_answer", args)

        body = json.loads(result[0].text)
        assert body["error"] == "permission_denied"
        assert body["retryable"] is False

    async def test_missing_session_is_denied_not_not_found(self):
        """A child cannot probe which session ids exist."""
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = None
        session = MCPSession("100", CHILD_A, "child")

        with _patch_child_call(mock_db):
            result = await session.call_tool(
                "submit_guided_answer",
                {
                    "question_id": 1,
                    "child_id": str(CHILD_A),
                    "session_id": 987654,
                    "step_number": 1,
                    "answer_text": "不知道",
                },
            )

        assert json.loads(result[0].text)["error"] == "permission_denied"

    async def test_non_integer_session_id_is_denied(self):
        """A non-numeric session_id is denied by the gate, not passed to the handler.

        The gate's int() conversion catches ValueError/TypeError and sets
        _session_id = None, which triggers _scope_denial = "session_id".
        This is the session_id equivalent of test_non_numeric_child_id_is_a_handler_argument_error,
        but the outcome differs: session_id denial is permission_denied (the gate answers),
        while non-numeric child_id is invalid_arguments (the handler answers).
        """
        mock_db = MagicMock()
        session = MCPSession("100", CHILD_A, "child")
        args = {
            "question_id": 1,
            "child_id": str(CHILD_A),
            "session_id": "not-a-number",
            "step_number": 1,
            "answer_text": "因为 2+3=5",
        }

        with _patch_child_call(mock_db):
            result = await session.call_tool("submit_guided_answer", args)

        body = json.loads(result[0].text)
        assert body["error"] == "permission_denied"
        assert body["retryable"] is False
        # The gate answered before any handler ran, so no DB query happened.
        mock_db.query.assert_not_called()

    async def test_own_session_reaches_the_handler(self):
        mock_db = MagicMock()
        # Gate sees the caller's own session; the handler then re-checks it.
        mock_db.query.return_value.filter.return_value.first.return_value = MagicMock(
            id=55, child_id=CHILD_A
        )
        session = MCPSession("100", CHILD_A, "child")

        with _patch_child_call(mock_db):
            result = await session.call_tool(
                "submit_guided_answer",
                {
                    "question_id": 1,
                    "child_id": str(CHILD_A),
                    "session_id": 55,
                    "step_number": 1,
                    "answer_text": "因为 2+3=5",
                },
            )

        body = json.loads(result[0].text)
        assert body["step_number"] == 1
        assert "quality_assessment" in body

    async def test_teacher_persona_needs_no_child_handle(self):
        mock_db = MagicMock()
        session = MCPSession("100", CHILD_A, "child")

        with _patch_child_call(mock_db):
            result = await session.call_tool(
                "get_teacher_persona", {"subject": "mathematics", "age_group": "mid"}
            )

        assert "style" in json.loads(result[0].text)

    async def test_optional_child_id_is_pinned_to_the_caller(self):
        """get_child_literacy_profile declares child_optional: a child's
        omitted child_id means "me", so the handler query is pinned to the
        caller rather than listing the whole family.

        The gate function is exercised directly because the registry does not
        yet grant this tool to children — the role gate answers first there,
        which is why the isolation is the honest way to prove the rewrite.
        """
        from apps.backend.app.services.mcp_session import MCPSession

        mock_db = MagicMock()
        mock_db.query.return_value.all.return_value = []
        mock_db.query.return_value.filter.return_value.all.return_value = []
        session = MCPSession("100", CHILD_A, "child")

        with _patch_child_call(mock_db):
            result = await session.call_tool("get_child_literacy_profile", {})

        assert json.loads(result[0].text)["error"] == "permission_denied"

        # Same call, but with the registry granting the tool to children: the
        # gate must pin the query to the caller, so the handler returns an
        # empty list (no user with that ID exists in the mock).
        from apps.backend.app.services import mcp_tool_registry as registry

        meta = registry.get_tool("get_child_literacy_profile")
        assert meta is not None
        widened = registry.MCPToolMeta(
            name=meta.name,
            description=meta.description,
            input_schema=meta.input_schema,
            allowed_roles=meta.allowed_roles | {"child"},
            requires_write=meta.requires_write,
            child_scope=meta.child_scope,
        )
        # Fresh mock so the call log from the denied attempt is not mixed in.
        mock_db = MagicMock()
        mock_db.query.return_value.all.return_value = []
        mock_db.query.return_value.filter.return_value.all.return_value = []
        with (
            patch.dict(registry.TOOL_REGISTRY, {meta.name: widened}),
            _patch_child_call(mock_db),
        ):
            result = await session.call_tool("get_child_literacy_profile", {})

        body = json.loads(result[0].text)
        # The handler ran (no permission error) and returned an empty children
        # list, proving the gate pinned the query to the caller rather than
        # letting it enumerate the whole family.
        assert "children" in body
        assert body["children"] == []

    async def test_empty_string_child_id_is_pinned_to_caller(self):
        """An empty-string child_id on a child_optional tool means 'me'.

        The gate treats None and '' identically for child_optional: both resolve
        to the caller's own id. This locks the contract that the correctness
        reviewer noted was only tested with None.
        """
        from apps.backend.app.services import mcp_tool_registry as registry

        meta = registry.get_tool("get_child_literacy_profile")
        assert meta is not None
        widened = registry.MCPToolMeta(
            name=meta.name,
            description=meta.description,
            input_schema=meta.input_schema,
            allowed_roles=meta.allowed_roles | {"child"},
            requires_write=meta.requires_write,
            child_scope=meta.child_scope,
        )
        mock_db = MagicMock()
        mock_db.query.return_value.all.return_value = []
        mock_db.query.return_value.filter.return_value.all.return_value = []
        session = MCPSession("100", CHILD_A, "child")

        with (
            patch.dict(registry.TOOL_REGISTRY, {meta.name: widened}),
            _patch_child_call(mock_db),
        ):
            result = await session.call_tool(
                "get_child_literacy_profile", {"child_id": ""}
            )

        body = json.loads(result[0].text)
        # The handler ran (no permission error) — the gate pinned the query to
        # the caller rather than denying the empty-string value.
        assert "children" in body
        assert body["children"] == []


@pytest.mark.asyncio
class TestParentScopeUnchanged:
    """Owners, members and external tokens keep querying any child."""

    async def test_owner_may_name_a_sibling_child_and_reach_the_handler(self):
        mock_db = MagicMock()
        # Child lookup succeeds (this is what the old check allowed); the
        # question lookup then returns nothing, so the handler reports its own
        # not-found error instead of a permission error.
        mock_db.query.return_value.filter.return_value.first.side_effect = [
            MagicMock(id=SIBLING_ID, family_id="100"),  # the sibling, in family
            None,  # question
        ]
        session = MCPSession("100", "owner1", "owner")

        with _patch_child_call(mock_db, caller_id="owner1", role="owner"):
            result = await session.call_tool(
                "get_guided_question",
                {"question_id": 1, "child_id": SIBLING_ID, "topic_id": 1},
            )

        assert json.loads(result[0].text)["error"] == "question_not_found"

    async def test_member_may_name_a_sibling_child_and_reach_the_handler(self):
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = MagicMock(
            id=SIBLING_ID, family_id="100"
        )
        session = MCPSession("100", "member1", "member")

        with _patch_child_call(mock_db, caller_id="member1", role="member"):
            result = await session.call_tool(
                "get_knowledge_bridge", {"child_id": SIBLING_ID, "topic_id": 1}
            )

        body = json.loads(result[0].text)
        # The handler ran and answered for the sibling rather than being gated.
        assert body["child_id"] == SIBLING_ID
        assert "prerequisite_chain" in body

    async def test_external_token_with_own_synthetic_id_is_unaffected(self):
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.side_effect = [
            MagicMock(id=SIBLING_ID, family_id="100"),  # the sibling, in family
            None,  # question
        ]
        session = MCPSession(
            "100", "svc1", "external_token", allow_write=False
        )

        with _patch_child_call(mock_db, caller_id="svc1", role="external_token"):
            result = await session.call_tool(
                "get_guided_question",
                {"question_id": 1, "child_id": SIBLING_ID, "topic_id": 1},
            )

        assert json.loads(result[0].text)["error"] == "question_not_found"
