"""Tests for child claim/abandon endpoints and widened child chore query (Unit 3)."""

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
        "username": "claimchild1",
        "avatar_color": "#FF5733",
        "pin": ["🐱", "🌟", "🎈", "🐶"],
    })
    assert resp.status_code == 201
    child = resp.json()["data"]
    token = child_login_two_phase(client, "claimchild1", "ChildPass1", ["🐱", "🌟", "🎈", "🐶"])
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
        "username": "claimchild2",
        "avatar_color": "#00AAFF",
        "pin": ["🌈", "🐸", "🍎", "🦊"],
    })
    assert resp.status_code == 201
    child = resp.json()["data"]
    token = child_login_two_phase(client, "claimchild2", "ChildPass2", ["🌈", "🐸", "🍎", "🦊"])
    client.cookies.delete("access_token")
    return {
        "id": child["id"],
        "headers": {"Authorization": f"Bearer {token}"},
    }


@pytest.fixture
def pool_template(client, auth_headers):
    """Create a pool chore template."""
    resp = client.post("/api/v1/family/chore-templates", headers=auth_headers, json={
        "name": "扫地",
        "emoji": "🧹",
        "coin_reward": 5,
        "frequency": "daily",
        "assignment_type": "pool",
        "assignee_ids": [],
    })
    assert resp.status_code == 201
    return resp.json()["data"]


@pytest.fixture
def pool_instance(client, child_user, pool_template):
    """Get (or create) a pool chore instance for child_user on a fixed date."""
    resp = client.get("/api/v1/child/chores?date=2026-06-01", headers=child_user["headers"])
    assert resp.status_code == 200
    instances = resp.json()["data"]
    pool = next(i for i in instances if i["template_id"] == pool_template["id"])
    return pool


# ---------------------------------------------------------------------------
# Happy path: claim unclaimed pool instance
# ---------------------------------------------------------------------------


def test_claim_unclaimed_pool_instance(client, child_user, pool_instance):
    """Claiming an unclaimed pool instance sets child_user_id and claimed_at."""
    instance_id = pool_instance["id"]

    resp = client.post(
        f"/api/v1/child/chores/{instance_id}/claim",
        headers=child_user["headers"],
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["child_user_id"] == str(child_user["id"])
    assert data["claimed_at"] is not None
    assert data["is_pool_unclaimed"] is False


def test_claim_sets_child_user_id_in_db(client, db, child_user, pool_instance):
    """After claim, DB row has child_user_id == child.id and claimed_at set."""
    from apps.backend.app.models.chore import ChoreInstance

    instance_id = pool_instance["id"]
    client.post(f"/api/v1/child/chores/{instance_id}/claim", headers=child_user["headers"])

    row = db.query(ChoreInstance).filter(ChoreInstance.id == instance_id).first()
    assert row is not None
    assert str(row.child_user_id) == child_user["id"]
    assert row.claimed_at is not None


# ---------------------------------------------------------------------------
# Happy path: abandon claimed instance
# ---------------------------------------------------------------------------


def test_abandon_claimed_instance(client, db, child_user, pool_instance):
    """Abandoning a claimed instance resets child_user_id to family_id and clears claimed_at."""
    from apps.backend.app.models.chore import ChoreInstance

    instance_id = pool_instance["id"]

    # First claim it
    client.post(f"/api/v1/child/chores/{instance_id}/claim", headers=child_user["headers"])

    # Then abandon
    resp = client.post(
        f"/api/v1/child/chores/{instance_id}/abandon",
        headers=child_user["headers"],
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["claimed_at"] is None
    assert data["assigned_by_user_id"] is None
    assert data["is_pool_unclaimed"] is True

    row = db.query(ChoreInstance).filter(ChoreInstance.id == instance_id).first()
    assert row.claimed_at is None
    assert row.assigned_by_user_id is None


def test_abandon_fires_notification(client, child_user, pool_instance):
    """Abandon returns 200 (notification side-effect is fire-and-forget, not asserted on response)."""
    instance_id = pool_instance["id"]
    client.post(f"/api/v1/child/chores/{instance_id}/claim", headers=child_user["headers"])
    resp = client.post(f"/api/v1/child/chores/{instance_id}/abandon", headers=child_user["headers"])
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Happy path: abandon hard-assigned instance
# ---------------------------------------------------------------------------


def test_abandon_hard_assigned_instance(client, db, auth_headers, child_user, pool_instance):
    """Abandoning a hard-assigned instance also resets to pool (clears assigned_by_user_id)."""
    from apps.backend.app.models.chore import ChoreInstance

    instance_id = pool_instance["id"]

    # Parent hard-assigns to child_user
    client.post(
        f"/api/v1/family/chore-instances/{instance_id}/assign",
        headers=auth_headers,
        json={"child_user_id": child_user["id"]},
    )

    # Child abandons
    resp = client.post(
        f"/api/v1/child/chores/{instance_id}/abandon",
        headers=child_user["headers"],
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["claimed_at"] is None
    assert data["assigned_by_user_id"] is None
    assert data["is_pool_unclaimed"] is True

    row = db.query(ChoreInstance).filter(ChoreInstance.id == instance_id).first()
    assert row.assigned_by_user_id is None


# ---------------------------------------------------------------------------
# Edge case: two children claim same instance — second gets 409
# ---------------------------------------------------------------------------


def test_concurrent_claim_second_gets_409(client, child_user, child_user2, pool_instance):
    """Simulated race: first claim succeeds, second claim on same instance returns 409."""
    instance_id = pool_instance["id"]

    # child_user claims first
    resp1 = client.post(
        f"/api/v1/child/chores/{instance_id}/claim",
        headers=child_user["headers"],
    )
    assert resp1.status_code == 200

    # child_user2 tries to claim the same instance — should get 409
    resp2 = client.post(
        f"/api/v1/child/chores/{instance_id}/claim",
        headers=child_user2["headers"],
    )
    assert resp2.status_code == 409


# ---------------------------------------------------------------------------
# Edge case: claim instance already claimed by another child → 409
# ---------------------------------------------------------------------------


def test_claim_already_claimed_by_another_child_returns_409(client, child_user, child_user2, pool_instance):
    """Claiming an instance already claimed by another child returns 409."""
    instance_id = pool_instance["id"]

    client.post(f"/api/v1/child/chores/{instance_id}/claim", headers=child_user["headers"])

    resp = client.post(
        f"/api/v1/child/chores/{instance_id}/claim",
        headers=child_user2["headers"],
    )
    assert resp.status_code == 409


# ---------------------------------------------------------------------------
# Edge case: claim instance hard-assigned to a different child → 404 (not visible)
# ---------------------------------------------------------------------------


def test_claim_hard_assigned_to_other_child_returns_404(
    client, auth_headers, child_user, child_user2, pool_instance
):
    """An instance hard-assigned to child_user is invisible to child_user2 — returns 404."""
    instance_id = pool_instance["id"]

    # Parent hard-assigns to child_user
    client.post(
        f"/api/v1/family/chore-instances/{instance_id}/assign",
        headers=auth_headers,
        json={"child_user_id": child_user["id"]},
    )

    # child_user2 tries to claim — should get 404 (not visible)
    resp = client.post(
        f"/api/v1/child/chores/{instance_id}/claim",
        headers=child_user2["headers"],
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Error path: abandon instance with status pending_approval → 409
# ---------------------------------------------------------------------------


def test_abandon_pending_approval_instance_returns_409(client, child_user, pool_instance):
    """Abandoning an instance in pending_approval status returns 409."""
    instance_id = pool_instance["id"]

    # Claim then mark complete → pending_approval
    client.post(f"/api/v1/child/chores/{instance_id}/claim", headers=child_user["headers"])
    client.post(f"/api/v1/child/chores/{instance_id}/complete", headers=child_user["headers"])

    resp = client.post(
        f"/api/v1/child/chores/{instance_id}/abandon",
        headers=child_user["headers"],
    )
    assert resp.status_code == 409


# ---------------------------------------------------------------------------
# Error path: abandon instance belonging to different child → 404
# ---------------------------------------------------------------------------


def test_abandon_other_childs_instance_returns_404(client, child_user, child_user2, pool_instance):
    """Abandoning an instance claimed by another child returns 404."""
    instance_id = pool_instance["id"]

    # child_user claims it
    client.post(f"/api/v1/child/chores/{instance_id}/claim", headers=child_user["headers"])

    # child_user2 tries to abandon — should get 404
    resp = client.post(
        f"/api/v1/child/chores/{instance_id}/abandon",
        headers=child_user2["headers"],
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Integration: after abandon, GET /child/chores for another child includes unclaimed instance
# ---------------------------------------------------------------------------


def test_after_abandon_other_child_sees_unclaimed_instance(
    client, child_user, child_user2, pool_template, pool_instance
):
    """After child_user abandons, child_user2's GET /child/chores includes the unclaimed instance."""
    instance_id = pool_instance["id"]

    # child_user claims then abandons
    client.post(f"/api/v1/child/chores/{instance_id}/claim", headers=child_user["headers"])
    client.post(f"/api/v1/child/chores/{instance_id}/abandon", headers=child_user["headers"])

    # child_user2 fetches chores — should see the now-unclaimed pool instance
    resp = client.get("/api/v1/child/chores?date=2026-06-01", headers=child_user2["headers"])
    assert resp.status_code == 200
    instances = resp.json()["data"]
    pool_instances = [i for i in instances if i["template_id"] == pool_template["id"]]
    assert len(pool_instances) == 1
    assert pool_instances[0]["is_pool_unclaimed"] is True


# ---------------------------------------------------------------------------
# Integration: widened child query returns pool unclaimed tasks alongside personal tasks
# ---------------------------------------------------------------------------


def test_widened_query_returns_pool_and_personal_tasks(client, auth_headers, child_user, pool_template):
    """GET /child/chores returns both personal (assigned) and unclaimed pool tasks."""
    # Create an assigned template for child_user
    assigned_resp = client.post("/api/v1/family/chore-templates", headers=auth_headers, json={
        "name": "洗碗",
        "emoji": "🍽️",
        "coin_reward": 3,
        "frequency": "daily",
        "assignment_type": "assigned",
        "assignee_ids": [child_user["id"]],
    })
    assert assigned_resp.status_code == 201
    assigned_template_id = assigned_resp.json()["data"]["id"]

    resp = client.get("/api/v1/child/chores?date=2026-06-01", headers=child_user["headers"])
    assert resp.status_code == 200
    instances = resp.json()["data"]

    template_ids = {i["template_id"] for i in instances}
    assert pool_template["id"] in template_ids
    assert assigned_template_id in template_ids

    # Pool instance should be marked is_pool_unclaimed=True
    pool_inst = next(i for i in instances if i["template_id"] == pool_template["id"])
    assert pool_inst["is_pool_unclaimed"] is True

    # Assigned instance should be is_pool_unclaimed=False
    assigned_inst = next(i for i in instances if i["template_id"] == assigned_template_id)
    assert assigned_inst["is_pool_unclaimed"] is False


def test_hard_assigned_to_other_child_not_visible(
    client, auth_headers, child_user, child_user2, pool_template, pool_instance
):
    """An instance hard-assigned to child_user is NOT returned in child_user2's query."""
    instance_id = pool_instance["id"]

    # Parent hard-assigns to child_user
    client.post(
        f"/api/v1/family/chore-instances/{instance_id}/assign",
        headers=auth_headers,
        json={"child_user_id": child_user["id"]},
    )

    # child_user2 fetches chores — should NOT see the hard-assigned instance
    resp = client.get("/api/v1/child/chores?date=2026-06-01", headers=child_user2["headers"])
    assert resp.status_code == 200
    instances = resp.json()["data"]
    ids = [i["id"] for i in instances]
    assert instance_id not in ids


def test_claimed_by_other_child_not_visible(
    client, child_user, child_user2, pool_template, pool_instance
):
    """An instance claimed by child_user is NOT returned in child_user2's query."""
    instance_id = pool_instance["id"]

    # child_user claims it
    client.post(f"/api/v1/child/chores/{instance_id}/claim", headers=child_user["headers"])

    # child_user2 fetches chores — should NOT see the claimed instance
    resp = client.get("/api/v1/child/chores?date=2026-06-01", headers=child_user2["headers"])
    assert resp.status_code == 200
    instances = resp.json()["data"]
    ids = [i["id"] for i in instances]
    assert instance_id not in ids
