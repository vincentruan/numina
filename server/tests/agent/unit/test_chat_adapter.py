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


@pytest.mark.asyncio
async def test_stream_injects_mcp_server_into_adapter():
    """ChatAdapter.stream() must call create_family_adapter with mcp_servers list."""
    from apps.agent.services.deerflow_adapter.adapter import StreamChunk

    adapter = ChatAdapter("http://backend:8000", "secret-token")
    captured: dict = {}

    def fake_create(*args, **kwargs):
        captured["kwargs"] = kwargs
        mock_adapter = AsyncMock()

        async def fake_stream(*a, **kw):
            yield StreamChunk(type="text", content="hello")
        mock_adapter.stream_dispatch = fake_stream
        return mock_adapter

    with (
        patch("apps.agent.services.chat_adapter._create_family_adapter", side_effect=fake_create),
        patch.object(adapter, "_resolve_prompt", new=AsyncMock(return_value="sys")),
    ):
        chunks: list = []
        async for c in adapter.stream(
            family_id="100",
            question="hi",
            thread_id="t1",
            ai_config={"api_key": "k", "ai_model_id": "m", "ai_provider": "openai"},
            deep_think=False,
            web_search=False,
        ):
            chunks.append(c)

    assert len(chunks) == 1 and chunks[0].content == "hello"
    mcp_servers = captured["kwargs"].get("mcp_servers")
    assert mcp_servers and mcp_servers[0]["url"].endswith("/internal/mcp/100/sse")
    assert mcp_servers[0]["headers"]["X-Agent-Token"] == "secret-token"


@pytest.mark.asyncio
async def test_stream_deep_think_enables_subagent_and_plan_mode():
    adapter = ChatAdapter("http://backend:8000", "secret-token")
    captured: dict = {}

    def fake_create(*args, **kwargs):
        captured["kwargs"] = kwargs
        mock_adapter = AsyncMock()

        async def fake_stream(*a, **kw):
            yield  # empty generator
        mock_adapter.stream_dispatch = fake_stream
        return mock_adapter

    with (
        patch("apps.agent.services.chat_adapter._create_family_adapter", side_effect=fake_create),
        patch.object(adapter, "_resolve_prompt", new=AsyncMock(return_value="sys")),
    ):
        async for _ in adapter.stream(
            family_id="100",
            question="hi",
            thread_id="t1",
            ai_config={"api_key": "k", "ai_model_id": "m", "ai_provider": "openai"},
            deep_think=True,
            web_search=False,
        ):
            break

    kw = captured["kwargs"]
    assert kw.get("subagent_enabled") is True
    assert kw.get("plan_mode") is True
