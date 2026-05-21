"""Unit tests for ChatAdapter — system prompt loading + MCP URL composition."""
from unittest.mock import AsyncMock, patch

import pytest

from apps.agent.services.chat_adapter import ChatAdapter


@pytest.fixture
def adapter():
    return ChatAdapter(
        backend_base_url="http://backend:8000",
        internal_token="test-token",
    )


def test_default_prompt_loaded_from_file(adapter):
    prompt = adapter._load_default_prompt()
    assert "Numina 家庭资产助手" in prompt
    # frontmatter must be stripped
    assert "---" not in prompt.splitlines()[0]


@pytest.mark.asyncio
async def test_resolve_prompt_uses_family_override_when_present(adapter):
    with patch.object(adapter, "_fetch_family_prompt", new=AsyncMock(return_value="family custom")):
        result = await adapter._resolve_prompt("100")
        assert result == "family custom"


@pytest.mark.asyncio
async def test_resolve_prompt_falls_back_to_default_when_no_override(adapter):
    with patch.object(adapter, "_fetch_family_prompt", new=AsyncMock(return_value=None)):
        result = await adapter._resolve_prompt("100")
        assert "Numina 家庭资产助手" in result


@pytest.mark.asyncio
async def test_resolve_prompt_falls_back_on_fetch_error(adapter):
    with patch.object(adapter, "_fetch_family_prompt", new=AsyncMock(side_effect=Exception("net err"))):
        result = await adapter._resolve_prompt("100")
        assert "Numina 家庭资产助手" in result


def test_mcp_url_contains_family_id(adapter):
    url = adapter._mcp_url("100")
    assert url == "http://backend:8000/api/v1/internal/mcp/100/sse"


def test_mcp_url_rejects_unsafe_family_id(adapter):
    with pytest.raises(ValueError):
        adapter._mcp_url("../etc/passwd")
