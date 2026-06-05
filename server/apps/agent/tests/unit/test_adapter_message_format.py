"""Test that adapter uses [SKILL:xxx] natural language format instead of JSON."""

import json
import pytest

from apps.agent.services.deerflow_adapter.adapter import DeerFlowAdapter
from apps.agent.schemas.context import RedactedContext


def test_build_prompt_uses_skill_tag_format():
    """The message sent to DeerFlow must use [SKILL:xxx] format, not JSON."""
    context = RedactedContext(family_id="f1", free_text="test query")
    adapter = DeerFlowAdapter.__new__(DeerFlowAdapter)
    message = adapter._build_prompt("alerts", context)
    assert message.startswith("[SKILL:alerts]")
    # Must NOT be valid JSON at the top level (it has a prefix)
    with pytest.raises(json.JSONDecodeError):
        json.loads(message)


def test_build_prompt_includes_context_data():
    """The [SKILL:xxx] message must include context data as pretty-printed JSON."""
    context = RedactedContext(family_id="f1", free_text="test query")
    adapter = DeerFlowAdapter.__new__(DeerFlowAdapter)
    message = adapter._build_prompt("alerts", context)
    assert "family_id" in message
    assert "f1" in message
    assert "test query" in message
