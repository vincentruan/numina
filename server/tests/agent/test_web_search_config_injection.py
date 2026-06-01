# server/tests/agent/test_web_search_config_injection.py
"""Test the web search injection logic inside _generate_temp_config.

Since _generate_temp_config reads YAML from disk and returns a Path, we test
by creating a real temp config dir and reading back the generated YAML.
"""
import tempfile
from pathlib import Path

import pytest
import yaml


def _make_base_config_dir(tools: list[dict]) -> str:
    """Create a temp dir with a base/config.yaml for testing."""
    tmp = tempfile.mkdtemp(prefix="test_ws_")
    base_dir = Path(tmp) / "base"
    base_dir.mkdir()
    config = {
        "models": [{"model_name": "test", "use": "langchain_openai:ChatOpenAI"}],
        "tools": tools,
    }
    (base_dir / "config.yaml").write_text(yaml.dump(config), encoding="utf-8")
    return tmp


@pytest.fixture
def base_config_dir():
    tools = [
        {"name": "web_search", "use": "placeholder", "api_key": "", "max_results": 5},
        {"name": "crawl", "use": "some_crawler"},
    ]
    return _make_base_config_dir(tools)


@pytest.fixture
def ai_config_with_ws():
    return {
        "api_key": "sk-test",
        "ai_model_id": "gpt-4",
        "ai_provider": "openai",
        "web_search_providers": [
            {
                "provider_id": 1001,
                "provider_name": "tavily",
                "provider_class": "deerflow.community.tavily.tools:web_search_tool",
                "api_key": "tvly-real-key",
                "max_results": 5,
                "display_order": 1,
            },
        ],
        "web_search_mcp_servers": [],
    }


@pytest.fixture
def ai_config_no_ws():
    return {
        "api_key": "sk-test",
        "ai_model_id": "gpt-4",
        "ai_provider": "openai",
        "web_search_providers": [],
        "web_search_mcp_servers": [],
    }


@pytest.fixture
def ai_config_mcp_only():
    return {
        "api_key": "sk-test",
        "ai_model_id": "gpt-4",
        "ai_provider": "openai",
        "web_search_providers": [],
        "web_search_mcp_servers": [
            {"name": "brave-mcp", "url": "http://localhost:3001/sse", "transport": "sse"}
        ],
    }


def test_inject_web_search_provider_into_config(base_config_dir, ai_config_with_ws):
    """First available provider (tavily) should be injected into web_search tool."""
    from apps.agent.services.deerflow_adapter.family_adapter_cache import _generate_temp_config

    config_path = _generate_temp_config(base_config_dir, ai_config_with_ws, family_id="test1")
    config = yaml.safe_load(config_path.read_text())
    ws_tool = next(t for t in config["tools"] if t["name"] == "web_search")
    assert ws_tool["use"] == "deerflow.community.tavily.tools:web_search_tool"
    assert ws_tool["api_key"] == "tvly-real-key"
    assert ws_tool["max_results"] == 5


def test_no_web_search_providers_removes_tool(base_config_dir, ai_config_no_ws):
    """When no providers configured, web_search tool should be removed."""
    from apps.agent.services.deerflow_adapter.family_adapter_cache import _generate_temp_config

    config_path = _generate_temp_config(base_config_dir, ai_config_no_ws, family_id="test2")
    config = yaml.safe_load(config_path.read_text())
    tool_names = [t["name"] for t in config.get("tools", [])]
    assert "web_search" not in tool_names
    assert "crawl" in tool_names


def test_web_search_mcp_fallback_when_no_native(base_config_dir, ai_config_mcp_only):
    """When only MCP websearch available, web_search tool removed but MCP injected."""
    from apps.agent.services.deerflow_adapter.family_adapter_cache import _generate_temp_config

    config_path = _generate_temp_config(base_config_dir, ai_config_mcp_only, family_id="test3")
    config = yaml.safe_load(config_path.read_text())
    tool_names = [t["name"] for t in config.get("tools", [])]
    assert "web_search" not in tool_names
    assert any(m["name"] == "brave-mcp" for m in config.get("mcp_servers", []))