"""Integration tests for the internal MCP SSE endpoint."""
import pytest
from fastapi.testclient import TestClient

from apps.backend.app.main import app
from packages.core.settings import settings as _core_settings
from packages.security.service_auth.agent_jwt import create_agent_token

_core_settings.SECRET_KEY = "test-secret-key-for-jwt-tests"


@pytest.fixture
def client():
    return TestClient(app)


def test_mcp_sse_endpoint_rejects_missing_token(client):
    resp = client.get("/api/v1/internal/mcp/100/sse")
    assert resp.status_code == 401


def test_mcp_sse_endpoint_rejects_invalid_token(client):
    resp = client.get(
        "/api/v1/internal/mcp/100/sse",
        headers={"X-Agent-Token": "wrong"},
    )
    assert resp.status_code == 401


@pytest.mark.skip(reason="MCP SSE requires full ASGI client handshake; integration test needed")
def test_mcp_sse_endpoint_accepts_valid_token(client):
    """Endpoint should accept valid auth and return MCPSSEResponse."""
    # Note: MCP SSE uses ASGI-level response (MCPSSEResponse)
    # Full SSE streaming requires MCP client handshake, not simple GET
    # Unit test can't easily simulate MCP protocol
    # Integration test with real MCP client needed for SSE verification
    pass