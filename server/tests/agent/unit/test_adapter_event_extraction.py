"""Unit tests for U2: StreamChunk extended types + _process_event() extraction branches.

Covers:
- AI message with tool_calls → StreamChunk(type="tool_call") per call
- AI message with write_todos tool call → internal=True in data
- Tool message (type="tool") → StreamChunk(type="tool_result")
- Values event with todos → StreamChunk(type="plan_update")
- Values event without todos → no chunk emitted
- Repeated values events with same todos → still emits (diffing is frontend's job)
- Existing thinking/text extraction unchanged (regression)
- messages-tuple with type not "ai" or "tool" → skipped
"""

from dataclasses import dataclass
from typing import Any
from unittest.mock import MagicMock

import pytest

from apps.agent.services.deerflow_adapter.adapter import (
    DeerFlowAdapter,
    StreamChunk,
)
from tests.agent.golden.fixtures import REDACTED_CONTEXT

# ── Fake event helpers ────────────────────────────────────────────────────────


@dataclass
class _FakeStreamEvent:
    type: str
    data: Any


def _ai_event(
    content=None,
    reasoning_content=None,
    tool_calls=None,
) -> _FakeStreamEvent:
    data: dict[str, Any] = {"type": "ai"}
    if content is not None:
        data["content"] = content
    if reasoning_content is not None:
        data["additional_kwargs"] = {"reasoning_content": reasoning_content}
    if tool_calls is not None:
        data["tool_calls"] = tool_calls
    return _FakeStreamEvent(type="messages-tuple", data=data)


def _tool_event(
    tool_call_id: str = "call-1",
    tool_name: str = "get_assets",
    content: Any = '{"balance": 100}',
) -> _FakeStreamEvent:
    return _FakeStreamEvent(
        type="messages-tuple",
        data={
            "type": "tool",
            "tool_call_id": tool_call_id,
            "name": tool_name,
            "content": content,
        },
    )


def _values_event(data: dict) -> _FakeStreamEvent:
    return _FakeStreamEvent(type="values", data=data)


# ── Adapter factory ───────────────────────────────────────────────────────────


def _make_adapter(events) -> DeerFlowAdapter:
    adapter = DeerFlowAdapter.__new__(DeerFlowAdapter)
    adapter._timeout = 10
    adapter._family_id = "fam_test"
    adapter._ai_config = {}
    adapter._is_family_mode = True
    adapter._config_path = None
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


# ── StreamChunk shape ─────────────────────────────────────────────────────────


def test_stream_chunk_has_data_field():
    """StreamChunk accepts an optional data dict field."""
    chunk = StreamChunk(type="tool_call", content="", data={"key": "value"})
    assert chunk.data == {"key": "value"}


def test_stream_chunk_data_defaults_to_none():
    """StreamChunk.data defaults to None for backward compatibility."""
    chunk = StreamChunk(type="text", content="hello")
    assert chunk.data is None


# ── tool_call extraction ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_ai_message_with_tool_calls_emits_tool_call_chunks():
    """AI message with tool_calls list emits one StreamChunk(type='tool_call') per call."""
    tool_calls = [
        {"name": "get_assets", "args": {"family_id": "f1"}, "id": "call-1"},
        {"name": "get_liabilities", "args": {}, "id": "call-2"},
    ]
    chunks = await _collect([_ai_event(tool_calls=tool_calls)])
    tool_call_chunks = [c for c in chunks if c.type == "tool_call"]
    assert len(tool_call_chunks) == 2
    assert tool_call_chunks[0].data["tool_name"] == "get_assets"
    assert tool_call_chunks[0].data["tool_call_id"] == "call-1"
    assert tool_call_chunks[1].data["tool_name"] == "get_liabilities"
    assert tool_call_chunks[1].data["tool_call_id"] == "call-2"


@pytest.mark.asyncio
async def test_tool_call_chunk_has_empty_content():
    """Tool call chunk has empty string content (data carries the payload)."""
    tool_calls = [{"name": "get_assets", "args": {}, "id": "c1"}]
    chunks = await _collect([_ai_event(tool_calls=tool_calls)])
    assert chunks[0].content == ""


@pytest.mark.asyncio
async def test_tool_call_chunk_includes_tool_metadata():
    """Tool call chunk data includes tool_type, display_name, icon from registry."""
    tool_calls = [{"name": "get_assets", "args": {}, "id": "c1"}]
    chunks = await _collect([_ai_event(tool_calls=tool_calls)])
    data = chunks[0].data
    # U7: get_assets is now an MCP base-name tool in the data_collect category.
    assert data["tool_type"] == "data_collect"
    assert data["display_name"] == "查询资产数据"
    assert data["icon"] == "💰"


@pytest.mark.asyncio
async def test_tool_call_chunk_includes_args():
    """Tool call chunk data carries the args dict."""
    tool_calls = [{"name": "get_assets", "args": {"family_id": "f99"}, "id": "c1"}]
    chunks = await _collect([_ai_event(tool_calls=tool_calls)])
    assert chunks[0].data["args"] == {"family_id": "f99"}


@pytest.mark.asyncio
async def test_write_todos_tool_call_marked_internal():
    """write_todos tool call is marked with internal=True in chunk data."""
    tool_calls = [{"name": "write_todos", "args": {"todos": ["task 1"]}, "id": "c-wt"}]
    chunks = await _collect([_ai_event(tool_calls=tool_calls)])
    assert len(chunks) == 1
    assert chunks[0].type == "tool_call"
    assert chunks[0].data["internal"] is True


@pytest.mark.asyncio
async def test_regular_tool_call_not_marked_internal():
    """Regular tool calls have internal=False in chunk data."""
    tool_calls = [{"name": "get_assets", "args": {}, "id": "c2"}]
    chunks = await _collect([_ai_event(tool_calls=tool_calls)])
    assert chunks[0].data["internal"] is False


@pytest.mark.asyncio
async def test_ai_message_with_tool_calls_does_not_emit_text_chunk():
    """When tool_calls are present, no text/thinking chunks are emitted for that message."""
    tool_calls = [{"name": "get_assets", "args": {}, "id": "c1"}]
    # Even if content is also present, tool_calls branch returns early
    chunks = await _collect([_ai_event(content="some text", tool_calls=tool_calls)])
    text_chunks = [c for c in chunks if c.type == "text"]
    assert len(text_chunks) == 0


@pytest.mark.asyncio
async def test_unknown_tool_falls_back_to_unknown_metadata():
    """Tool not in registry uses fallback metadata (type='unknown', icon='tool')."""
    tool_calls = [{"name": "my_custom_tool", "args": {}, "id": "cx"}]
    chunks = await _collect([_ai_event(tool_calls=tool_calls)])
    data = chunks[0].data
    assert data["tool_type"] == "unknown"
    assert data["icon"] == "tool"
    assert data["display_name"] == "my_custom_tool"


# ── tool_result extraction ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_tool_message_emits_tool_result_chunk():
    """Tool message (type='tool') emits StreamChunk(type='tool_result')."""
    chunks = await _collect([_tool_event(tool_call_id="call-1", tool_name="get_assets")])
    assert len(chunks) == 1
    assert chunks[0].type == "tool_result"


@pytest.mark.asyncio
async def test_tool_result_chunk_has_empty_content():
    """Tool result chunk content is empty string; payload is in data."""
    chunks = await _collect([_tool_event()])
    assert chunks[0].content == ""


@pytest.mark.asyncio
async def test_tool_result_chunk_data_has_correct_fields():
    """Tool result chunk data includes tool_call_id, tool_name, and content."""
    chunks = await _collect([
        _tool_event(tool_call_id="call-42", tool_name="get_liabilities", content='{"items": []}')
    ])
    data = chunks[0].data
    assert data["tool_call_id"] == "call-42"
    assert data["tool_name"] == "get_liabilities"
    assert data["content"] == '{"items": []}'


# ── plan_update extraction ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_values_event_with_todos_emits_plan_update():
    """Values event with 'todos' key emits StreamChunk(type='plan_update')."""
    todos = [{"id": 1, "title": "Step 1", "done": False}]
    chunks = await _collect([_values_event({"todos": todos})])
    assert len(chunks) == 1
    assert chunks[0].type == "plan_update"


@pytest.mark.asyncio
async def test_plan_update_chunk_has_empty_content():
    """Plan update chunk content is empty string; payload is in data."""
    chunks = await _collect([_values_event({"todos": []})])
    assert chunks[0].content == ""


@pytest.mark.asyncio
async def test_plan_update_chunk_data_has_todos():
    """Plan update chunk data contains the todos list."""
    todos = [{"id": 1, "title": "Analyze assets", "done": False}]
    chunks = await _collect([_values_event({"todos": todos})])
    assert chunks[0].data["todos"] == todos


@pytest.mark.asyncio
async def test_values_event_without_todos_emits_nothing():
    """Values event without 'todos' key is silently skipped — no chunk emitted."""
    chunks = await _collect([_values_event({"title": "some title", "other_key": 42})])
    assert chunks == []


@pytest.mark.asyncio
async def test_values_event_with_empty_todos_list_emits_plan_update():
    """Values event with todos=[] still emits a plan_update (empty list is valid)."""
    chunks = await _collect([_values_event({"todos": []})])
    assert len(chunks) == 1
    assert chunks[0].type == "plan_update"
    assert chunks[0].data["todos"] == []


@pytest.mark.asyncio
async def test_repeated_values_events_with_same_todos_each_emit_chunk():
    """Repeated values events with same todos both emit plan_update chunks.

    Deduplication/diffing is the frontend's responsibility — the adapter emits every event.
    """
    todos = [{"id": 1, "title": "task", "done": False}]
    chunks = await _collect([
        _values_event({"todos": todos}),
        _values_event({"todos": todos}),
    ])
    plan_chunks = [c for c in chunks if c.type == "plan_update"]
    assert len(plan_chunks) == 2


# ── regression: existing thinking/text unchanged ──────────────────────────────


@pytest.mark.asyncio
async def test_ai_message_plain_text_still_yields_text_chunk():
    """Regression: plain AI text message still yields StreamChunk(type='text')."""
    chunks = await _collect([_ai_event(content="The answer is 42.")])
    assert chunks == [StreamChunk(type="text", content="The answer is 42.")]


@pytest.mark.asyncio
async def test_ai_message_reasoning_still_yields_thinking_chunk():
    """Regression: reasoning_content on AI message still yields StreamChunk(type='thinking')."""
    chunks = await _collect([_ai_event(content="answer", reasoning_content="my reasoning")])
    assert chunks[0] == StreamChunk(type="thinking", content="my reasoning")
    assert chunks[1] == StreamChunk(type="text", content="answer")


@pytest.mark.asyncio
async def test_anthropic_thinking_block_still_yields_thinking_then_text():
    """Regression: Anthropic content-block thinking still yields thinking then text."""
    content_blocks = [
        {"type": "thinking", "thinking": "deep thought"},
        {"type": "text", "text": "final answer"},
    ]
    chunks = await _collect([_ai_event(content=content_blocks)])
    assert chunks[0] == StreamChunk(type="thinking", content="deep thought")
    assert chunks[1] == StreamChunk(type="text", content="final answer")


# ── skipped event types ───────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_messages_tuple_with_human_type_is_skipped():
    """messages-tuple event with type='human' is skipped — no chunk emitted."""
    event = _FakeStreamEvent(
        type="messages-tuple",
        data={"type": "human", "content": "what is my net worth?"},
    )
    chunks = await _collect([event])
    assert chunks == []


@pytest.mark.asyncio
async def test_messages_tuple_with_system_type_is_skipped():
    """messages-tuple event with type='system' is skipped — no chunk emitted."""
    event = _FakeStreamEvent(
        type="messages-tuple",
        data={"type": "system", "content": "You are a helpful assistant."},
    )
    chunks = await _collect([event])
    assert chunks == []


@pytest.mark.asyncio
async def test_unrecognized_event_type_is_skipped():
    """Events with an unrecognized type field are silently skipped."""
    event = _FakeStreamEvent(type="unknown_event_type", data={"foo": "bar"})
    chunks = await _collect([event])
    assert chunks == []


@pytest.mark.asyncio
async def test_mixed_event_sequence_yields_correct_chunks():
    """A realistic sequence of events yields chunks in correct order."""
    todos = [{"id": 1, "title": "Step 1", "done": False}]
    tool_calls = [{"name": "get_assets", "args": {}, "id": "call-x"}]
    events = [
        _values_event({"todos": todos}),
        _ai_event(tool_calls=tool_calls),
        _tool_event(tool_call_id="call-x", tool_name="get_assets", content='{"items": []}'),
        _ai_event(content="Here is the analysis."),
    ]
    chunks = await _collect(events)
    types = [c.type for c in chunks]
    assert types == ["plan_update", "tool_call", "tool_result", "text"]
