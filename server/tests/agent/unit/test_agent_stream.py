"""Tests for U2: agent_stream.py reasoning_effort parameter."""

from pydantic import ValidationError

from apps.agent.routers.agent_stream import AgentStreamRequest


# ── U2: AgentStreamRequest validation tests ─────────────────────────────────────


def test_agent_stream_request_defaults():
    """Default values for AgentStreamRequest. reasoning_effort defaults to 'medium'
    per plan U2 (non-nullable Literal['low','medium','high'])."""
    req = AgentStreamRequest(message="hello")
    assert req.enable_thinking == False
    assert req.web_search == False
    assert req.thread_id is None
    assert req.reasoning_effort == "medium"


def test_agent_stream_request_web_search_true():
    """web_search=True is accepted and exposed via the model."""
    req = AgentStreamRequest(message="test", web_search=True)
    assert req.web_search is True


def test_agent_stream_request_with_reasoning_effort_low():
    """reasoning_effort='low' is accepted."""
    req = AgentStreamRequest(message="test", enable_thinking=True, reasoning_effort="low")
    assert req.reasoning_effort == "low"


def test_agent_stream_request_with_reasoning_effort_medium():
    """reasoning_effort='medium' is accepted."""
    req = AgentStreamRequest(message="test", enable_thinking=True, reasoning_effort="medium")
    assert req.reasoning_effort == "medium"


def test_agent_stream_request_with_reasoning_effort_high():
    """reasoning_effort='high' is accepted."""
    req = AgentStreamRequest(message="test", enable_thinking=True, reasoning_effort="high")
    assert req.reasoning_effort == "high"


def test_agent_stream_request_invalid_reasoning_effort():
    """Invalid reasoning_effort value raises ValidationError."""
    try:
        AgentStreamRequest(message="test", reasoning_effort="invalid")
        assert False, "Should have raised ValidationError"
    except ValidationError as e:
        # Check that the error mentions reasoning_effort
        errors = e.errors()
        assert len(errors) == 1
        assert errors[0]["loc"][0] == "reasoning_effort"


def test_agent_stream_request_reasoning_effort_rejects_none():
    """reasoning_effort=None is rejected — Literal['low','medium','high'] is non-nullable.
    Callers wanting the default should omit the field entirely."""
    try:
        AgentStreamRequest(message="test", enable_thinking=True, reasoning_effort=None)
        assert False, "Should have raised ValidationError"
    except ValidationError as e:
        errors = e.errors()
        assert any(err["loc"][0] == "reasoning_effort" for err in errors)