"""Tests for GET/PATCH /family/settings (coin tier config) and GET /family/children/{id}/balance."""

import pytest


def test_get_family_settings_defaults(client, auth_headers):
    resp = client.get("/api/v1/family/settings", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["coin_copper_to_silver"] == 10
    assert data["coin_silver_to_gold"] == 10
    assert "auto_approve_hours" in data
    assert "ai_enabled" in data


def test_patch_coin_rates(client, auth_headers):
    resp = client.patch("/api/v1/family/settings", headers=auth_headers, json={
        "coin_copper_to_silver": 5,
        "coin_silver_to_gold": 20,
    })
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["coin_copper_to_silver"] == 5
    assert data["coin_silver_to_gold"] == 20

    # Verify persisted
    get_resp = client.get("/api/v1/family/settings", headers=auth_headers)
    assert get_resp.json()["data"]["coin_copper_to_silver"] == 5
    assert get_resp.json()["data"]["coin_silver_to_gold"] == 20


def test_patch_coin_rate_boundary_min_accepted(client, auth_headers):
    """Exact lower boundary (1) must be accepted."""
    resp = client.patch("/api/v1/family/settings", headers=auth_headers, json={
        "coin_copper_to_silver": 1,
        "coin_silver_to_gold": 1,
    })
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["coin_copper_to_silver"] == 1
    assert data["coin_silver_to_gold"] == 1


def test_patch_coin_rate_boundary_max_accepted(client, auth_headers):
    """Exact upper boundary (100) must be accepted."""
    resp = client.patch("/api/v1/family/settings", headers=auth_headers, json={
        "coin_copper_to_silver": 100,
        "coin_silver_to_gold": 100,
    })
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["coin_copper_to_silver"] == 100
    assert data["coin_silver_to_gold"] == 100


def test_patch_coin_rate_zero_rejected(client, auth_headers):
    resp = client.patch("/api/v1/family/settings", headers=auth_headers, json={
        "coin_copper_to_silver": 0,
    })
    assert resp.status_code == 422


def test_patch_coin_rate_over_100_rejected(client, auth_headers):
    resp = client.patch("/api/v1/family/settings", headers=auth_headers, json={
        "coin_silver_to_gold": 101,
    })
    assert resp.status_code == 422


@pytest.fixture
def child_user(client, auth_headers):
    resp = client.post("/api/v1/family/children", headers=auth_headers, json={
        "display_name": "小明",
        "password": "ChildPass1",
        "username": "xiaoming7",
        "avatar_color": "#FF5733",
        "pin": ["🐱", "🌟", "🎈", "🐶"],
    })
    assert resp.status_code == 201
    return resp.json()["data"]


def test_get_child_balance(client, auth_headers, child_user):
    resp = client.get(f"/api/v1/family/children/{child_user['id']}/balance", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["data"]["balance"] == 0


def test_get_child_balance_after_grant(client, auth_headers, child_user):
    client.post("/api/v1/family/coins/grant", headers=auth_headers, json={
        "child_user_id": child_user["id"],
        "amount": 42,
        "reason": "测试",
    })
    resp = client.get(f"/api/v1/family/children/{child_user['id']}/balance", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["data"]["balance"] == 42


def test_get_child_balance_cross_family_fails(client, auth_headers, second_user_headers):
    """Parent cannot query balance of a child in another family."""
    resp = client.post("/api/v1/family/children", headers=second_user_headers, json={
        "display_name": "外家孩子",
        "password": "ChildPass1",
        "username": "otherchild2",
        "avatar_color": "#AABBCC",
        "pin": ["🐸", "🦊", "🐼", "🐨"],
    })
    assert resp.status_code == 201
    other_child_id = resp.json()["data"]["id"]

    resp = client.get(f"/api/v1/family/children/{other_child_id}/balance", headers=auth_headers)
    assert resp.status_code == 404


def test_get_all_child_balances_empty(client, auth_headers):
    """Returns empty dict when family has no children."""
    resp = client.get("/api/v1/family/children/balances", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["data"] == {}


def test_get_all_child_balances_multiple_children(client, auth_headers):
    """Batch endpoint returns correct balances for all children in one request."""
    # Create two children
    child_a = client.post("/api/v1/family/children", headers=auth_headers, json={
        "display_name": "小明",
        "password": "ChildPass1",
        "username": "xiaoming6", "avatar_color": "#FF5733", "pin": ["🐱", "🌟", "🎈", "🐶"],
    }).json()["data"]
    child_b = client.post("/api/v1/family/children", headers=auth_headers, json={
        "display_name": "小红",
        "password": "ChildPass1",
        "username": "xiaohong5", "avatar_color": "#33AAFF", "pin": ["🌈", "🍎", "🐸", "🦁"],
    }).json()["data"]

    # Grant different amounts
    client.post("/api/v1/family/coins/grant", headers=auth_headers, json={
        "child_user_id": child_a["id"], "amount": 30, "reason": "测试A",
    })
    client.post("/api/v1/family/coins/grant", headers=auth_headers, json={
        "child_user_id": child_b["id"], "amount": 50, "reason": "测试B",
    })

    resp = client.get("/api/v1/family/children/balances", headers=auth_headers)
    assert resp.status_code == 200
    balances = resp.json()["data"]
    assert balances[str(child_a["id"])] == 30
    assert balances[str(child_b["id"])] == 50


def test_get_all_child_balances_cross_family_isolation(client, auth_headers, second_user_headers):
    """Batch endpoint only returns children from the requesting parent's family."""
    # Create child in second family
    client.post("/api/v1/family/children", headers=second_user_headers, json={
        "display_name": "外家孩子",
        "password": "ChildPass1",
        "username": "otherchild", "avatar_color": "#AABBCC", "pin": ["🐸", "🦊", "🐼", "🐨"],
    })

    resp = client.get("/api/v1/family/children/balances", headers=auth_headers)
    assert resp.status_code == 200
    # First family has no children, so result is empty
    assert resp.json()["data"] == {}

