"""Tests for ChildWish feature: CRUD, approval workflow, realize, defer, stats."""

import pytest

from tests.conftest import child_login_two_phase


def _data(resp):
    """Unwrap envelope response: {"code": "OK", "data": {...}} → data."""
    body = resp.json()
    return body.get("data", body)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def child_user(client, auth_headers):
    """Create a child user and return their info + child auth headers."""
    resp = client.post("/api/v1/family/children", headers=auth_headers, json={
        "display_name": "小明",
        "password": "ChildPass1",
        "username": "xiaoming8",
        "avatar_color": "#FF5733",
        "pin": ["🐱", "🌟", "🎈", "🐶"],
    })
    assert resp.status_code == 201
    child = _data(resp)
    token = child_login_two_phase(client, "xiaoming8", "ChildPass1", ["🐱", "🌟", "🎈", "🐶"])
    client.cookies.delete("access_token")
    return {"id": child["id"], "headers": {"Authorization": f"Bearer {token}"}}


@pytest.fixture
def category_id(client, auth_headers):
    resp = client.get("/api/v1/categories", headers=auth_headers)
    assert resp.status_code == 200
    categories = _data(resp)
    physical = [c for c in categories if c["asset_type"] == "physical"]
    assert len(physical) > 0
    return physical[0]["id"]


@pytest.fixture
def sample_wish(client, child_user):
    resp = client.post("/api/v1/child/wishes", headers=child_user["headers"], json={
        "name": "乐高积木",
        "description": "城市系列",
        "emoji": "🧱",
        "priority": "high",
    })
    assert resp.status_code == 201
    return _data(resp)


# ---------------------------------------------------------------------------
# Unit 2: Child CRUD
# ---------------------------------------------------------------------------

def test_create_wish_returns_pending_review(client, child_user):
    resp = client.post("/api/v1/child/wishes", headers=child_user["headers"], json={
        "name": "玩具车",
        "priority": "medium",
    })
    assert resp.status_code == 201
    data = _data(resp)
    assert data["name"] == "玩具车"
    assert data["status"] == "pending_review"
    assert data["has_cost_set"] is False
    assert data["progress"] is None


def test_create_wish_name_too_long(client, child_user):
    resp = client.post("/api/v1/child/wishes", headers=child_user["headers"], json={
        "name": "x" * 51,
        "priority": "low",
    })
    assert resp.status_code == 422


def test_create_wish_invalid_priority(client, child_user):
    resp = client.post("/api/v1/child/wishes", headers=child_user["headers"], json={
        "name": "玩具",
        "priority": "urgent",
    })
    assert resp.status_code == 422


def test_list_wishes_grouped_by_status(client, child_user, sample_wish):
    resp = client.get("/api/v1/child/wishes", headers=child_user["headers"])
    assert resp.status_code == 200
    data = _data(resp)
    assert len(data["pending_review"]) == 1
    assert data["pending_review"][0]["id"] == str(sample_wish["id"])
    assert data["active"] == []
    assert data["realized"] == []


def test_get_wish_detail(client, child_user, sample_wish):
    resp = client.get(f"/api/v1/child/wishes/{sample_wish['id']}", headers=child_user["headers"])
    assert resp.status_code == 200
    assert _data(resp)["id"] == str(sample_wish["id"])


def test_get_wish_not_found(client, child_user):
    resp = client.get("/api/v1/child/wishes/999999999999999999", headers=child_user["headers"])
    assert resp.status_code == 404


def test_request_redemption_on_pending_review_fails(client, child_user, sample_wish):
    resp = client.post(
        f"/api/v1/child/wishes/{sample_wish['id']}/request-redemption",
        headers=child_user["headers"],
    )
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Unit 3: Parent approval / rejection / cost update
# ---------------------------------------------------------------------------

def test_approve_wish_sets_active_and_cost(client, auth_headers, child_user, sample_wish):
    resp = client.post(
        f"/api/v1/family/child-wishes/{sample_wish['id']}/approve",
        headers=auth_headers,
        json={"star_coin_cost": 100},
    )
    assert resp.status_code == 200
    data = _data(resp)
    assert data["status"] == "active"
    assert data["star_coin_cost"] == 100


def test_approve_wish_invalid_cost(client, auth_headers, child_user, sample_wish):
    resp = client.post(
        f"/api/v1/family/child-wishes/{sample_wish['id']}/approve",
        headers=auth_headers,
        json={"star_coin_cost": 0},
    )
    assert resp.status_code == 422


def test_approve_already_active_fails(client, auth_headers, child_user, sample_wish):
    client.post(
        f"/api/v1/family/child-wishes/{sample_wish['id']}/approve",
        headers=auth_headers,
        json={"star_coin_cost": 50},
    )
    resp = client.post(
        f"/api/v1/family/child-wishes/{sample_wish['id']}/approve",
        headers=auth_headers,
        json={"star_coin_cost": 50},
    )
    assert resp.status_code == 422


def test_reject_wish(client, auth_headers, child_user, sample_wish):
    resp = client.post(
        f"/api/v1/family/child-wishes/{sample_wish['id']}/reject",
        headers=auth_headers,
        json={"rejection_reason": "太贵了"},
    )
    assert resp.status_code == 200
    data = _data(resp)
    assert data["status"] == "rejected"
    assert data["rejection_reason"] == "太贵了"


def test_update_cost_lower_succeeds(client, auth_headers, child_user, sample_wish):
    client.post(
        f"/api/v1/family/child-wishes/{sample_wish['id']}/approve",
        headers=auth_headers,
        json={"star_coin_cost": 100},
    )
    resp = client.patch(
        f"/api/v1/family/child-wishes/{sample_wish['id']}/cost",
        headers=auth_headers,
        json={"star_coin_cost": 80},
    )
    assert resp.status_code == 200
    data = _data(resp)
    assert data["star_coin_cost"] == 80
    assert len(data["cost_history"]) == 1
    assert data["cost_history"][0]["old_cost"] == 100
    assert data["cost_history"][0]["new_cost"] == 80


def test_update_cost_higher_fails(client, auth_headers, child_user, sample_wish):
    client.post(
        f"/api/v1/family/child-wishes/{sample_wish['id']}/approve",
        headers=auth_headers,
        json={"star_coin_cost": 100},
    )
    resp = client.patch(
        f"/api/v1/family/child-wishes/{sample_wish['id']}/cost",
        headers=auth_headers,
        json={"star_coin_cost": 150},
    )
    assert resp.status_code == 422


def test_parent_queue_shows_pending(client, auth_headers, child_user, sample_wish):
    resp = client.get("/api/v1/family/child-wishes", headers=auth_headers)
    assert resp.status_code == 200
    ids = [w["id"] for w in _data(resp)]
    assert sample_wish["id"] in ids


def test_cross_family_isolation(client, second_user_headers, child_user, sample_wish):
    resp = client.post(
        f"/api/v1/family/child-wishes/{sample_wish['id']}/approve",
        headers=second_user_headers,
        json={"star_coin_cost": 50},
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Unit 4: Realize + defer
# ---------------------------------------------------------------------------

def _approve_grant_request(client, auth_headers, child_user, wish_id, cost=5):
    """Approve wish, grant coins to child, then request redemption."""
    client.post(
        f"/api/v1/family/child-wishes/{wish_id}/approve",
        headers=auth_headers,
        json={"star_coin_cost": cost},
    )
    client.post("/api/v1/family/coins/grant", headers=auth_headers, json={
        "child_user_id": child_user["id"],
        "amount": cost,
        "reason": "test grant",
    })
    client.post(
        f"/api/v1/child/wishes/{wish_id}/request-redemption",
        headers=child_user["headers"],
    )


def test_request_redemption_insufficient_balance(client, auth_headers, child_user, sample_wish):
    client.post(
        f"/api/v1/family/child-wishes/{sample_wish['id']}/approve",
        headers=auth_headers,
        json={"star_coin_cost": 999},
    )
    resp = client.post(
        f"/api/v1/child/wishes/{sample_wish['id']}/request-redemption",
        headers=child_user["headers"],
    )
    assert resp.status_code == 422


def test_request_redemption_sufficient_balance(client, auth_headers, child_user, sample_wish):
    client.post(
        f"/api/v1/family/child-wishes/{sample_wish['id']}/approve",
        headers=auth_headers,
        json={"star_coin_cost": 5},
    )
    client.post("/api/v1/family/coins/grant", headers=auth_headers, json={
        "child_user_id": child_user["id"],
        "amount": 10,
        "reason": "test",
    })
    resp = client.post(
        f"/api/v1/child/wishes/{sample_wish['id']}/request-redemption",
        headers=child_user["headers"],
    )
    assert resp.status_code == 200
    assert _data(resp)["status"] == "redemption_requested"


def test_realize_wish_creates_asset(client, auth_headers, child_user, sample_wish, category_id):
    _approve_grant_request(client, auth_headers, child_user, sample_wish["id"])
    resp = client.post(
        f"/api/v1/family/child-wishes/{sample_wish['id']}/realize",
        headers=auth_headers,
        json={"category_id": category_id},
    )
    assert resp.status_code == 200
    data = _data(resp)
    assert data["status"] == "realized"
    assert data["realized_asset_id"] is not None


def test_realize_wish_without_category_uses_default(client, auth_headers, child_user, sample_wish):
    _approve_grant_request(client, auth_headers, child_user, sample_wish["id"])
    resp = client.post(
        f"/api/v1/family/child-wishes/{sample_wish['id']}/realize",
        headers=auth_headers,
        json={},
    )
    assert resp.status_code == 200
    assert _data(resp)["status"] == "realized"


def test_realize_non_redemption_requested_fails(client, auth_headers, child_user, sample_wish):
    resp = client.post(
        f"/api/v1/family/child-wishes/{sample_wish['id']}/realize",
        headers=auth_headers,
        json={},
    )
    assert resp.status_code == 422


def test_defer_redemption(client, auth_headers, child_user, sample_wish):
    _approve_grant_request(client, auth_headers, child_user, sample_wish["id"])
    resp = client.post(
        f"/api/v1/family/child-wishes/{sample_wish['id']}/defer",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert _data(resp)["status"] == "active"


# ---------------------------------------------------------------------------
# Unit 5: Stats
# ---------------------------------------------------------------------------

def test_stats_empty(client, child_user):
    resp = client.get("/api/v1/child/wishes/stats", headers=child_user["headers"])
    assert resp.status_code == 200
    data = _data(resp)
    assert data["active_wish_count"] == 0
    assert data["realized_wish_count"] == 0
    assert data["priority_simulation"] == []
    assert data["balance"] == 0


def test_stats_with_active_wishes(client, auth_headers, child_user):
    for name, priority, cost in [("高优先级", "high", 200), ("中优先级", "medium", 150)]:
        r = client.post("/api/v1/child/wishes", headers=child_user["headers"], json={
            "name": name, "priority": priority,
        })
        wish_id = _data(r)["id"]
        client.post(
            f"/api/v1/family/child-wishes/{wish_id}/approve",
            headers=auth_headers,
            json={"star_coin_cost": cost},
        )

    resp = client.get("/api/v1/child/wishes/stats", headers=child_user["headers"])
    assert resp.status_code == 200
    data = _data(resp)
    assert data["active_wish_count"] == 2
    sim = data["priority_simulation"]
    assert sim[0]["priority"] == "high"
    assert sim[1]["priority"] == "medium"
