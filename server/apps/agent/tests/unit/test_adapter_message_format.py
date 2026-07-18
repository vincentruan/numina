"""Test that adapter builds a context-only prompt (skill content is injected natively)."""

import json

from apps.agent.schemas.context import RedactedContext
from apps.agent.services.deerflow_adapter.adapter import DeerFlowAdapter


def test_build_prompt_is_context_json_without_skill_prefix():
    """The message sent to DeerFlow is the redacted context as JSON.

    The former ``[SKILL:xxx]`` prefix had no consumer — skill content is now
    injected by DeerFlow's native ``<skill_system>`` system-prompt section
    (filtered by ``available_skills``), so the user message carries only context.
    """
    context = RedactedContext(family_id="f1", free_text="test query")
    adapter = DeerFlowAdapter.__new__(DeerFlowAdapter)
    message = adapter._build_prompt("alerts", context)
    # No [SKILL:] prefix; the whole message is valid JSON.
    assert not message.startswith("[SKILL:")
    parsed = json.loads(message)
    assert isinstance(parsed, dict)


def test_build_prompt_includes_context_data():
    """The context JSON message must include family_id and free_text."""
    context = RedactedContext(family_id="f1", free_text="test query")
    adapter = DeerFlowAdapter.__new__(DeerFlowAdapter)
    message = adapter._build_prompt("alerts", context)
    assert "family_id" in message
    assert "f1" in message
    assert "test query" in message
