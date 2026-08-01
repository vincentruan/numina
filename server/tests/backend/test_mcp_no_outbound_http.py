"""Dead-loop guard: verify MCP session paths have zero outbound HTTP.

Static checks: mcp_session.py and mcp_tool_registry.py must not import HTTP libraries.
Dynamic checks: patching httpx ensures no outbound calls during tool execution.
"""

import ast
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from apps.backend.app.services.mcp_session import MCPSession

_MCP_FILES = [
    "apps/backend/app/services/mcp_session.py",
    "apps/backend/app/services/mcp_tool_registry.py",
]

# Resolve paths relative to the server/ directory (pyproject.toml root)
_SERVER_ROOT = Path(__file__).resolve().parent.parent.parent

_FORBIDDEN_IMPORTS = {"httpx", "aiohttp", "apps.agent", "core.backend_client"}


class TestStaticImportGuard:
    @pytest.mark.parametrize("filepath", _MCP_FILES)
    def test_no_http_library_imports(self, filepath):
        source = (_SERVER_ROOT / filepath).read_text()
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert not any(
                        alias.name.startswith(f) for f in _FORBIDDEN_IMPORTS
                    ), f"{filepath} imports forbidden module: {alias.name}"
            elif isinstance(node, ast.ImportFrom) and node.module:
                assert not any(
                    node.module.startswith(f) for f in _FORBIDDEN_IMPORTS
                ), f"{filepath} imports from forbidden module: {node.module}"


class TestDynamicZeroOutboundHTTP:
    @pytest.fixture
    def session(self):
        return MCPSession("100", "u1", "owner")

    @pytest.fixture(autouse=True)
    def mock_session_local(self):
        with patch("apps.backend.app.services.mcp_session.SessionLocal") as mock_sl:
            mock_db = MagicMock()
            mock_sl.return_value.__enter__ = MagicMock(return_value=mock_db)
            mock_sl.return_value.__exit__ = MagicMock(return_value=False)
            self._mock_db = mock_db
            yield

    @pytest.fixture(autouse=True)
    def mock_caller_user(self):
        with patch("apps.backend.app.services.mcp_session._get_caller_user") as mock_get:
            mock_get.return_value = MagicMock(id="u1", family_id="100")
            yield

    @pytest.fixture(autouse=True)
    def mock_services(self):
        with patch("apps.backend.app.services.dashboard.get_overview", return_value={"ok": True}), \
             patch("apps.backend.app.services.asset.list_assets_for_family", return_value=[]), \
             patch("apps.backend.app.services.liability.list_liabilities_for_family", return_value=[]), \
             patch("apps.backend.app.services.family.list_members", return_value=[]), \
             patch("apps.backend.app.services.dashboard.get_recent_alerts", return_value=[]):
            yield

    @pytest.mark.asyncio
    async def test_call_tool_get_family_overview_zero_outbound_http(self, session):
        with patch("httpx.AsyncClient.send", side_effect=AssertionError("outbound HTTP!")), \
             patch("httpx.Client.send", side_effect=AssertionError("outbound HTTP!")):
            result = await session.call_tool("get_family_overview", {})
            assert "error" not in result[0].text or "permission_denied" not in result[0].text

    @pytest.mark.asyncio
    async def test_call_tool_get_assets_zero_outbound_http(self, session):
        with patch("httpx.AsyncClient.send", side_effect=AssertionError("outbound HTTP!")), \
             patch("httpx.Client.send", side_effect=AssertionError("outbound HTTP!")):
            await session.call_tool("get_assets", {"limit": 5})

    @pytest.mark.asyncio
    async def test_call_tool_get_liabilities_zero_outbound_http(self, session):
        with patch("httpx.AsyncClient.send", side_effect=AssertionError("outbound HTTP!")), \
             patch("httpx.Client.send", side_effect=AssertionError("outbound HTTP!")):
            await session.call_tool("get_liabilities", {"limit": 5})

    @pytest.mark.asyncio
    async def test_call_tool_get_members_zero_outbound_http(self, session):
        with patch("httpx.AsyncClient.send", side_effect=AssertionError("outbound HTTP!")), \
             patch("httpx.Client.send", side_effect=AssertionError("outbound HTTP!")):
            await session.call_tool("get_members", {})

    @pytest.mark.asyncio
    async def test_call_tool_get_recent_alerts_zero_outbound_http(self, session):
        with patch("httpx.AsyncClient.send", side_effect=AssertionError("outbound HTTP!")), \
             patch("httpx.Client.send", side_effect=AssertionError("outbound HTTP!")):
            await session.call_tool("get_recent_alerts", {"limit": 5})

    @pytest.mark.asyncio
    async def test_permission_denied_path_zero_outbound_http(self, session):
        """Role check failure path also has zero outbound HTTP."""
        child_session = MCPSession("100", "u1", "child")
        with patch("httpx.AsyncClient.send", side_effect=AssertionError("outbound HTTP!")), \
             patch("httpx.Client.send", side_effect=AssertionError("outbound HTTP!")):
            result = await child_session.call_tool("get_family_overview", {})
            assert "permission_denied" in result[0].text

    @pytest.mark.asyncio
    async def test_unknown_tool_path_zero_outbound_http(self, session):
        """Unknown tool path also has zero outbound HTTP."""
        with patch("httpx.AsyncClient.send", side_effect=AssertionError("outbound HTTP!")), \
             patch("httpx.Client.send", side_effect=AssertionError("outbound HTTP!")):
            result = await session.call_tool("nonexistent_tool", {})
            assert "permission_denied" in result[0].text
