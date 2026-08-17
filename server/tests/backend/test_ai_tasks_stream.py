"""Tests for GET /ai/tasks/detail/{task_id}/stream — v3 subscribe-only SSE endpoint.

Test scenarios:
- Completed task → cached result emitted via SSE
- Failed task → error event emitted
- Cross-family task → 404
- Non-existent task → 404
- Running task → SSE stream with mocked bridge events
- Connection cap → 429 when family exceeds 3 concurrent SSE connections
"""

import json
from unittest.mock import patch

import pytest

from apps.backend.app.services.ai_task_service import AITaskService


@pytest.fixture
def family_id(auth_headers, client):
    """Get the family_id for the test user."""
    resp = client.get("/api/v1/auth/me", headers=auth_headers)
    return resp.json()["data"]["family_id"]


@pytest.fixture
def completed_narrative_task(db, family_id):
    """Create a completed narrative task with cached result."""
    from apps.backend.app.models.ai_chat_session import AIChatSession
    from apps.backend.app.services.finance_coach_cache import upsert_skill_result

    session = db.query(AIChatSession).filter(AIChatSession.family_id == family_id).first()
    if not session:
        session = AIChatSession(family_id=family_id)
        db.add(session)
        db.flush()

    task = AITaskService.create_task(
        family_id=family_id,
        skill_id="narrative",
        session_id=session.id,
        db=db,
    )
    task.status = "completed"
    task.run_id = "test-run-id-narrative"

    # Cache a narrative result
    upsert_skill_result(db, family_id, "narrative", {"narrative": "测试月度报告内容"})

    db.commit()
    return task


@pytest.fixture
def completed_coach_task(db, family_id):
    """Create a completed coach task with cached result."""
    from apps.backend.app.models.ai_chat_session import AIChatSession
    from apps.backend.app.services.finance_coach_cache import upsert_skill_result

    session = db.query(AIChatSession).filter(AIChatSession.family_id == family_id).first()
    if not session:
        session = AIChatSession(family_id=family_id)
        db.add(session)
        db.flush()

    task = AITaskService.create_task(
        family_id=family_id,
        skill_id="coach",
        session_id=session.id,
        db=db,
    )
    task.status = "completed"
    task.run_id = "test-run-id-coach"

    upsert_skill_result(db, family_id, "finance_coach", {"advice": "建议减少非必要开支"})

    db.commit()
    return task


@pytest.fixture
def failed_task(db, family_id):
    """Create a failed task with error message."""
    from apps.backend.app.models.ai_chat_session import AIChatSession

    session = db.query(AIChatSession).filter(AIChatSession.family_id == family_id).first()
    if not session:
        session = AIChatSession(family_id=family_id)
        db.add(session)
        db.flush()

    task = AITaskService.create_task(
        family_id=family_id,
        skill_id="narrative",
        session_id=session.id,
        db=db,
    )
    task.status = "failed"
    task.error_message = "AI 服务异常"
    task.run_id = "test-run-id-failed"
    db.commit()
    return task


@pytest.fixture
def completed_literacy_task(client, auth_headers, db, family_id):
    """Create a completed literacy task with a persisted weekly report."""
    from datetime import date

    from apps.backend.app.models.ai_chat_session import AIChatSession
    from packages.db.models.literacy_report import LiteracyWeeklyReport

    # Get the test user (parent) id to derive a child in the same family
    resp = client.get("/api/v1/auth/me", headers=auth_headers)
    user_id = resp.json()["data"]["id"]

    report = LiteracyWeeklyReport(
        child_id=user_id,  # user doubles as the child row for the join test
        week_start=date(2026, 8, 16),
        report_json='{"week_start": "2026-08-16"}',
        narrative="本周理财小结",
    )
    db.add(report)

    session = db.query(AIChatSession).filter(AIChatSession.family_id == family_id).first()
    if not session:
        session = AIChatSession(family_id=family_id)
        db.add(session)
        db.flush()

    task = AITaskService.create_task(
        family_id=family_id,
        skill_id="literacy",
        session_id=session.id,
        db=db,
    )
    task.status = "completed"
    task.run_id = "test-run-id-literacy"
    db.commit()
    return task


@pytest.fixture
def running_task(db, family_id):
    """Create a running task (active, with run_id)."""
    from apps.backend.app.models.ai_chat_session import AIChatSession

    session = db.query(AIChatSession).filter(AIChatSession.family_id == family_id).first()
    if not session:
        session = AIChatSession(family_id=family_id)
        db.add(session)
        db.flush()

    task = AITaskService.create_task(
        family_id=family_id,
        skill_id="narrative",
        session_id=session.id,
        db=db,
    )
    task.run_id = "test-run-id-running"
    db.commit()
    return task


class TestStreamTaskEventsTerminalStates:
    """Test SSE stream endpoint for tasks in terminal states."""

    def test_completed_narrative_task_emits_result(
        self, client, auth_headers, completed_narrative_task
    ):
        """Completed narrative task → SSE emits result event with cached narrative."""
        resp = client.get(
            f"/api/v1/ai/tasks/detail/{completed_narrative_task.id}/stream",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert "text/event-stream" in resp.headers.get("content-type", "")

        content = resp.text
        # Should contain a result event
        assert "event: result" in content
        # Find the result data
        for line in content.split("\n"):
            if line.startswith("data: ") and line != "data: null":
                try:
                    data = json.loads(line[len("data: "):])
                    if "narrative" in data:
                        assert data["narrative"] == "测试月度报告内容"
                except json.JSONDecodeError:
                    pass

        # Should end with end event
        assert "event: end" in content

    def test_completed_coach_task_emits_result(
        self, client, auth_headers, completed_coach_task
    ):
        """Completed coach task → SSE emits result event with cached JSON."""
        resp = client.get(
            f"/api/v1/ai/tasks/detail/{completed_coach_task.id}/stream",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        content = resp.text
        assert "event: result" in content
        assert "event: end" in content

    def test_completed_literacy_task_emits_report_via_family_join(
        self, client, auth_headers, completed_literacy_task
    ):
        """Completed literacy task -> result via users.family_id join (no family_id col)."""
        resp = client.get(
            f"/api/v1/ai/tasks/detail/{completed_literacy_task.id}/stream",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        content = resp.text
        assert "event: result" in content
        # The narrative from the joined LiteracyWeeklyReport must be in the result
        found = False
        for line in content.split("\n"):
            if line.startswith("data: ") and "report" in line:
                try:
                    data = json.loads(line[len("data: "):])
                    if data.get("report", {}).get("narrative") == "本周理财小结":
                        found = True
                except json.JSONDecodeError:
                    pass
        assert found, "literacy report narrative not found in SSE result"

    def test_failed_task_emits_error(self, client, auth_headers, failed_task):
        """Failed task → SSE emits error event with error_message."""
        resp = client.get(
            f"/api/v1/ai/tasks/detail/{failed_task.id}/stream",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        content = resp.text
        assert "event: error" in content
        # JSON may unicode-escape Chinese chars, so parse the data field
        for line in content.split("\n"):
            if line.startswith("data: ") and line != "data: null":
                try:
                    data = json.loads(line[len("data: "):])
                    if "error" in data:
                        assert data["error"] == "AI 服务异常"
                except json.JSONDecodeError:
                    pass
        assert "event: end" in content


class TestStreamTaskEventsAccessControl:
    """Test tenant isolation and access control."""

    def test_nonexistent_task_returns_404(self, client, auth_headers):
        """Task that doesn't exist → 404."""
        resp = client.get(
            "/api/v1/ai/tasks/detail/9999999999999/stream",
            headers=auth_headers,
        )
        # 404 via AppError → error envelope
        assert resp.status_code == 404

    def test_cross_family_task_returns_404(
        self, client, auth_headers, second_user_headers, db
    ):
        """Task belonging to a different family → 404 (tenant isolation)."""
        from apps.backend.app.models.ai_chat_session import AIChatSession

        # Get the second user's family_id
        resp = client.get("/api/v1/auth/me", headers=second_user_headers)
        other_family_id = resp.json()["data"]["family_id"]

        session = AIChatSession(family_id=other_family_id)
        db.add(session)
        db.flush()

        task = AITaskService.create_task(
            family_id=other_family_id,
            skill_id="narrative",
            session_id=session.id,
            db=db,
        )
        task.status = "completed"
        db.commit()

        # First user should NOT be able to access this task
        resp = client.get(
            f"/api/v1/ai/tasks/detail/{task.id}/stream",
            headers=auth_headers,
        )
        assert resp.status_code == 404


class TestStreamTaskEventsActiveTask:
    """Test SSE stream for active (running) tasks."""

    def test_running_task_subscribes_to_stream(
        self, client, auth_headers, running_task
    ):
        """Running task → SSE stream with bridge events."""
        async def mock_consume_task_stream(*args, **kwargs):
            yield "event: custom\ndata: {\"type\": \"thinking\", \"content\": \"分析中...\"}\n\n"
            yield "event: end\ndata: null\n\n"

        with patch(
            "apps.backend.app.services.bridge_consumer.consume_task_stream",
            side_effect=mock_consume_task_stream,
        ):
            resp = client.get(
                f"/api/v1/ai/tasks/detail/{running_task.id}/stream",
                headers=auth_headers,
            )
            assert resp.status_code == 200
            content = resp.text
            assert "event: custom" in content
            assert "分析中" in content

    def test_running_task_without_run_id_returns_404(
        self, client, auth_headers, db, family_id
    ):
        """Running task without run_id → 404 (agent hasn't started yet)."""
        from apps.backend.app.models.ai_chat_session import AIChatSession

        session = db.query(AIChatSession).filter(AIChatSession.family_id == family_id).first()
        if not session:
            session = AIChatSession(family_id=family_id)
            db.add(session)
            db.flush()

        task = AITaskService.create_task(
            family_id=family_id,
            skill_id="coach",
            session_id=session.id,
            db=db,
        )
        # task.run_id is None by default
        db.commit()

        resp = client.get(
            f"/api/v1/ai/tasks/detail/{task.id}/stream",
            headers=auth_headers,
        )
        assert resp.status_code == 404


class TestConnectionCap:
    """Test F7: per-family concurrent SSE connection cap."""

    def test_connection_cap_enforced(self, client, auth_headers, running_task):
        """4th concurrent SSE connection for same family → 429."""
        from apps.backend.app.routers.ai_tasks import _active_sse_connections

        family_id = running_task.family_id

        async def mock_stream(*args, **kwargs):
            yield "event: end\ndata: null\n\n"

        # Simulate 3 active connections
        _active_sse_connections[family_id] = 3

        try:
            with patch(
                "apps.backend.app.services.bridge_consumer.consume_task_stream",
                side_effect=mock_stream,
            ):
                resp = client.get(
                    f"/api/v1/ai/tasks/detail/{running_task.id}/stream",
                    headers=auth_headers,
                )
                # Should be rate-limited
                assert resp.status_code == 429
        finally:
            # Clean up
            _active_sse_connections.pop(family_id, None)
