"""Unit tests for services/message_classifier.py.

Tests cover all classify_message() branches, all extraction helpers, and the
resolve_tool_metadata() lookup — using both dict inputs and minimal object
stubs to exercise both code paths.
"""

from types import SimpleNamespace
from typing import Any

from apps.agent.services.message_classifier import (
    classify_message,
    extract_content,
    extract_reasoning,
    extract_tool_calls,
    extract_tool_result,
    resolve_tool_metadata,
)

# ── Helpers: lightweight message stubs ──────────────────────────────────────


def _ai_msg(
    content: str = "",
    tool_calls: list | None = None,
    reasoning_content: str | None = None,
    additional_kwargs: dict | None = None,
) -> Any:
    """Minimal AIMessage-like object (no LangChain dep required)."""
    obj = SimpleNamespace(
        content=content,
        tool_calls=tool_calls or [],
        reasoning_content=reasoning_content,
        additional_kwargs=additional_kwargs or {},
    )
    return obj


def _tool_msg(content: str = "result", tool_call_id: str = "call-1") -> Any:
    """Minimal ToolMessage-like object."""
    return SimpleNamespace(content=content, tool_call_id=tool_call_id)


# ── classify_message: object path ───────────────────────────────────────────


def test_classify_ai_message_with_tool_calls_returns_tool_call():
    """AIMessage with non-empty tool_calls → 'tool_call'."""
    msg = _ai_msg(tool_calls=[{"name": "get_assets", "args": {}, "id": "c1"}])
    assert classify_message(msg) == "tool_call"


def test_classify_tool_message_returns_tool_result():
    """ToolMessage with tool_call_id → 'tool_result'."""
    msg = _tool_msg(tool_call_id="call-1")
    assert classify_message(msg) == "tool_result"


def test_classify_ai_message_with_reasoning_returns_thinking():
    """AIMessage with reasoning_content and no tool_calls → 'thinking'."""
    msg = _ai_msg(reasoning_content="Let me think…")
    assert classify_message(msg) == "thinking"


def test_classify_ai_message_with_text_content_returns_text():
    """AIMessage with plain text content → 'text'."""
    msg = _ai_msg(content="The answer is 42.")
    assert classify_message(msg) == "text"


def test_classify_empty_message_returns_unknown():
    """AIMessage with no content, no tool_calls, no reasoning → 'unknown'."""
    msg = _ai_msg(content="")
    assert classify_message(msg) == "unknown"


def test_classify_tool_call_takes_priority_over_reasoning():
    """tool_calls present on an AIMessage takes priority over reasoning_content."""
    msg = _ai_msg(
        tool_calls=[{"name": "get_assets", "args": {}, "id": "c1"}],
        reasoning_content="some thinking",
    )
    assert classify_message(msg) == "tool_call"


def test_classify_tool_result_takes_priority_over_tool_calls():
    """tool_call_id check fires before tool_calls check (ToolMessage wins)."""
    msg = SimpleNamespace(
        tool_call_id="c1",
        tool_calls=[{"name": "x", "args": {}, "id": "c1"}],
        content="result",
        reasoning_content=None,
        additional_kwargs={},
    )
    assert classify_message(msg) == "tool_result"


# ── classify_message: dict path ─────────────────────────────────────────────


def test_classify_dict_with_tool_call_id_returns_tool_result():
    """Dict with 'tool_call_id' key → 'tool_result'."""
    assert classify_message({"tool_call_id": "c1", "content": "res"}) == "tool_result"


def test_classify_dict_with_tool_calls_returns_tool_call():
    """Dict with non-empty 'tool_calls' list → 'tool_call'."""
    msg = {"tool_calls": [{"name": "get_assets", "args": {}, "id": "c1"}]}
    assert classify_message(msg) == "tool_call"


def test_classify_dict_with_reasoning_content_returns_thinking():
    """Dict with 'reasoning_content' key → 'thinking'."""
    assert classify_message({"reasoning_content": "hmm"}) == "thinking"


def test_classify_dict_with_content_returns_text():
    """Dict with 'content' key → 'text'."""
    assert classify_message({"content": "hello"}) == "text"


def test_classify_empty_dict_returns_unknown():
    """Empty dict → 'unknown'."""
    assert classify_message({}) == "unknown"


# ── extract_tool_calls ───────────────────────────────────────────────────────


def test_extract_tool_calls_from_dict_with_args():
    """Dict message with tool_calls list returns normalized {name, args, id}."""
    msg = {
        "tool_calls": [
            {"name": "get_assets", "args": {"family_id": "123"}, "id": "call-abc"},
        ]
    }
    result = extract_tool_calls(msg)
    assert len(result) == 1
    assert result[0]["name"] == "get_assets"
    assert result[0]["args"] == {"family_id": "123"}
    assert result[0]["id"] == "call-abc"


def test_extract_tool_calls_from_object():
    """Object with tool_calls list attribute returns normalized list."""
    call = SimpleNamespace(name="web_search", args={"query": "gold price"}, id="c2")
    msg = _ai_msg(tool_calls=[call])
    result = extract_tool_calls(msg)
    assert len(result) == 1
    assert result[0]["name"] == "web_search"
    assert result[0]["args"] == {"query": "gold price"}
    assert result[0]["id"] == "c2"


def test_extract_tool_calls_uses_arguments_key_fallback():
    """Dict tool_call item with 'arguments' key (not 'args') is normalized."""
    msg = {
        "tool_calls": [
            {"name": "get_assets", "arguments": {"x": 1}, "id": "c3"},
        ]
    }
    result = extract_tool_calls(msg)
    assert result[0]["args"] == {"x": 1}


def test_extract_tool_calls_non_dict_args_wrapped():
    """Non-dict args value is wrapped in {'_raw': ...}."""
    msg = {"tool_calls": [{"name": "foo", "args": "raw-string", "id": "c4"}]}
    result = extract_tool_calls(msg)
    assert result[0]["args"] == {"_raw": "raw-string"}


def test_extract_tool_calls_empty_returns_empty_list():
    """Message with no tool_calls returns []."""
    assert extract_tool_calls({"content": "hello"}) == []
    assert extract_tool_calls(_ai_msg()) == []


def test_extract_tool_calls_multiple_calls():
    """Multiple tool_calls are all returned."""
    msg = {
        "tool_calls": [
            {"name": "a", "args": {}, "id": "1"},
            {"name": "b", "args": {}, "id": "2"},
        ]
    }
    result = extract_tool_calls(msg)
    assert len(result) == 2
    assert result[0]["name"] == "a"
    assert result[1]["name"] == "b"


# ── extract_tool_result ──────────────────────────────────────────────────────


def test_extract_tool_result_from_tool_message_object():
    """ToolMessage object returns (tool_call_id, content)."""
    msg = _tool_msg(content="{'balance': 100}", tool_call_id="call-99")
    provider_id, content = extract_tool_result(msg)
    assert provider_id == "call-99"
    assert content == "{'balance': 100}"


def test_extract_tool_result_from_dict():
    """Dict ToolMessage returns (tool_call_id, content)."""
    msg = {"tool_call_id": "c5", "content": "done"}
    provider_id, content = extract_tool_result(msg)
    assert provider_id == "c5"
    assert content == "done"


def test_extract_tool_result_missing_tool_call_id_returns_empty_string():
    """Missing tool_call_id returns empty string (no crash)."""
    provider_id, _ = extract_tool_result({"content": "x"})
    assert provider_id == ""


# ── extract_reasoning ────────────────────────────────────────────────────────


def test_extract_reasoning_from_object_direct_attribute():
    """reasoning_content directly on object is returned."""
    msg = _ai_msg(reasoning_content="Step 1: analyse the data.")
    assert extract_reasoning(msg) == "Step 1: analyse the data."


def test_extract_reasoning_from_additional_kwargs_fallback():
    """reasoning_content in additional_kwargs (fallback path) is returned."""
    msg = _ai_msg(additional_kwargs={"reasoning_content": "fallback thinking"})
    # Ensure reasoning_content attribute itself is falsy so fallback is exercised
    msg.reasoning_content = None
    assert extract_reasoning(msg) == "fallback thinking"


def test_extract_reasoning_from_dict_direct():
    """Dict message with 'reasoning_content' key is returned."""
    assert extract_reasoning({"reasoning_content": "abc"}) == "abc"


def test_extract_reasoning_from_dict_additional_kwargs():
    """Dict message with additional_kwargs.reasoning_content fallback path."""
    msg = {"additional_kwargs": {"reasoning_content": "nested"}}
    assert extract_reasoning(msg) == "nested"


def test_extract_reasoning_returns_none_when_absent():
    """Returns None when no reasoning content exists anywhere."""
    assert extract_reasoning({"content": "hello"}) is None
    assert extract_reasoning(_ai_msg(content="hello")) is None


# ── extract_content ──────────────────────────────────────────────────────────


def test_extract_content_from_object():
    """String content attribute on object is returned."""
    msg = _ai_msg(content="The answer is 7.")
    assert extract_content(msg) == "The answer is 7."


def test_extract_content_from_dict():
    """Dict message with 'content' key is returned."""
    assert extract_content({"content": "hello"}) == "hello"


def test_extract_content_returns_none_for_empty_content():
    """Object with empty string content returns empty string (truthy check is caller's job)."""
    assert extract_content({"content": ""}) == ""


def test_extract_content_returns_none_when_absent():
    """Returns None when no content key/attribute exists."""
    assert extract_content({}) is None


# ── resolve_tool_metadata ────────────────────────────────────────────────────


def test_resolve_tool_metadata_known_tool():
    """Known tool name returns correct (type, display_name, icon, i18n_key)."""
    ttype, display, icon, i18n_key = resolve_tool_metadata("get_assets")
    # U7: get_assets is now an MCP base-name tool in the data_collect category
    # (was a built-in asset_query capability tool in the pre-U7 NDJSON era).
    assert ttype == "data_collect"
    assert display == "查询资产数据"
    assert icon == "💰"
    assert i18n_key == "toolName.getAssetsData"


def test_resolve_tool_metadata_web_search():
    """web_search tool maps to web_search type."""
    ttype, display, icon, i18n_key = resolve_tool_metadata("web_search")
    assert ttype == "web_search"
    assert icon == "🔍"
    assert i18n_key == "toolName.webSearch"


def test_resolve_tool_metadata_unknown_tool_fallback():
    """Unknown tool name falls back to ('unknown', <name>, 'tool', None)."""
    ttype, display, icon, i18n_key = resolve_tool_metadata("some_custom_tool")
    assert ttype == "unknown"
    assert display == "some_custom_tool"
    assert icon == "tool"
    assert i18n_key == ""


def test_resolve_tool_metadata_tavily_search():
    """tavily_search maps to web_search type (same as web_search)."""
    ttype, _, _, _ = resolve_tool_metadata("tavily_search")
    assert ttype == "web_search"
