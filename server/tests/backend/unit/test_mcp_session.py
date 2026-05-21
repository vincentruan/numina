"""Unit tests for MCPSession — verifies family_id-bound tool isolation."""
import json
from unittest.mock import MagicMock, patch

import pytest

from apps.backend.app.services.mcp_session import MCPSession


@pytest.fixture
def mock_db():
    return MagicMock()


def test_session_binds_family_id_at_construction():
    session = MCPSession(family_id="100")
    assert session.family_id == "100"


def test_session_family_id_is_immutable():
    session = MCPSession(family_id="100")
    with pytest.raises(AttributeError):
        session.family_id = "200"


@pytest.mark.asyncio
async def test_list_tools_returns_five_tools():
    session = MCPSession(family_id="100")
    tools = await session.list_tools()
    names = {t.name for t in tools}
    assert names == {
        "get_family_overview",
        "get_assets",
        "get_liabilities",
        "get_members",
        "get_recent_alerts",
    }


@pytest.mark.asyncio
async def test_no_tool_exposes_family_id_parameter():
    session = MCPSession(family_id="100")
    tools = await session.list_tools()
    for tool in tools:
        schema = tool.inputSchema
        props = schema.get("properties", {}) if isinstance(schema, dict) else {}
        assert "family_id" not in props, f"Tool {tool.name} must not expose family_id"


@pytest.mark.asyncio
async def test_get_family_overview_uses_bound_family_id(mock_db):
    session = MCPSession(family_id="100")
    with patch("apps.backend.app.services.mcp_session.SessionLocal") as mock_session_local:
        mock_session_local.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_session_local.return_value.__exit__ = MagicMock(return_value=False)
        with patch("apps.backend.app.services.mcp_session._get_owner_user") as mock_user:
            mock_user.return_value = MagicMock(id="u1", family_id="100")
            with patch("apps.backend.app.services.dashboard.get_overview") as mock_get_overview:
                mock_get_overview.return_value = {"net_worth": 1000000}
                result = await session.call_tool("get_family_overview", {})
                mock_get_overview.assert_called_once()
                assert "net_worth" in result[0].text