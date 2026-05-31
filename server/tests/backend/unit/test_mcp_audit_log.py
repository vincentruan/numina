"""Tests for MCP audit log field completeness."""

from unittest.mock import MagicMock, patch

import pytest

from apps.backend.app.services.mcp_session import MCPSession


@pytest.fixture
def session():
    return MCPSession("100", "u1", "member")


@pytest.fixture(autouse=True)
def mock_session_local():
    with patch("apps.backend.app.services.mcp_session.SessionLocal") as mock_sl:
        mock_db = MagicMock()
        mock_sl.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_sl.return_value.__exit__ = MagicMock(return_value=False)
        yield


@pytest.fixture(autouse=True)
def mock_caller_user():
    with patch("apps.backend.app.services.mcp_session._get_caller_user") as mock_get:
        mock_get.return_value = MagicMock(id="u1", family_id="100")
        yield


class TestAuditLogFields:
    @pytest.mark.asyncio
    async def test_audit_log_success_level_info(self, session):
        with patch("apps.backend.app.services.dashboard.get_overview", return_value={"ok": True}):
            with patch("apps.backend.app.services.mcp_session.logger") as mock_logger:
                await session.call_tool("get_family_overview", {})
                mock_logger.info.assert_called_once()
                log_msg = mock_logger.info.call_args[0][0]
                assert "ok" in log_msg

    @pytest.mark.asyncio
    async def test_audit_log_permission_denied_level_warning(self):
        child_session = MCPSession("100", "u1", "child")
        with patch("apps.backend.app.services.mcp_session.logger") as mock_logger:
            await child_session.call_tool("get_family_overview", {})
            mock_logger.warning.assert_called_once()
            log_msg = mock_logger.warning.call_args[0][0]
            assert "permission_denied" in log_msg

    @pytest.mark.asyncio
    async def test_audit_log_service_error_level_error(self, session):
        with patch("apps.backend.app.services.dashboard.get_overview", side_effect=RuntimeError("db down")):
            with patch("apps.backend.app.services.mcp_session.logger") as mock_logger:
                await session.call_tool("get_family_overview", {})
                mock_logger.error.assert_called_once()
                log_msg = mock_logger.error.call_args[0][0]
                assert "failed" in log_msg

    @pytest.mark.asyncio
    async def test_audit_log_includes_caller_user_id(self, session):
        with patch("apps.backend.app.services.dashboard.get_overview", return_value={"ok": True}):
            with patch("apps.backend.app.services.mcp_session.logger") as mock_logger:
                await session.call_tool("get_family_overview", {})
                log_args = mock_logger.info.call_args[0]
                assert "u1" in str(log_args)

    @pytest.mark.asyncio
    async def test_audit_log_includes_caller_role(self, session):
        with patch("apps.backend.app.services.dashboard.get_overview", return_value={"ok": True}):
            with patch("apps.backend.app.services.mcp_session.logger") as mock_logger:
                await session.call_tool("get_family_overview", {})
                log_args = mock_logger.info.call_args[0]
                assert "member" in str(log_args)

    @pytest.mark.asyncio
    async def test_audit_log_does_not_use_family_id_as_user_id_stand_in(self, session):
        with patch("apps.backend.app.services.dashboard.get_overview", return_value={"ok": True}):
            with patch("apps.backend.app.services.mcp_session.logger") as mock_logger:
                await session.call_tool("get_family_overview", {})
                log_msg_format = mock_logger.info.call_args[0][0]
                # The log format should have caller_user_id as a distinct field
                assert "caller_user_id" in log_msg_format
