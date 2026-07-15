# server/apps/agent/tests/unit/test_interrupt_tools.py
"""Unit tests for interrupt tool registration."""
from __future__ import annotations


def test_get_interrupt_tools_returns_ask_clarification():
    """get_interrupt_tools() must return a list containing ask_clarification."""
    from apps.agent.services.deerflow_adapter.interrupt_tools import (
        get_interrupt_tools,
    )

    tools = get_interrupt_tools()
    assert len(tools) >= 1
    tool_names = [t.name for t in tools]
    assert "ask_clarification" in tool_names


def test_ask_clarification_tool_has_correct_signature():
    """ask_clarification must accept question, options, context, choice_with_other."""
    from apps.agent.services.deerflow_adapter.interrupt_tools import (
        get_interrupt_tools,
    )

    tools = get_interrupt_tools()
    ask_tool = next(t for t in tools if t.name == "ask_clarification")

    # Check args_schema
    schema = ask_tool.args_schema
    assert schema is not None
    fields = schema.model_fields
    assert "question" in fields
    assert "options" in fields
    assert "context" in fields
    assert "choice_with_other" in fields


def test_ask_clarification_tool_calls_interrupt(monkeypatch):
    """ask_clarification must call LangGraph interrupt() when invoked."""
    from apps.agent.services.deerflow_adapter.interrupt_tools import (
        get_interrupt_tools,
    )

    interrupt_called = False
    interrupt_value = None

    def mock_interrupt(value):
        nonlocal interrupt_called, interrupt_value
        interrupt_called = True
        interrupt_value = value
        return "user_answer"

    monkeypatch.setattr(
        "apps.agent.services.deerflow_adapter.interrupt_tools.interrupt",
        mock_interrupt,
    )

    tools = get_interrupt_tools()
    ask_tool = next(t for t in tools if t.name == "ask_clarification")

    result = ask_tool.invoke({
        "question": "Which asset category?",
        "options": [{"label": "股票", "value": "stock"}],
        "context": "I need clarification.",
        "choice_with_other": False,
    })

    assert interrupt_called
    assert interrupt_value["question"] == "Which asset category?"
    assert interrupt_value["options"] == [{"label": "股票", "value": "stock"}]
    assert result == "user_answer"