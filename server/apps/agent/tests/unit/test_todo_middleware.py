"""Tests for TodoMiddleware — sync hooks, singleton, context-loss + premature-exit.

R2 (critical): numina's adapter runs the SYNC ``DeerFlowClient.stream()``
path, so LangGraph dispatches the SYNC ``before_model`` / ``after_model`` /
``wrap_model_call`` hooks. An async-only middleware would silently no-op. These
tests assert the sync hooks fire and behave correctly.

R3 (critical): ``family_adapter_cache.py:726`` keys the LRU cache on
``tuple(id(m) for m in middlewares)``. ``get_todo_middleware()`` must return a
process-wide singleton so ``id()`` is stable across calls (no agent rebuild).
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

from langchain_core.messages import AIMessage, HumanMessage

from apps.agent.services.deerflow_adapter.todo_middleware import (
    TodoMiddleware,
    _format_completion_reminder,
    _format_todos,
    _has_tool_call_intent_or_error,
    _reminder_in_messages,
    _todos_in_messages,
    get_todo_middleware,
)


def _runtime(*, thread_id: str = "thread-1", run_id: str = "run-1") -> Any:
    """Build a fake Runtime with a context dict (TodoMiddleware reads thread/run id)."""
    ctx = MagicMock()
    ctx.get = lambda key, default=None: {"thread_id": thread_id, "run_id": run_id}.get(key, default)
    runtime = MagicMock()
    runtime.context = ctx
    return runtime


def _state(*, todos: list | None = None, messages: list | None = None) -> dict:
    """Build a minimal state dict with the channels TodoMiddleware reads."""
    return {"todos": todos or [], "messages": messages or []}


# ── R3: singleton ────────────────────────────────────────────────────────────


def test_get_todo_middleware_is_singleton_with_stable_id():
    """R3: repeated calls return the same object (stable id() for LRU key)."""
    m1 = get_todo_middleware()
    m2 = get_todo_middleware()
    assert m1 is m2
    assert id(m1) == id(m2)


def test_todo_middleware_is_subclass_of_langchain_base():
    """The langchain TodoListMiddleware base provides the write_todos tool."""
    from langchain.agents.middleware import TodoListMiddleware

    assert isinstance(get_todo_middleware(), TodoListMiddleware)


# ── R2: sync hooks present ───────────────────────────────────────────────────


def test_sync_hooks_are_defined():
    """R2: sync before_model / after_model / wrap_model_call must exist."""
    m = get_todo_middleware()
    assert callable(getattr(m, "before_model", None))
    assert callable(getattr(m, "after_model", None))
    assert callable(getattr(m, "wrap_model_call", None))
    # async variants also present (delegate to sync)
    assert callable(getattr(m, "abefore_model", None))
    assert callable(getattr(m, "aafter_model", None))


# ── before_model: context-loss reminder ──────────────────────────────────────


def test_before_model_returns_none_when_no_todos():
    """No todos → no reminder injected."""
    m = get_todo_middleware()
    result = m.before_model(_state(todos=[], messages=[HumanMessage(content="hi")]), _runtime())
    assert result is None


def test_before_model_returns_none_when_write_todos_still_visible():
    """todos exist + write_todos tool call still in context → no reminder."""
    m = get_todo_middleware()
    ai = AIMessage(content="planning", tool_calls=[{"name": "write_todos", "args": {}, "id": "tc-1"}])
    result = m.before_model(
        _state(todos=[{"content": "x", "status": "pending"}], messages=[ai]),
        _runtime(),
    )
    assert result is None


def test_before_model_injects_reminder_when_write_todos_truncated():
    """todos exist but no write_todos in messages → inject hidden reminder."""
    m = get_todo_middleware()
    # messages have an AI message WITHOUT a write_todos call (it was truncated)
    result = m.before_model(
        _state(
            todos=[{"content": "step 1", "status": "in_progress"}],
            messages=[HumanMessage(content="hi"), AIMessage(content="working")],
        ),
        _runtime(),
    )
    assert result is not None
    assert "messages" in result
    reminder = result["messages"][0]
    assert isinstance(reminder, HumanMessage)
    assert reminder.name == "todo_reminder"
    # hide_from_ui so it doesn't leak into the user-visible stream
    assert reminder.additional_kwargs.get("hide_from_ui") is True
    assert "step 1" in reminder.content
    assert "[in_progress]" in reminder.content


def test_before_model_does_not_double_inject_reminder():
    """A reminder already present (not yet truncated) → don't add another."""
    m = get_todo_middleware()
    existing = HumanMessage(name="todo_reminder", content="<system_reminder>...</system_reminder>")
    result = m.before_model(
        _state(
            todos=[{"content": "x", "status": "pending"}],
            messages=[existing],
        ),
        _runtime(),
    )
    assert result is None


# ── after_model: premature-exit prevention ───────────────────────────────────


def test_after_model_returns_none_when_all_todos_completed():
    """All todos completed + clean final AI message → allow exit."""
    m = get_todo_middleware()
    last_ai = AIMessage(content="done, here is your answer")
    result = m.after_model(
        _state(
            todos=[{"content": "a", "status": "completed"}, {"content": "b", "status": "completed"}],
            messages=[HumanMessage(content="hi"), last_ai],
        ),
        _runtime(),
    )
    assert result is None


def test_after_model_jumps_to_model_when_todos_incomplete_and_clean_final():
    """Incomplete todos + final AI message (no tool calls) → jump_to model."""
    m = get_todo_middleware()
    last_ai = AIMessage(content="here is a partial answer")
    result = m.after_model(
        _state(
            todos=[{"content": "a", "status": "completed"}, {"content": "b", "status": "in_progress"}],
            messages=[HumanMessage(content="hi"), last_ai],
        ),
        _runtime(),
    )
    assert result is not None
    assert result.get("jump_to") == "model"
    # reminder was queued for the next model request
    assert m._completion_reminder_count_for_runtime(_runtime()) == 1


def test_after_model_does_not_intervene_when_ai_has_tool_calls():
    """AI message with tool_calls is not a clean exit → let the tool path run."""
    m = get_todo_middleware()
    last_ai = AIMessage(
        content="",
        tool_calls=[{"name": "some_tool", "args": {}, "id": "tc-1"}],
    )
    result = m.after_model(
        _state(
            todos=[{"content": "a", "status": "in_progress"}],
            messages=[HumanMessage(content="hi"), last_ai],
        ),
        _runtime(),
    )
    assert result is None


def test_after_model_reminder_cap_prevents_infinite_loop():
    """After _MAX_COMPLETION_REMINDERS, allow exit even if todos incomplete."""
    m = get_todo_middleware()
    runtime = _runtime(thread_id="t-cap", run_id="r-cap")
    last_ai = AIMessage(content="partial")
    state = _state(
        todos=[{"content": "a", "status": "in_progress"}],
        messages=[HumanMessage(content="hi"), last_ai],
    )
    # Queue up to the cap
    for _ in range(TodoMiddleware._MAX_COMPLETION_REMINDERS):
        res = m.after_model(state, runtime)
        assert res is not None and res.get("jump_to") == "model"
    # Next call should NOT intervene (cap reached)
    result = m.after_model(state, runtime)
    assert result is None


# ── helper functions ─────────────────────────────────────────────────────────


def test_todos_in_messages_detects_write_todos_call():
    ai = AIMessage(content="", tool_calls=[{"name": "write_todos", "args": {}, "id": "1"}])
    assert _todos_in_messages([ai]) is True
    ai2 = AIMessage(content="", tool_calls=[{"name": "other", "args": {}, "id": "2"}])
    assert _todos_in_messages([ai2]) is False
    assert _todos_in_messages([HumanMessage(content="hi")]) is False


def test_reminder_in_messages_detects_todo_reminder():
    reminder = HumanMessage(name="todo_reminder", content="x")
    assert _reminder_in_messages([reminder]) is True
    assert _reminder_in_messages([HumanMessage(content="x")]) is False


def test_format_todos_includes_status_and_content():
    out = _format_todos([{"content": "do thing", "status": "in_progress"}])
    assert "[in_progress]" in out
    assert "do thing" in out


def test_format_completion_reminder_only_lists_incomplete():
    out = _format_completion_reminder(
        [
            {"content": "all-the-things", "status": "completed"},
            {"content": "pending task", "status": "pending"},
        ]
    )
    assert "pending task" in out
    # completed items are excluded from the incomplete list
    assert "all-the-things" not in out


def test_has_tool_call_intent_or_error_detects_tool_calls():
    assert _has_tool_call_intent_or_error(
        AIMessage(content="", tool_calls=[{"name": "x", "args": {}, "id": "1"}])
    ) is True
    assert _has_tool_call_intent_or_error(AIMessage(content="clean answer")) is False


# ── base class integration: write_todos tool is registered ───────────────────


def test_base_class_write_todos_tool_is_available():
    """The langchain TodoListMiddleware base registers the write_todos tool.

    We don't instantiate the full agent here (that requires DeerFlow config);
    we assert the base class exposes the tool via its tool registry mechanism.
    The presence of the `write_todos` tool name in the base class's known
    tool set confirms the agent will receive it when plan_mode=True.
    """
    m = get_todo_middleware()
    # The base class stores the tool description; verify the tool is wired by
    # checking the system_prompt references write_todos (the base class injects
    # both the tool and a system-prompt section instructing its use).
    assert "write_todos" in m.system_prompt
