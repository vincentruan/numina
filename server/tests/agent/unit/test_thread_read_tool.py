"""Tests for the thread_read tool (T25 U6)."""

from __future__ import annotations

import json

import pytest
from langchain_core.messages import HumanMessage

from apps.agent.services.runtime.thread_read_tool import (
    build_thread_read_tool,
)


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


def _msgs(n: int):
    return [HumanMessage(content=f"m{i}") for i in range(n)]


@pytest.mark.asyncio
async def test_reads_messages_for_valid_family_thread() -> None:
    """Thread belonging to the bound family returns paginated messages."""
    checkpointer = _FakeCheckpointer(_FakeCheckpointTuple(messages=_msgs(3)))
    tool = build_thread_read_tool(checkpointer, "fam_1")

    raw = await tool.ainvoke({"thread_id": "t1"})
    page = json.loads(raw)

    assert "messages" in page
    assert len(page["messages"]) == 3
    assert page["messages"][0]["content"] == "m0"


@pytest.mark.asyncio
async def test_rejects_thread_from_another_family() -> None:
    """Thread belonging to a different family returns a not-found error."""
    checkpointer = _FakeCheckpointer(
        _FakeCheckpointTuple(messages=_msgs(2), family_id="fam_2")
    )
    tool = build_thread_read_tool(checkpointer, "fam_1")

    raw = await tool.ainvoke({"thread_id": "t1"})
    page = json.loads(raw)

    assert "error" in page


@pytest.mark.asyncio
async def test_missing_thread_returns_not_found() -> None:
    """Non-existent thread returns a not-found error."""
    checkpointer = _FakeCheckpointer(None)
    tool = build_thread_read_tool(checkpointer, "fam_1")

    raw = await tool.ainvoke({"thread_id": "missing"})
    page = json.loads(raw)

    assert "error" in page


@pytest.mark.asyncio
async def test_cursor_pagination() -> None:
    """Cursor returned from one call continues the next page."""
    checkpointer = _FakeCheckpointer(_FakeCheckpointTuple(messages=_msgs(5)))
    tool = build_thread_read_tool(checkpointer, "fam_1")

    page1 = json.loads(await tool.ainvoke({"thread_id": "t1", "limit": 2}))
    assert page1["next_cursor"] == "2"
    assert len(page1["messages"]) == 2

    page2 = json.loads(
        await tool.ainvoke({"thread_id": "t1", "limit": 2, "cursor": page1["next_cursor"]})
    )
    assert page2["messages"][0]["content"] == "m2"


@pytest.mark.asyncio
async def test_limit_clamped_to_50() -> None:
    """Limit values above 50 are clamped by the underlying reader."""
    checkpointer = _FakeCheckpointer(_FakeCheckpointTuple(messages=_msgs(60)))
    tool = build_thread_read_tool(checkpointer, "fam_1")

    page = json.loads(await tool.ainvoke({"thread_id": "t1", "limit": 100}))
    assert len(page["messages"]) == 50


@pytest.mark.asyncio
async def test_missing_thread_id_returns_error() -> None:
    """Missing thread_id returns an error payload without raising."""
    checkpointer = _FakeCheckpointer(_FakeCheckpointTuple(messages=_msgs(1)))
    tool = build_thread_read_tool(checkpointer, "fam_1")

    raw = await tool.ainvoke({"thread_id": ""})
    page = json.loads(raw)

    assert "error" in page


@pytest.mark.asyncio
async def test_tool_has_expected_name_and_family_binding() -> None:
    """The factory produces a tool named thread_read bound to family_id."""
    tool = build_thread_read_tool(_FakeCheckpointer(None), "fam_bound")
    assert tool.name == "thread_read"

    checkpointer = _FakeCheckpointer(_FakeCheckpointTuple(messages=_msgs(1), family_id="fam_bound"))
    tool2 = build_thread_read_tool(checkpointer, "fam_bound")
    raw = await tool2.ainvoke({"thread_id": "t1"})
    page = json.loads(raw)
    assert "error" not in page


@pytest.mark.asyncio
async def test_checkpointer_failure_returns_error_payload() -> None:
    """Corrupted checkpointer state returns a JSON error payload."""

    class _BrokenCheckpointer:
        async def aget_tuple(self, config):  # noqa: ANN001
            raise RuntimeError("checkpoint corrupted")

    tool = build_thread_read_tool(_BrokenCheckpointer(), "fam_1")

    raw = await tool.ainvoke({"thread_id": "t1"})
    page = json.loads(raw)

    assert "error" in page
