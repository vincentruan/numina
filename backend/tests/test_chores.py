"""Tests for chore templates, instances, approvals, and coin transactions."""

import pytest


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def child_user(client, auth_headers):
    """Create a child user and return their info + child auth headers."""
    # Create child via parent
    resp = client.post("/api/v1/family/children", headers=auth_headers, json={
        "display_name": "小明",
        "avatar_color": "#FF5733",
        "pin": ["🐱", "🌟", "🎈", "🐶"],
    })
    assert resp.status_code == 201
    child = resp.json()["data"]

    # Login as child
    login_resp = client.post("/api/v1/auth/child/login", json={
        "child_id": child["id"],
        "pin_sequence": ["🐱", "🌟", "🎈", "🐶"],
    })
    assert login_resp.status_code == 200
    token = login_resp.json()["data"]["access_token"]
    # Remove parent's access_token cookie so child Bearer token isn't shadowed
    client.cookies.delete("access_token")
    return {
        "id": child["id"],
        "headers": {"Authorization": f"Bearer {token}"},
    }


@pytest.fixture
def daily_template(client, auth_headers, child_user):
    """Create a daily chore template assigned to child."""
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
def pool_template(client, auth_headers):
    """Create a pool chore template."""
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


# ---------------------------------------------------------------------------
# Template CRUD
# ---------------------------------------------------------------------------

def test_create_template_assigned(client, auth_headers, child_user):
    resp = client.post("/api/v1/family/chore-templates", headers=auth_headers, json={
        "name": "刷牙",
        "coin_reward": 2,
        "frequency": "daily",
        "assignment_type": "assigned",
        "assignee_ids": [child_user["id"]],
    })
    assert resp.status_code == 201
    data = resp.json()["data"]
    assert data["name"] == "刷牙"
    assert data["coin_reward"] == 2
    assert data["frequency"] == "daily"
    assert data["is_active"] is True
    assert len(data["assignees"]) == 1


def test_create_template_pool(client, auth_headers):
    resp = client.post("/api/v1/family/chore-templates", headers=auth_headers, json={
        "name": "倒垃圾",
        "coin_reward": 4,
        "frequency": "weekly",
        "assignment_type": "pool",
        "assignee_ids": [],
    })
    assert resp.status_code == 201
    assert resp.json()["data"]["assignment_type"] == "pool"


def test_create_template_assigned_requires_assignees(client, auth_headers):
    resp = client.post("/api/v1/family/chore-templates", headers=auth_headers, json={
        "name": "读书",
        "coin_reward": 3,
        "frequency": "daily",
        "assignment_type": "assigned",
        "assignee_ids": [],
    })
    assert resp.status_code == 422


def test_create_template_invalid_frequency(client, auth_headers, child_user):
    resp = client.post("/api/v1/family/chore-templates", headers=auth_headers, json={
        "name": "读书",
        "coin_reward": 3,
        "frequency": "monthly",
        "assignment_type": "assigned",
        "assignee_ids": [child_user["id"]],
    })
    assert resp.status_code == 422


def test_child_cannot_create_template(client, child_user):
    resp = client.post("/api/v1/family/chore-templates", headers=child_user["headers"], json={
        "name": "偷懒",
        "coin_reward": 100,
        "frequency": "daily",
        "assignment_type": "pool",
        "assignee_ids": [],
    })
    assert resp.status_code == 403


def test_list_templates(client, auth_headers, daily_template):
    resp = client.get("/api/v1/family/chore-templates", headers=auth_headers)
    assert resp.status_code == 200
    assert len(resp.json()["data"]) >= 1


def test_update_template(client, auth_headers, daily_template):
    resp = client.patch(
        f"/api/v1/family/chore-templates/{daily_template['id']}",
        headers=auth_headers,
        json={"name": "大扫除", "coin_reward": 10},
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["name"] == "大扫除"
    assert resp.json()["data"]["coin_reward"] == 10


def test_toggle_template(client, auth_headers, daily_template):
    resp = client.patch(
        f"/api/v1/family/chore-templates/{daily_template['id']}/toggle?is_active=false",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["is_active"] is False


def test_delete_template(client, auth_headers, daily_template):
    resp = client.delete(
        f"/api/v1/family/chore-templates/{daily_template['id']}",
        headers=auth_headers,
    )
    assert resp.status_code == 204


# ---------------------------------------------------------------------------
# Instance generation
# ---------------------------------------------------------------------------

def test_get_chores_creates_instances(client, child_user, daily_template):
    resp = client.get("/api/v1/child/chores?date=2026-04-15", headers=child_user["headers"])
    assert resp.status_code == 200
    instances = resp.json()["data"]
    assert len(instances) == 1
    assert instances[0]["chore_name"] == "扫地"
    assert instances[0]["status"] == "available"


def test_get_chores_idempotent(client, child_user, daily_template):
    """Calling twice on same date returns same instance, not duplicates."""
    resp1 = client.get("/api/v1/child/chores?date=2026-04-15", headers=child_user["headers"])
    resp2 = client.get("/api/v1/child/chores?date=2026-04-15", headers=child_user["headers"])
    assert resp1.status_code == 200
    assert resp2.status_code == 200
    ids1 = {i["id"] for i in resp1.json()["data"]}
    ids2 = {i["id"] for i in resp2.json()["data"]}
    assert ids1 == ids2


def test_disabled_template_not_generated(client, auth_headers, child_user, daily_template):
    # Disable template
    client.patch(
        f"/api/v1/family/chore-templates/{daily_template['id']}/toggle?is_active=false",
        headers=auth_headers,
    )
    resp = client.get("/api/v1/child/chores?date=2026-04-16", headers=child_user["headers"])
    assert resp.status_code == 200
    assert len(resp.json()["data"]) == 0


def test_pool_template_generates_per_child(client, auth_headers, child_user, pool_template):
    """Pool template generates an instance for the child."""
    resp = client.get("/api/v1/child/chores?date=2026-04-15", headers=child_user["headers"])
    assert resp.status_code == 200
    names = [i["chore_name"] for i in resp.json()["data"]]
    assert "浇花" in names


# ---------------------------------------------------------------------------
# Mark complete + approval flow
# ---------------------------------------------------------------------------

def test_mark_complete(client, child_user, daily_template):
    instances = client.get("/api/v1/child/chores?date=2026-04-15", headers=child_user["headers"]).json()["data"]
    instance_id = instances[0]["id"]

    resp = client.post(f"/api/v1/child/chores/{instance_id}/complete", headers=child_user["headers"])
    assert resp.status_code == 200
    assert resp.json()["data"]["status"] == "pending_approval"


def test_mark_complete_sets_submitted_by_user_id(client, db, auth_headers, child_user, daily_template):
    """submitted_by_user_id is written to the DB row when a child marks a chore complete."""
    from app.models.chore import ChoreInstance

    instances = client.get("/api/v1/child/chores?date=2026-04-15", headers=child_user["headers"]).json()["data"]
    instance_id = instances[0]["id"]
    client.post(f"/api/v1/child/chores/{instance_id}/complete", headers=child_user["headers"])

    # Verify the column is set directly on the DB row — not just via the fallback path
    row = db.query(ChoreInstance).filter(ChoreInstance.id == instance_id).first()
    assert row is not None
    assert row.submitted_by_user_id == child_user["id"]


def test_mark_complete_twice_fails(client, child_user, daily_template):
    instances = client.get("/api/v1/child/chores?date=2026-04-15", headers=child_user["headers"]).json()["data"]
    instance_id = instances[0]["id"]
    client.post(f"/api/v1/child/chores/{instance_id}/complete", headers=child_user["headers"])
    resp = client.post(f"/api/v1/child/chores/{instance_id}/complete", headers=child_user["headers"])
    assert resp.status_code == 422


def test_approve_instance(client, auth_headers, child_user, daily_template):
    instances = client.get("/api/v1/child/chores?date=2026-04-15", headers=child_user["headers"]).json()["data"]
    instance_id = instances[0]["id"]
    client.post(f"/api/v1/child/chores/{instance_id}/complete", headers=child_user["headers"])

    resp = client.post(f"/api/v1/family/chore-approvals/{instance_id}/approve", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["data"]["status"] == "approved"

    # Balance should increase
    balance_resp = client.get("/api/v1/child/coins/balance", headers=child_user["headers"])
    assert balance_resp.status_code == 200
    assert balance_resp.json()["data"]["balance"] == 5  # coin_reward


def test_approve_writes_coin_transaction(client, auth_headers, child_user, daily_template):
    instances = client.get("/api/v1/child/chores?date=2026-04-15", headers=child_user["headers"]).json()["data"]
    instance_id = instances[0]["id"]
    client.post(f"/api/v1/child/chores/{instance_id}/complete", headers=child_user["headers"])
    client.post(f"/api/v1/family/chore-approvals/{instance_id}/approve", headers=auth_headers)

    ledger = client.get("/api/v1/child/coins/ledger", headers=child_user["headers"]).json()["data"]
    assert len(ledger) == 1
    assert ledger[0]["amount"] == 5
    assert ledger[0]["transaction_type"] == "chore_earn"


def test_reject_instance(client, auth_headers, child_user, daily_template):
    instances = client.get("/api/v1/child/chores?date=2026-04-15", headers=child_user["headers"]).json()["data"]
    instance_id = instances[0]["id"]
    client.post(f"/api/v1/child/chores/{instance_id}/complete", headers=child_user["headers"])

    resp = client.post(
        f"/api/v1/family/chore-approvals/{instance_id}/reject",
        headers=auth_headers,
        json={"return_to_redo": False},
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["status"] == "rejected"


def test_reject_return_to_redo(client, auth_headers, child_user, daily_template):
    instances = client.get("/api/v1/child/chores?date=2026-04-15", headers=child_user["headers"]).json()["data"]
    instance_id = instances[0]["id"]
    client.post(f"/api/v1/child/chores/{instance_id}/complete", headers=child_user["headers"])

    resp = client.post(
        f"/api/v1/family/chore-approvals/{instance_id}/reject",
        headers=auth_headers,
        json={"return_to_redo": True},
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["status"] == "available"


def test_child_cannot_approve(client, child_user, daily_template):
    instances = client.get("/api/v1/child/chores?date=2026-04-15", headers=child_user["headers"]).json()["data"]
    instance_id = instances[0]["id"]
    client.post(f"/api/v1/child/chores/{instance_id}/complete", headers=child_user["headers"])

    resp = client.post(f"/api/v1/family/chore-approvals/{instance_id}/approve", headers=child_user["headers"])
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Coin ledger
# ---------------------------------------------------------------------------

def test_balance_starts_at_zero(client, child_user):
    resp = client.get("/api/v1/child/coins/balance", headers=child_user["headers"])
    assert resp.status_code == 200
    assert resp.json()["data"]["balance"] == 0


def test_child_cannot_view_other_childs_ledger(client, auth_headers, child_user):
    """Child can only view their own ledger."""
    # Create second child
    resp2 = client.post("/api/v1/family/children", headers=auth_headers, json={
        "display_name": "小红",
        "avatar_color": "#FF0000",
        "pin": ["🌈", "🐸", "🍎", "🦊"],
    })
    assert resp2.status_code == 201

    # child_user tries to get balance — should only see their own
    resp = client.get("/api/v1/child/coins/balance", headers=child_user["headers"])
    assert resp.status_code == 200
    assert resp.json()["data"]["balance"] == 0  # their own balance, not other child's


def test_parent_grant(client, auth_headers, child_user):
    resp = client.post("/api/v1/family/coins/grant", headers=auth_headers, json={
        "child_user_id": child_user["id"],
        "amount": 10,
        "reason": "表现很棒！",
    })
    assert resp.status_code == 201
    assert resp.json()["data"]["amount"] == 10

    balance = client.get("/api/v1/child/coins/balance", headers=child_user["headers"]).json()["data"]
    assert balance["balance"] == 10


def test_parent_grant_invalid_amount(client, auth_headers, child_user):
    resp = client.post("/api/v1/family/coins/grant", headers=auth_headers, json={
        "child_user_id": child_user["id"],
        "amount": 200,
        "reason": "太多了",
    })
    assert resp.status_code == 422


def test_ledger_relative_time(client, auth_headers, child_user, daily_template):
    instances = client.get("/api/v1/child/chores?date=2026-04-15", headers=child_user["headers"]).json()["data"]
    instance_id = instances[0]["id"]
    client.post(f"/api/v1/child/chores/{instance_id}/complete", headers=child_user["headers"])
    client.post(f"/api/v1/family/chore-approvals/{instance_id}/approve", headers=auth_headers)

    ledger = client.get("/api/v1/child/coins/ledger", headers=child_user["headers"]).json()["data"]
    assert ledger[0]["relative_time"] in ("今天", "昨天") or "天前" in ledger[0]["relative_time"]


def test_pending_approvals_include_child_fields(client, auth_headers, child_user, daily_template):
    """GET /family/chore-approvals returns child identity fields on each item."""
    instances = client.get("/api/v1/child/chores?date=2026-04-15", headers=child_user["headers"]).json()["data"]
    instance_id = instances[0]["id"]
    client.post(f"/api/v1/child/chores/{instance_id}/complete", headers=child_user["headers"])

    resp = client.get("/api/v1/family/chore-approvals", headers=auth_headers)
    assert resp.status_code == 200
    items = resp.json()["data"]
    assert len(items) == 1
    item = items[0]
    assert item["child_user_id"] == child_user["id"]
    assert item["child_display_name"] == "小明"
    assert item["child_avatar_color"] == "#FF5733"


# ---------------------------------------------------------------------------
# Access control: approval endpoints require owner role
# ---------------------------------------------------------------------------

def _register_member_in_family(client, owner_headers) -> dict:
    """Join the owner's family as a member, return member auth headers."""
    family_resp = client.get("/api/v1/family/info", headers=owner_headers)
    invite_code = family_resp.json()["data"]["invite_code"]
    resp = client.post("/api/v1/auth/family/join", json={
        "username": "member_chore",
        "display_name": "Member",
        "password": "MemberPass1",
        "invite_code": invite_code,
    })
    assert resp.status_code == 200
    return {"Authorization": f"Bearer {resp.json()['data']['access_token']}"}


def test_member_cannot_approve_chore(client, auth_headers, child_user, daily_template):
    """Member role gets 403 on approve — endpoint requires owner."""
    instances = client.get("/api/v1/child/chores?date=2026-04-15", headers=child_user["headers"]).json()["data"]
    instance_id = instances[0]["id"]
    client.post(f"/api/v1/child/chores/{instance_id}/complete", headers=child_user["headers"])

    member_headers = _register_member_in_family(client, auth_headers)
    resp = client.post(f"/api/v1/family/chore-approvals/{instance_id}/approve", headers=member_headers)
    assert resp.status_code == 403


def test_member_cannot_reject_chore(client, auth_headers, child_user, daily_template):
    """Member role gets 403 on reject — endpoint requires owner."""
    instances = client.get("/api/v1/child/chores?date=2026-04-15", headers=child_user["headers"]).json()["data"]
    instance_id = instances[0]["id"]
    client.post(f"/api/v1/child/chores/{instance_id}/complete", headers=child_user["headers"])

    member_headers = _register_member_in_family(client, auth_headers)
    resp = client.post(f"/api/v1/family/chore-approvals/{instance_id}/reject", headers=member_headers)
    assert resp.status_code == 403


def test_cross_family_owner_cannot_approve_chore(client, auth_headers, child_user, daily_template, second_user_headers):
    """Owner from a different family gets 404 on approve (instance not in their family)."""
    instances = client.get("/api/v1/child/chores?date=2026-04-15", headers=child_user["headers"]).json()["data"]
    instance_id = instances[0]["id"]
    client.post(f"/api/v1/child/chores/{instance_id}/complete", headers=child_user["headers"])

    resp = client.post(f"/api/v1/family/chore-approvals/{instance_id}/approve", headers=second_user_headers)
    assert resp.status_code == 404


def test_cross_family_owner_cannot_reject_chore(client, auth_headers, child_user, daily_template, second_user_headers):
    """Owner from a different family gets 404 on reject (instance not in their family)."""
    instances = client.get("/api/v1/child/chores?date=2026-04-15", headers=child_user["headers"]).json()["data"]
    instance_id = instances[0]["id"]
    client.post(f"/api/v1/child/chores/{instance_id}/complete", headers=child_user["headers"])

    resp = client.post(f"/api/v1/family/chore-approvals/{instance_id}/reject", json={"return_to_redo": False}, headers=second_user_headers)
    assert resp.status_code == 404


def test_member_cannot_list_approvals(client, auth_headers, child_user, daily_template):
    """Member role gets 403 on list approvals — endpoint requires owner."""
    member_headers = _register_member_in_family(client, auth_headers)
    resp = client.get("/api/v1/family/chore-approvals", headers=member_headers)
    assert resp.status_code == 403
