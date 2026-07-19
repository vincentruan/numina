"""Unit tests for MCPSession — verifies family_id-bound tool isolation."""
import json
from unittest.mock import MagicMock, patch

import pytest

from apps.backend.app.services.mcp_session import MCPSession


@pytest.fixture
def mock_db():
    return MagicMock()


def test_session_binds_family_id_at_construction():
    session = MCPSession(family_id="100", caller_user_id="u1", caller_role="owner")
    assert session.family_id == "100"


def test_session_family_id_is_immutable():
    session = MCPSession(family_id="100", caller_user_id="u1", caller_role="owner")
    with pytest.raises(AttributeError):
        session._undeclared = "200"  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_list_tools_returns_eight_tools():
    session = MCPSession(family_id="100", caller_user_id="u1", caller_role="owner")
    tools = await session.list_tools()
    names = {t.name for t in tools}
    # #11 (U8 follow-up): 3 import_*_batch write tools added → 8 total.
    assert names == {
        "get_family_overview",
        "get_assets",
        "get_liabilities",
        "get_members",
        "get_recent_alerts",
        "import_assets_batch",
        "import_liabilities_batch",
        "import_credit_cards_batch",
    }


@pytest.mark.asyncio
async def test_no_tool_exposes_family_id_parameter():
    session = MCPSession(family_id="100", caller_user_id="u1", caller_role="owner")
    tools = await session.list_tools()
    for tool in tools:
        schema = tool.inputSchema
        props = schema.get("properties", {}) if isinstance(schema, dict) else {}
        assert "family_id" not in props, f"Tool {tool.name} must not expose family_id"


@pytest.mark.asyncio
async def test_get_family_overview_uses_bound_family_id(mock_db):
    session = MCPSession(family_id="100", caller_user_id="u1", caller_role="owner")
    with patch("apps.backend.app.services.mcp_session.SessionLocal") as mock_session_local:
        mock_session_local.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_session_local.return_value.__exit__ = MagicMock(return_value=False)
        with patch("apps.backend.app.services.mcp_session._get_caller_user") as mock_user:
            mock_user.return_value = MagicMock(id="u1", family_id="100")
            with patch("apps.backend.app.services.dashboard.get_overview") as mock_get_overview:
                mock_get_overview.return_value = {"net_worth": 1000000}
                result = await session.call_tool("get_family_overview", {})
                mock_get_overview.assert_called_once()
                assert "net_worth" in result[0].text


@pytest.mark.asyncio
async def test_child_role_cannot_use_batch_write_tools():
    """#11: import_*_batch tools require owner/member — child role is denied."""
    session = MCPSession(family_id="100", caller_user_id="u1", caller_role="child")
    # The tools must not even appear in the child's listing.
    tools = await session.list_tools()
    assert all(not t.name.startswith("import_") for t in tools)
    # And a direct call is rejected with permission_denied at the enforcement layer.
    result = await session.call_tool("import_assets_batch", {"items": []})
    payload = json.loads(result[0].text)
    assert payload["error"] == "permission_denied"


@pytest.mark.asyncio
async def test_import_assets_batch_skips_unknown_category(mock_db):
    """#11: items whose category_hint matches no system Category are skipped,
    not failed — the agent can retry with a supported hint."""
    session = MCPSession(family_id="100", caller_user_id="u1", caller_role="owner")

    # Category query returns None for the unknown hint.
    mock_query = MagicMock()
    mock_query.filter.return_value.first.return_value = None
    mock_db.query.return_value = mock_query

    with patch("apps.backend.app.services.mcp_session.SessionLocal") as mock_sl:
        mock_sl.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_sl.return_value.__exit__ = MagicMock(return_value=False)
        with patch("apps.backend.app.services.mcp_session._get_caller_user") as mock_user:
            mock_user.return_value = MagicMock(id="u1", family_id="100")
            result = await session.call_tool("import_assets_batch", {
                "items": [
                    {"temp_id": "t1", "name": "茅台", "category_hint": "未知类别",
                     "current_value": 1000.0},
                ]
            })
    payload = json.loads(result[0].text)
    assert payload["created"] == 0
    assert payload["skipped"] == 1
    assert payload["items"][0]["status"] == "skipped"
    assert payload["items"][0]["temp_id"] == "t1"


@pytest.mark.asyncio
async def test_import_credit_cards_batch_applies_category_override(mock_db):
    """#11: import_credit_cards_batch forces category='credit_card' regardless
    of any per-item category, via the category_override kwarg."""
    from apps.backend.app.schemas.liability import LiabilityCreate

    session = MCPSession(family_id="100", caller_user_id="u1", caller_role="owner")
    created_reqs: list[LiabilityCreate] = []

    def _fake_create_liability(db, user, req):
        created_reqs.append(req)
        return MagicMock(id=999, name=req.name)

    with patch("apps.backend.app.services.mcp_session.SessionLocal") as mock_sl:
        mock_sl.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_sl.return_value.__exit__ = MagicMock(return_value=False)
        with patch("apps.backend.app.services.mcp_session._get_caller_user") as mock_user:
            mock_user.return_value = MagicMock(id="u1", family_id="100")
            with patch(
                "apps.backend.app.services.liability.create_liability",
                side_effect=_fake_create_liability,
            ):
                result = await session.call_tool("import_credit_cards_batch", {
                    "items": [
                        {"temp_id": "c1", "name": "招行信用卡",
                         "original_amount": 50000.0, "remaining_amount": 3000.0,
                         "category": "should_be_ignored"},
                    ]
                })
    payload = json.loads(result[0].text)
    assert payload["created"] == 1
    assert created_reqs[0].category == "credit_card"  # override applied
    assert created_reqs[0].name == "招行信用卡"