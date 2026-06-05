"""Test that non-chat capabilities receive MCP server injection."""

from apps.agent.services.orchestrator import Orchestrator


def test_mcp_server_config_for_non_chat():
    """Non-chat capabilities should receive numina-family-data MCP server config."""
    o = Orchestrator.__new__(Orchestrator)
    config = o._build_mcp_servers("family-123", user_id="user-456")
    assert len(config) == 1
    assert config[0]["name"] == "numina-family-data"
    assert "family-123" in config[0]["url"]
    assert config[0]["transport"] == "sse"
    assert config[0]["headers"]["X-Family-Id"] == "family-123"
    assert config[0]["headers"]["X-Caller-User-Id"] == "user-456"


def test_mcp_server_config_without_user_id():
    """MCP config omits X-Caller-User-Id when user_id is None."""
    o = Orchestrator.__new__(Orchestrator)
    config = o._build_mcp_servers("family-123", user_id=None)
    assert "X-Caller-User-Id" not in config[0]["headers"]
