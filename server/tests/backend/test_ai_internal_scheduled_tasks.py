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

    family = Family(id=1001, name="Test", created_by=2001, ai_enabled=True)
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

        mock_response = AsyncMock()
        mock_response.status_code = 200

        with patch(
            "apps.backend.app.services.agent_client.AgentClient"
        ) as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
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
        # The worker only reads the status code, so a swallowed agent error would
        # otherwise look identical to a real dispatch.
        assert data["triggered"] == 1

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
        mock_response = AsyncMock()
        mock_response.status_code = 200

        with patch(
            "apps.backend.app.services.agent_client.AgentClient"
        ) as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
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


    def test_ai_disabled_family_returns_403(self, client, _seed_task, db):
        """A family with AI disabled cannot have scheduled tasks dispatched."""
        from apps.backend.app.models.family import Family

        task = _seed_task["task"]
        family = db.query(Family).filter(Family.id == 1001).first()
        family.ai_enabled = False
        db.commit()

        response = client.post(
            BASE,
            headers=_system_headers(),
            json={"task_id": task.id},
        )

        assert response.status_code == 403

    def test_agent_gateway_non_2xx_returns_502(self, client, _seed_task):
        """A gateway 409/5xx must not silently report success to the worker."""
        from fastapi.testclient import TestClient

        from apps.backend.app.main import app

        task = _seed_task["task"]

        bad_response = AsyncMock()
        bad_response.status_code = 409
        bad_response.text = "Conflict: task already running"

        with patch(
            "apps.backend.app.services.agent_client.AgentClient"
        ) as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=bad_response)
            mock_client_cls.return_value = mock_client

            with TestClient(app, raise_server_exceptions=False) as raw_client:
                response = raw_client.post(
                    BASE,
                    headers=_system_headers(),
                    json={"task_id": task.id},
                )

        assert response.status_code == 502
        assert response.json()["code"] == "SCHEDULED_TASK_EXECUTE_FAILED"

    def test_agent_failure_returns_502_and_fails_the_task(self, client, _seed_task, db):
        """A failed agent dispatch must not report success, and must not strand rows.

        The worker treats HTTP 200 as success and advances the schedule, so a
        swallowed gateway error would mark the task successful while nothing ran.
        The AITask and its chat session are committed before the dispatch, so the
        failure path has to close them out too.
        """
        from fastapi.testclient import TestClient

        from apps.backend.app.main import app
        from packages.db.models.ai_task import AITask

        task = _seed_task["task"]

        with patch(
            "apps.backend.app.services.agent_client.AgentClient"
        ) as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(side_effect=RuntimeError("gateway down"))
            mock_client_cls.return_value = mock_client

            with TestClient(app, raise_server_exceptions=False) as raw_client:
                response = raw_client.post(
                    BASE,
                    headers=_system_headers(),
                    json={"task_id": task.id},
                )

        assert response.status_code == 502
        assert response.json()["code"] == "SCHEDULED_TASK_EXECUTE_FAILED"

        # No AITask may be left 'running' with no agent run behind it.
        ai_task = (
            db.query(AITask)
            .filter(AITask.family_id == _seed_task["family"].id)
            .first()
        )
        assert ai_task is not None
        assert ai_task.status == "failed"
        assert ai_task.completed_at is not None
        assert ai_task.error_message == "agent trigger failed: RuntimeError"


@pytest.fixture()
def _seed_literacy_task(db, _seed_task):
    """Switch the seeded task to the literacy skill and add two children."""
    import bcrypt

    from apps.backend.app.models.user import User
    from packages.db.models.scheduled_task import ScheduledTask

    family_id = _seed_task["family"].id

    for child_id, name in ((3001, "kid-a"), (3002, "kid-b")):
        db.add(
            User(
                id=child_id,
                family_id=family_id,
                username=name,
                display_name=name,
                password_hash=bcrypt.hashpw(b"pass", bcrypt.gensalt(rounds=4)).decode(),
                role="child",
            )
        )
    db.flush()

    task = db.query(ScheduledTask).filter(ScheduledTask.id == _seed_task["task"].id).first()
    task.skill_id = "literacy-weekly-report"
    db.commit()
    db.refresh(task)

    return {**_seed_task, "task": task}


def _patch_literacy(return_value=None, side_effect=None):
    """Patch generate_literacy_report at its definition site."""
    return patch(
        "apps.backend.app.services.literacy_report_service.generate_literacy_report",
        new=AsyncMock(return_value=return_value, side_effect=side_effect),
    )


class TestExecuteLiteracyReport:
    """The second schedulable skill had no coverage at all.

    Its failures are silent to the worker (which only reads the HTTP status),
    so a broken dispatch here would mark the task successful while nothing ran.
    """

    def test_all_children_generated_returns_count(self, client, _seed_literacy_task):
        task = _seed_literacy_task["task"]
        report = object()

        with _patch_literacy(return_value=report):
            response = client.post(
                BASE,
                headers=_system_headers(),
                json={"task_id": task.id},
            )

        assert response.status_code == 200
        data = _body(response)
        assert data["skill_id"] == "literacy-weekly-report"
        assert data["triggered"] == 2

    def test_partial_failure_returns_partial_count(self, client, _seed_literacy_task):
        """One child raising must not turn the whole dispatch into a failure."""
        task = _seed_literacy_task["task"]
        calls = {"n": 0}

        async def _side_effect(*args, **kwargs):
            calls["n"] += 1
            if calls["n"] == 1:
                raise RuntimeError("child boom")
            return object()

        with _patch_literacy(side_effect=_side_effect):
            response = client.post(
                BASE,
                headers=_system_headers(),
                json={"task_id": task.id},
            )

        assert response.status_code == 200
        data = _body(response)
        assert data["triggered"] == 1

    def test_no_active_children_returns_zero(self, client, db, _seed_task):
        """A family with no children is not an error — nothing to generate."""
        from packages.db.models.scheduled_task import ScheduledTask

        task = db.query(ScheduledTask).filter(ScheduledTask.id == _seed_task["task"].id).first()
        task.skill_id = "literacy-weekly-report"
        db.commit()
        db.refresh(task)

        with _patch_literacy(return_value=object()) as mock_gen:
            response = client.post(
                BASE,
                headers=_system_headers(),
                json={"task_id": task.id},
            )

        assert response.status_code == 200
        assert _body(response)["triggered"] == 0
        mock_gen.assert_not_awaited()

    def test_all_children_failing_returns_502(self, client, _seed_literacy_task):
        """Every child failing must surface as SCHEDULED_TASK_EXECUTE_FAILED.

        Returning 200 here would make the worker advance the schedule and mark
        the task successful with no report generated for anyone.
        """
        from fastapi.testclient import TestClient

        from apps.backend.app.main import app

        task = _seed_literacy_task["task"]

        with _patch_literacy(side_effect=RuntimeError("boom")), TestClient(
            app, raise_server_exceptions=False
        ) as raw_client:
            response = raw_client.post(
                BASE,
                headers=_system_headers(),
                json={"task_id": task.id},
            )

        assert response.status_code == 502
        assert response.json()["code"] == "SCHEDULED_TASK_EXECUTE_FAILED"

    def test_generated_report_none_counts_as_failure(self, client, _seed_literacy_task):
        """``None`` from the service means it produced nothing, not success."""
        from fastapi.testclient import TestClient

        from apps.backend.app.main import app

        task = _seed_literacy_task["task"]

        with _patch_literacy(return_value=None), TestClient(
            app, raise_server_exceptions=False
        ) as raw_client:
            response = raw_client.post(
                BASE,
                headers=_system_headers(),
                json={"task_id": task.id},
            )

        assert response.status_code == 502
