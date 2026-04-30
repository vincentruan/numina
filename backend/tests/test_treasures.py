"""Tests for GET /child/treasures endpoint."""

import pytest


@pytest.fixture
def category_id(client, auth_headers):
    resp = client.get("/api/v1/categories", headers=auth_headers)
    categories = resp.json()["data"]
    physical = [c for c in categories if c["asset_type"] == "physical"]
    return physical[0]["id"]


@pytest.fixture
def child_user(client, auth_headers):
    resp = client.post("/api/v1/family/children", headers=auth_headers, json={
        "username": "xiaoming",
        "display_name": "小明",
        "password": "ChildPass1",
        "avatar_color": "#FF5733",
        "pin": ["🐱", "🌟", "🎈", "🐶"],
    })
    assert resp.status_code == 201
    child = resp.json()["data"]
    login = client.post("/api/v1/auth/child/login", json={
        "child_id": child["id"],
        "pin_sequence": ["🐱", "🌟", "🎈", "🐶"],
    })
    token = login.json()["data"]["access_token"]
    client.cookies.delete("access_token")
    client.cookies.delete("child_access_token")
    return {"id": child["id"], "headers": {"Authorization": f"Bearer {token}"}}


def test_treasures_empty(client, auth_headers, child_user):
    resp = client.get("/api/v1/child/treasures", headers=child_user["headers"])
    assert resp.status_code == 200
    assert resp.json()["data"] == []


def test_treasures_shows_child_assets(client, auth_headers, child_user, category_id):
    """Wish-fulfilled assets appear in the treasures gallery with coins_spent populated."""
    # 1. Child creates a wish
    wish_resp = client.post("/api/v1/child/wishes", headers=child_user["headers"], json={
        "name": "新玩具",
        "priority": "high",
    })
    assert wish_resp.status_code == 201
    wish_id = wish_resp.json()["data"]["id"]

    # 2. Parent grants coins so child can afford the wish
    client.post("/api/v1/family/coins/grant", headers=auth_headers, json={
        "child_user_id": child_user["id"],
        "amount": 50,
        "reason": "测试赠送",
    })

    # 3. Parent approves wish with cost=30
    approve_resp = client.post(f"/api/v1/family/child-wishes/{wish_id}/approve", headers=auth_headers, json={
        "star_coin_cost": 30,
    })
    assert approve_resp.status_code == 200

    # 4. Child requests redemption
    client.post(f"/api/v1/child/wishes/{wish_id}/request-redemption", headers=child_user["headers"])

    # 5. Parent realizes the wish (creates asset atomically)
    realize_resp = client.post(f"/api/v1/family/child-wishes/{wish_id}/realize", headers=auth_headers, json={
        "category_id": category_id,
    })
    assert realize_resp.status_code == 200

    # 6. Verify the asset appears in child's treasures with correct coins_spent
    treasures_resp = client.get("/api/v1/child/treasures", headers=child_user["headers"])
    assert treasures_resp.status_code == 200
    treasures = treasures_resp.json()["data"]
    assert len(treasures) == 1
    assert treasures[0]["name"] == "新玩具"
    assert treasures[0]["coins_spent"] == 30


def test_treasures_cross_family_isolation(client, auth_headers, child_user, second_user_headers, category_id):
    """Child cannot see assets belonging to another family."""
    # Create a child in the second family
    resp2 = client.post("/api/v1/family/children", headers=second_user_headers, json={
        "display_name": "小花",
        "password": "ChildPass1",
        "username": "xiaohua",
        "avatar_color": "#AABBCC",
        "pin": ["🐸", "🦊", "🐼", "🐨"],
    })
    assert resp2.status_code == 201
    other_child_id = resp2.json()["data"]["id"]

    # Get a category for the second family
    cat_resp = client.get("/api/v1/categories", headers=second_user_headers)
    other_cat_id = [c for c in cat_resp.json()["data"] if c["asset_type"] == "physical"][0]["id"]

    # Create asset for other child
    client.post("/api/v1/assets", headers=second_user_headers, json={
        "name": "别人的玩具",
        "asset_type": "physical",
        "category_id": other_cat_id,
        "purchase_price": 0,
        "user_id": other_child_id,
    })

    # Our child should not see the other child's asset
    resp = client.get("/api/v1/child/treasures", headers=child_user["headers"])
    assert resp.status_code == 200
    names = [t["name"] for t in resp.json()["data"]]
    assert "别人的玩具" not in names
