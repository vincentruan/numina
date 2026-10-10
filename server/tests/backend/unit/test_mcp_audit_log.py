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
        with patch("apps.backend.app.services.dashboard.get_overview", return_value={"ok": True}), \
             patch("apps.backend.app.services.mcp_session.logger") as mock_logger:
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
        with patch("apps.backend.app.services.dashboard.get_overview", side_effect=RuntimeError("db down")), \
             patch("apps.backend.app.services.mcp_session.logger") as mock_logger:
            await session.call_tool("get_family_overview", {})
            mock_logger.error.assert_called_once()
            log_msg = mock_logger.error.call_args[0][0]
            assert "failed" in log_msg

    @pytest.mark.asyncio
    async def test_audit_log_includes_caller_user_id(self, session):
        with patch("apps.backend.app.services.dashboard.get_overview", return_value={"ok": True}), \
             patch("apps.backend.app.services.mcp_session.logger") as mock_logger:
            await session.call_tool("get_family_overview", {})
            log_args = mock_logger.info.call_args[0]
            assert "u1" in str(log_args)

    @pytest.mark.asyncio
    async def test_audit_log_includes_caller_role(self, session):
        with patch("apps.backend.app.services.dashboard.get_overview", return_value={"ok": True}), \
             patch("apps.backend.app.services.mcp_session.logger") as mock_logger:
            await session.call_tool("get_family_overview", {})
            log_args = mock_logger.info.call_args[0]
            assert "member" in str(log_args)

    @pytest.mark.asyncio
    async def test_audit_log_does_not_use_family_id_as_user_id_stand_in(self, session):
        with patch("apps.backend.app.services.dashboard.get_overview", return_value={"ok": True}), \
             patch("apps.backend.app.services.mcp_session.logger") as mock_logger:
            await session.call_tool("get_family_overview", {})
            log_msg_format = mock_logger.info.call_args[0][0]
            # The log format should have caller_user_id as a distinct field
            assert "caller_user_id" in log_msg_format


class TestAuditRedaction:
    """Tests for recursive secret redaction in audit args_digest."""

    def test_top_level_secret_key_redacted(self):
        from apps.backend.app.services.mcp_audit import _redact_args

        result = _redact_args({"api_key": "sk-abcdefghij123", "name": "visible"})
        assert "[REDACTED]" in result
        assert "sk-abcdefghij123" not in result
        assert "visible" in result

    def test_nested_dict_secret_redacted(self):
        """P2 fix: redaction must recurse into nested structures."""
        from apps.backend.app.services.mcp_audit import _redact_args

        result = _redact_args({"config": {"api_key": "sk-nested-secret-123"}})
        assert "sk-nested-secret-123" not in result
        assert "[REDACTED]" in result

    def test_deeply_nested_secret_redacted(self):
        from apps.backend.app.services.mcp_audit import _redact_args

        result = _redact_args({"a": {"b": {"c": {"password": "hunter2"}}}})
        assert "hunter2" not in result
        assert "[REDACTED]" in result

    def test_secret_inside_list_of_dicts_redacted(self):
        from apps.backend.app.services.mcp_audit import _redact_args

        result = _redact_args({"items": [{"token": "mcp_abcdefghijklmnop"}, {"k": "v"}]})
        assert "mcp_abcdefghijklmnop" not in result
        assert "[REDACTED]" in result

    def test_token_pattern_in_plain_value_redacted(self):
        """Values matching secret patterns are redacted even under innocuous keys."""
        from apps.backend.app.services.mcp_audit import _redact_args

        result = _redact_args({"note": "use mcp_abcdefghijklmnop to auth"})
        assert "mcp_abcdefghijklmnop" not in result

    def test_bearer_token_redacted(self):
        from apps.backend.app.services.mcp_audit import _redact_args

        result = _redact_args({"header": "Bearer eyJhbGciOiJIUzI1NiJ9.payload.sig"})
        assert "eyJhbGciOiJIUzI1NiJ9" not in result

    def test_non_sensitive_nested_values_preserved(self):
        from apps.backend.app.services.mcp_audit import _redact_args

        result = _redact_args({"data": {"name": "get_assets", "count": 5}})
        assert "get_assets" in result
        assert "5" in result
        assert "[REDACTED]" not in result

    def test_depth_limit_prevents_unbounded_recursion(self):
        from apps.backend.app.services.mcp_audit import _redact_obj

        deep = current = {}
        for _ in range(20):
            current["child"] = {}
            current = current["child"]
        result = _redact_obj(deep)
        assert "[MAX_DEPTH]" in str(result)

    def test_digest_truncated_to_max_length(self):
        from apps.backend.app.services.mcp_audit import _MAX_DIGEST_LEN, _redact_args

        result = _redact_args({"big": "x" * 5000})
        assert len(result) <= _MAX_DIGEST_LEN + 1  # +1 for the ellipsis char

    def test_empty_args_returns_none(self):
        from apps.backend.app.services.mcp_audit import _redact_args

        assert _redact_args(None) is None
        assert _redact_args({}) is None
