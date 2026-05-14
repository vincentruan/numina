def test_recent_activities_empty(client, auth_headers):
    """Returns empty list when no activities exist."""
    response = client.get("/api/v1/activities/recent", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["data"] == []


def test_activities_after_asset_create(client, auth_headers):
    """Creating an asset should log an activity."""
    categories = client.get("/api/v1/categories", headers=auth_headers).json()["data"]
    category_id = next(c["id"] for c in categories if c["asset_type"] == "physical")

    client.post("/api/v1/assets", headers=auth_headers, json={
        "name": "测试资产",
        "category_id": category_id,
        "asset_type": "physical",
        "purchase_price": 5000,
    })

    response = client.get("/api/v1/activities/recent", headers=auth_headers)
    assert response.status_code == 200
    activities = response.json()["data"]
    assert len(activities) >= 1

    activity = activities[0]
    assert "id" in activity
    assert "type" in activity
    assert "entity_type" in activity
    assert "title" in activity
    assert "created_at" in activity


def test_activities_limit(client, auth_headers):
    """Limit parameter caps the number of returned activities."""
    categories = client.get("/api/v1/categories", headers=auth_headers).json()["data"]
    category_id = next(c["id"] for c in categories if c["asset_type"] == "physical")

    for i in range(5):
        client.post("/api/v1/assets", headers=auth_headers, json={
            "name": f"资产{i}",
            "category_id": category_id,
            "asset_type": "physical",
        })

    response = client.get("/api/v1/activities/recent?limit=3", headers=auth_headers)
    assert response.status_code == 200
    assert len(response.json()["data"]) <= 3


def test_activities_family_isolation(client, auth_headers, second_user_headers):
    """Activities are scoped to the user's family."""
    categories = client.get("/api/v1/categories", headers=auth_headers).json()["data"]
    category_id = next(c["id"] for c in categories if c["asset_type"] == "physical")

    client.post("/api/v1/assets", headers=auth_headers, json={
        "name": "家庭1资产",
        "category_id": category_id,
        "asset_type": "physical",
    })

    response = client.get("/api/v1/activities/recent", headers=second_user_headers)
    assert response.status_code == 200
    assert response.json()["data"] == []


def test_activities_require_auth(client):
    response = client.get("/api/v1/activities/recent")
    assert response.status_code == 401
