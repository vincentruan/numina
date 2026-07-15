# server/apps/agent/services/deerflow_adapter/interrupt_tools.py
"""Interrupt tools for human-in-the-loop clarification.

Registers the `ask_clarification` tool, which calls LangGraph's `interrupt()`
primitive to pause graph execution and wait for user input.
"""
from __future__ import annotations

from langchain_core.tools import BaseTool, StructuredTool
from langgraph.types import interrupt
from pydantic import BaseModel, Field


class AskClarificationInput(BaseModel):
    """Input schema for ask_clarification tool."""
    question: str = Field(description="The question to ask the user (markdown supported)")
    options: list[dict[str, str]] | None = Field(
        default=None,
        description="Optional list of choices: [{label, value}]",
    )
    context: str | None = Field(
        default=None,
        description="Optional background context (markdown)",
    )
    choice_with_other: bool = Field(
        default=False,
        description="Allow user to select an option OR provide custom text",
    )
    multi_select: bool = Field(
        default=False,
        description="Allow user to select multiple options (checkboxes instead of radio)",
    )


def _ask_clarification(
    question: str,
    options: list[dict[str, str]] | None = None,
    context: str | None = None,
    choice_with_other: bool = False,
    multi_select: bool = False,
) -> str:
    """Ask the user for clarification during agent execution.

    This tool pauses the agent and waits for user input. The agent will
    resume with the user's answer.
    """
    interrupt_value = {
        "question": question,
        "options": options,
        "context": context,
        "choice_with_other": choice_with_other,
        "multi_select": multi_select,
    }
    # LangGraph interrupt() pauses the graph and returns this value to the UI.
    # When the user responds, LangGraph resumes and returns the user's answer.
    user_answer = interrupt(interrupt_value)
    return user_answer


def get_interrupt_tools() -> list[BaseTool]:
    """Return list of interrupt tools for DeerFlow harness."""
    ask_tool = StructuredTool.from_function(
        func=_ask_clarification,
        name="ask_clarification",
        description="Ask the user for clarification during execution. Pauses the agent and waits for user input.",
        args_schema=AskClarificationInput,
    )
    return [ask_tool]