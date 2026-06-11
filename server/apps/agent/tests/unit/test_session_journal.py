"""Test session_journal write_tool_call and write_tool_result methods."""

import json
import tempfile
from pathlib import Path

from apps.agent.app.config import settings
from apps.agent.services.session_journal import SessionJournalService


class TestSessionJournalToolEvents:
    """Tests for write_tool_call and write_tool_result persistence."""

    def test_write_tool_call_creates_event(self, tmp_path: Path) -> None:
        """write_tool_call creates tool.call event with nested tool object."""
        journal = SessionJournalService(str(tmp_path))
        journal.write_tool_call(
            family_id="family123",
            session_id="session456",
            tool_name="search_assets",
            tool_id="tool789",
            arguments={"query": "stocks", "limit": 10},
        )

        # Read the JSONL file - path structure: base_dir / family_id / agent / _default / _shared / session_id.jsonl
        jsonl_path = tmp_path / "family123" / "agent" / "_default" / "_shared" / "session456.jsonl"
        assert jsonl_path.exists()

        lines = jsonl_path.read_text().strip().split("\n")
        assert len(lines) == 1

        event = json.loads(lines[0])
        assert event["type"] == "tool.call"
        assert event["sessionId"] == "session456"
        assert event["familyId"] == "family123"
        assert event["actor"] == "assistant"
        assert event["visibility"] == "public"

        # Payload is spread to top level, not nested under "payload"
        assert "tool" in event
        assert event["tool"]["id"] == "tool789"
        assert event["tool"]["name"] == "search_assets"
        assert event["tool"]["display_name"] == "search_assets"
        assert event["tool"]["icon"] == "tool"
        assert event["tool"]["arguments"] == {"query": "stocks", "limit": 10}

    def test_write_tool_result_creates_event(self, tmp_path: Path) -> None:
        """write_tool_result creates tool.result event with result object."""
        journal = SessionJournalService(str(tmp_path))
        journal.write_tool_result(
            family_id="family123",
            session_id="session456",
            tool_id="tool789",
            success=True,
            execution_time_ms=150,
            error=None,
        )

        # Read the JSONL file
        jsonl_path = tmp_path / "family123" / "agent" / "_default" / "_shared" / "session456.jsonl"
        assert jsonl_path.exists()

        lines = jsonl_path.read_text().strip().split("\n")
        assert len(lines) == 1

        event = json.loads(lines[0])
        assert event["type"] == "tool.result"
        assert event["sessionId"] == "session456"
        assert event["familyId"] == "family123"
        assert event["actor"] == "tool"
        assert event["visibility"] == "public"

        # Payload is spread to top level
        assert event["tool_id"] == "tool789"
        assert "result" in event
        assert event["result"]["success"] is True
        assert event["result"]["execution_time_ms"] == 150
        assert event["result"]["error"] is None

    def test_write_tool_result_with_error(self, tmp_path: Path) -> None:
        """write_tool_result with error field creates correct event."""
        journal = SessionJournalService(str(tmp_path))
        journal.write_tool_result(
            family_id="family123",
            session_id="session456",
            tool_id="tool789",
            success=False,
            execution_time_ms=50,
            error="API timeout",
        )

        jsonl_path = tmp_path / "family123" / "agent" / "_default" / "_shared" / "session456.jsonl"
        event = json.loads(jsonl_path.read_text().strip())

        assert event["result"]["success"] is False
        assert event["result"]["error"] == "API timeout"

    def test_multiple_tool_events_append(self, tmp_path: Path) -> None:
        """Multiple tool events append to same JSONL file."""
        journal = SessionJournalService(str(tmp_path))
        journal.write_tool_call(
            family_id="family123",
            session_id="session456",
            tool_name="search",
            tool_id="tool1",
            arguments={},
        )
        journal.write_tool_result(
            family_id="family123",
            session_id="session456",
            tool_id="tool1",
            success=True,
            execution_time_ms=100,
        )
        journal.write_tool_call(
            family_id="family123",
            session_id="session456",
            tool_name="analyze",
            tool_id="tool2",
            arguments={},
        )

        jsonl_path = tmp_path / "family123" / "agent" / "_default" / "_shared" / "session456.jsonl"
        lines = jsonl_path.read_text().strip().split("\n")
        assert len(lines) == 3

        events = [json.loads(line) for line in lines]
        assert events[0]["type"] == "tool.call"
        assert events[1]["type"] == "tool.result"
        assert events[2]["type"] == "tool.call"

    def test_different_sessions_create_separate_files(self, tmp_path: Path) -> None:
        """Different sessions write to separate JSONL files."""
        journal = SessionJournalService(str(tmp_path))

        journal.write_tool_call(
            family_id="family123",
            session_id="sessionA",
            tool_name="search",
            tool_id="tool1",
            arguments={},
        )
        journal.write_tool_call(
            family_id="family123",
            session_id="sessionB",
            tool_name="search",
            tool_id="tool2",
            arguments={},
        )

        path_a = tmp_path / "family123" / "agent" / "_default" / "_shared" / "sessionA.jsonl"
        path_b = tmp_path / "family123" / "agent" / "_default" / "_shared" / "sessionB.jsonl"
        assert path_a.exists()
        assert path_b.exists()

        event_a = json.loads(path_a.read_text().strip())
        event_b = json.loads(path_b.read_text().strip())
        assert event_a["tool"]["id"] == "tool1"
        assert event_b["tool"]["id"] == "tool2"

    def test_payload_structure_matches_streaming_format(self, tmp_path: Path) -> None:
        """Journal payload structure matches streaming EventStreamBuilder format."""
        from apps.agent.services.stream_events import EventStreamBuilder

        journal = SessionJournalService(str(tmp_path))
        builder = EventStreamBuilder(capability_id="test", task_id="test")

        # Create streaming event
        stream_evt = builder.tool_call(
            tool_name="search",
            arguments={"query": "test"},
            display_name="Search",
            icon="🔍",
            tool_type="search",
        )

        # Create journal event
        journal.write_tool_call(
            family_id="family123",
            session_id="session456",
            tool_name="search",
            tool_id=stream_evt.payload["tool"]["id"],
            arguments={"query": "test"},
        )

        # Read journal event
        jsonl_path = tmp_path / "family123" / "agent" / "_default" / "_shared" / "session456.jsonl"
        journal_evt = json.loads(jsonl_path.read_text().strip())

        # Both should have "tool" object at payload level (streaming) / top level (journal)
        stream_payload = stream_evt.payload
        # Journal payload is spread to top level, so "tool" is directly in event

        # Both should have nested "tool" object structure
        assert "tool" in stream_payload
        assert "tool" in journal_evt

        # Key fields should match
        assert stream_payload["tool"]["id"] == journal_evt["tool"]["id"]
        assert stream_payload["tool"]["name"] == journal_evt["tool"]["name"]
        assert stream_payload["tool"]["arguments"] == journal_evt["tool"]["arguments"]


class TestSessionJournalPlanUpdate:
    """Tests for write_plan_update method (CR-9)."""

    def test_write_plan_update_creates_event(self, tmp_path: Path) -> None:
        """write_plan_update creates plan.update event with todos array."""
        journal = SessionJournalService(str(tmp_path))
        todos = [
            {"id": "todo-1", "content": "Query asset data", "status": "active"},
            {"id": "todo-2", "content": "Analyze results", "status": "pending"},
            {"id": "todo-3", "content": "Generate report", "status": "pending"},
        ]
        journal.write_plan_update(
            family_id="family123",
            session_id="session456",
            todos=todos,
        )

        jsonl_path = tmp_path / "family123" / "agent" / "_default" / "_shared" / "session456.jsonl"
        assert jsonl_path.exists()

        event = json.loads(jsonl_path.read_text().strip())
        assert event["type"] == "plan.update"
        assert event["sessionId"] == "session456"
        assert event["familyId"] == "family123"
        assert event["actor"] == "assistant"
        assert event["visibility"] == "public"
        assert "todos" in event
        assert len(event["todos"]) == 3
        assert event["todos"][0]["status"] == "active"

    def test_write_plan_update_empty_todos(self, tmp_path: Path) -> None:
        """write_plan_update with empty todos list still creates event."""
        journal = SessionJournalService(str(tmp_path))
        journal.write_plan_update(
            family_id="family123",
            session_id="session456",
            todos=[],
        )

        jsonl_path = tmp_path / "family123" / "agent" / "_default" / "_shared" / "session456.jsonl"
        event = json.loads(jsonl_path.read_text().strip())
        assert event["type"] == "plan.update"
        assert event["todos"] == []

    def test_write_plan_update_status_progression(self, tmp_path: Path) -> None:
        """write_plan_update can track status progression over time."""
        journal = SessionJournalService(str(tmp_path))

        # Initial plan
        todos_initial = [
            {"id": "todo-1", "content": "Step 1", "status": "active"},
            {"id": "todo-2", "content": "Step 2", "status": "pending"},
        ]
        journal.write_plan_update(
            family_id="family123",
            session_id="session456",
            todos=todos_initial,
        )

        # Progress update
        todos_progress = [
            {"id": "todo-1", "content": "Step 1", "status": "done"},
            {"id": "todo-2", "content": "Step 2", "status": "active"},
        ]
        journal.write_plan_update(
            family_id="family123",
            session_id="session456",
            todos=todos_progress,
        )

        jsonl_path = tmp_path / "family123" / "agent" / "_default" / "_shared" / "session456.jsonl"
        lines = jsonl_path.read_text().strip().split("\n")
        assert len(lines) == 2

        events = [json.loads(line) for line in lines]
        assert events[0]["todos"][0]["status"] == "active"
        assert events[1]["todos"][0]["status"] == "done"


class TestSessionJournalSubagentUpdate:
    """Tests for write_subagent_update method (CR-10)."""

    def test_write_subagent_update_running(self, tmp_path: Path) -> None:
        """write_subagent_update creates subagent.update event for running status."""
        journal = SessionJournalService(str(tmp_path))
        journal.write_subagent_update(
            family_id="family123",
            session_id="session456",
            task_id="task-001",
            status="running",
            title="Asset analysis",
            description="Processing asset data...",
        )

        jsonl_path = tmp_path / "family123" / "agent" / "_default" / "_shared" / "session456.jsonl"
        assert jsonl_path.exists()

        event = json.loads(jsonl_path.read_text().strip())
        assert event["type"] == "subagent.update"
        assert event["sessionId"] == "session456"
        assert event["familyId"] == "family123"
        assert event["actor"] == "assistant"
        assert event["visibility"] == "public"
        assert "subagent" in event
        assert event["subagent"]["taskId"] == "task-001"
        assert event["subagent"]["status"] == "running"
        assert event["subagent"]["title"] == "Asset analysis"
        assert event["subagent"]["description"] == "Processing asset data..."

    def test_write_subagent_update_done(self, tmp_path: Path) -> None:
        """write_subagent_update creates event for done status with result."""
        journal = SessionJournalService(str(tmp_path))
        journal.write_subagent_update(
            family_id="family123",
            session_id="session456",
            task_id="task-001",
            status="done",
            title="Asset analysis",
            result="Analysis complete: 5 assets found",
        )

        jsonl_path = tmp_path / "family123" / "agent" / "_default" / "_shared" / "session456.jsonl"
        event = json.loads(jsonl_path.read_text().strip())
        assert event["subagent"]["status"] == "done"
        assert event["subagent"]["result"] == "Analysis complete: 5 assets found"
        assert event["subagent"]["description"] is None

    def test_write_subagent_update_failed(self, tmp_path: Path) -> None:
        """write_subagent_update creates event for failed status with error."""
        journal = SessionJournalService(str(tmp_path))
        journal.write_subagent_update(
            family_id="family123",
            session_id="session456",
            task_id="task-001",
            status="failed",
            title="Asset analysis",
            error="Connection timeout",
        )

        jsonl_path = tmp_path / "family123" / "agent" / "_default" / "_shared" / "session456.jsonl"
        event = json.loads(jsonl_path.read_text().strip())
        assert event["subagent"]["status"] == "failed"
        assert event["subagent"]["error"] == "Connection timeout"

    def test_write_subagent_update_partial_fields(self, tmp_path: Path) -> None:
        """write_subagent_update accepts partial field updates."""
        journal = SessionJournalService(str(tmp_path))
        # Only status update
        journal.write_subagent_update(
            family_id="family123",
            session_id="session456",
            task_id="task-001",
            status="running",
        )

        jsonl_path = tmp_path / "family123" / "agent" / "_default" / "_shared" / "session456.jsonl"
        event = json.loads(jsonl_path.read_text().strip())
        assert event["subagent"]["taskId"] == "task-001"
        assert event["subagent"]["status"] == "running"
        assert event["subagent"]["title"] is None
        assert event["subagent"]["description"] is None

    def test_write_subagent_update_status_progression(self, tmp_path: Path) -> None:
        """write_subagent_update can track task status progression."""
        journal = SessionJournalService(str(tmp_path))

        # Start task
        journal.write_subagent_update(
            family_id="family123",
            session_id="session456",
            task_id="task-001",
            status="running",
            title="Analysis",
            description="Starting...",
        )

        # Complete task
        journal.write_subagent_update(
            family_id="family123",
            session_id="session456",
            task_id="task-001",
            status="done",
            result="Complete",
        )

        jsonl_path = tmp_path / "family123" / "agent" / "_default" / "_shared" / "session456.jsonl"
        lines = jsonl_path.read_text().strip().split("\n")
        assert len(lines) == 2

        events = [json.loads(line) for line in lines]
        assert events[0]["subagent"]["status"] == "running"
        assert events[1]["subagent"]["status"] == "done"