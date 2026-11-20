"""Tests for the scheduled-task CRUD API.

Covers the owner-only access contract, skill allowlisting, cron validation and
the timezone rule that a cron expression typed by the owner is interpreted in
Asia/Shanghai while ``next_run_at`` is returned (and stored) as UTC.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

BASE = "/api/v1/ai/scheduled-tasks"


def _body(resp):
    body = resp.json()
    return body.get("data") if body.get("data") is not None else body


@pytest.fixture()
def member_headers(client, auth_headers, db):
    """Headers for a non-owner adult in the same family as auth_headers."""
    import bcrypt

    from apps.backend.app.models.user import User

    me = client.get("/api/v1/auth/me", headers=auth_headers).json()
    me = me.get("data", me)

    member = User(
        family_id=int(me["family_id"]),
        username="sched_member",
        display_name="成员",
        password_hash=bcrypt.hashpw(b"MemberPass123", bcrypt.gensalt(rounds=4)).decode(),
        role="member",
    )
    db.add(member)
    db.flush()

    token = client.post(
        "/api/v1/auth/login",
        json={"username": "sched_member", "password": "MemberPass123"},
    ).json()
    token = token.get("data", token)
    return {"Authorization": f"Bearer {token['access_token']}"}


@pytest.fixture()
def _clear_defaults(db, auth_headers):
    """Remove the default scheduled tasks seeded at family registration.

    Depends on auth_headers so registration (which seeds defaults) runs first.
    """
    from packages.db.models.scheduled_task import ScheduledTask

    db.query(ScheduledTask).delete()
    db.commit()


@pytest.mark.usefixtures("_clear_defaults")
class TestCreateScheduledTask:
    def test_creates_daily_task_with_utc_next_run(self, client, auth_headers):
        response = client.post(
            BASE,
            headers=auth_headers,
            json={"skill_id": "asset-report", "cron_expression": "0 9 * * *"},
        )

        assert response.status_code == 201
        data = _body(response)
        assert data["skill_id"] == "asset-report"
        assert data["cron_expression"] == "0 9 * * *"
        assert data["is_enabled"] is True
        assert data["status"] == "idle"
        assert data["last_run_at"] is None

        # cron is interpreted in Asia/Shanghai: the stored instant must be 01:00 UTC.
        next_run = datetime.fromisoformat(data["next_run_at"])
        assert next_run.tzinfo is not None
        assert next_run.astimezone(UTC).hour == 1
        assert next_run.astimezone(UTC).minute == 0

    def test_rejects_skill_outside_allowlist(self, client, auth_headers):
        response = client.post(
            BASE,
            headers=auth_headers,
            json={"skill_id": "finance-coach", "cron_expression": "0 9 * * *"},
        )

        assert response.status_code == 400
        assert _body(response)["code"] == "SCHEDULED_TASK_SKILL_INVALID"

    @pytest.mark.parametrize(
        "expression",
        ["0 9 * *", "not a cron", "0 25 * * *", "", "0 9 * * * *", "@daily"],
    )
    def test_rejects_invalid_cron(self, client, auth_headers, expression):
        response = client.post(
            BASE,
            headers=auth_headers,
            json={"skill_id": "asset-report", "cron_expression": expression},
        )

        assert response.status_code == 400
        assert _body(response)["code"] == "SCHEDULED_TASK_CRON_INVALID"

    def test_non_owner_cannot_create(self, client, member_headers):
        response = client.post(
            BASE,
            headers=member_headers,
            json={"skill_id": "asset-report", "cron_expression": "0 9 * * *"},
        )

        assert response.status_code == 403


@pytest.mark.usefixtures("_clear_defaults")
class TestListScheduledTasks:
    def test_empty_initially(self, client, auth_headers):
        response = client.get(BASE, headers=auth_headers)

        assert response.status_code == 200
        assert _body(response)["items"] == []

    def test_returns_created_tasks(self, client, auth_headers):
        client.post(
            BASE,
            headers=auth_headers,
            json={"skill_id": "asset-report", "cron_expression": "0 9 * * *"},
        )
        client.post(
            BASE,
            headers=auth_headers,
            json={
                "skill_id": "literacy-weekly-report",
                "cron_expression": "0 9 * * 0",
            },
        )

        response = client.get(BASE, headers=auth_headers)

        assert response.status_code == 200
        items = _body(response)["items"]
        assert len(items) == 2
        assert {i["skill_id"] for i in items} == {
            "asset-report",
            "literacy-weekly-report",
        }

    def test_scoped_to_callers_family(self, client, auth_headers, second_user_headers):
        """Custom tasks created by one family are not visible to another family."""
        client.post(
            BASE,
            headers=auth_headers,
            json={"skill_id": "asset-report", "cron_expression": "0 9 * * *"},
        )

        response = client.get(BASE, headers=second_user_headers)

        assert response.status_code == 200
        items = _body(response)["items"]
        # Second family has defaults seeded at registration, but not the custom task
        # created by the first family. Verify no custom (is_default=False) tasks.
        custom_tasks = [i for i in items if not i.get("is_default", True)]
        assert custom_tasks == []

    def test_non_owner_cannot_list(self, client, member_headers):
        response = client.get(BASE, headers=member_headers)

        assert response.status_code == 403


@pytest.mark.usefixtures("_clear_defaults")
class TestUpdateScheduledTask:
    def test_updates_cron_and_recomputes_next_run(self, client, auth_headers):
        created = _body(
            client.post(
                BASE,
                headers=auth_headers,
                json={"skill_id": "asset-report", "cron_expression": "0 9 * * *"},
            )
        )
        original_next_run = created["next_run_at"]

        response = client.put(
            f"{BASE}/{created['id']}",
            headers=auth_headers,
            json={"cron_expression": "0 21 * * *"},
        )

        assert response.status_code == 200
        data = _body(response)
        assert data["cron_expression"] == "0 21 * * *"
        # 21:00 Beijing == 13:00 UTC
        updated_next_run = datetime.fromisoformat(data["next_run_at"])
        assert updated_next_run.astimezone(UTC).hour == 13
        assert data["next_run_at"] != original_next_run

    def test_toggling_enabled_keeps_schedule(self, client, auth_headers):
        created = _body(
            client.post(
                BASE,
                headers=auth_headers,
                json={"skill_id": "asset-report", "cron_expression": "0 9 * * *"},
            )
        )

        response = client.put(
            f"{BASE}/{created['id']}",
            headers=auth_headers,
            json={"is_enabled": False},
        )

        assert response.status_code == 200
        data = _body(response)
        assert data["is_enabled"] is False
        assert data["next_run_at"] == created["next_run_at"]

    def test_rejects_invalid_cron_on_update(self, client, auth_headers):
        created = _body(
            client.post(
                BASE,
                headers=auth_headers,
                json={"skill_id": "asset-report", "cron_expression": "0 9 * * *"},
            )
        )

        response = client.put(
            f"{BASE}/{created['id']}",
            headers=auth_headers,
            json={"cron_expression": "bogus"},
        )

        assert response.status_code == 400
        assert _body(response)["code"] == "SCHEDULED_TASK_CRON_INVALID"

    def test_unknown_task_returns_404(self, client, auth_headers):
        response = client.put(
            f"{BASE}/999999999",
            headers=auth_headers,
            json={"is_enabled": False},
        )

        assert response.status_code == 404

    def test_cannot_update_other_familys_task(
        self, client, auth_headers, second_user_headers
    ):
        created = _body(
            client.post(
                BASE,
                headers=auth_headers,
                json={"skill_id": "asset-report", "cron_expression": "0 9 * * *"},
            )
        )

        response = client.put(
            f"{BASE}/{created['id']}",
            headers=second_user_headers,
            json={"is_enabled": False},
        )

        # Cross-family access surfaces as 404, not 403 — it must not confirm the
        # task id exists in another family.
        assert response.status_code == 404

    def test_non_owner_cannot_update(self, client, auth_headers, member_headers):
        created = _body(
            client.post(
                BASE,
                headers=auth_headers,
                json={"skill_id": "asset-report", "cron_expression": "0 9 * * *"},
            )
        )

        response = client.put(
            f"{BASE}/{created['id']}",
            headers=member_headers,
            json={"is_enabled": False},
        )

        assert response.status_code == 403


@pytest.mark.usefixtures("_clear_defaults")
class TestDeleteScheduledTask:
    def test_deletes_task(self, client, auth_headers):
        created = _body(
            client.post(
                BASE,
                headers=auth_headers,
                json={"skill_id": "asset-report", "cron_expression": "0 9 * * *"},
            )
        )

        response = client.delete(f"{BASE}/{created['id']}", headers=auth_headers)
        assert response.status_code == 204

        remaining = _body(client.get(BASE, headers=auth_headers))["items"]
        assert remaining == []

    def test_unknown_task_returns_404(self, client, auth_headers):
        response = client.delete(f"{BASE}/999999999", headers=auth_headers)

        assert response.status_code == 404

    def test_cannot_delete_other_familys_task(
        self, client, auth_headers, second_user_headers
    ):
        created = _body(
            client.post(
                BASE,
                headers=auth_headers,
                json={"skill_id": "asset-report", "cron_expression": "0 9 * * *"},
            )
        )

        response = client.delete(
            f"{BASE}/{created['id']}", headers=second_user_headers
        )

        assert response.status_code == 404
        # Still present for its real owner.
        remaining = _body(client.get(BASE, headers=auth_headers))["items"]
        assert len(remaining) == 1

    def test_non_owner_cannot_delete(self, client, auth_headers, member_headers):
        created = _body(
            client.post(
                BASE,
                headers=auth_headers,
                json={"skill_id": "asset-report", "cron_expression": "0 9 * * *"},
            )
        )

        response = client.delete(
            f"{BASE}/{created['id']}", headers=member_headers
        )

        assert response.status_code == 403


class TestDefaultScheduledTasks:
    """Defaults are seeded at family registration and marked is_default."""

    def test_registration_seeds_defaults(self, client, auth_headers):
        items = _body(client.get(BASE, headers=auth_headers))["items"]

        assert len(items) == 2
        skill_ids = {i["skill_id"] for i in items}
        assert skill_ids == {"asset-report", "literacy-weekly-report"}
        for item in items:
            assert item["is_default"] is True
            assert item["is_enabled"] is True
            assert item["status"] == "idle"

    def test_default_cron_matches_code_constants(self, client, auth_headers):
        items = _body(client.get(BASE, headers=auth_headers))["items"]
        by_skill = {i["skill_id"]: i for i in items}

        # Daily 08:35 Asia/Shanghai (legacy auto_report_job alignment)
        assert by_skill["asset-report"]["cron_expression"] == "35 8 * * *"
        # Sunday 02:00 Asia/Shanghai (legacy literacy_report_weekly_job alignment)
        assert by_skill["literacy-weekly-report"]["cron_expression"] == "0 2 * * 0"

    def test_update_flips_is_default_to_false(self, client, auth_headers):
        defaults = _body(client.get(BASE, headers=auth_headers))["items"]
        default = next(i for i in defaults if i["skill_id"] == "asset-report")

        response = client.put(
            f"{BASE}/{default['id']}",
            headers=auth_headers,
            json={"is_enabled": False},
        )

        assert response.status_code == 200
        data = _body(response)
        assert data["is_default"] is False
        assert data["is_enabled"] is False

    def test_delete_all_stays_empty(self, client, auth_headers):
        defaults = _body(client.get(BASE, headers=auth_headers))["items"]
        for d in defaults:
            response = client.delete(f"{BASE}/{d['id']}", headers=auth_headers)
            assert response.status_code == 204

        remaining = _body(client.get(BASE, headers=auth_headers))["items"]
        assert remaining == []
