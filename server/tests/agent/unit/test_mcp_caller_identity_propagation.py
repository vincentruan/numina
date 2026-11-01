"""Tests for agent-path caller identity propagation — verifies ContextVar → header injection and args-isolation."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestResolveMcpServerHeaderInjection:
    """Verify _resolve_numina_mcp_servers injects X-Caller-User-Id from the user_id parameter."""

    @pytest.mark.asyncio
    async def test_injects_caller_user_id_header(self):
        """_resolve_numina_mcp_servers injects X-Caller-User-Id from user_id into backend MCP headers."""
        from apps.agent.services.runtime.run_pipeline import (
            _resolve_numina_mcp_servers,
        )

        mock_client = AsyncMock()
        mock_client.get_enabled_mcp_servers.return_value = [
            {
                "name": "Numina Backend MCP",
                "url": "http://backend:8000/api/v1/internal/mcp/100/sse",
            }
        ]

        with patch(
            "apps.agent.app.config.settings"
        ) as mock_settings:
            mock_settings.BACKEND_BASE_URL = "http://backend:8000"
            with patch(
                "packages.security.service_auth.agent_jwt.create_agent_token",
                return_value="test-jwt-token",
            ):
                result = await _resolve_numina_mcp_servers(
                    client=mock_client,
                    family_id="100",
                    user_id="user-A",
                    label="[test]",
                )

        assert len(result) == 1
        headers = result[0]["headers"]
        assert headers["X-Caller-User-Id"] == "user-A"
        assert headers["X-Family-Id"] == "100"
        assert "X-Agent-Token" in headers

    @pytest.mark.asyncio
    async def test_no_caller_user_id_when_user_is_none(self):
        """_resolve_numina_mcp_servers omits X-Caller-User-Id when user_id is None."""
        from apps.agent.services.runtime.run_pipeline import (
            _resolve_numina_mcp_servers,
        )

        mock_client = AsyncMock()
        mock_client.get_enabled_mcp_servers.return_value = [
            {
                "name": "Numina Backend MCP",
                "url": "http://backend:8000/api/v1/internal/mcp/100/sse",
            }
        ]

        with patch(
            "apps.agent.app.config.settings"
        ) as mock_settings:
            mock_settings.BACKEND_BASE_URL = "http://backend:8000"
            with patch(
                "packages.security.service_auth.agent_jwt.create_agent_token",
                return_value="test-jwt-token",
            ):
                result = await _resolve_numina_mcp_servers(
                    client=mock_client,
                    family_id="100",
                    user_id=None,
                    label="[test]",
                )

        assert len(result) == 1
        headers = result[0]["headers"]
        assert "X-Caller-User-Id" not in headers

    @pytest.mark.asyncio
    async def test_injects_headers_only_for_backend_mcp_servers(self):
        """_resolve_numina_mcp_servers only injects headers into backend MCP servers, not external ones."""
        from apps.agent.services.runtime.run_pipeline import (
            _resolve_numina_mcp_servers,
        )

        mock_client = AsyncMock()
        mock_client.get_enabled_mcp_servers.return_value = [
            {
                "name": "External Tool Server",
                "url": "https://external.example.com/mcp/sse",
            },
            {
                "name": "Numina Backend MCP",
                "url": "http://backend:8000/api/v1/internal/mcp/100/sse",
            },
        ]

        with patch(
            "apps.agent.app.config.settings"
        ) as mock_settings:
            mock_settings.BACKEND_BASE_URL = "http://backend:8000"
            with patch(
                "packages.security.service_auth.agent_jwt.create_agent_token",
                return_value="test-jwt-token",
            ):
                result = await _resolve_numina_mcp_servers(
                    client=mock_client,
                    family_id="100",
                    user_id="user-A",
                    label="[test]",
                )

        assert len(result) == 2
        # External server should NOT have auth headers
        assert "headers" not in result[0] or "X-Caller-User-Id" not in result[0].get("headers", {})
        # Backend server SHOULD have auth headers
        assert result[1]["headers"]["X-Caller-User-Id"] == "user-A"


class TestArgsIsolationInAgentPath:
    """Verify MCPSession ignores injected identity in tool arguments (agent-path context)."""

    @pytest.mark.asyncio
    async def test_args_injection_does_not_override_session_identity(self):
        """MCPSession bound to user-A ignores caller_user_id in tool args."""
        from apps.backend.app.services.mcp_session import MCPSession

        session = MCPSession("100", "user-A", "member")
        with (
            patch("apps.backend.app.services.mcp_session.SessionLocal") as mock_sl,
            patch("apps.backend.app.services.mcp_session._get_caller_user") as mock_get,
            patch("apps.backend.app.services.dashboard.get_overview") as mock_overview,
        ):
            mock_db = MagicMock()
            mock_sl.return_value.__enter__ = MagicMock(return_value=mock_db)
            mock_sl.return_value.__exit__ = MagicMock(return_value=False)
            # _get_caller_user returns the session-bound user, not the injected one
            mock_get.return_value = MagicMock(id="user-A", family_id="100", role="member")
            mock_overview.return_value = {"net_worth": 100}

            await session.call_tool(
                "get_family_overview",
                {"caller_user_id": "user-B", "family_id": "fam-2"},
            )
            # Verify _get_caller_user was called with session-bound identity, not injected args
            mock_get.assert_called_once_with("100", "user-A", mock_db)

    @pytest.mark.asyncio
    async def test_role_injection_does_not_override_session_identity(self):
        """MCPSession bound to member role ignores injected role='owner' in tool args."""
        from apps.backend.app.services.mcp_session import MCPSession

        session = MCPSession("100", "u1", "member")
        with (
            patch("apps.backend.app.services.mcp_session.SessionLocal") as mock_sl,
            patch("apps.backend.app.services.mcp_session._get_caller_user") as mock_get,
            patch("apps.backend.app.services.dashboard.get_overview") as mock_overview,
        ):
            mock_db = MagicMock()
            mock_sl.return_value.__enter__ = MagicMock(return_value=mock_db)
            mock_sl.return_value.__exit__ = MagicMock(return_value=False)
            mock_get.return_value = MagicMock(id="u1", family_id="100", role="member")
            mock_overview.return_value = {"net_worth": 100}

            await session.call_tool(
                "get_family_overview",
                {"role": "owner"},
            )
            mock_get.assert_called_once_with("100", "u1", mock_db)


class TestCallToolRoleReValidation:
    """Verify call_tool() uses fresh user.role from DB, not cached self._caller_role."""

    @pytest.mark.asyncio
    async def test_call_tool_uses_fresh_role_from_db(self):
        """call_tool() uses user.role from _get_caller_user for role check, not self._caller_role."""
        from apps.backend.app.services.mcp_session import MCPSession

        # Session created with "member" role
        session = MCPSession("100", "u1", "member")
        with (
            patch("apps.backend.app.services.mcp_session.SessionLocal") as mock_sl,
            patch("apps.backend.app.services.mcp_session._get_caller_user") as mock_get,
            patch("apps.backend.app.services.dashboard.get_overview") as mock_overview,
        ):
            mock_db = MagicMock()
            mock_sl.return_value.__enter__ = MagicMock(return_value=mock_db)
            mock_sl.return_value.__exit__ = MagicMock(return_value=False)
            # But DB returns "owner" role (role changed mid-session)
            mock_get.return_value = MagicMock(id="u1", family_id="100", role="owner")
            mock_overview.return_value = {"net_worth": 100}

            result = await session.call_tool("get_family_overview", {})
            # Tool should succeed because fresh role is "owner" (has access)
            assert len(result) == 1
            assert "net_worth" in result[0].text

    @pytest.mark.asyncio
    async def test_deactivated_user_returns_permission_denied_with_audit(self):
        """Deactivated user triggers audit callback with permission_denied before returning error."""
        from apps.backend.app.services.mcp_session import MCPSession

        audit_cb = MagicMock()
        session = MCPSession("100", "u1", "member", audit_callback=audit_cb)
        with (
            patch("apps.backend.app.services.mcp_session.SessionLocal") as mock_sl,
            patch("apps.backend.app.services.mcp_session._get_caller_user") as mock_get,
        ):
            mock_db = MagicMock()
            mock_sl.return_value.__enter__ = MagicMock(return_value=mock_db)
            mock_sl.return_value.__exit__ = MagicMock(return_value=False)
            # User deactivated — _get_caller_user raises RuntimeError
            mock_get.side_effect = RuntimeError("caller invalid")

            result = await session.call_tool("get_family_overview", {})

            # Should return permission_denied
            assert len(result) == 1
            assert "permission_denied" in result[0].text

            # Audit callback should fire with permission_denied + caller_invalid
            audit_cb.assert_called_once()
            cb_kwargs = audit_cb.call_args.kwargs
            assert cb_kwargs["status"] == "permission_denied"
            assert cb_kwargs["error_code"] == "caller_invalid"
