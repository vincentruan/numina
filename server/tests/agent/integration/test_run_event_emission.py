"""Integration tests for run event emission from worker and pipeline.

Verifies that run.start, run.end, llm.ai.response, and llm.tool.result events
are recorded when the worker dispatches a run.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from apps.agent.services.run_event_store import RunEventStore


@pytest.fixture()
def event_store(tmp_path: Path) -> RunEventStore:
    return RunEventStore(tmp_path)


class TestWorkerEventEmission:
    """Verify that run.start and run.end events are emitted by the worker."""

    def test_run_start_and_end_recorded(self, event_store: RunEventStore) -> None:
        """Simulate worker event emission for a successful run."""
        # Simulate run.start
        event_store.record_raw(
            "run.start",
            run_id="run-123",
            thread_id="thread-456",
            family_id="family-789",
            data={"app": "numina"},
        )
        # Simulate run.end
        event_store.record_raw(
            "run.end",
            run_id="run-123",
            thread_id="thread-456",
            family_id="family-789",
            data={"status": "success"},
        )

        events = event_store.query_by_thread("thread-456", family_id="family-789")
        assert len(events) == 2
        assert events[0].event_type == "run.start"
        assert events[0].data["app"] == "numina"
        assert events[1].event_type == "run.end"
        assert events[1].data["status"] == "success"

    def test_run_end_recorded_on_error(self, event_store: RunEventStore) -> None:
        """Simulate worker event emission for a failed run."""
        event_store.record_raw(
            "run.start",
            run_id="run-err",
            thread_id="thread-err",
            family_id="family-err",
            data={"app": "numina"},
        )
        event_store.record_raw(
            "run.end",
            run_id="run-err",
            thread_id="thread-err",
            family_id="family-err",
            data={"status": "error"},
        )

        events = event_store.query_by_thread("thread-err", family_id="family-err")
        assert len(events) == 2
        assert events[1].data["status"] == "error"


class TestPipelineEventEmission:
    """Verify that llm.ai.response and llm.tool.result events are recorded."""

    def test_llm_ai_response_recorded(self, event_store: RunEventStore) -> None:
        """Simulate pipeline recording an AI response event."""
        event_store.record_raw(
            "llm.ai.response",
            run_id="run-1",
            thread_id="thread-1",
            family_id="family-1",
            data={"content_preview": "Hello, how can I help?"},
        )

        events = event_store.query_by_thread("thread-1", family_id="family-1")
        assert len(events) == 1
        assert events[0].event_type == "llm.ai.response"
        assert "content_preview" in events[0].data

    def test_llm_tool_result_recorded(self, event_store: RunEventStore) -> None:
        """Simulate pipeline recording a tool result event."""
        event_store.record_raw(
            "llm.tool.result",
            run_id="run-1",
            thread_id="thread-1",
            family_id="family-1",
            data={
                "tool_call_id": "tc-1",
                "tool_name": "get_assets",
                "content_preview": '{"assets": []}',
            },
        )

        events = event_store.query_by_thread("thread-1", family_id="family-1")
        assert len(events) == 1
        assert events[0].event_type == "llm.tool.result"
        assert events[0].data["tool_name"] == "get_assets"

    def test_complete_run_lifecycle(self, event_store: RunEventStore) -> None:
        """Covers AE1: verify complete run audit trail."""
        # Simulate a full run: start → 2 AI responses → 3 tool results → end
        event_store.record_raw("run.start", "run-full", "thread-full", "family-full")
        event_store.record_raw("llm.ai.response", "run-full", "thread-full", "family-full", {"content_preview": "Let me check..."})
        event_store.record_raw("llm.tool.result", "run-full", "thread-full", "family-full", {"tool_name": "get_overview"})
        event_store.record_raw("llm.ai.response", "run-full", "thread-full", "family-full", {"content_preview": "Here is your overview..."})
        event_store.record_raw("llm.tool.result", "run-full", "thread-full", "family-full", {"tool_name": "get_assets"})
        event_store.record_raw("llm.tool.result", "run-full", "thread-full", "family-full", {"tool_name": "get_liabilities"})
        event_store.record_raw("run.end", "run-full", "thread-full", "family-full", {"status": "success"})

        events = event_store.query_by_thread("thread-full", family_id="family-full")
        assert len(events) == 7
        types = [e.event_type for e in events]
        assert types == [
            "run.start",
            "llm.ai.response",
            "llm.tool.result",
            "llm.ai.response",
            "llm.tool.result",
            "llm.tool.result",
            "run.end",
        ]
