"""Test that capability.end can include suggestions."""

from apps.agent.services.stream_events import EventStreamBuilder


def test_end_event_includes_suggestions():
    """capability.end should include suggestions when provided."""
    builder = EventStreamBuilder(capability_id="chat", task_id="t1")
    event = builder.end("summary text", suggestions=["查看详情", "分析趋势"])
    data = event.to_dict()
    assert data["result"]["suggestions"] == ["查看详情", "分析趋势"]


def test_end_event_omits_suggestions_when_none():
    """capability.end should omit suggestions field when not provided."""
    builder = EventStreamBuilder(capability_id="chat", task_id="t1")
    event = builder.end("summary text")
    data = event.to_dict()
    assert "suggestions" not in data["result"]


def test_end_event_omits_suggestions_when_empty_list():
    """capability.end should omit suggestions when empty list."""
    builder = EventStreamBuilder(capability_id="chat", task_id="t1")
    event = builder.end("summary text", suggestions=[])
    data = event.to_dict()
    assert "suggestions" not in data["result"]
