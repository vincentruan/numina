"""End-to-end tenant isolation test:
Family A connects to MCP and cannot see family B's data.
"""
import json
from unittest.mock import MagicMock, patch

import pytest

from apps.backend.app.services.mcp_session import MCPSession


@pytest.mark.asyncio
async def test_family_a_session_only_sees_own_data():
    """MCPSession for family A returns only family A's data."""
    mock_db = MagicMock()
    session_a = MCPSession(family_id="100", caller_user_id="u1", caller_role="owner")

    with patch("apps.backend.app.services.mcp_session.SessionLocal") as mock_session_local:
        mock_session_local.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_session_local.return_value.__exit__ = MagicMock(return_value=False)

        with patch("apps.backend.app.services.mcp_session._get_caller_user") as mock_user:
            mock_user.return_value = MagicMock(id="u1", family_id="100")

            with patch("apps.backend.app.services.dashboard.get_overview") as mock_overview:
                mock_overview.return_value = {"net_worth": 500000, "family_id": "100"}
                result = await session_a.call_tool("get_family_overview", {})
                data = json.loads(result[0].text)
                assert data["family_id"] == "100"
                mock_user.assert_called_with("100", "u1", mock_db)


@pytest.mark.asyncio
async def test_two_families_get_isolated_data():
    """Two MCPSessions for different families return different data."""
    mock_db = MagicMock()

    session_a = MCPSession(family_id="100", caller_user_id="u1", caller_role="owner")
    session_b = MCPSession(family_id="200", caller_user_id="u2", caller_role="owner")

    with patch("apps.backend.app.services.mcp_session.SessionLocal") as mock_session_local:
        mock_session_local.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_session_local.return_value.__exit__ = MagicMock(return_value=False)

        with patch("apps.backend.app.services.mcp_session._get_caller_user") as mock_user:
            mock_user.side_effect = lambda fid, uid, db: MagicMock(id=uid, family_id=fid)

            with patch("apps.backend.app.services.dashboard.get_overview") as mock_overview:
                def fake_overview(db, user):
                    return {"family_id": user.family_id, "net_worth": int(user.family_id) * 100}
                mock_overview.side_effect = fake_overview

                result_a = await session_a.call_tool("get_family_overview", {})
                data_a = json.loads(result_a[0].text)

                result_b = await session_b.call_tool("get_family_overview", {})
                data_b = json.loads(result_b[0].text)

                assert data_a["family_id"] == "100"
                assert data_b["family_id"] == "200"
                assert data_a["net_worth"] != data_b["net_worth"]


@pytest.mark.asyncio
async def test_llm_cannot_escalate_via_family_id_arg():
    """Even if LLM passes family_id=200 from family 100's session, it must be ignored."""
    mock_db = MagicMock()
    session_a = MCPSession(family_id="100", caller_user_id="u1", caller_role="owner")

    with patch("apps.backend.app.services.mcp_session.SessionLocal") as mock_session_local:
        mock_session_local.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_session_local.return_value.__exit__ = MagicMock(return_value=False)

        with patch("apps.backend.app.services.mcp_session._get_caller_user") as mock_user:
            mock_user.return_value = MagicMock(id="u1", family_id="100")

            with patch("apps.backend.app.services.asset.list_assets_for_family") as mock_list:
                mock_list.return_value = [{"id": "a1", "name": "car"}]

                # Adversarial call: LLM tries to pass family_id=200
                _result = await session_a.call_tool("get_assets", {"family_id": "200", "limit": 10})

                # Verify the service was called with the BOUND family_id (100), not the arg (200).
                call_args = mock_list.call_args
                assert call_args[0][1] == "100"


@pytest.mark.asyncio
async def test_no_tool_schema_contains_family_id():
    """Security: no tool's input schema should expose family_id to the LLM."""
    session = MCPSession(family_id="100", caller_user_id="u1", caller_role="owner")
    tools = await session.list_tools()

    for tool in tools:
        schema = tool.inputSchema
        props = schema.get("properties", {}) if isinstance(schema, dict) else {}
        assert "family_id" not in props, (
            f"SECURITY: Tool '{tool.name}' exposes family_id in its schema! "
            f"This would allow LLM to query any family's data."
        )
