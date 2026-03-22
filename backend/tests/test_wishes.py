import pytest


@pytest.fixture
def category_id(client, auth_headers):
    """Get a system category ID for creating wishes"""
    response = client.get("/api/v1/categories", headers=auth_headers)
    assert response.status_code == 200
    categories = response.json()
    physical = [c for c in categories if c["asset_type"] == "physical"]
    assert len(physical) > 0
    return physical[0]["id"]


@pytest.fixture
def sample_wish(client, auth_headers, category_id):
    """Create a sample wish"""
    response = client.post("/api/v1/wishes", headers=auth_headers, json={
        "name": "iPhone 15 Pro",
        "description": "想买最新款的 iPhone",
        "expected_price": 8999,
        "priority": "high",
        "category_id": category_id
    })
    assert response.status_code == 201
    return response.json()


def test_create_wish(client, auth_headers, category_id):
    """Test creating a wish"""
    response = client.post("/api/v1/wishes", headers=auth_headers, json={
        "name": "MacBook Pro",
        "description": "需要一台新的工作电脑",
        "expected_price": 15999,
        "priority": "medium",
        "category_id": category_id
    })
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "MacBook Pro"
    assert data["description"] == "需要一台新的工作电脑"
    assert data["expected_price"] == 15999
    assert data["priority"] == "medium"
    assert data["status"] == "pending"
    assert data["category_id"] == category_id


def test_create_wish_minimal(client, auth_headers):
    """Test creating a wish with minimal fields"""
    response = client.post("/api/v1/wishes", headers=auth_headers, json={
        "name": "新手机"
    })
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "新手机"
    assert data["priority"] == "medium"
    assert data["status"] == "pending"


def test_list_wishes(client, auth_headers, sample_wish):
    """Test listing wishes"""
    response = client.get("/api/v1/wishes", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1
    assert any(w["id"] == sample_wish["id"] for w in data)


def test_list_wishes_with_status_filter(client, auth_headers, sample_wish):
    """Test listing wishes with status filter"""
    response = client.get("/api/v1/wishes?status=pending", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert all(w["status"] == "pending" for w in data)


def test_get_wish(client, auth_headers, sample_wish):
    """Test getting a single wish"""
    response = client.get(f"/api/v1/wishes/{sample_wish['id']}", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == sample_wish["id"]
    assert data["name"] == sample_wish["name"]


def test_get_wish_not_found(client, auth_headers):
    """Test getting a non-existent wish"""
    response = client.get("/api/v1/wishes/nonexistent", headers=auth_headers)
    assert response.status_code == 404


def test_update_wish(client, auth_headers, sample_wish):
    """Test updating a wish"""
    response = client.put(f"/api/v1/wishes/{sample_wish['id']}", headers=auth_headers, json={
        "name": "iPhone 16 Pro",
        "expected_price": 9999,
        "priority": "low"
    })
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "iPhone 16 Pro"
    assert data["expected_price"] == 9999
    assert data["priority"] == "low"


def test_update_wish_status(client, auth_headers, sample_wish):
    """Test updating wish status"""
    response = client.put(f"/api/v1/wishes/{sample_wish['id']}", headers=auth_headers, json={
        "status": "cancelled"
    })
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "cancelled"


def test_delete_wish(client, auth_headers, sample_wish):
    """Test deleting a wish"""
    response = client.delete(f"/api/v1/wishes/{sample_wish['id']}", headers=auth_headers)
    assert response.status_code == 200

    # Verify it's deleted
    response = client.get(f"/api/v1/wishes/{sample_wish['id']}", headers=auth_headers)
    assert response.status_code == 404


def test_realize_wish(client, auth_headers, sample_wish):
    """Test realizing a wish (converting to asset)"""
    response = client.post(f"/api/v1/wishes/{sample_wish['id']}/realize", headers=auth_headers, json={
        "purchase_price": 8499,
        "purchase_date": "2024-03-20"
    })
    assert response.status_code == 201
    asset_data = response.json()
    assert asset_data["name"] == sample_wish["name"]
    assert asset_data["purchase_price"] == 8499
    assert asset_data["current_value"] == 8499

    # Verify wish status is updated
    wish_response = client.get(f"/api/v1/wishes/{sample_wish['id']}", headers=auth_headers)
    assert wish_response.status_code == 200
    wish_data = wish_response.json()
    assert wish_data["status"] == "realized"
    assert wish_data["realized_asset_id"] == asset_data["id"]


def test_realize_wish_without_category(client, auth_headers, category_id):
    """Test realizing a wish without category requires category_id in request"""
    # Create wish without category
    response = client.post("/api/v1/wishes", headers=auth_headers, json={
        "name": "无分类心愿",
        "expected_price": 1000
    })
    assert response.status_code == 201
    wish = response.json()

    # Try to realize without category_id - should fail
    response = client.post(f"/api/v1/wishes/{wish['id']}/realize", headers=auth_headers, json={
        "purchase_price": 999,
        "purchase_date": "2024-03-20"
    })
    assert response.status_code == 400

    # Realize with category_id - should succeed
    response = client.post(f"/api/v1/wishes/{wish['id']}/realize", headers=auth_headers, json={
        "purchase_price": 999,
        "purchase_date": "2024-03-20",
        "category_id": category_id
    })
    assert response.status_code == 201


def test_realize_already_realized_wish(client, auth_headers, sample_wish):
    """Test realizing an already realized wish"""
    # First realization
    response = client.post(f"/api/v1/wishes/{sample_wish['id']}/realize", headers=auth_headers, json={
        "purchase_price": 8499,
        "purchase_date": "2024-03-20"
    })
    assert response.status_code == 201

    # Second realization should fail
    response = client.post(f"/api/v1/wishes/{sample_wish['id']}/realize", headers=auth_headers, json={
        "purchase_price": 8499,
        "purchase_date": "2024-03-20"
    })
    assert response.status_code == 400


def test_cross_family_isolation(client, auth_headers, second_user_headers, sample_wish):
    """Test that users cannot access wishes from other families"""
    # Second user should not see first user's wish
    response = client.get(f"/api/v1/wishes/{sample_wish['id']}", headers=second_user_headers)
    assert response.status_code == 404

    # Second user should not be able to update first user's wish
    response = client.put(f"/api/v1/wishes/{sample_wish['id']}", headers=second_user_headers, json={
        "name": "Hacked"
    })
    assert response.status_code == 404

    # Second user should not be able to delete first user's wish
    response = client.delete(f"/api/v1/wishes/{sample_wish['id']}", headers=second_user_headers)
    assert response.status_code == 404


def test_update_permission(client, auth_headers, second_user_headers, category_id):
    """Test that only the creator can update/delete their wish"""
    # First user creates a wish
    response = client.post("/api/v1/wishes", headers=auth_headers, json={
        "name": "First User Wish",
        "expected_price": 5000,
        "category_id": category_id
    })
    assert response.status_code == 201
    wish = response.json()

    # Second user (different family) cannot see it
    response = client.get(f"/api/v1/wishes/{wish['id']}", headers=second_user_headers)
    assert response.status_code == 404

    # Second user cannot update it
    response = client.put(f"/api/v1/wishes/{wish['id']}", headers=second_user_headers, json={
        "name": "Modified"
    })
    assert response.status_code == 404

    # Second user cannot delete it
    response = client.delete(f"/api/v1/wishes/{wish['id']}", headers=second_user_headers)
    assert response.status_code == 404
