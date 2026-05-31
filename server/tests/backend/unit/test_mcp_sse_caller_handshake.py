"""Tests for MCP SSE handshake caller validation."""

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from apps.backend.app.main import app


@pytest.fixture
def client():
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def valid_token():
    return "test-agent-token"


@pytest.fixture(autouse=True)
def mock_settings(valid_token):
    with patch("apps.backend.app.routers.mcp_internal.settings") as mock_s:
        mock_s.AGENT_INTERNAL_TOKEN = valid_token
        yield mock_s


class TestSSEHandshakeCallerValidation:
    def test_missing_caller_header_returns_403(self, client, valid_token):
        resp = client.get(
            "/api/v1/internal/mcp/100/sse",
            headers={"X-Agent-Token": valid_token, "X-Family-Id": "100"},
        )
        assert resp.status_code == 403

    def test_empty_caller_header_returns_403(self, client, valid_token):
        resp = client.get(
            "/api/v1/internal/mcp/100/sse",
            headers={
                "X-Agent-Token": valid_token,
                "X-Family-Id": "100",
                "X-Caller-User-Id": "",
            },
        )
        assert resp.status_code == 403

    def test_unknown_caller_returns_403(self, client, valid_token):
        with patch("apps.backend.app.database.SessionLocal") as mock_sl:
            mock_db = MagicMock()
            mock_sl.return_value.__enter__ = MagicMock(return_value=mock_db)
            mock_sl.return_value.__exit__ = MagicMock(return_value=False)
            mock_db.query.return_value.filter.return_value.first.return_value = None

            resp = client.get(
                "/api/v1/internal/mcp/100/sse",
                headers={
                    "X-Agent-Token": valid_token,
                    "X-Family-Id": "100",
                    "X-Caller-User-Id": "nonexistent",
                },
            )
            assert resp.status_code == 403

    def test_cross_family_caller_returns_403(self, client, valid_token):
        with patch("apps.backend.app.database.SessionLocal") as mock_sl:
            mock_db = MagicMock()
            mock_sl.return_value.__enter__ = MagicMock(return_value=mock_db)
            mock_sl.return_value.__exit__ = MagicMock(return_value=False)
            mock_user = MagicMock(id="u1", family_id="999", is_active=True, role="owner")
            mock_db.query.return_value.filter.return_value.first.return_value = mock_user

            resp = client.get(
                "/api/v1/internal/mcp/100/sse",
                headers={
                    "X-Agent-Token": valid_token,
                    "X-Family-Id": "100",
                    "X-Caller-User-Id": "u1",
                },
            )
            assert resp.status_code == 403

    def test_inactive_caller_returns_403(self, client, valid_token):
        with patch("apps.backend.app.database.SessionLocal") as mock_sl:
            mock_db = MagicMock()
            mock_sl.return_value.__enter__ = MagicMock(return_value=mock_db)
            mock_sl.return_value.__exit__ = MagicMock(return_value=False)
            mock_user = MagicMock(id="u1", family_id="100", is_active=False, role="owner")
            mock_db.query.return_value.filter.return_value.first.return_value = mock_user

            resp = client.get(
                "/api/v1/internal/mcp/100/sse",
                headers={
                    "X-Agent-Token": valid_token,
                    "X-Family-Id": "100",
                    "X-Caller-User-Id": "u1",
                },
            )
            assert resp.status_code == 403

    def test_child_caller_returns_403(self, client, valid_token):
        with patch("apps.backend.app.database.SessionLocal") as mock_sl:
            mock_db = MagicMock()
            mock_sl.return_value.__enter__ = MagicMock(return_value=mock_db)
            mock_sl.return_value.__exit__ = MagicMock(return_value=False)
            mock_user = MagicMock(id="u1", family_id="100", is_active=True, role="child")
            mock_db.query.return_value.filter.return_value.first.return_value = mock_user

            resp = client.get(
                "/api/v1/internal/mcp/100/sse",
                headers={
                    "X-Agent-Token": valid_token,
                    "X-Family-Id": "100",
                    "X-Caller-User-Id": "u1",
                },
            )
            assert resp.status_code == 403

    def test_member_caller_passes(self, client, valid_token):
        with patch("apps.backend.app.database.SessionLocal") as mock_sl:
            mock_db = MagicMock()
            mock_sl.return_value.__enter__ = MagicMock(return_value=mock_db)
            mock_sl.return_value.__exit__ = MagicMock(return_value=False)
            mock_user = MagicMock(id="u1", family_id="100", is_active=True, role="member")
            mock_db.query.return_value.filter.return_value.first.return_value = mock_user

            with patch("apps.backend.app.routers.mcp_internal.MCPSession") as mock_session:
                mock_session.return_value = MagicMock()
                with patch("apps.backend.app.routers.mcp_internal.MCPSSEResponse") as mock_resp:
                    mock_resp.return_value = MagicMock(status_code=200)
                    # Verify no exception is raised — caller passes validation
                    mock_session.assert_not_called()  # not yet
                    resp = client.get(
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
                    )

    def test_owner_caller_passes(self, client, valid_token):
        with patch("apps.backend.app.database.SessionLocal") as mock_sl:
            mock_db = MagicMock()
            mock_sl.return_value.__enter__ = MagicMock(return_value=mock_db)
            mock_sl.return_value.__exit__ = MagicMock(return_value=False)
            mock_user = MagicMock(id="u1", family_id="100", is_active=True, role="owner")
            mock_db.query.return_value.filter.return_value.first.return_value = mock_user

            with patch("apps.backend.app.routers.mcp_internal.MCPSession") as mock_session:
                mock_session.return_value = MagicMock()
                with patch("apps.backend.app.routers.mcp_internal.MCPSSEResponse") as mock_resp:
                    mock_resp.return_value = MagicMock(status_code=200)
                    resp = client.get(
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
                        caller_role="owner",
                    )
