"""Additional tests for streak, auto-approve, idempotency, pool isolation, weekly, and grant cross-family."""

from datetime import UTC, datetime, timedelta

import pytest

from tests.backend.conftest import child_login_two_phase

# ---------------------------------------------------------------------------
# Fixtures (reuse pattern from test_chores.py)
# ---------------------------------------------------------------------------

@pytest.fixture
def child_user(client, auth_headers):
    resp = client.post("/api/v1/family/children", headers=auth_headers, json={
        "display_name": "小明",
        "password": "ChildPass1",
        "username": "xiaoming4",
        "avatar_color": "#FF5733",
        "pin": ["🐱", "🌟", "🎈", "🐶"],
    })
    assert resp.status_code == 201
    child = resp.json()["data"]
    token = child_login_two_phase(client, "xiaoming4", "ChildPass1", ["🐱", "🌟", "🎈", "🐶"])
    client.cookies.delete("access_token")
    return {"id": child["id"], "headers": {"Authorization": f"Bearer {token}"}}


@pytest.fixture
def child_user2(client, auth_headers):
    resp = client.post("/api/v1/family/children", headers=auth_headers, json={
        "display_name": "小红",
        "password": "ChildPass1",
        "username": "xiaohong4",
        "avatar_color": "#33FF57",
        "pin": ["🐶", "🌟", "🎈", "🐱"],
    })
    assert resp.status_code == 201
    child = resp.json()["data"]
    token = child_login_two_phase(client, "xiaohong4", "ChildPass1", ["🐶", "🌟", "🎈", "🐱"])
    client.cookies.delete("access_token")
    return {"id": child["id"], "headers": {"Authorization": f"Bearer {token}"}}


@pytest.fixture
def daily_template(client, auth_headers, child_user):
    resp = client.post("/api/v1/family/chore-templates", headers=auth_headers, json={
        "name": "扫地",
        "emoji": "🧹",
        "coin_reward": 5,
        "frequency": "daily",
        "assignment_type": "assigned",
        "assignee_ids": [child_user["id"]],
    })
    assert resp.status_code == 201
    return resp.json()["data"]


@pytest.fixture
def weekly_template(client, auth_headers, child_user):
    resp = client.post("/api/v1/family/chore-templates", headers=auth_headers, json={
        "name": "整理房间",
        "emoji": "🏠",
        "coin_reward": 10,
        "frequency": "weekly",
        "assignment_type": "assigned",
        "assignee_ids": [child_user["id"]],
    })
    assert resp.status_code == 201
    return resp.json()["data"]


@pytest.fixture
def pool_template(client, auth_headers):
    resp = client.post("/api/v1/family/chore-templates", headers=auth_headers, json={
        "name": "浇花",
        "emoji": "🌸",
        "coin_reward": 3,
        "frequency": "daily",
        "assignment_type": "pool",
        "assignee_ids": [],
    })
    assert resp.status_code == 201
    return resp.json()["data"]


def _get_instance(client, child_headers, date):
    resp = client.get(f"/api/v1/child/chores?date={date}", headers=child_headers)
    assert resp.status_code == 200
    return resp.json()["data"][0]


def _complete_and_approve(client, child_headers, auth_headers, instance_id):
    client.post(f"/api/v1/child/chores/{instance_id}/complete", headers=child_headers)
    client.post(f"/api/v1/family/chore-approvals/{instance_id}/approve", headers=auth_headers)


# ---------------------------------------------------------------------------
# Streak tests
# ---------------------------------------------------------------------------

def test_streak_first_approval_is_one(client, child_user, daily_template, auth_headers):
    inst = _get_instance(client, child_user["headers"], "2026-04-15")
    _complete_and_approve(client, child_user["headers"], auth_headers, inst["id"])
    resp = client.get("/api/v1/child/chores?date=2026-04-15", headers=child_user["headers"])
    approved = next(i for i in resp.json()["data"] if i["id"] == inst["id"])
    assert approved["streak_count"] == 1


def test_streak_consecutive_days_increments(client, child_user, daily_template, auth_headers):
    # Day 1
    inst1 = _get_instance(client, child_user["headers"], "2026-04-15")
    _complete_and_approve(client, child_user["headers"], auth_headers, inst1["id"])
    # Day 2
    inst2 = _get_instance(client, child_user["headers"], "2026-04-16")
    _complete_and_approve(client, child_user["headers"], auth_headers, inst2["id"])
    resp = client.get("/api/v1/child/chores?date=2026-04-16", headers=child_user["headers"])
    approved = next(i for i in resp.json()["data"] if i["id"] == inst2["id"])
    assert approved["streak_count"] == 2


def test_streak_non_consecutive_resets_to_one(client, child_user, daily_template, auth_headers):
    # Day 1
    inst1 = _get_instance(client, child_user["headers"], "2026-04-15")
    _complete_and_approve(client, child_user["headers"], auth_headers, inst1["id"])
    # Skip day 2 — day 3
    inst3 = _get_instance(client, child_user["headers"], "2026-04-17")
    _complete_and_approve(client, child_user["headers"], auth_headers, inst3["id"])
    resp = client.get("/api/v1/child/chores?date=2026-04-17", headers=child_user["headers"])
    approved = next(i for i in resp.json()["data"] if i["id"] == inst3["id"])
    assert approved["streak_count"] == 1


def test_streak_weekly_consecutive_increments(client, child_user, weekly_template, auth_headers):
    # Week 1: 2026-04-13 (W16)
    inst1 = _get_instance(client, child_user["headers"], "2026-04-13")
    _complete_and_approve(client, child_user["headers"], auth_headers, inst1["id"])
    # Week 2: 2026-04-20 (W17)
    inst2 = _get_instance(client, child_user["headers"], "2026-04-20")
    _complete_and_approve(client, child_user["headers"], auth_headers, inst2["id"])
    resp = client.get("/api/v1/child/chores?date=2026-04-20", headers=child_user["headers"])
    approved = next(i for i in resp.json()["data"] if i["id"] == inst2["id"])
    assert approved["streak_count"] == 2


# ---------------------------------------------------------------------------
# Auto-approve lazy trigger
# ---------------------------------------------------------------------------

def test_auto_approve_triggers_on_list(client, child_user, daily_template, auth_headers, db):
    """When parent lists approvals after timeout, instance is auto-approved."""
    inst = _get_instance(client, child_user["headers"], "2026-04-15")
    client.post(f"/api/v1/child/chores/{inst['id']}/complete", headers=child_user["headers"])

    # Backdate submitted_at to exceed auto_approve_hours (default 24h)
    from apps.backend.app.models.chore import ChoreInstance
    record = db.query(ChoreInstance).filter_by(id=inst["id"]).first()
    record.submitted_at = datetime.now(UTC) - timedelta(hours=25)
    db.commit()

    # Parent lists approvals — should trigger auto-approve
    resp = client.get("/api/v1/family/chore-approvals", headers=auth_headers)
    assert resp.status_code == 200
    # Instance should NOT appear in pending (it was auto-approved)
    pending_ids = {i["id"] for i in resp.json()["data"]}
    assert inst["id"] not in pending_ids

    # Verify coin transaction was written
    client.cookies.delete("access_token")
    # Re-login child to check balance
    child_token = child_login_two_phase(client, "xiaoming4", "ChildPass1", ["🐱", "🌟", "🎈", "🐶"])
    child_headers = {"Authorization": f"Bearer {child_token}"}
    bal_resp = client.get("/api/v1/child/coins/balance", headers=child_headers)
    assert bal_resp.json()["data"]["balance"] == 5  # coin_reward from daily_template


# ---------------------------------------------------------------------------
# Double-approve idempotency (409)
# ---------------------------------------------------------------------------

def test_double_approve_returns_422(client, child_user, daily_template, auth_headers):
    """Second approve attempt returns 422 — instance is no longer pending_approval."""
    inst = _get_instance(client, child_user["headers"], "2026-04-15")
    client.post(f"/api/v1/child/chores/{inst['id']}/complete", headers=child_user["headers"])
    # First approve
    r1 = client.post(f"/api/v1/family/chore-approvals/{inst['id']}/approve", headers=auth_headers)
    assert r1.status_code == 200
    # Second approve — 422 because status is no longer pending_approval
    r2 = client.post(f"/api/v1/family/chore-approvals/{inst['id']}/approve", headers=auth_headers)
    assert r2.status_code == 422


# ---------------------------------------------------------------------------
# Pool template per-child isolation
# ---------------------------------------------------------------------------

def test_pool_template_visible_to_all_children(client, child_user, child_user2, pool_template, auth_headers):
    """Pool chores are visible to all children in the family (shared instance)."""
    resp1 = client.get("/api/v1/child/chores?date=2026-04-15", headers=child_user["headers"])
    resp2 = client.get("/api/v1/child/chores?date=2026-04-15", headers=child_user2["headers"])
    assert resp1.status_code == 200
    assert resp2.status_code == 200
    # Both children see the pool chore
    assert len(resp1.json()["data"]) == 1
    assert len(resp2.json()["data"]) == 1
    # Pool chores share the same instance (first-come-first-served)
    assert resp1.json()["data"][0]["id"] == resp2.json()["data"][0]["id"]


# ---------------------------------------------------------------------------
# Weekly same-week idempotency
# ---------------------------------------------------------------------------

def test_weekly_same_week_idempotent(client, child_user, weekly_template):
    """Two dates in the same ISO week return the same instance."""
    resp_mon = client.get("/api/v1/child/chores?date=2026-04-13", headers=child_user["headers"])
    resp_fri = client.get("/api/v1/child/chores?date=2026-04-17", headers=child_user["headers"])
    assert resp_mon.status_code == 200
    assert resp_fri.status_code == 200
    ids_mon = {i["id"] for i in resp_mon.json()["data"]}
    ids_fri = {i["id"] for i in resp_fri.json()["data"]}
    assert ids_mon == ids_fri


# ---------------------------------------------------------------------------
# Parent grant cross-family isolation
# ---------------------------------------------------------------------------

def test_parent_grant_cross_family_rejected(client, auth_headers):
    """Parent cannot grant coins to a child from a different family."""
    # Register a second family — use explicit Bearer to avoid cookie contamination
    r = client.post("/api/v1/auth/register", json={
        "username": "other_parent",
        "display_name": "Other Parent",
        "password": "TestPass123",
        "family_name": "Other Family",
        "family_invitation_code": "AUT12"
    })
    other_token = r.json()["data"]["access_token"]
    other_headers = {"Authorization": f"Bearer {other_token}"}
    # Clear cookie so first family's auth_headers still works via Bearer
    client.cookies.delete("access_token")

    # Create child in other family
    child_resp = client.post("/api/v1/family/children", headers=other_headers, json={
        "display_name": "外来孩子",
        "password": "ChildPass1",
        "username": "visitorchild",
        "avatar_color": "#AABBCC",
        "pin": ["🐱", "🌟", "🎈", "🐶"],
    })
    other_child_id = child_resp.json()["data"]["id"]

    # Try to grant coins to other family's child using first family's parent token
    resp = client.post("/api/v1/family/coins/grant", headers=auth_headers, json={
        "child_user_id": other_child_id,
        "amount": 10,
        "reason": "跨家庭测试",
    })
    assert resp.status_code in (403, 404, 422)
