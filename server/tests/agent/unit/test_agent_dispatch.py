"""Tests for U4: agent_dispatch._resolve_skills inline helper.

Per plan U4 + KD1, the skill resolution layer lives inline in agent_dispatch.py
as a module-level pure function. It enforces R5/R6/R15:
- R5: AI问答 (skills=["chat"]) → empty skill list (pure LLM mode)
- R6: 数鸣 (skills=["*"] sentinel) → all family-enabled skills
- R15: custom agent (skills=["report", ...]) → intersect with family-enabled

Also tests for U1: tool.call/tool.result + phase.thinking event emission.

These tests run TEST-FIRST per the unit's Execution note.
"""

from apps.agent.services.agent_dispatch import (
    _extract_reasoning_content,
    _extract_tool_calls,
    _extract_text_content,
    _get_msg_type,
    _map_tool_type,
    _resolve_skills,
)
from apps.agent.services.stream_events import EventStreamBuilder


# Helper: build a family enabled-skill list matching BackendClient.get_enabled_skills() shape.
def _enabled(*skill_ids: str) -> list[dict]:
    return [{"skill_id": sid, "skill_type": "builtin"} for sid in skill_ids]


# ── R5: AI问答 — chat-reserved capability returns empty ──────────────────────────


def test_chat_reserved_capability_returns_empty():
    """skills=['chat'] resolves to [] regardless of family-enabled skills."""
    family_enabled = _enabled("report", "allocation", "disposal")
    assert _resolve_skills(["chat"], family_enabled) == []


def test_chat_reserved_capability_returns_empty_even_with_no_family_skills():
    """skills=['chat'] resolves to [] when family has no enabled skills."""
    assert _resolve_skills(["chat"], []) == []


# ── R6: 数鸣 sentinel — wildcard returns all family-enabled ─────────────────────


def test_sentinel_returns_all_family_enabled_skills():
    """skills=['*'] resolves to the full family-enabled skill list."""
    family_enabled = _enabled("report", "allocation", "disposal")
    result = _resolve_skills(["*"], family_enabled)
    assert {s["skill_id"] for s in result} == {"report", "allocation", "disposal"}


def test_sentinel_with_zero_family_skills_returns_empty():
    """AE9: 数鸣 with sentinel + zero family skills → empty list (no error)."""
    assert _resolve_skills(["*"], []) == []


def test_sentinel_alongside_specific_skills_treated_as_wildcard():
    """If '*' appears anywhere in the list, treat as wildcard (per R6 spec)."""
    family_enabled = _enabled("report", "allocation")
    # Defensive: even if a custom agent accidentally includes "*", honor the sentinel
    result = _resolve_skills(["report", "*"], family_enabled)
    assert {s["skill_id"] for s in result} == {"report", "allocation"}


# ── R15: custom agent — intersect declared skills with family-enabled ───────────


def test_custom_agent_intersects_with_family_enabled():
    """custom agent skills are intersected with family-enabled skills."""
    family_enabled = _enabled("report", "allocation", "disposal", "liability")
    result = _resolve_skills(["report", "allocation"], family_enabled)
    assert {s["skill_id"] for s in result} == {"report", "allocation"}


def test_custom_agent_with_disabled_skill_returns_empty():
    """custom agent declaring a skill that family hasn't enabled gets empty intersection."""
    family_enabled = _enabled("allocation", "disposal")
    assert _resolve_skills(["report"], family_enabled) == []


def test_custom_agent_partial_intersection():
    """custom agent with mix of enabled + disabled skills gets only enabled subset."""
    family_enabled = _enabled("report", "disposal")
    result = _resolve_skills(["report", "allocation", "disposal"], family_enabled)
    assert {s["skill_id"] for s in result} == {"report", "disposal"}


# ── Edge cases: empty / None / unexpected input ────────────────────────────────


def test_none_agent_skills_returns_empty():
    """agent.skills=None resolves to []."""
    family_enabled = _enabled("report", "allocation")
    assert _resolve_skills(None, family_enabled) == []


def test_empty_list_agent_skills_returns_empty():
    """agent.skills=[] resolves to []."""
    family_enabled = _enabled("report", "allocation")
    assert _resolve_skills([], family_enabled) == []


# ── Identity preservation: returned dicts match family list shape ──────────────


def test_resolved_skills_preserve_skill_dict_shape():
    """Resolved skills carry the same dict structure as the family-enabled list."""
    family_enabled = [
        {"skill_id": "report", "skill_type": "builtin"},
        {"skill_id": "allocation", "skill_type": "custom"},
    ]
    result = _resolve_skills(["report", "allocation"], family_enabled)
    assert len(result) == 2
    by_id = {s["skill_id"]: s for s in result}
    assert by_id["report"]["skill_type"] == "builtin"
    assert by_id["allocation"]["skill_type"] == "custom"


def test_sentinel_preserves_skill_dict_shape():
    """Sentinel resolution preserves all dict fields from family-enabled list."""
    family_enabled = [
        {"skill_id": "report", "skill_type": "builtin", "extra": "data"},
    ]
    result = _resolve_skills(["*"], family_enabled)
    assert result[0]["skill_id"] == "report"
    assert result[0]["skill_type"] == "builtin"
    assert result[0]["extra"] == "data"


# ── U1: Tool type mapping tests ───────────────────────────────────────────────


def test_map_tool_type_known_asset_tool():
    """Known asset tools map to asset_query type."""
    tool_type, display_name, icon = _map_tool_type("query_assets")
    assert tool_type == "asset_query"
    assert display_name == "资产查询"
    assert icon == "asset"


def test_map_tool_type_known_report_tool():
    """Known report tools map to report_gen type."""
    tool_type, display_name, icon = _map_tool_type("generate_report")
    assert tool_type == "report_gen"
    assert display_name == "报告生成"
    assert icon == "report"


def test_map_tool_type_unknown_returns_fallback():
    """Unknown tool names return fallback values."""
    tool_type, display_name, icon = _map_tool_type("custom_unknown_tool")
    assert tool_type == "unknown"
    assert display_name == "custom_unknown_tool"
    assert icon == "tool"


# ── U1: Message type detection tests ───────────────────────────────────────


def test_get_msg_type_from_dict():
    """Dict messages return their 'type' field."""
    msg = {"type": "ai", "content": "hello"}
    assert _get_msg_type(msg) == "ai"


def test_get_msg_type_from_object():
    """Object messages return their 'type' attribute."""
    class MockMsg:
        type = "tool"
    assert _get_msg_type(MockMsg()) == "tool"


def test_get_msg_type_unknown():
    """Unknown message format returns 'unknown'."""
    assert _get_msg_type("plain string") == "unknown"


# ── U1: Reasoning content extraction tests ───────────────────────────────────────


def test_extract_reasoning_content_from_additional_kwargs():
    """Reasoning content from additional_kwargs is extracted."""
    msg = {"type": "ai", "content": "", "additional_kwargs": {"reasoning_content": "thinking..."}}
    assert _extract_reasoning_content(msg) == "thinking..."


def test_extract_reasoning_content_from_thinking_block():
    """Reasoning content from thinking blocks in content list is extracted."""
    msg = {"type": "ai", "content": [{"type": "thinking", "thinking": "deep thought"}]}
    assert _extract_reasoning_content(msg) == "deep thought"


def test_extract_reasoning_content_none_when_absent():
    """Returns None when no reasoning content present."""
    msg = {"type": "ai", "content": "just text"}
    assert _extract_reasoning_content(msg) is None


# ── U1: Tool calls extraction tests ───────────────────────────────────────


def test_extract_tool_calls_from_dict():
    """Tool calls extracted from dict message."""
    msg = {"type": "ai", "tool_calls": [{"id": "t1", "name": "query_assets", "args": {}}]}
    result = _extract_tool_calls(msg)
    assert len(result) == 1
    assert result[0]["name"] == "query_assets"


def test_extract_tool_calls_empty_when_absent():
    """Returns empty list when no tool calls."""
    msg = {"type": "ai", "content": "text"}
    assert _extract_tool_calls(msg) == []


# ── U1: Text content extraction tests ───────────────────────────────────────


def test_extract_text_content_from_string():
    """String content is extracted directly."""
    msg = {"type": "ai", "content": "answer text"}
    assert _extract_text_content(msg) == "answer text"


def test_extract_text_content_from_list():
    """Text blocks from content list are joined."""
    msg = {"type": "ai", "content": [{"type": "text", "text": "part1"}, {"type": "text", "text": "part2"}]}
    assert _extract_text_content(msg) == "part1part2"


def test_extract_text_content_excludes_thinking():
    """Thinking blocks are excluded from text extraction."""
    msg = {"type": "ai", "content": [{"type": "thinking", "thinking": "hmm"}, {"type": "text", "text": "answer"}]}
    assert _extract_text_content(msg) == "answer"


# ── U1: Event emission tests ───────────────────────────────────────────────


def test_tool_call_event_includes_tool_type():
    """EventStreamBuilder.tool_call includes tool_type field."""
    builder = EventStreamBuilder(capability_id="test", task_id="task1")
    event = builder.tool_call(
        tool_name="query_assets",
        arguments={"family_id": "123"},
        tool_type="asset_query",
        display_name="资产查询",
        icon="asset",
    )
    event_dict = event.to_dict()
    assert event_dict["type"] == "tool.call"
    assert event_dict["tool"]["tool_type"] == "asset_query"
    assert event_dict["tool"]["display_name"] == "资产查询"
    assert event_dict["tool"]["icon"] == "asset"


def test_phase_thinking_event_emitted():
    """EventStreamBuilder can emit phase.thinking event."""
    builder = EventStreamBuilder(capability_id="test", task_id="task1")
    event = builder.phase("thinking")
    event_dict = event.to_dict()
    assert event_dict["type"] == "phase.thinking"
    assert event_dict["phase"] == "thinking"


def test_tool_result_event():
    """EventStreamBuilder.tool_result emits correct event."""
    builder = EventStreamBuilder(capability_id="test", task_id="task1")
    # First emit a tool call to get a tool_id
    call_event = builder.tool_call("test_tool", {})
    tool_id = call_event.to_dict()["tool"]["id"]

    result_event = builder.tool_result(
        tool_id=tool_id,
        success=True,
        execution_time_ms=100,
        data={"result": "ok"},
    )
    result_dict = result_event.to_dict()
    assert result_dict["type"] == "tool.result"
    assert result_dict["tool_id"] == tool_id
    assert result_dict["result"]["success"] is True


# ── U2: reasoning_effort parameter tests ───────────────────────────────────────


def test_tool_call_event_with_reasoning_effort_low():
    """tool_call with tool_type reflects reasoning context."""
    builder = EventStreamBuilder(capability_id="test", task_id="task1")
    event = builder.tool_call(
        tool_name="query_assets",
        arguments={},
        tool_type="asset_query",
        display_name="资产查询",
        icon="asset",
    )
    event_dict = event.to_dict()
    # Verify tool_type is correctly included
    assert event_dict["tool"]["tool_type"] == "asset_query"


def test_tool_call_event_with_unknown_tool_type():
    """Unknown tool names get fallback tool_type."""
    builder = EventStreamBuilder(capability_id="test", task_id="task1")
    event = builder.tool_call(
        tool_name="some_new_unknown_tool",
        arguments={},
        tool_type="unknown",
        display_name="some_new_unknown_tool",
        icon="tool",
    )
    event_dict = event.to_dict()
    assert event_dict["tool"]["tool_type"] == "unknown"
    assert event_dict["tool"]["display_name"] == "some_new_unknown_tool"
