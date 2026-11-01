"""Unit tests for RunEventStore."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from apps.agent.services.run_event_store import RunEvent, RunEventStore


@pytest.fixture()
def store(tmp_path: Path) -> RunEventStore:
    return RunEventStore(tmp_path)


class TestRunEventStore:
    def test_record_creates_file(self, store: RunEventStore, tmp_path: Path) -> None:
        store.record_raw("run.start", "run-1", "thread-1", "family-1")
        f = tmp_path / "run_events" / "family-1.jsonl"
        assert f.exists()
        lines = f.read_text().strip().splitlines()
        assert len(lines) == 1
        data = json.loads(lines[0])
        assert data["event_type"] == "run.start"
        assert data["run_id"] == "run-1"
        assert data["thread_id"] == "thread-1"
        assert data["family_id"] == "family-1"
        assert "timestamp" in data

    def test_record_multiple_events_same_thread(self, store: RunEventStore) -> None:
        store.record_raw("run.start", "run-1", "thread-1", "family-1")
        store.record_raw("llm.ai.response", "run-1", "thread-1", "family-1", {"content": "hello"})
        store.record_raw("run.end", "run-1", "thread-1", "family-1", {"status": "success"})

        events = store.query_by_thread("thread-1", family_id="family-1")
        assert len(events) == 3
        assert events[0].event_type == "run.start"
        assert events[1].event_type == "llm.ai.response"
        assert events[1].data == {"content": "hello"}
        assert events[2].event_type == "run.end"

    def test_query_by_thread_returns_empty_for_unknown(self, store: RunEventStore) -> None:
        events = store.query_by_thread("nonexistent", family_id="family-1")
        assert events == []

    def test_query_by_thread_without_family_scans_all(
        self, store: RunEventStore,
    ) -> None:
        store.record_raw("run.start", "run-1", "thread-1", "family-1")
        store.record_raw("run.start", "run-2", "thread-1", "family-2")

        events = store.query_by_thread("thread-1")
        assert len(events) == 2
        families = {e.family_id for e in events}
        assert families == {"family-1", "family-2"}

    def test_query_by_family(self, store: RunEventStore) -> None:
        store.record_raw("run.start", "run-1", "thread-1", "family-1")
        store.record_raw("run.start", "run-2", "thread-2", "family-1")
        store.record_raw("run.start", "run-3", "thread-3", "family-2")

        events = store.query_by_family("family-1")
        assert len(events) == 2
        thread_ids = {e.thread_id for e in events}
        assert thread_ids == {"thread-1", "thread-2"}

    def test_query_by_family_empty(self, store: RunEventStore) -> None:
        events = store.query_by_family("nonexistent")
        assert events == []

    def test_query_by_family_pagination(self, store: RunEventStore) -> None:
        for i in range(10):
            store.record_raw("run.start", f"run-{i}", f"thread-{i}", "family-1")

        page1 = store.query_by_family("family-1", limit=3, offset=0)
        assert len(page1) == 3
        page2 = store.query_by_family("family-1", limit=3, offset=3)
        assert len(page2) == 3
        # No overlap
        assert {e.run_id for e in page1}.isdisjoint({e.run_id for e in page2})

    def test_events_ordered_by_timestamp(self, store: RunEventStore) -> None:
        # Record events with slightly different timestamps
        store.record_raw("run.start", "run-1", "thread-1", "family-1")
        store.record_raw("llm.ai.response", "run-1", "thread-1", "family-1")
        store.record_raw("run.end", "run-1", "thread-1", "family-1")

        events = store.query_by_thread("thread-1", family_id="family-1")
        timestamps = [e.timestamp for e in events]
        assert timestamps == sorted(timestamps)

    def test_run_event_model_extra_fields(self) -> None:
        ev = RunEvent(
            event_type="run.start",
            run_id="r1",
            thread_id="t1",
            family_id="f1",
            timestamp="2026-11-01T00:00:00+00:00",
            custom_field="extra",
        )
        assert ev.event_type == "run.start"

    def test_family_id_path_traversal_rejected(self, store: RunEventStore) -> None:
        """Defense-in-depth: family_id with separators must not escape the base dir."""
        with pytest.raises(ValueError, match="Invalid family_id"):
            store.record_raw("run.start", "r1", "t1", "../evil")
        with pytest.raises(ValueError, match="Invalid family_id"):
            store.query_by_family("../../etc/passwd")

    def test_malformed_line_skipped(self, store: RunEventStore, tmp_path: Path) -> None:
        # Write a malformed line directly
        f = tmp_path / "run_events" / "family-1.jsonl"
        f.parent.mkdir(parents=True, exist_ok=True)
        lines = (
            '{"event_type": "run.start", "run_id": "r1", "thread_id": "t1", "family_id": "f1", "timestamp": "2026-01-01T00:00:00", "data": {}}\n'
            "not valid json\n"
            '{"event_type": "run.end", "run_id": "r1", "thread_id": "t1", "family_id": "f1", "timestamp": "2026-01-01T00:01:00", "data": {}}\n'
        )
        f.write_text(lines)

        events = store.query_by_thread("t1", family_id="family-1")
        assert len(events) == 2  # malformed line skipped
