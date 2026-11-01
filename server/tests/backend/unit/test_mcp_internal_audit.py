"""Tests for internal SSE path audit callback — verifies persistent DB audit for agent-initiated MCP calls."""

from unittest.mock import ANY, MagicMock, patch

import pytest


@pytest.fixture
def client():
    from fastapi.testclient import TestClient

    from apps.backend.app.main import app

    return TestClient(app)


@pytest.fixture
def valid_token():
    from packages.security.service_auth.agent_jwt import create_agent_token

    return create_agent_token("100")


class TestInternalAuditCallback:
    """Verify the internal SSE path wires audit_callback to MCPSession."""

    def test_internal_sse_passes_audit_callback_to_session(self, client, valid_token):
        """Internal SSE constructs MCPSession with a non-None audit_callback."""
        with patch("apps.backend.app.database.SessionLocal") as mock_sl:
            mock_db = MagicMock()
            mock_sl.return_value.__enter__ = MagicMock(return_value=mock_db)
            mock_sl.return_value.__exit__ = MagicMock(return_value=False)
            mock_user = MagicMock(id="u1", family_id="100", is_active=True, role="member")
            mock_db.query.return_value.filter.return_value.first.return_value = mock_user

            with patch("apps.backend.app.routers.mcp_internal.MCPSession") as mock_session:
                mock_session.return_value = MagicMock()
                with patch(
                    "apps.backend.app.routers.mcp_internal.MCPSSEResponse"
                ) as mock_resp:
                    mock_resp.return_value = MagicMock(status_code=200)
                    client.get(
                        "/api/v1/internal/mcp/100/sse",
                        headers={
                            "X-Agent-Token": valid_token,
                            "X-Family-Id": "100",
                            "X-Caller-User-Id": "u1",
                        },
                    )
                    mock_session.assert_called_once_with(
                        family_id="100",
                        caller_user_id="u1",
                        caller_role="member",
                        thread_id=None,
                        audit_callback=ANY,
                    )

    def test_internal_audit_callback_writes_with_token_id_none(self, client, valid_token):
        """The internal audit callback writes with token_id=None and client_ip='internal'."""
        with patch("apps.backend.app.database.SessionLocal") as mock_sl:
            mock_db = MagicMock()
            mock_sl.return_value.__enter__ = MagicMock(return_value=mock_db)
            mock_sl.return_value.__exit__ = MagicMock(return_value=False)
            mock_user = MagicMock(id="u1", family_id="100", is_active=True, role="member")
            mock_db.query.return_value.filter.return_value.first.return_value = mock_user

            with patch(
                "apps.backend.app.routers.mcp_internal.write_mcp_access_log"
            ) as mock_write:
                with patch(
                    "apps.backend.app.routers.mcp_internal.MCPSession"
                ) as mock_session:
                    mock_session.return_value = MagicMock()
                    with patch(
                        "apps.backend.app.routers.mcp_internal.MCPSSEResponse"
                    ) as mock_resp:
                        mock_resp.return_value = MagicMock(status_code=200)
                        client.get(
                            "/api/v1/internal/mcp/100/sse",
                            headers={
                                "X-Agent-Token": valid_token,
                                "X-Family-Id": "100",
                                "X-Caller-User-Id": "u1",
                            },
                        )

                        audit_cb = mock_session.call_args.kwargs["audit_callback"]
                        audit_cb(
                            event_type="tool_call",
                            tool_name="get_family_overview",
                            status="success",
                            duration_ms=42,
                            args_digest={"limit": 10},
                        )

                        mock_write.assert_called_once_with(
                            family_id=100,
                            token_id=None,
                            event_type="tool_call",
                            tool_name="get_family_overview",
                            status="success",
                            duration_ms=42,
                            client_ip="internal",
                            args_digest={"limit": 10},
                            error_code=None,
                        )

    def test_internal_audit_callback_permission_denied(self, client, valid_token):
        """The internal audit callback fires with status='permission_denied' on role check failure."""
        with patch("apps.backend.app.database.SessionLocal") as mock_sl:
            mock_db = MagicMock()
            mock_sl.return_value.__enter__ = MagicMock(return_value=mock_db)
            mock_sl.return_value.__exit__ = MagicMock(return_value=False)
            mock_user = MagicMock(id="u1", family_id="100", is_active=True, role="member")
            mock_db.query.return_value.filter.return_value.first.return_value = mock_user

            with patch(
                "apps.backend.app.routers.mcp_internal.write_mcp_access_log"
            ) as mock_write:
                with patch(
                    "apps.backend.app.routers.mcp_internal.MCPSession"
                ) as mock_session:
                    mock_session.return_value = MagicMock()
                    with patch(
                        "apps.backend.app.routers.mcp_internal.MCPSSEResponse"
                    ) as mock_resp:
                        mock_resp.return_value = MagicMock(status_code=200)
                        client.get(
                            "/api/v1/internal/mcp/100/sse",
                            headers={
                                "X-Agent-Token": valid_token,
                                "X-Family-Id": "100",
                                "X-Caller-User-Id": "u1",
                            },
                        )

                        audit_cb = mock_session.call_args.kwargs["audit_callback"]
                        audit_cb(
                            event_type="tool_call",
                            tool_name="restricted_tool",
                            status="permission_denied",
                            error_code="role_not_allowed",
                        )

                        mock_write.assert_called_once()
                        call_kwargs = mock_write.call_args.kwargs
                        assert call_kwargs["status"] == "permission_denied"
                        assert call_kwargs["error_code"] == "role_not_allowed"
                        assert call_kwargs["token_id"] is None
                        assert call_kwargs["client_ip"] == "internal"
