"""Tests for T27: Run event hash chain (tamper-evidence)."""

from __future__ import annotations

import json

import pytest

from apps.agent.services.run_event_store import (
    RunEvent,
    RunEventStore,
    _compute_event_hash,
)


@pytest.fixture
def event_store(tmp_path):
    """Create a RunEventStore with a temporary directory."""
    return RunEventStore(tmp_path)


def test_compute_event_hash_deterministic():
    """Hash computation is deterministic."""
    event_data = {
        "event_type": "run.start",
        "run_id": "run-1",
        "thread_id": "thread-1",
        "family_id": "family-1",
        "timestamp": "2026-11-03T10:00:00Z",
        "data": {"app": "numina"},
    }
    prev_hash = "0" * 64

    hash1 = _compute_event_hash(prev_hash, event_data)
    hash2 = _compute_event_hash(prev_hash, event_data)

    assert hash1 == hash2
    assert len(hash1) == 64  # SHA-256 hex digest


def test_compute_event_hash_excludes_hash_field():
    """Hash computation excludes the hash field itself."""
    event_data = {
        "event_type": "run.start",
        "run_id": "run-1",
        "thread_id": "thread-1",
        "family_id": "family-1",
        "timestamp": "2026-11-03T10:00:00Z",
        "data": {},
    }
    prev_hash = "0" * 64

    # Hash with and without hash field in data
    hash_without = _compute_event_hash(prev_hash, event_data)
    event_data_with_hash = {**event_data, "hash": "some-hash"}
    hash_with = _compute_event_hash(prev_hash, event_data_with_hash)

    # Should be the same (hash field excluded)
    assert hash_without == hash_with


def test_record_adds_hash_chain(event_store):
    """record() computes and stores prev_hash and hash."""
    event = RunEvent(
        event_type="run.start",
        run_id="run-1",
        thread_id="thread-1",
        family_id="family-1",
        timestamp="2026-11-03T10:00:00Z",
        data={"app": "numina"},
    )

    event_store.record(event)

    # Event should have prev_hash and hash set
    assert event.prev_hash == "0" * 64  # First event
    assert event.hash is not None
    assert len(event.hash) == 64

    # Verify written to file
    events = event_store.query_by_family("family-1")
    assert len(events) == 1
    assert events[0].prev_hash == "0" * 64
    assert events[0].hash == event.hash


def test_record_chain_links_events(event_store):
    """Multiple events form a hash chain."""
    event1 = RunEvent(
        event_type="run.start",
        run_id="run-1",
        thread_id="thread-1",
        family_id="family-1",
        timestamp="2026-11-03T10:00:00Z",
        data={},
    )
    event_store.record(event1)

    event2 = RunEvent(
        event_type="run.end",
        run_id="run-1",
        thread_id="thread-1",
        family_id="family-1",
        timestamp="2026-11-03T10:01:00Z",
        data={"status": "success"},
    )
    event_store.record(event2)

    # Second event's prev_hash should be first event's hash
    assert event2.prev_hash == event1.hash
    assert event2.hash != event1.hash


def test_verify_events_valid_chain(event_store):
    """verify_events returns True for valid chain."""
    # Create 3 events
    for i in range(3):
        event = RunEvent(
            event_type=f"event-{i}",
            run_id="run-1",
            thread_id="thread-1",
            family_id="family-1",
            timestamp=f"2026-11-03T10:0{i}:00Z",
            data={},
        )
        event_store.record(event)

    result = event_store.verify_events("family-1")
    assert result["verified"] is True
    assert result["event_count"] == 3
    assert result["tampered_event_index"] is None


def test_verify_events_detects_tampering(event_store):
    """verify_events detects tampered events."""
    # Create 3 events
    for i in range(3):
        event = RunEvent(
            event_type=f"event-{i}",
            run_id="run-1",
            thread_id="thread-1",
            family_id="family-1",
            timestamp=f"2026-11-03T10:0{i}:00Z",
            data={},
        )
        event_store.record(event)

    # Tamper with event 1 by modifying the file
    path = event_store._file_for_family("family-1")
    lines = path.read_text().strip().split("\n")
    tampered_event = json.loads(lines[1])
    tampered_event["data"] = {"tampered": True}
    lines[1] = json.dumps(tampered_event)
    path.write_text("\n".join(lines) + "\n")

    # Clear cache to force re-read
    event_store._last_hash_cache.clear()

    result = event_store.verify_events("family-1")
    assert result["verified"] is False
    assert result["tampered_event_index"] == 1
    assert "hash mismatch" in result["reason"]


def test_verify_events_legacy_events_unverified(event_store):
    """verify_events returns 'unverified' for legacy events without hashes."""
    # Write legacy events (no hash fields)
    path = event_store._file_for_family("family-1")
    path.parent.mkdir(parents=True, exist_ok=True)
    legacy_event = {
        "event_type": "run.start",
        "run_id": "run-1",
        "thread_id": "thread-1",
        "family_id": "family-1",
        "timestamp": "2026-11-03T10:00:00Z",
        "data": {},
    }
    path.write_text(json.dumps(legacy_event) + "\n")

    result = event_store.verify_events("family-1")
    assert result["verified"] == "unverified"
    assert result["event_count"] == 1
    assert "predate hash-chaining" in result["reason"]


def test_verify_events_empty_file(event_store):
    """verify_events returns True for empty/non-existent file."""
    result = event_store.verify_events("nonexistent-family")
    assert result["verified"] is True
    assert result["event_count"] == 0


def test_concurrent_writes_do_not_fork_chain(event_store):
    """Concurrent record() calls must not chain from the same prev_hash.

    Chain computation, cache update, and file append all happen under one
    lock. Without that, two threads could both read the same last hash and
    write siblings at the same chain position, which verify_events would
    report as a prev_hash mismatch.
    """
    import threading

    errors: list[Exception] = []

    def write_events(worker_id: int) -> None:
        try:
            for i in range(20):
                event_store.record_raw(
                    "concurrent",
                    run_id=f"run-{worker_id}",
                    thread_id="thread-1",
                    family_id="family-1",
                    data={"worker": worker_id, "i": i},
                )
        except Exception as exc:  # pragma: no cover - surfaced via assert below
            errors.append(exc)

    threads = [threading.Thread(target=write_events, args=(w,)) for w in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors, f"record() raised: {errors}"

    # 4 workers x 20 events = 80 events, all on one unbroken chain
    result = event_store.verify_events("family-1")
    assert result["verified"] is True, f"chain broken: {result}"
    assert result["event_count"] == 80


def test_hash_cache_performance(event_store):
    """Hash cache avoids re-reading file on every write."""
    # Create 10 events
    for i in range(10):
        event = RunEvent(
            event_type=f"event-{i}",
            run_id="run-1",
            thread_id="thread-1",
            family_id="family-1",
            timestamp=f"2026-11-03T10:0{i}:00Z",
            data={},
        )
        event_store.record(event)

    # Cache should have the last hash
    assert "family-1" in event_store._last_hash_cache
    assert len(event_store._last_hash_cache["family-1"]) == 64


def test_verify_events_per_run_filters_count(event_store):
    """verify_events with run_id counts only events for that run."""
    # Run-1: 2 events; Run-2: 3 events
    for i in range(2):
        event_store.record_raw(
            "run1-event",
            run_id="run-1",
            thread_id="t1",
            family_id="family-1",
            data={"i": i},
        )
    for i in range(3):
        event_store.record_raw(
            "run2-event",
            run_id="run-2",
            thread_id="t1",
            family_id="family-1",
            data={"i": i},
        )

    # Whole chain verifies
    result = event_store.verify_events("family-1")
    assert result["verified"] is True
    assert result["event_count"] == 5

    # Per-run: counts only matching events
    result_run1 = event_store.verify_events("family-1", run_id="run-1")
    assert result_run1["verified"] is True
    assert result_run1["event_count"] == 2

    result_run2 = event_store.verify_events("family-1", run_id="run-2")
    assert result_run2["verified"] is True
    assert result_run2["event_count"] == 3

    # Non-existent run: chain still verified, count is 0
    result_empty = event_store.verify_events("family-1", run_id="no-such-run")
    assert result_empty["verified"] is True
    assert result_empty["event_count"] == 0


def test_verify_events_per_run_detects_tampering_across_run_boundary(event_store):
    """Per-run verify still catches tampering even if tampered event is outside the run."""
    for i in range(2):
        event_store.record_raw(
            "run1-event",
            run_id="run-1",
            thread_id="t1",
            family_id="family-1",
            data={"i": i},
        )
    for i in range(2):
        event_store.record_raw(
            "run2-event",
            run_id="run-2",
            thread_id="t1",
            family_id="family-1",
            data={"i": i},
        )

    # Tamper with event 0 (belongs to run-1)
    path = event_store._file_for_family("family-1")
    lines = path.read_text().strip().split("\n")
    tampered = json.loads(lines[0])
    tampered["data"]["tampered"] = True
    lines[0] = json.dumps(tampered)
    path.write_text("\n".join(lines) + "\n")

    event_store._last_hash_cache.clear()

    # Per-run verify for run-2 (the tampered event is in run-1) should still fail
    # — the whole chain must validate, but count reflects only run-2 events
    result = event_store.verify_events("family-1", run_id="run-2")
    assert result["verified"] is False
    assert result["tampered_event_index"] == 0
