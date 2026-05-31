"""Tests for MCPSession caller binding — verifies caller identity is frozen and enforced."""

from unittest.mock import MagicMock, patch

import pytest

from apps.backend.app.services.mcp_session import MCPSession, _get_caller_user


class TestSlotsAndConstruction:
    def test_slots_contains_exactly_four_fields(self):
        assert MCPSession.__slots__ == (
            "_family_id",
            "_caller_user_id",
            "_caller_role",
            "_server",
        )

    def test_init_freezes_caller_user_id(self):
        session = MCPSession("100", "u1", "member")
        assert session._caller_user_id == "u1"
        with pytest.raises(AttributeError):
            session._new_attr = "should_fail"  # type: ignore[attr-defined]

    def test_init_rejects_empty_caller_user_id(self):
        with pytest.raises((ValueError, RuntimeError)):
            MCPSession("100", "", "member")

    def test_init_rejects_empty_caller_role(self):
        with pytest.raises((ValueError, RuntimeError)):
            MCPSession("100", "u1", "")


class TestGetCallerUser:
    def test_get_caller_user_rejects_cross_family(self):
        db = MagicMock()
        mock_user = MagicMock(id="u1", family_id="family_A", is_active=True)
        db.query.return_value.filter.return_value.first.return_value = mock_user
        with pytest.raises(RuntimeError, match="caller invalid"):
            _get_caller_user("family_B", "u1", db)

    def test_get_caller_user_rejects_inactive(self):
        db = MagicMock()
        mock_user = MagicMock(id="u1", family_id="100", is_active=False)
        db.query.return_value.filter.return_value.first.return_value = mock_user
        with pytest.raises(RuntimeError, match="caller invalid"):
            _get_caller_user("100", "u1", db)

    def test_get_caller_user_rejects_unknown_user_id(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None
        with pytest.raises(RuntimeError, match="caller invalid"):
            _get_caller_user("100", "nonexistent", db)


class TestCallToolIgnoresArgs:
    @pytest.mark.asyncio
    async def test_call_tool_ignores_caller_user_id_in_args(self):
        session = MCPSession("100", "u1", "member")
        with patch(
            "apps.backend.app.services.mcp_session.SessionLocal"
        ) as mock_sl:
            mock_db = MagicMock()
            mock_sl.return_value.__enter__ = MagicMock(return_value=mock_db)
            mock_sl.return_value.__exit__ = MagicMock(return_value=False)
            with patch(
                "apps.backend.app.services.mcp_session._get_caller_user"
            ) as mock_get:
                mock_get.return_value = MagicMock(id="u1", family_id="100")
                with patch(
                    "apps.backend.app.services.dashboard.get_overview"
                ) as mock_overview:
                    mock_overview.return_value = {"net_worth": 100}
                    await session.call_tool(
                        "get_family_overview", {"caller_user_id": "u_other"}
                    )
                    mock_get.assert_called_once_with("100", "u1", mock_db)

    @pytest.mark.asyncio
    async def test_call_tool_ignores_role_in_args(self):
        session = MCPSession("100", "u1", "member")
        with patch(
            "apps.backend.app.services.mcp_session.SessionLocal"
        ) as mock_sl:
            mock_db = MagicMock()
            mock_sl.return_value.__enter__ = MagicMock(return_value=mock_db)
            mock_sl.return_value.__exit__ = MagicMock(return_value=False)
            with patch(
                "apps.backend.app.services.mcp_session._get_caller_user"
            ) as mock_get:
                mock_get.return_value = MagicMock(id="u1", family_id="100")
                with patch(
                    "apps.backend.app.services.dashboard.get_overview"
                ) as mock_overview:
                    mock_overview.return_value = {"net_worth": 100}
                    await session.call_tool(
                        "get_family_overview", {"role": "owner"}
                    )
                    mock_get.assert_called_once_with("100", "u1", mock_db)


class TestAuditLog:
    @pytest.mark.asyncio
    async def test_audit_log_records_caller_user_id_not_owner(self):
        session = MCPSession("100", "u1", "member")
        with patch(
            "apps.backend.app.services.mcp_session.SessionLocal"
        ) as mock_sl:
            mock_db = MagicMock()
            mock_sl.return_value.__enter__ = MagicMock(return_value=mock_db)
            mock_sl.return_value.__exit__ = MagicMock(return_value=False)
            with patch(
                "apps.backend.app.services.mcp_session._get_caller_user"
            ) as mock_get:
                mock_get.return_value = MagicMock(id="u1", family_id="100")
                with patch(
                    "apps.backend.app.services.dashboard.get_overview"
                ) as mock_overview:
                    mock_overview.return_value = {"net_worth": 100}
                    with patch(
                        "apps.backend.app.services.mcp_session.logger"
                    ) as mock_logger:
                        await session.call_tool("get_family_overview", {})
                        log_call = mock_logger.info.call_args
                        log_msg = log_call[0][0] if log_call else ""
                        assert "caller_user_id" in log_msg or "u1" in str(
                            log_call
                        )
