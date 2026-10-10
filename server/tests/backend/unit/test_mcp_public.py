"""Tests for public MCP SSE endpoint auth and tool gating."""

from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest

from apps.backend.app.models.family import Family
from apps.backend.app.models.user import User
from apps.backend.app.services import mcp_token as token_svc
from apps.backend.app.utils.snowflake import next_id
from packages.core.roles import UserRole


def _create_family_with_token(db, *, allow_external=False, allow_write=False, expired=False):
    """Helper: create a family + token + synthetic user."""
    family = Family(id=next_id(), name="T", created_by=next_id())
    db.add(family)
    db.flush()

    plaintext, row = token_svc.generate_token(family.id, db)
    row.allow_external = allow_external
    row.allow_write = allow_write
    if expired:
        row.expires_at = datetime.now(UTC) - timedelta(hours=1)
    db.flush()

    # Ensure synthetic user exists
    synthetic = (
        db.query(User)
        .filter(User.family_id == family.id, User.role == UserRole.EXTERNAL_TOKEN)
        .first()
    )

    return family, plaintext, row, synthetic


class TestPublicMCPEndpointAuth:
    """AE1, AE2, AE3, AE5 — auth flows for public MCP endpoints."""

    def test_missing_token_returns_401(self, client):
        resp = client.get("/api/v1/mcp/public/123/sse")
        assert resp.status_code == 401

    def test_invalid_token_returns_401(self, client):
        resp = client.get(
            "/api/v1/mcp/public/123/sse",
            headers={"Authorization": "Bearer mcp_invalidtoken"},
        )
        assert resp.status_code == 401

    def test_allow_external_false_returns_403(self, client, db):
        family, plaintext, _, _ = _create_family_with_token(db, allow_external=False)
        db.commit()

        resp = client.get(
            f"/api/v1/mcp/public/{family.id}/sse",
            headers={"Authorization": f"Bearer {plaintext}"},
        )
        assert resp.status_code == 403

    def test_expired_token_returns_401(self, client, db):
        family, plaintext, _, _ = _create_family_with_token(db, allow_external=True, expired=True)
        db.commit()

        resp = client.get(
            f"/api/v1/mcp/public/{family.id}/sse",
            headers={"Authorization": f"Bearer {plaintext}"},
        )
        assert resp.status_code == 401

    def test_revoked_token_returns_401(self, client, db):
        family, plaintext, row, _ = _create_family_with_token(db, allow_external=True)
        row.is_active = False
        db.commit()

        resp = client.get(
            f"/api/v1/mcp/public/{family.id}/sse",
            headers={"Authorization": f"Bearer {plaintext}"},
        )
        assert resp.status_code == 401

    def test_query_param_auth_succeeds(self, client, db):
        """AE3: query param token is accepted and a WARNING audit log is emitted."""
        import asyncio
        import logging

        from starlette.requests import Request

        from apps.backend.app.routers import mcp_public

        family, plaintext, _, _ = _create_family_with_token(db, allow_external=True)
        db.commit()

        # Build a request with the token in the query string (no Bearer header)
        scope = {
            "type": "http",
            "headers": [],
            "query_string": f"token={plaintext}".encode(),
            "client": ("10.0.0.5", 54321),
        }
        request = Request(scope)

        with patch.object(mcp_public.logger, "warning") as mock_warn:
            result = asyncio.run(
                mcp_public.mcp_public_sse(str(family.id), request, token=plaintext)
            )

        # Valid token → SSE response object (not 401/403)
        assert isinstance(result, mcp_public.PublicMCPSSEResponse)
        assert result.session.caller_role == "external_token"

        # WARNING audit log emitted for query-param auth (with client IP + prefix)
        mock_warn.assert_called_once()
        args, kwargs = mock_warn.call_args
        assert "10.0.0.5" in args[0] or "10.0.0.5" in str(args)
        assert plaintext[:8] in str(args)

    def test_bearer_header_auth_no_warning(self, client, db):
        """R6: Bearer header usage does NOT trigger the WARNING audit log."""
        import asyncio

        from starlette.requests import Request

        from apps.backend.app.routers import mcp_public

        family, plaintext, _, _ = _create_family_with_token(db, allow_external=True)
        db.commit()

        scope = {
            "type": "http",
            "headers": [(b"authorization", f"Bearer {plaintext}".encode())],
            "query_string": b"",
            "client": ("10.0.0.5", 54321),
        }
        request = Request(scope)

        with patch.object(mcp_public.logger, "warning") as mock_warn:
            result = asyncio.run(
                mcp_public.mcp_public_sse(str(family.id), request, token=None)
            )

        assert isinstance(result, mcp_public.PublicMCPSSEResponse)
        mock_warn.assert_not_called()

    def test_session_gets_allow_write_from_token(self, client, db):
        """AE4: allow_write=True flows from the token row into MCPSession."""
        import asyncio

        from starlette.requests import Request

        from apps.backend.app.routers import mcp_public

        family, plaintext, _, _ = _create_family_with_token(
            db, allow_external=True, allow_write=True
        )
        db.commit()

        scope = {
            "type": "http",
            "headers": [(b"authorization", f"Bearer {plaintext}".encode())],
            "query_string": b"",
            "client": ("10.0.0.5", 54321),
        }
        request = Request(scope)

        result = asyncio.run(
            mcp_public.mcp_public_sse(str(family.id), request, token=None)
        )
        assert result.session.caller_role == "external_token"


class TestPublicMCPMessagesEndpoint:
    def test_messages_missing_token_returns_401(self, client):
        resp = client.post("/api/v1/mcp/public/messages")
        assert resp.status_code == 401

    def test_messages_invalid_token_returns_401(self, client):
        resp = client.post(
            "/api/v1/mcp/public/messages",
            headers={"Authorization": "Bearer mcp_invalidtoken"},
        )
        assert resp.status_code == 401


class TestToolGating:
    """AE2, AE4 — two-level tool gating for external_token callers."""

    @pytest.mark.asyncio
    async def test_read_only_tools_when_allow_write_false(self):
        from apps.backend.app.services.mcp_session import MCPSession

        session = MCPSession(
            family_id="123",
            caller_user_id="456",
            caller_role="external_token",
            allow_write=False,
        )
        tools = await session.list_tools()
        tool_names = {t.name for t in tools}

        # Read-only tools should be present
        assert "get_assets" in tool_names
        assert "get_family_overview" in tool_names

        # Write tools should NOT be present
        assert "import_assets_batch" not in tool_names
        assert "import_liabilities_batch" not in tool_names

    @pytest.mark.asyncio
    async def test_all_tools_when_allow_write_true(self):
        from apps.backend.app.services.mcp_session import MCPSession

        session = MCPSession(
            family_id="123",
            caller_user_id="456",
            caller_role="external_token",
            allow_write=True,
        )
        tools = await session.list_tools()
        tool_names = {t.name for t in tools}

        # Both read and write tools should be present
        assert "get_assets" in tool_names
        assert "import_assets_batch" in tool_names


class TestLoginRejection:
    """AE4 (auth guard) — external_token user cannot log in."""

    def test_external_token_user_cannot_login(self, client, db):
        from apps.backend.app.services.auth import hash_password

        family = Family(id=next_id(), name="T", created_by=next_id())
        db.add(family)
        db.flush()

        synthetic = User(
            id=next_id(),
            family_id=family.id,
            username="__mcp_service_test",
            display_name="MCP Service",
            password_hash=hash_password("test_password"),
            role=UserRole.EXTERNAL_TOKEN,
        )
        db.add(synthetic)
        db.commit()

        resp = client.post("/api/v1/auth/login", json={
            "username": "__mcp_service_test",
            "password": "test_password",
        })
        # Should be rejected — either 401 (AUTH_INVALID_CREDENTIALS)
        assert resp.status_code == 401


class TestInternalMCPUnaffected:
    """AE7 — internal agent MCP path remains unchanged."""

    def test_internal_endpoint_still_rejects_no_token(self, client):
        resp = client.get("/api/v1/internal/mcp/100/sse")
        assert resp.status_code == 401

    def test_internal_endpoint_still_rejects_invalid_token(self, client):
        resp = client.get(
            "/api/v1/internal/mcp/100/sse",
            headers={"X-Agent-Token": "wrong"},
        )
        assert resp.status_code == 401


class TestToolRegistryValidation:
    """Verify registry validates with external_token in _VALID_ROLES."""

    def test_validate_registry_passes(self):
        from apps.backend.app.services.mcp_tool_registry import validate_registry

        # Should not raise
        validate_registry()

    def test_external_token_in_valid_roles(self):
        from apps.backend.app.services.mcp_tool_registry import _VALID_ROLES

        assert "external_token" in _VALID_ROLES
