"""Tests for structured agent stream events."""

import json

from services.stream_events import EventStreamBuilder


def test_phase_event_serializes_as_one_ndjson_line():
    builder = EventStreamBuilder(capability_id="chat", task_id="task-1")

    line = builder.phase("connecting", {"model": "qwen"}).to_ndjson()

    assert line.endswith("\n")
    data = json.loads(line)
    assert data["id"] == "task-1-0001"
    assert data["type"] == "phase.connecting"
    assert data["capability_id"] == "chat"
    assert data["task_id"] == "task-1"
    assert data["phase"] == "connecting"
    assert data["metadata"] == {"model": "qwen"}


def test_token_event_preserves_chinese_and_thinking_flag():
    builder = EventStreamBuilder(capability_id="chat", task_id="task-1")

    data = json.loads(builder.token("净资产分析", is_thinking=False).to_ndjson())

    assert data["type"] == "token.stream"
    assert data["token"] == "净资产分析"
    assert data["is_thinking"] is False


def test_tool_events_have_stable_tool_id():
    builder = EventStreamBuilder(capability_id="chat", task_id="task-1")

    call = json.loads(
        builder.tool_call(
            tool_name="asset_search",
            arguments={"query": "房产"},
            display_name="资产查询",
            icon="search",
        ).to_ndjson()
    )

    assert call["type"] == "tool.call"
    assert call["tool"]["id"] == "task-1-tool-0001"
    assert call["tool"]["name"] == "asset_search"
    assert call["tool"]["display_name"] == "资产查询"
    assert call["tool"]["arguments"] == {"query": "房产"}
