"""Unit tests for DeerFlowAdapter._produce() StreamChunk migration (U1)."""

from dataclasses import dataclass
from typing import Any
from unittest.mock import MagicMock

import pytest

from apps.agent.services.deerflow_adapter.adapter import (
    DeerFlowAdapter,
    DeerFlowError,
    StreamChunk,
)
from tests.agent.golden.fixtures import REDACTED_CONTEXT


@dataclass
class _FakeStreamEvent:
    type: str
    data: Any


def _ai_event(content=None, reasoning_content=None) -> _FakeStreamEvent:
    data: dict[str, Any] = {"type": "ai"}
    if content is not None:
        data["content"] = content
    if reasoning_content is not None:
        data["additional_kwargs"] = {"reasoning_content": reasoning_content}
    return _FakeStreamEvent(type="messages-tuple", data=data)


def _make_adapter(events) -> DeerFlowAdapter:
    adapter = DeerFlowAdapter.__new__(DeerFlowAdapter)
    adapter._timeout = 10
    adapter._family_id = "fam_test"
    adapter._ai_config = {}
    adapter._is_family_mode = True
    adapter._config_path = None  # Required attribute for _produce method
    client = MagicMock()
    client.stream.return_value = iter(events)
    adapter._client = client
    return adapter


async def _collect(events) -> list[StreamChunk]:
    adapter = _make_adapter(events)
    chunks = []
    async for chunk in adapter.stream_dispatch("chat", REDACTED_CONTEXT, "thread_1"):
        chunks.append(chunk)
    return chunks


@pytest.mark.asyncio
async def test_plain_text_yields_text_chunk():
    chunks = await _collect([_ai_event(content="hello")])
    assert chunks == [StreamChunk(type="text", content="hello")]


@pytest.mark.asyncio
async def test_reasoning_content_yields_thinking_before_text():
    chunks = await _collect([_ai_event(content="answer", reasoning_content="my reasoning")])
    assert chunks[0] == StreamChunk(type="thinking", content="my reasoning")
    assert chunks[1] == StreamChunk(type="text", content="answer")


@pytest.mark.asyncio
async def test_anthropic_thinking_block_yields_thinking_then_text():
    content_blocks = [
        {"type": "thinking", "thinking": "deep thought"},
        {"type": "text", "text": "final answer"},
    ]
    chunks = await _collect([_ai_event(content=content_blocks)])
    assert chunks[0] == StreamChunk(type="thinking", content="deep thought")
    assert chunks[1] == StreamChunk(type="text", content="final answer")


@pytest.mark.asyncio
async def test_empty_content_yields_no_chunk():
    chunks = await _collect([_ai_event(content="")])
    assert chunks == []


@pytest.mark.asyncio
async def test_non_ai_event_skipped():
    non_ai = _FakeStreamEvent(type="values", data={"title": "some title"})
    chunks = await _collect([non_ai])
    assert chunks == []


@pytest.mark.asyncio
async def test_multiple_text_events_yield_multiple_chunks():
    chunks = await _collect([
        _ai_event(content="part one"),
        _ai_event(content="part two"),
    ])
    assert chunks == [
        StreamChunk(type="text", content="part one"),
        StreamChunk(type="text", content="part two"),
    ]


@pytest.mark.asyncio
async def test_error_in_produce_raises_deerflow_error():
    adapter = DeerFlowAdapter.__new__(DeerFlowAdapter)
    adapter._timeout = 10
    adapter._family_id = "fam_test"
    adapter._ai_config = {}
    adapter._is_family_mode = True
    adapter._config_path = None  # Required attribute
    client = MagicMock()
    client.stream.side_effect = RuntimeError("upstream failure")
    adapter._client = client
    with pytest.raises(DeerFlowError):
        async for _ in adapter.stream_dispatch("chat", REDACTED_CONTEXT, "thread_1"):
            pass


@pytest.mark.asyncio
async def test_no_think_text_string_prefixes_in_output():
    """Regression: no [THINK] or [TEXT] prefix strings should appear in chunk content."""
    chunks = await _collect([
        _ai_event(content="answer", reasoning_content="reasoning"),
        _ai_event(content=[{"type": "thinking", "thinking": "t"}, {"type": "text", "text": "a"}]),
    ])
    for chunk in chunks:
        assert not chunk.content.startswith("[THINK]")
        assert not chunk.content.startswith("[TEXT]")
