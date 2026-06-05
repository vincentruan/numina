"""Test family-scoped capabilities endpoint."""

from unittest.mock import MagicMock, patch


def test_capabilities_without_family_id():
    """GET /capabilities (no family_id) should call list_capabilities."""
    from apps.agent.routers.capabilities import list_capabilities

    with patch("apps.agent.routers.capabilities.capability_registry") as mock_reg:
        with patch("apps.agent.routers.capabilities.settings") as mock_settings:
            mock_settings.AGENT_INTERNAL_TOKEN = "test"
            mock_settings.BACKEND_BASE_URL = "http://backend:8000"
            mock_reg.list_capabilities = MagicMock(return_value=[])
            result = list_capabilities(x_agent_token="test", family_id=None)
    assert result == []
    mock_reg.list_capabilities.assert_called_once()


def test_capabilities_with_family_id():
    """GET /capabilities?family_id=xxx should call list_capabilities_for_family."""
    from apps.agent.routers.capabilities import list_capabilities

    with patch("apps.agent.routers.capabilities.capability_registry") as mock_reg:
        with patch("apps.agent.routers.capabilities.settings") as mock_settings:
            mock_settings.AGENT_INTERNAL_TOKEN = "test"
            mock_settings.BACKEND_BASE_URL = "http://backend:8000"
            mock_reg.list_capabilities_for_family = MagicMock(return_value=[])
            result = list_capabilities(x_agent_token="test", family_id="fam-123")
    assert result == []
    mock_reg.list_capabilities_for_family.assert_called_once_with(
        "fam-123",
        "http://backend:8000",
        "test",
    )
