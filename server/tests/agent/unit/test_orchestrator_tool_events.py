"""Unit tests for _chunk_to_event_lines — new StreamChunk type branches.

Covers:
- tool_call chunk → tool.call NDJSON event
- tool_call with internal=True → tool.call with tool_type="internal", display_name="规划步骤", icon="🗂️"
- tool_result chunk → tool.result NDJSON event, success=True
- tool_result references correct backend_id from prior tool_call mapping
- plan_update chunk → plan.update NDJSON event with normalized todos
- plan_update todos normalized to {id: "plan-N", content, status}
- tool_progress method produces valid NDJSON with tool_id and message
- thinking/text chunks still produce phase + token events (regression)
- Empty/null data in new chunk types → graceful skip, no crash
"""

import json

import pytest

from apps.agent.services.deerflow_adapter.adapter import StreamChunk
from apps.agent.services.orchestrator import Orchestrator
from apps.agent.services.stream_events import EventStreamBuilder


# ── helpers ───────────────────────────────────────────────────────────────────


async def _collect(orchestrator, chunk, tool_call_id_map=None):
    """Collect all NDJSON lines from _chunk_to_event_lines for a single chunk."""
    builder = EventStreamBuilder(capability_id="chat", task_id="t-1")
    answer_parts: list[str] = []
    if tool_call_id_map is None:
        tool_call_id_map = {}
    lines = []
    async for line in orchestrator._chunk_to_event_lines(
        builder, chunk, answer_parts, tool_call_id_map=tool_call_id_map
    ):
        lines.append(json.loads(line))
    return lines, answer_parts, builder


@pytest.fixture
def orch():
    return Orchestrator()


# ── tool_call ─────────────────────────────────────────────────────────────────


async def test_tool_call_chunk_emits_tool_call_event(orch):
    chunk = StreamChunk(
        type="tool_call",
        content="",
        data={
            "tool_call_id": "abc-123",
            "tool_name": "search_assets",
            "tool_type": "data",
            "display_name": "资产查询",
            "icon": "search",
            "args": {"query": "房产"},
            "internal": False,
        },
    )
    lines, _, _ = await _collect(orch, chunk)

    assert len(lines) == 1
    event = lines[0]
    assert event["type"] == "tool.call"
    tool = event["tool"]
    assert tool["name"] == "search_assets"
    assert tool["tool_type"] == "data"
    assert tool["display_name"] == "资产查询"
    assert tool["icon"] == "search"
    assert tool["arguments"] == {"query": "房产"}


async def test_tool_call_internal_uses_fixed_metadata(orch):
    chunk = StreamChunk(
        type="tool_call",
        content="",
        data={
            "tool_call_id": "write-1",
            "tool_name": "write_todos",
            "tool_type": "internal",
            "display_name": "write_todos",
            "icon": "todo",
            "args": {"todos": ["步骤1"]},
            "internal": True,
        },
    )
    lines, _, _ = await _collect(orch, chunk)

    assert len(lines) == 1
    tool = lines[0]["tool"]
    assert tool["tool_type"] == "internal"
    assert tool["display_name"] == "规划步骤"
    assert tool["icon"] == "🗂️"


async def test_tool_call_id_recorded_in_map(orch):
    tool_call_id_map: dict[str, str] = {}
    chunk = StreamChunk(
        type="tool_call",
        content="",
        data={
            "tool_call_id": "provider-id-1",
            "tool_name": "search",
            "args": {},
            "internal": False,
        },
    )
    await _collect(orch, chunk, tool_call_id_map=tool_call_id_map)

    assert "provider-id-1" in tool_call_id_map
    # backend id follows task-id-tool-NNNN pattern
    assert tool_call_id_map["provider-id-1"].startswith("t-1-tool-")


async def test_tool_call_empty_data_no_crash(orch):
    chunk = StreamChunk(type="tool_call", content="", data=None)
    lines, _, _ = await _collect(orch, chunk)
    # Should emit a tool.call with empty/default values, not crash
    assert len(lines) == 1
    assert lines[0]["type"] == "tool.call"


# ── tool_result ───────────────────────────────────────────────────────────────


async def test_tool_result_emits_tool_result_event(orch):
    tool_call_id_map = {"provider-id-1": "t-1-tool-0001"}
    chunk = StreamChunk(
        type="tool_result",
        content="",
        data={
            "tool_call_id": "provider-id-1",
            "tool_name": "search",
            "content": {"assets": []},
        },
    )
    lines, _, _ = await _collect(orch, chunk, tool_call_id_map=tool_call_id_map)

    assert len(lines) == 1
    event = lines[0]
    assert event["type"] == "tool.result"
    assert event["tool_id"] == "t-1-tool-0001"
    assert event["result"]["success"] is True


async def test_tool_result_uses_backend_id_from_map(orch):
    tool_call_id_map = {"prov-42": "t-1-tool-0042"}
    chunk = StreamChunk(
        type="tool_result",
        content="",
        data={"tool_call_id": "prov-42", "content": "ok"},
    )
    lines, _, _ = await _collect(orch, chunk, tool_call_id_map=tool_call_id_map)

    assert lines[0]["tool_id"] == "t-1-tool-0042"


async def test_tool_result_falls_back_to_provider_id_when_not_in_map(orch):
    chunk = StreamChunk(
        type="tool_result",
        content="",
        data={"tool_call_id": "unknown-id", "content": None},
    )
    lines, _, _ = await _collect(orch, chunk)

    assert lines[0]["tool_id"] == "unknown-id"


async def test_tool_result_empty_data_no_crash(orch):
    chunk = StreamChunk(type="tool_result", content="", data=None)
    lines, _, _ = await _collect(orch, chunk)
    assert len(lines) == 1
    assert lines[0]["type"] == "tool.result"


# ── plan_update ───────────────────────────────────────────────────────────────


async def test_plan_update_emits_plan_update_event(orch):
    chunk = StreamChunk(
        type="plan_update",
        content="",
        data={
            "todos": [
                {"content": "查询资产", "status": "pending"},
                {"content": "生成报告", "status": "done"},
            ]
        },
    )
    lines, _, _ = await _collect(orch, chunk)

    assert len(lines) == 1
    event = lines[0]
    assert event["type"] == "plan.update"
    todos = event["todos"]
    assert len(todos) == 2
    assert todos[0] == {"id": "plan-0", "content": "查询资产", "status": "pending"}
    assert todos[1] == {"id": "plan-1", "content": "生成报告", "status": "done"}


async def test_plan_update_null_todos_no_output(orch):
    chunk = StreamChunk(type="plan_update", content="", data={"todos": None})
    lines, _, _ = await _collect(orch, chunk)
    assert lines == []


async def test_plan_update_empty_data_no_crash(orch):
    chunk = StreamChunk(type="plan_update", content="", data=None)
    lines, _, _ = await _collect(orch, chunk)
    assert lines == []


async def test_plan_update_empty_todos_list(orch):
    chunk = StreamChunk(type="plan_update", content="", data={"todos": []})
    lines, _, _ = await _collect(orch, chunk)
    assert len(lines) == 1
    assert lines[0]["todos"] == []


# ── tool_progress (EventStreamBuilder method) ─────────────────────────────────


def test_tool_progress_produces_valid_ndjson():
    builder = EventStreamBuilder(capability_id="chat", task_id="task-x")
    line = builder.tool_progress(tool_id="task-x-tool-0001", message="正在搜索...").to_ndjson()

    assert line.endswith("\n")
    data = json.loads(line)
    assert data["type"] == "tool.progress"
    assert data["tool_id"] == "task-x-tool-0001"
    assert data["message"] == "正在搜索..."


def test_tool_progress_increments_event_id():
    builder = EventStreamBuilder(capability_id="chat", task_id="task-x")
    builder.phase("connecting")  # consume event id 1
    line = builder.tool_progress(tool_id="t", message="msg").to_ndjson()
    data = json.loads(line)
    assert data["id"] == "task-x-0002"


# ── plan_update (EventStreamBuilder method) ───────────────────────────────────


def test_plan_update_normalizes_todo_ids():
    builder = EventStreamBuilder(capability_id="chat", task_id="task-x")
    event = builder.plan_update([
        {"content": "步骤A", "status": "pending"},
        {"content": "步骤B"},
    ])
    data = event.to_dict()
    assert data["type"] == "plan.update"
    assert data["todos"][0]["id"] == "plan-0"
    assert data["todos"][1]["id"] == "plan-1"
    assert data["todos"][1]["status"] == "pending"  # default


def test_plan_update_empty_list():
    builder = EventStreamBuilder(capability_id="chat", task_id="task-x")
    event = builder.plan_update([])
    assert event.to_dict()["todos"] == []


# ── regression: thinking / text still work ────────────────────────────────────


async def test_thinking_chunk_produces_phase_and_token(orch):
    chunk = StreamChunk(type="thinking", content="深度思考中…")
    lines, _, _ = await _collect(orch, chunk)

    assert len(lines) == 2
    assert lines[0]["type"] == "phase.thinking"
    assert lines[1]["type"] == "token.stream"
    assert lines[1]["is_thinking"] is True
    assert lines[1]["token"] == "深度思考中…"


async def test_text_chunk_produces_phase_and_token(orch):
    chunk = StreamChunk(type="text", content="这是回答")
    lines, answer_parts, _ = await _collect(orch, chunk)

    assert len(lines) == 2
    assert lines[0]["type"] == "phase.answering"
    assert lines[1]["type"] == "token.stream"
    assert lines[1]["is_thinking"] is False
    assert lines[1]["token"] == "这是回答"
    assert answer_parts == ["这是回答"]


async def test_text_chunk_empty_content_no_output(orch):
    chunk = StreamChunk(type="text", content="")
    lines, answer_parts, _ = await _collect(orch, chunk)

    assert lines == []
    assert answer_parts == []
