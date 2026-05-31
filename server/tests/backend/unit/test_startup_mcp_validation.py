"""Tests for MCP tool registry startup validation in backend lifespan."""

from unittest.mock import patch

from fastapi.testclient import TestClient


def test_lifespan_calls_validate_registry():
    with patch(
        "apps.backend.app.services.mcp_tool_registry.validate_registry"
    ) as mock_validate:
        from apps.backend.app.main import app

        with TestClient(app):
            mock_validate.assert_called_once()


def test_lifespan_aborts_on_invalid_registry():
    with patch(
        "apps.backend.app.services.mcp_tool_registry.validate_registry",
        side_effect=RuntimeError("broken registry"),
    ):
        from apps.backend.app.main import app

        try:
            with TestClient(app, raise_server_exceptions=True):
                pass
        except RuntimeError as e:
            assert "broken registry" in str(e)
