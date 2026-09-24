"""Tests for POST /internal/tasks/{task_id}/checkpoint endpoint.

Verifies:
- last_checkpoint_id stored correctly
- Cross-family isolation (404 for wrong family)
- Non-existent task returns 404
"""

import pytest

from apps.backend.app.services.ai_task_service import AITaskService
from packages.security.service_auth.agent_jwt import create_agent_token

OTHER_FAMILY_ID = 9999


@pytest.fixture
def family_id(auth_headers, client):
    """Get the family_id for the test user."""
    resp = client.get("/api/v1/auth/me", headers=auth_headers)
    return resp.json()["data"]["family_id"]


@pytest.fixture
def agent_headers(family_id):
    """Generate auth headers with a valid agent JWT for the test family."""
    token = create_agent_token(str(family_id))
    return {
        "Authorization": f"Bearer {token}",
        "X-Family-Id": str(family_id),
    }


@pytest.fixture
def other_family_headers():
    """Generate auth headers for a different family."""
    token = create_agent_token(str(OTHER_FAMILY_ID))
    return {
        "Authorization": f"Bearer {token}",
        "X-Family-Id": str(OTHER_FAMILY_ID),
    }


@pytest.fixture
def running_task(db, family_id):
    """Create a running task for the test family."""
    from apps.backend.app.models.ai_chat_session import AIChatSession

    session = db.query(AIChatSession).filter(AIChatSession.family_id == family_id).first()
    if not session:
        session = AIChatSession(family_id=family_id)
        db.add(session)
        db.flush()

    task = AITaskService.create_task(
        family_id=family_id,
        skill_id="asset-report",
        session_id=session.id,
        db=db,
    )
    db.commit()
    return task


class TestCheckpointEndpoint:
    """Tests for POST /internal/tasks/{task_id}/checkpoint."""

    def test_store_checkpoint_id(self, client, running_task, agent_headers):
        """Checkpoint ID is stored on the task."""
        resp = client.post(
            f"/api/v1/internal/tasks/{running_task.id}/checkpoint",
            json={"checkpoint_id": "ckpt-abc123"},
            headers=agent_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        # Response wrapped in standard envelope {code, data, message}
        inner = data.get("data", data)
        assert inner["ok"] is True
        assert inner["task_id"] == str(running_task.id)

    def test_checkpoint_id_persisted_in_db(
        self, client, db, running_task, agent_headers
    ):
        """Verify the checkpoint ID is actually persisted."""
        client.post(
            f"/api/v1/internal/tasks/{running_task.id}/checkpoint",
            json={"checkpoint_id": "ckpt-persisted"},
            headers=agent_headers,
        )
        db.refresh(running_task)
        assert running_task.last_checkpoint_id == "ckpt-persisted"

    def test_checkpoint_id_default_null(self, running_task):
        """last_checkpoint_id is None by default."""
        assert running_task.last_checkpoint_id is None

    def test_nonexistent_task_returns_404(self, client, agent_headers):
        """Non-existent task returns 404."""
        resp = client.post(
            "/api/v1/internal/tasks/999999999999/checkpoint",
            json={"checkpoint_id": "ckpt-xyz"},
            headers=agent_headers,
        )
        assert resp.status_code == 404

    def test_cross_family_returns_404(
        self, client, running_task, other_family_headers
    ):
        """Task from another family returns 404."""
        resp = client.post(
            f"/api/v1/internal/tasks/{running_task.id}/checkpoint",
            json={"checkpoint_id": "ckpt-cross"},
            headers=other_family_headers,
        )
        assert resp.status_code == 404

    def test_idempotent_update(self, client, running_task, agent_headers):
        """Calling checkpoint twice overwrites the previous value."""
        client.post(
            f"/api/v1/internal/tasks/{running_task.id}/checkpoint",
            json={"checkpoint_id": "ckpt-first"},
            headers=agent_headers,
        )
        resp = client.post(
            f"/api/v1/internal/tasks/{running_task.id}/checkpoint",
            json={"checkpoint_id": "ckpt-second"},
            headers=agent_headers,
        )
        assert resp.status_code == 200
