"""Tests for AITaskService zombie task lifecycle and thread_id resolution.

Test scenarios:
- get_zombie_running_tasks returns only running tasks without run_id
- get_zombie_running_tasks respects grace period (excludes recently-promoted)
- get_zombie_running_tasks scopes by family_id
- _try_promote_next cancels zombies before promoting queued tasks
- GET /ai/tasks?thread_id=<UUID> resolves UUID to session_id
- GET /ai/tasks?thread_id=<unknown> returns empty list
"""

from datetime import UTC, datetime, timedelta

import pytest

from apps.backend.app.services.ai_task_service import AITaskService
from packages.db.models.ai_task import AITask


@pytest.fixture
def family_id(auth_headers, client):
    """Get the family_id for the test user."""
    resp = client.get("/api/v1/auth/me", headers=auth_headers)
    return resp.json()["data"]["family_id"]


class TestGetZombieRunningTasks:
    """Test get_zombie_running_tasks query logic."""

    def test_returns_only_running_without_run_id(self, db, family_id):
        """Only tasks with status='running' AND run_id IS NULL are returned."""
        # Create a zombie (running, no run_id)
        zombie = AITask(
            family_id=family_id,
            skill_id="finance-coach",
            status="running",
            run_id=None,
            started_at=datetime.now(UTC) - timedelta(seconds=120),
        )
        db.add(zombie)

        # Create a healthy running task (has run_id)
        healthy = AITask(
            family_id=family_id,
            skill_id="narrative",
            status="running",
            run_id="some-run-id",
            started_at=datetime.now(UTC) - timedelta(seconds=120),
        )
        db.add(healthy)

        # Create a completed task (not running)
        completed = AITask(
            family_id=family_id,
            skill_id="asset-report",
            status="completed",
            run_id=None,
            started_at=datetime.now(UTC) - timedelta(seconds=120),
        )
        db.add(completed)
        db.commit()

        zombies = AITaskService.get_zombie_running_tasks(db, family_id)
        assert len(zombies) == 1
        assert zombies[0].id == zombie.id

    def test_grace_period_excludes_recent_tasks(self, db, family_id):
        """Tasks promoted within the grace period are excluded."""
        # Recent zombie (within 60s grace)
        recent = AITask(
            family_id=family_id,
            skill_id="finance-coach",
            status="running",
            run_id=None,
            started_at=datetime.now(UTC) - timedelta(seconds=30),
        )
        db.add(recent)

        # Old zombie (beyond 60s grace)
        old = AITask(
            family_id=family_id,
            skill_id="narrative",
            status="running",
            run_id=None,
            started_at=datetime.now(UTC) - timedelta(seconds=120),
        )
        db.add(old)
        db.commit()

        # Default grace_seconds=60 — only the old zombie should be returned
        zombies = AITaskService.get_zombie_running_tasks(db, family_id)
        assert len(zombies) == 1
        assert zombies[0].id == old.id

        # With grace_seconds=0, both should be returned
        all_zombies = AITaskService.get_zombie_running_tasks(
            db, family_id, grace_seconds=0,
        )
        assert len(all_zombies) == 2

    def test_family_id_scoping(self, db, family_id):
        """Zombies from other families are not returned."""
        other_family_zombie = AITask(
            family_id=int(family_id) + 99999,
            skill_id="finance-coach",
            status="running",
            run_id=None,
            started_at=datetime.now(UTC) - timedelta(seconds=120),
        )
        db.add(other_family_zombie)
        db.commit()

        zombies = AITaskService.get_zombie_running_tasks(db, family_id)
        assert len(zombies) == 0

        # Without family_id filter, the other family's zombie is visible
        all_zombies = AITaskService.get_zombie_running_tasks(db)
        assert len(all_zombies) == 1


class TestTryPromoteNextZombieCancellation:
    """Test _try_promote_next zombie cancellation path."""

    def test_cancels_zombies_then_promotes(self, db, family_id):
        """Zombies are cancelled before the next queued task is promoted."""
        # Create a zombie
        zombie = AITask(
            family_id=family_id,
            skill_id="finance-coach",
            status="running",
            run_id=None,
            started_at=datetime.now(UTC) - timedelta(seconds=120),
        )
        db.add(zombie)

        # Create a queued task
        queued = AITask(
            family_id=family_id,
            skill_id="narrative",
            status="queued",
            started_at=datetime.now(UTC),
        )
        db.add(queued)
        db.commit()

        AITaskService._try_promote_next(family_id, db)

        # Refresh from DB
        db.refresh(zombie)
        db.refresh(queued)

        assert zombie.status == "interrupted"
        assert zombie.error_message is not None
        assert queued.status == "running"

    def test_cancels_zombies_without_queued_task(self, db, family_id):
        """Zombies are cancelled even when no queued task exists."""
        zombie = AITask(
            family_id=family_id,
            skill_id="finance-coach",
            status="running",
            run_id=None,
            started_at=datetime.now(UTC) - timedelta(seconds=120),
        )
        db.add(zombie)
        db.commit()

        AITaskService._try_promote_next(family_id, db)

        db.refresh(zombie)
        assert zombie.status == "interrupted"


class TestThreadIdQueryParam:
    """Test GET /ai/tasks?thread_id=<UUID> resolution."""

    def test_thread_id_resolves_to_session(self, client, auth_headers, db, family_id):
        """thread_id query param resolves UUID to session_id and returns tasks."""
        from apps.backend.app.models.ai_chat_session import AIChatSession

        # Create a session with a known thread_id
        session = AIChatSession(family_id=family_id, thread_id="test-thread-uuid-123")
        db.add(session)
        db.flush()

        # Create a task linked to that session
        task = AITask(
            family_id=family_id,
            skill_id="chat",
            session_id=session.id,
            status="completed",
            started_at=datetime.now(UTC),
        )
        db.add(task)
        db.commit()

        resp = client.get(
            "/api/v1/ai/tasks",
            params={"thread_id": "test-thread-uuid-123", "skill_id": "chat"},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        body = resp.json()
        # Response may be wrapped in envelope or raw list
        data = body.get("data", body) if isinstance(body, dict) else body
        assert len(data) >= 1
        assert any(t["id"] == str(task.id) for t in data)

    def test_unknown_thread_id_returns_empty(self, client, auth_headers):
        """Unknown thread_id returns an empty list."""
        resp = client.get(
            "/api/v1/ai/tasks",
            params={"thread_id": "nonexistent-uuid"},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        body = resp.json()
        data = body.get("data", body) if isinstance(body, dict) else body
        assert data == []
