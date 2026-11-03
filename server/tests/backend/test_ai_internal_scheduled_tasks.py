"""Tests for the internal scheduled-task execute endpoint (U3).

Covers the worker-to-backend dispatch contract: system token auth, task lookup,
skill_id read from DB (not request body), and per-skill dispatch logic.
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest

from packages.db.models.scheduled_task import ScheduledTask
from packages.security.service_auth.agent_jwt import create_system_token

BASE = "/api/v1/internal/ai/scheduled-tasks/execute"


def _system_headers() -> dict:
    return {"Authorization": f"Bearer {create_system_token()}"}


def _body(resp):
    body = resp.json()
    return body.get("data") if body.get("data") is not None else body


@pytest.fixture()
def _seed_task(db):
    """Create a family + task for execute tests."""
    import bcrypt

    from apps.backend.app.models.family import Family
    from apps.backend.app.models.user import User

    family = Family(id=1001, name="Test", created_by=2001)
    db.add(family)
    db.flush()

    owner = User(
        id=2001,
        family_id=family.id,
        username="owner",
        display_name="Owner",
        password_hash=bcrypt.hashpw(b"pass", bcrypt.gensalt(rounds=4)).decode(),
        role="owner",
    )
    db.add(owner)
    db.flush()

    task = ScheduledTask(
        family_id=family.id,
        skill_id="asset-report",
        cron_expression="0 9 * * *",
        is_enabled=True,
        next_run_at=datetime.now(UTC),
        status="idle",
    )
    db.add(task)
    db.commit()
    db.refresh(task)

    return {"family": family, "owner": owner, "task": task}


class TestExecuteScheduledTask:
    def test_valid_asset_report_task_triggers_agent(self, client, _seed_task):
        task = _seed_task["task"]

        with patch(
            "apps.backend.app.services.agent_client.AgentClient"
        ) as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock()
            mock_client_cls.return_value = mock_client

            response = client.post(
                BASE,
                headers=_system_headers(),
                json={"task_id": task.id},
            )

        assert response.status_code == 200
        data = _body(response)
        assert data["status"] == "triggered"
        assert data["skill_id"] == "asset-report"

        # AgentClient was instantiated with the correct family_id and owner.
        mock_client_cls.assert_called_once_with(
            _seed_task["family"].id, _seed_task["owner"].id, timeout=30.0
        )
        # POST was called to the asset-report gateway route.
        mock_client.post.assert_called_once()
        call_args = mock_client.post.call_args
        assert "/internal/gateway/runs/asset-report/" in call_args.args[0]

    def test_invalid_task_id_returns_404(self, client):
        response = client.post(
            BASE,
            headers=_system_headers(),
            json={"task_id": 999999999},
        )

        assert response.status_code == 404

    def test_disabled_task_returns_400(self, client, _seed_task, db):
        task = _seed_task["task"]
        task.is_enabled = False
        db.commit()
        db.refresh(task)

        response = client.post(
            BASE,
            headers=_system_headers(),
            json={"task_id": task.id},
        )

        assert response.status_code == 400

    def test_invalid_system_token_returns_401(self, client, _seed_task):
        task = _seed_task["task"]

        response = client.post(
            BASE,
            headers={"Authorization": "Bearer invalid-token"},
            json={"task_id": task.id},
        )

        assert response.status_code == 401

    def test_cannot_override_skill_id_via_body(self, client, _seed_task):
        task = _seed_task["task"]

        # Even if the caller tries to inject a different skill_id, the endpoint
        # must read it from the DB row, not the request body.
        with patch(
            "apps.backend.app.services.agent_client.AgentClient"
        ) as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock()
            mock_client_cls.return_value = mock_client

            response = client.post(
                BASE,
                headers=_system_headers(),
                json={"task_id": task.id, "skill_id": "finance-coach"},
            )

        assert response.status_code == 200
        # The dispatched skill_id must match the DB row (asset-report), not the
        # injected value (finance-coach).
        data = _body(response)
        assert data["skill_id"] == "asset-report"
