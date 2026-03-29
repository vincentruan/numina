import pytest


@pytest.fixture
def category_id(client, auth_headers):
    response = client.get("/api/v1/categories", headers=auth_headers)
    assert response.status_code == 200
    categories = response.json()
    physical = [c for c in categories if c["asset_type"] == "physical"]
    assert len(physical) > 0
    return physical[0]["id"]


@pytest.fixture
def sample_wish(client, auth_headers):
    response = client.post("/api/v1/wishes", headers=auth_headers, json={
        "name": "MacBook Pro",
        "description": "工作用笔记本",
        "expected_price": 15000,
        "priority": "high",
        "currency": "CNY",
    })
    assert response.status_code == 201
    return response.json()


def test_create_wish(client, auth_headers):
    response = client.post("/api/v1/wishes", headers=auth_headers, json={
        "name": "索尼相机",
        "expected_price": 8000,
        "priority": "medium",
    })
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "索尼相机"
    assert data["expected_price"] == 8000
    assert data["priority"] == "medium"
    assert data["status"] == "pending"
    assert data["realized_asset_id"] is None


def test_list_wishes(client, auth_headers, sample_wish):
    response = client.get("/api/v1/wishes", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["name"] == "MacBook Pro"


def test_list_wishes_filter_by_status(client, auth_headers, sample_wish):
    response = client.get("/api/v1/wishes?status=pending", headers=auth_headers)
    assert response.status_code == 200
    assert len(response.json()) == 1

    response = client.get("/api/v1/wishes?status=realized", headers=auth_headers)
    assert response.status_code == 200
    assert len(response.json()) == 0


def test_get_wish(client, auth_headers, sample_wish):
    wish_id = sample_wish["id"]
    response = client.get(f"/api/v1/wishes/{wish_id}", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["name"] == "MacBook Pro"


def test_update_wish(client, auth_headers, sample_wish):
    wish_id = sample_wish["id"]
    response = client.put(f"/api/v1/wishes/{wish_id}", headers=auth_headers, json={
        "name": "MacBook Pro M4",
        "expected_price": 18000,
    })
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "MacBook Pro M4"
    assert data["expected_price"] == 18000


def test_delete_wish(client, auth_headers, sample_wish):
    wish_id = sample_wish["id"]
    response = client.delete(f"/api/v1/wishes/{wish_id}", headers=auth_headers)
    assert response.status_code == 200

    response = client.get(f"/api/v1/wishes/{wish_id}", headers=auth_headers)
    assert response.status_code == 404


def test_realize_wish(client, auth_headers, sample_wish, category_id):
    """Realizing a wish creates an asset and marks the wish as realized."""
    wish_id = sample_wish["id"]
    response = client.post(f"/api/v1/wishes/{wish_id}/realize", headers=auth_headers, json={
        "purchase_price": 14500,
        "purchase_date": "2026-03-01",
        "category_id": category_id,
    })
    assert response.status_code == 201
    asset = response.json()
    assert asset["name"] == "MacBook Pro"
    assert asset["purchase_price"] == 14500

    # Wish should now be realized
    wish_response = client.get(f"/api/v1/wishes/{wish_id}", headers=auth_headers)
    wish = wish_response.json()
    assert wish["status"] == "realized"
    assert wish["realized_asset_id"] == asset["id"]


def test_cross_family_isolation(client, auth_headers, second_user_headers, sample_wish):
    wish_id = sample_wish["id"]
    response = client.get(f"/api/v1/wishes/{wish_id}", headers=second_user_headers)
    assert response.status_code == 404
