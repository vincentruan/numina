"""Tests for parent assign/reassign and void chore instance endpoints (Unit 2)."""

import pytest

from tests.backend.conftest import child_login_two_phase

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def child_user(client, auth_headers):
    """Create a child user and return their info + child auth headers."""
    resp = client.post("/api/v1/family/children", headers=auth_headers, json={
        "display_name": "小明",
        "password": "ChildPass1",
        "username": "assignchild1",
        "avatar_color": "#FF5733",
        "pin": ["🐱", "🌟", "🎈", "🐶"],
    })
    assert resp.status_code == 201
    child = resp.json()["data"]
    token = child_login_two_phase(client, "assignchild1", "ChildPass1", ["🐱", "🌟", "🎈", "🐶"])
    client.cookies.delete("access_token")
    return {
        "id": child["id"],
        "headers": {"Authorization": f"Bearer {token}"},
    }


@pytest.fixture
def child_user2(client, auth_headers):
    """Create a second child user in the same family."""
    resp = client.post("/api/v1/family/children", headers=auth_headers, json={
        "display_name": "小红",
        "password": "ChildPass2",
        "username": "assignchild2",
        "avatar_color": "#00AAFF",
        "pin": ["🌈", "🐸", "🍎", "🦊"],
    })
    assert resp.status_code == 201
    child = resp.json()["data"]
    token = child_login_two_phase(client, "assignchild2", "ChildPass2", ["🌈", "🐸", "🍎", "🦊"])
    client.cookies.delete("access_token")
    return {
        "id": child["id"],
        "headers": {"Authorization": f"Bearer {token}"},
    }


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


@pytest.fixture
def pool_instance(client, auth_headers, child_user, pool_template):
    """Get (or create) a pool chore instance for child_user on a fixed date."""
    resp = client.get("/api/v1/child/chores?date=2026-05-01", headers=child_user["headers"])
    assert resp.status_code == 200
    instances = resp.json()["data"]
    pool = next(i for i in instances if i["template_id"] == pool_template["id"])
    return pool


# ---------------------------------------------------------------------------
# Happy path: assign unclaimed pool instance
# ---------------------------------------------------------------------------


def test_assign_unclaimed_pool_instance(client, auth_headers, child_user, pool_instance):
    """Assigning an unclaimed pool instance sets child_user_id and assigned_by_user_id."""
    instance_id = pool_instance["id"]

    resp = client.post(
        f"/api/v1/family/chore-instances/{instance_id}/assign",
        headers=auth_headers,
        json={"child_user_id": child_user["id"]},
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["child_user_id"] == str(child_user["id"])
    # assigned_by_user_id must be set (serialized as string)
    assert data["assigned_by_user_id"] is not None
    # After assign, is_pool_unclaimed should be False (child_user_id != family_id now)
    assert data["is_pool_unclaimed"] is False


def test_assign_sets_assigned_by_user_id_in_db(client, db, auth_headers, child_user, pool_instance):
    """assigned_by_user_id is persisted to the DB row after assign."""
    from apps.backend.app.models.chore import ChoreInstance

    instance_id = pool_instance["id"]
    client.post(
        f"/api/v1/family/chore-instances/{instance_id}/assign",
        headers=auth_headers,
        json={"child_user_id": child_user["id"]},
    )
    row = db.query(ChoreInstance).filter(ChoreInstance.id == instance_id).first()
    assert row is not None
    assert str(row.child_user_id) == child_user["id"]
    assert row.assigned_by_user_id is not None


# ---------------------------------------------------------------------------
# Happy path: reassign already-claimed instance
# ---------------------------------------------------------------------------


def test_reassign_claimed_instance_clears_claimed_at(client, db, auth_headers, child_user, child_user2, pool_instance):
    """Reassigning a claimed instance updates child_user_id and clears claimed_at."""
    from datetime import datetime

    from apps.backend.app.models.chore import ChoreInstance

    instance_id = pool_instance["id"]

    # Simulate a claimed state by directly setting claimed_at in DB
    row = db.query(ChoreInstance).filter(ChoreInstance.id == instance_id).first()
    row.claimed_at = datetime(2026, 5, 1, 10, 0, 0)
    row.child_user_id = int(child_user["id"])
    db.commit()

    # Reassign to child_user2
    resp = client.post(
        f"/api/v1/family/chore-instances/{instance_id}/assign",
        headers=auth_headers,
        json={"child_user_id": child_user2["id"]},
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["child_user_id"] == str(child_user2["id"])
    assert data["claimed_at"] is None

    db.refresh(row)
    assert str(row.child_user_id) == child_user2["id"]
    assert row.claimed_at is None


# ---------------------------------------------------------------------------
# Happy path: void available instance
# ---------------------------------------------------------------------------


def test_void_available_instance(client, db, auth_headers, pool_instance):
    """Voiding an available instance hard-deletes the row and returns 204."""
    from apps.backend.app.models.chore import ChoreInstance

    instance_id = pool_instance["id"]

    resp = client.delete(
        f"/api/v1/family/chore-instances/{instance_id}",
        headers=auth_headers,
    )
    assert resp.status_code == 204

    row = db.query(ChoreInstance).filter(ChoreInstance.id == instance_id).first()
    assert row is None


# ---------------------------------------------------------------------------
# Integration: after void, get_or_create_instances creates a fresh instance
# ---------------------------------------------------------------------------


def test_void_then_recreate_instance(client, db, auth_headers, child_user, pool_instance, pool_template):
    """After voiding, calling the child chores endpoint creates a fresh instance."""
    from apps.backend.app.models.chore import ChoreInstance

    instance_id = pool_instance["id"]

    client.delete(f"/api/v1/family/chore-instances/{instance_id}", headers=auth_headers)

    # Child fetches chores again — a new instance should be created
    resp = client.get("/api/v1/child/chores?date=2026-05-01", headers=child_user["headers"])
    assert resp.status_code == 200
    instances = resp.json()["data"]
    pool_instances = [i for i in instances if i["template_id"] == pool_template["id"]]
    assert len(pool_instances) == 1
    new_id = pool_instances[0]["id"]
    assert new_id != instance_id  # fresh row


# ---------------------------------------------------------------------------
# Edge case: assign to non-child user (adult) in family → 403
# ---------------------------------------------------------------------------


def test_assign_to_adult_returns_403(client, auth_headers, pool_instance):
    """Assigning to an adult (owner) in the same family returns 403."""
    # Get the owner's user ID from /auth/me
    me_resp = client.get("/api/v1/auth/me", headers=auth_headers)
    assert me_resp.status_code == 200
    owner_id = me_resp.json()["data"]["id"]

    instance_id = pool_instance["id"]
    resp = client.post(
        f"/api/v1/family/chore-instances/{instance_id}/assign",
        headers=auth_headers,
        json={"child_user_id": owner_id},
    )
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Edge case: assign to child in different family → 404
# ---------------------------------------------------------------------------


def test_assign_to_child_in_different_family_returns_404(client, auth_headers, pool_instance, second_user_headers):
    """Assigning to a child that belongs to a different family returns 404."""
    # Create a child in the second family
    child_resp = client.post("/api/v1/family/children", headers=second_user_headers, json={
        "display_name": "外家孩子",
        "password": "ChildPass1",
        "username": "otherfamilychild",
        "avatar_color": "#AABBCC",
        "pin": ["🐱", "🌟", "🎈", "🐶"],
    })
    assert child_resp.status_code == 201
    other_child_id = child_resp.json()["data"]["id"]

    instance_id = pool_instance["id"]
    resp = client.post(
        f"/api/v1/family/chore-instances/{instance_id}/assign",
        headers=auth_headers,
        json={"child_user_id": other_child_id},
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Error path: assign instance with status pending_approval → 409
# ---------------------------------------------------------------------------


def test_assign_pending_approval_instance_returns_409(client, auth_headers, child_user, pool_instance):
    """Assigning an instance that is pending_approval returns 409 Conflict."""
    instance_id = pool_instance["id"]

    # Child marks it complete → status becomes pending_approval
    client.post(f"/api/v1/child/chores/{instance_id}/complete", headers=child_user["headers"])

    resp = client.post(
        f"/api/v1/family/chore-instances/{instance_id}/assign",
        headers=auth_headers,
        json={"child_user_id": child_user["id"]},
    )
    assert resp.status_code == 409


# ---------------------------------------------------------------------------
# Error path: assign instance with status approved → 409
# ---------------------------------------------------------------------------


def test_assign_approved_instance_returns_409(client, auth_headers, child_user, pool_instance):
    """Assigning an already-approved instance returns 409 Conflict."""
    instance_id = pool_instance["id"]

    client.post(f"/api/v1/child/chores/{instance_id}/complete", headers=child_user["headers"])
    client.post(f"/api/v1/family/chore-approvals/{instance_id}/approve", headers=auth_headers)

    resp = client.post(
        f"/api/v1/family/chore-instances/{instance_id}/assign",
        headers=auth_headers,
        json={"child_user_id": child_user["id"]},
    )
    assert resp.status_code == 409


# ---------------------------------------------------------------------------
# Error path: void instance with status pending_approval → 409
# ---------------------------------------------------------------------------


def test_void_pending_approval_instance_returns_409(client, auth_headers, child_user, pool_instance):
    """Voiding an instance that is pending_approval returns 409 Conflict."""
    instance_id = pool_instance["id"]

    client.post(f"/api/v1/child/chores/{instance_id}/complete", headers=child_user["headers"])

    resp = client.delete(
        f"/api/v1/family/chore-instances/{instance_id}",
        headers=auth_headers,
    )
    assert resp.status_code == 409


# ---------------------------------------------------------------------------
# Error path: assign non-existent instance → 404
# ---------------------------------------------------------------------------


def test_assign_nonexistent_instance_returns_404(client, auth_headers, child_user):
    """Assigning a non-existent instance returns 404."""
    resp = client.post(
        "/api/v1/family/chore-instances/999999999999999999/assign",
        headers=auth_headers,
        json={"child_user_id": child_user["id"]},
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Error path: void non-existent instance → 404
# ---------------------------------------------------------------------------


def test_void_nonexistent_instance_returns_404(client, auth_headers):
    """Voiding a non-existent instance returns 404."""
    resp = client.delete(
        "/api/v1/family/chore-instances/999999999999999999",
        headers=auth_headers,
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Access control: child cannot assign or void
# ---------------------------------------------------------------------------


def test_child_cannot_assign_instance(client, child_user, pool_instance):
    """Child token is rejected (403) on the assign endpoint."""
    instance_id = pool_instance["id"]
    resp = client.post(
        f"/api/v1/family/chore-instances/{instance_id}/assign",
        headers=child_user["headers"],
        json={"child_user_id": child_user["id"]},
    )
    assert resp.status_code == 403


def test_child_cannot_void_instance(client, child_user, pool_instance):
    """Child token is rejected (403) on the void endpoint."""
    instance_id = pool_instance["id"]
    resp = client.delete(
        f"/api/v1/family/chore-instances/{instance_id}",
        headers=child_user["headers"],
    )
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Cross-family: parent from different family cannot assign or void
# ---------------------------------------------------------------------------


def test_cross_family_parent_cannot_assign(client, auth_headers, pool_instance, second_user_headers):
    """Parent from a different family gets 404 on assign."""
    instance_id = pool_instance["id"]

    # Create a child in second family to use as target
    child_resp = client.post("/api/v1/family/children", headers=second_user_headers, json={
        "display_name": "外家孩子2",
        "password": "ChildPass1",
        "username": "otherfamilychild2",
        "avatar_color": "#AABBCC",
        "pin": ["🐱", "🌟", "🎈", "🐶"],
    })
    assert child_resp.status_code == 201
    other_child_id = child_resp.json()["data"]["id"]

    resp = client.post(
        f"/api/v1/family/chore-instances/{instance_id}/assign",
        headers=second_user_headers,
        json={"child_user_id": other_child_id},
    )
    assert resp.status_code == 404


def test_cross_family_parent_cannot_void(client, auth_headers, pool_instance, second_user_headers):
    """Parent from a different family gets 404 on void."""
    instance_id = pool_instance["id"]
    resp = client.delete(
        f"/api/v1/family/chore-instances/{instance_id}",
        headers=second_user_headers,
    )
    assert resp.status_code == 404
