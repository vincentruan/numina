"""Test stream_events subagent_update method (CR-12)."""

from apps.agent.services.stream_events import EventStreamBuilder


class TestSubagentUpdate:
    """Tests for EventStreamBuilder.subagent_update method."""

    def test_subagent_update_running(self) -> None:
        """subagent_update creates correct event for running status."""
        builder = EventStreamBuilder(capability_id="test-cap", task_id="test-task")
        event = builder.subagent_update(
            task_id="subagent-001",
            status="running",
            title="Data analysis",
            description="Processing records...",
        )

        evt_dict = event.to_dict()
        assert evt_dict["type"] == "subagent.update"
        assert evt_dict["capability_id"] == "test-cap"
        assert evt_dict["task_id"] == "test-task"
        assert "subagent" in evt_dict
        assert evt_dict["subagent"]["taskId"] == "subagent-001"
        assert evt_dict["subagent"]["status"] == "running"
        assert evt_dict["subagent"]["title"] == "Data analysis"
        assert evt_dict["subagent"]["description"] == "Processing records..."
        assert evt_dict["subagent"]["result"] is None
        assert evt_dict["subagent"]["error"] is None

    def test_subagent_update_done(self) -> None:
        """subagent_update creates correct event for done status."""
        builder = EventStreamBuilder(capability_id="test-cap", task_id="test-task")
        event = builder.subagent_update(
            task_id="subagent-001",
            status="done",
            title="Data analysis",
            result="Found 42 records",
        )

        evt_dict = event.to_dict()
        assert evt_dict["subagent"]["status"] == "done"
        assert evt_dict["subagent"]["result"] == "Found 42 records"
        assert evt_dict["subagent"]["description"] is None
        assert evt_dict["subagent"]["error"] is None

    def test_subagent_update_failed(self) -> None:
        """subagent_update creates correct event for failed status."""
        builder = EventStreamBuilder(capability_id="test-cap", task_id="test-task")
        event = builder.subagent_update(
            task_id="subagent-001",
            status="failed",
            title="Data analysis",
            error="Connection refused",
        )

        evt_dict = event.to_dict()
        assert evt_dict["subagent"]["status"] == "failed"
        assert evt_dict["subagent"]["error"] == "Connection refused"
        assert evt_dict["subagent"]["result"] is None

    def test_subagent_update_cancelled_status(self) -> None:
        """subagent_update supports cancelled status."""
        builder = EventStreamBuilder(capability_id="test-cap", task_id="test-task")
        event = builder.subagent_update(
            task_id="subagent-001",
            status="cancelled",
            error="User cancelled",
        )

        evt_dict = event.to_dict()
        assert evt_dict["subagent"]["status"] == "cancelled"
        assert evt_dict["subagent"]["error"] == "User cancelled"

    def test_subagent_update_timed_out_status(self) -> None:
        """subagent_update supports timed_out status."""
        builder = EventStreamBuilder(capability_id="test-cap", task_id="test-task")
        event = builder.subagent_update(
            task_id="subagent-001",
            status="timed_out",
            error="Task exceeded 30s timeout",
        )

        evt_dict = event.to_dict()
        assert evt_dict["subagent"]["status"] == "timed_out"
        assert evt_dict["subagent"]["error"] == "Task exceeded 30s timeout"

    def test_subagent_update_partial_fields(self) -> None:
        """subagent_update works with only required fields."""
        builder = EventStreamBuilder(capability_id="test-cap", task_id="test-task")
        event = builder.subagent_update(
            task_id="subagent-001",
            status="running",
        )

        evt_dict = event.to_dict()
        assert evt_dict["subagent"]["taskId"] == "subagent-001"
        assert evt_dict["subagent"]["status"] == "running"
        # Optional fields should be None
        assert evt_dict["subagent"]["title"] is None
        assert evt_dict["subagent"]["description"] is None
        assert evt_dict["subagent"]["result"] is None
        assert evt_dict["subagent"]["error"] is None

    def test_subagent_update_ndjson_format(self) -> None:
        """subagent_update event serializes correctly to NDJSON."""
        builder = EventStreamBuilder(capability_id="test-cap", task_id="test-task")
        event = builder.subagent_update(
            task_id="subagent-001",
            status="running",
            title="Task",
        )

        ndjson = event.to_ndjson()
        assert ndjson.endswith("\n")
        assert "subagent.update" in ndjson
        assert "subagent-001" in ndjson
        # NDJSON uses compact separators
        assert '",":"' in ndjson or ',"' in ndjson

    def test_subagent_update_unique_event_ids(self) -> None:
        """Each subagent_update call generates unique event ID."""
        builder = EventStreamBuilder(capability_id="test-cap", task_id="test-task")

        event1 = builder.subagent_update(task_id="task-1", status="running")
        event2 = builder.subagent_update(task_id="task-2", status="running")

        assert event1.id != event2.id

    def test_subagent_update_increments_event_id(self) -> None:
        """Event IDs increment sequentially for subagent updates."""
        builder = EventStreamBuilder(capability_id="test-cap", task_id="test-task")

        event1 = builder.subagent_update(task_id="task-1", status="running")
        event2 = builder.subagent_update(task_id="task-1", status="done")

        # IDs should differ (sequential increment)
        assert event1.id != event2.id
        # Both should share same task_id prefix
        assert "test-task" in event1.id
        assert "test-task" in event2.id