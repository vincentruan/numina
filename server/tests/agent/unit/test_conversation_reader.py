"""Tests for the conversation reader callback (T25 U4)."""

from __future__ import annotations

import json

import pytest
from langchain_core.messages import AIMessage, HumanMessage


class _FakeCheckpointTuple:
    def __init__(
        self,
        *,
        messages: list | None = None,
        family_id: str | None = "fam_1",
    ) -> None:
        self.checkpoint = {
            "channel_values": {"messages": messages or []},
        }
        self.metadata = {"family_id": family_id} if family_id else {}


class _FakeCheckpointer:
    def __init__(self, tuple_: _FakeCheckpointTuple | None) -> None:
        self._tuple = tuple_

    async def aget_tuple(self, config):  # noqa: ANN001
        return self._tuple


def _reader(checkpointer, family_id: str = "fam_1"):
    from apps.agent.services.conversation_reader import build_conversation_reader

    return build_conversation_reader(checkpointer, family_id)


def _msgs(n: int):
    return [HumanMessage(content=f"m{i}") for i in range(n)]


@pytest.mark.asyncio
async def test_valid_thread_returns_paginated_messages() -> None:
    """Valid family thread returns a page of serialized messages."""
    reader = _reader(_FakeCheckpointer(_FakeCheckpointTuple(messages=_msgs(3))))

    raw = await reader(thread_id="t1", limit=10)
    page = json.loads(raw)

    assert "messages" in page
    assert len(page["messages"]) == 3
    assert all(m["type"] == "human" for m in page["messages"])
    assert page["messages"][0]["content"] == "m0"


@pytest.mark.asyncio
async def test_different_family_returns_not_found() -> None:
    """Thread belonging to another family returns a not-found error payload."""
    reader = _reader(
        _FakeCheckpointer(_FakeCheckpointTuple(messages=_msgs(2), family_id="fam_2"))
    )

    raw = await reader(thread_id="t1")
    page = json.loads(raw)

    assert "error" in page
    assert "not found" in page["error"].lower()


@pytest.mark.asyncio
async def test_nonexistent_thread_returns_not_found() -> None:
    """Missing checkpoint returns a not-found error payload."""
    reader = _reader(_FakeCheckpointer(None))

    raw = await reader(thread_id="missing")
    page = json.loads(raw)

    assert "error" in page
    assert "not found" in page["error"].lower()


@pytest.mark.asyncio
async def test_cursor_pagination() -> None:
    """cursor + limit returns the correct page."""
    reader = _reader(_FakeCheckpointer(_FakeCheckpointTuple(messages=_msgs(5))))

    raw = await reader(thread_id="t1", limit=2)
    page1 = json.loads(raw)
    assert len(page1["messages"]) == 2
    assert page1["next_cursor"] == "2"

    raw2 = await reader(thread_id="t1", cursor=page1["next_cursor"], limit=2)
    page2 = json.loads(raw2)
    assert len(page2["messages"]) == 2
    assert page2["messages"][0]["content"] == "m2"
    assert page2["next_cursor"] == "4"

    raw3 = await reader(thread_id="t1", cursor=page2["next_cursor"], limit=2)
    page3 = json.loads(raw3)
    assert len(page3["messages"]) == 1
    assert page3["next_cursor"] is None


@pytest.mark.asyncio
async def test_message_seq_offset_continuation() -> None:
    """message_seq + offset returns a continuation slice of one message."""
    reader = _reader(_FakeCheckpointer(_FakeCheckpointTuple(messages=_msgs(2))))

    raw = await reader(thread_id="t1", message_seq=1, offset=0)
    page = json.loads(raw)

    assert page["message_seq"] == 1
    assert page["offset"] == 0
    assert page["messages"][0]["content"] == "m0"


@pytest.mark.asyncio
async def test_empty_thread_returns_empty_page() -> None:
    """Thread with no messages returns an empty page."""
    reader = _reader(_FakeCheckpointer(_FakeCheckpointTuple(messages=[])))

    raw = await reader(thread_id="t1", limit=10)
    page = json.loads(raw)

    assert page["messages"] == []
    assert page["next_cursor"] is None


@pytest.mark.asyncio
async def test_limit_clamped_to_50() -> None:
    """Limit values above 50 are clamped."""
    reader = _reader(_FakeCheckpointer(_FakeCheckpointTuple(messages=_msgs(60))))

    raw = await reader(thread_id="t1", limit=100)
    page = json.loads(raw)

    assert len(page["messages"]) == 50
    assert page["next_cursor"] == "50"


@pytest.mark.asyncio
async def test_tool_and_system_messages_excluded() -> None:
    """Only HumanMessage and AIMessage are included in the output."""
    from langchain_core.messages import SystemMessage, ToolMessage

    messages = [
        HumanMessage(content="user msg"),
        SystemMessage(content="sys"),
        AIMessage(content="ai reply"),
        ToolMessage(content="tool result", tool_call_id="tc1"),
    ]
    reader = _reader(_FakeCheckpointer(_FakeCheckpointTuple(messages=messages)))

    raw = await reader(thread_id="t1", limit=10)
    page = json.loads(raw)

    types = [m["type"] for m in page["messages"]]
    assert types == ["human", "ai"]


@pytest.mark.asyncio
async def test_checkpointer_exception_returns_error_payload() -> None:
    """Corrupted or unreadable checkpoint returns a JSON error payload."""

    class _BrokenCheckpointer:
        async def aget_tuple(self, config):  # noqa: ANN001
            raise RuntimeError("checkpoint corrupted")

    reader = _reader(_BrokenCheckpointer())

    raw = await reader(thread_id="t1")
    page = json.loads(raw)

    assert "error" in page
    assert "corrupted" in page["error"]


@pytest.mark.asyncio
async def test_message_seq_out_of_range() -> None:
    """message_seq beyond message count returns an error."""
    reader = _reader(_FakeCheckpointer(_FakeCheckpointTuple(messages=_msgs(2))))

    raw = await reader(thread_id="t1", message_seq=10, offset=0)
    page = json.loads(raw)

    assert "error" in page
    assert "out of range" in page["error"]


@pytest.mark.asyncio
async def test_no_family_id_metadata_rejected() -> None:
    """Checkpoint with no family_id metadata is rejected (not found)."""
    tuple_ = _FakeCheckpointTuple(messages=_msgs(1), family_id=None)
    # metadata is {} (no family_id key)
    reader = _reader(_FakeCheckpointer(tuple_))

    raw = await reader(thread_id="t1")
    page = json.loads(raw)

    assert "error" in page
