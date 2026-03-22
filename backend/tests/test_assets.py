import pytest


@pytest.fixture
def category_id(client, auth_headers):
    """Get a system category ID for creating assets"""
    response = client.get("/api/v1/categories", headers=auth_headers)
    assert response.status_code == 200
    categories = response.json()
    # Find a physical category (e.g., 房产)
    physical = [c for c in categories if c["asset_type"] == "physical"]
    assert len(physical) > 0
    return physical[0]["id"]


@pytest.fixture
def financial_category_id(client, auth_headers):
    """Get a financial category ID"""
    response = client.get("/api/v1/categories", headers=auth_headers)
    categories = response.json()
    financial = [c for c in categories if c["asset_type"] == "financial"]
    assert len(financial) > 0
    return financial[0]["id"]


@pytest.fixture
def sample_asset(client, auth_headers, category_id):
    """Create a sample physical asset"""
    response = client.post("/api/v1/assets", headers=auth_headers, json={
        "name": "朝阳区房产",
        "category_id": category_id,
        "asset_type": "physical",
        "purchase_price": 3000000,
        "current_value": 3500000,
        "purchase_date": "2020-01-15",
        "status": "in_use",
        "location": "北京市朝阳区",
        "expected_lifespan_days": 25550,
        "annual_maintenance_cost": 12000,
        "usage_frequency": "daily"
    })
    assert response.status_code == 201
    return response.json()


@pytest.fixture
def sample_financial_asset(client, auth_headers, financial_category_id):
    """Create a sample financial asset"""
    response = client.post("/api/v1/assets", headers=auth_headers, json={
        "name": "招商银行存款",
        "category_id": financial_category_id,
        "asset_type": "financial",
        "purchase_price": 200000,
        "current_value": 210000,
        "institution": "招商银行",
        "interest_rate": 2.5
    })
    assert response.status_code == 201
    return response.json()


def test_create_physical_asset(client, auth_headers, category_id):
    """Test creating a physical asset"""
    response = client.post("/api/v1/assets", headers=auth_headers, json={
        "name": "宝马X3",
        "category_id": category_id,
        "asset_type": "physical",
        "purchase_price": 400000,
        "current_value": 300000,
        "purchase_date": "2022-06-01",
        "status": "in_use",
        "usage_frequency": "daily",
        "expected_lifespan_days": 3650,
        "annual_maintenance_cost": 15000
    })
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "宝马X3"
    assert data["current_value"] == 300000
    assert data["usage_frequency"] == "daily"
    assert data["expected_lifespan_days"] == 3650
    assert data["annual_maintenance_cost"] == 15000


def test_create_financial_asset(client, auth_headers, financial_category_id):
    """Test creating a financial asset"""
    response = client.post("/api/v1/assets", headers=auth_headers, json={
        "name": "沪深300基金",
        "category_id": financial_category_id,
        "asset_type": "financial",
        "purchase_price": 100000,
        "current_value": 112500,
        "institution": "天天基金",
        "interest_rate": 5.0
    })
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "沪深300基金"
    assert data["institution"] == "天天基金"
    assert data["return_rate"] is not None
    assert abs(data["return_rate"] - 12.5) < 0.1  # (112500-100000)/100000*100


def test_list_assets(client, auth_headers, sample_asset, sample_financial_asset):
    """Test listing assets"""
    response = client.get("/api/v1/assets", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2


def test_list_assets_filter_by_type(client, auth_headers, sample_asset, sample_financial_asset):
    """Test filtering assets by type"""
    response = client.get("/api/v1/assets?asset_type=physical", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["asset_type"] == "physical"


def test_get_asset_detail(client, auth_headers, sample_asset):
    """Test getting asset detail"""
    asset_id = sample_asset["id"]
    response = client.get(f"/api/v1/assets/{asset_id}", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "朝阳区房产"
    assert data["daily_cost"] is not None  # Should have daily cost calculated


def test_update_asset(client, auth_headers, sample_asset):
    """Test updating an asset"""
    asset_id = sample_asset["id"]
    response = client.put(f"/api/v1/assets/{asset_id}", headers=auth_headers, json={
        "name": "朝阳区房产（已装修）",
        "current_value": 3800000
    })
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "朝阳区房产（已装修）"
    assert data["current_value"] == 3800000


def test_update_asset_value(client, auth_headers, sample_asset):
    """Test quick value update"""
    asset_id = sample_asset["id"]
    response = client.put(f"/api/v1/assets/{asset_id}/value", headers=auth_headers, json={
        "current_value": 4000000
    })
    assert response.status_code == 200
    assert response.json()["current_value"] == 4000000


def test_delete_asset(client, auth_headers, sample_asset):
    """Test archiving an asset"""
    asset_id = sample_asset["id"]
    response = client.delete(f"/api/v1/assets/{asset_id}", headers=auth_headers)
    assert response.status_code == 200

    # Verify it's archived (not in default list)
    list_response = client.get("/api/v1/assets", headers=auth_headers)
    ids = [a["id"] for a in list_response.json()]
    assert asset_id not in ids


def test_daily_cost_calculation(client, auth_headers, sample_asset):
    """Test daily cost is correctly calculated"""
    asset_id = sample_asset["id"]
    response = client.get(f"/api/v1/assets/{asset_id}", headers=auth_headers)
    data = response.json()
    assert data["daily_cost"] is not None
    assert data["daily_cost"] > 0
    # daily_cost = (purchase_price + annual_maintenance_cost * years) / days_used


def test_return_rate_calculation(client, auth_headers, sample_financial_asset):
    """Test return rate is correctly calculated for financial assets"""
    asset_id = sample_financial_asset["id"]
    response = client.get(f"/api/v1/assets/{asset_id}", headers=auth_headers)
    data = response.json()
    assert data["return_rate"] is not None
    # return_rate = (210000 - 200000) / 200000 * 100 = 5.0
    assert abs(data["return_rate"] - 5.0) < 0.1


def test_cross_family_isolation(client, auth_headers, second_user_headers, sample_asset):
    """Test that users from different families cannot access each other's assets"""
    asset_id = sample_asset["id"]
    response = client.get(f"/api/v1/assets/{asset_id}", headers=second_user_headers)
    assert response.status_code == 404


# Batch operation tests
def test_batch_archive_assets(client, auth_headers, category_id):
    """Test batch archiving assets"""
    # Create multiple assets
    asset_ids = []
    for i in range(3):
        response = client.post("/api/v1/assets", headers=auth_headers, json={
            "name": f"测试资产{i}",
            "category_id": category_id,
            "asset_type": "physical",
            "purchase_price": 10000 * (i + 1),
        })
        assert response.status_code == 201
        asset_ids.append(response.json()["id"])

    # Batch archive
    response = client.post("/api/v1/assets/batch/archive", headers=auth_headers, json={
        "asset_ids": asset_ids
    })
    assert response.status_code == 200
    data = response.json()
    assert data["success_count"] == 3
    assert data["failed_count"] == 0

    # Verify they are archived
    list_response = client.get("/api/v1/assets", headers=auth_headers)
    active_ids = [a["id"] for a in list_response.json()]
    for aid in asset_ids:
        assert aid not in active_ids


def test_batch_update_category(client, auth_headers, category_id, financial_category_id):
    """Test batch updating asset category"""
    # Create assets with physical category
    asset_ids = []
    for i in range(2):
        response = client.post("/api/v1/assets", headers=auth_headers, json={
            "name": f"测试资产{i}",
            "category_id": category_id,
            "asset_type": "physical",
        })
        assert response.status_code == 201
        asset_ids.append(response.json()["id"])

    # Batch update to financial category
    response = client.put("/api/v1/assets/batch/category", headers=auth_headers, json={
        "asset_ids": asset_ids,
        "category_id": financial_category_id
    })
    assert response.status_code == 200
    data = response.json()
    assert data["success_count"] == 2

    # Verify categories changed
    for aid in asset_ids:
        asset_response = client.get(f"/api/v1/assets/{aid}", headers=auth_headers)
        assert asset_response.json()["category_id"] == financial_category_id


def test_batch_update_tags(client, auth_headers, category_id):
    """Test batch updating asset tags"""
    # Create tags
    tag1 = client.post("/api/v1/tags", headers=auth_headers, json={
        "name": "标签1",
        "color": "#FF0000"
    }).json()
    tag2 = client.post("/api/v1/tags", headers=auth_headers, json={
        "name": "标签2",
        "color": "#00FF00"
    }).json()

    # Create assets
    asset_ids = []
    for i in range(2):
        response = client.post("/api/v1/assets", headers=auth_headers, json={
            "name": f"测试资产{i}",
            "category_id": category_id,
            "asset_type": "physical",
        })
        assert response.status_code == 201
        asset_ids.append(response.json()["id"])

    # Batch update tags
    response = client.put("/api/v1/assets/batch/tags", headers=auth_headers, json={
        "asset_ids": asset_ids,
        "tag_ids": [tag1["id"], tag2["id"]]
    })
    assert response.status_code == 200
    data = response.json()
    assert data["success_count"] == 2

    # Verify tags applied
    for aid in asset_ids:
        asset_response = client.get(f"/api/v1/assets/{aid}", headers=auth_headers)
        tags = asset_response.json()["tags"]
        assert len(tags) == 2


def test_batch_update_status(client, auth_headers, category_id):
    """Test batch updating asset status"""
    # Create assets
    asset_ids = []
    for i in range(2):
        response = client.post("/api/v1/assets", headers=auth_headers, json={
            "name": f"测试资产{i}",
            "category_id": category_id,
            "asset_type": "physical",
        })
        assert response.status_code == 201
        asset_ids.append(response.json()["id"])

    # Batch archive via status
    response = client.put("/api/v1/assets/batch/status", headers=auth_headers, json={
        "asset_ids": asset_ids,
        "status": "archived"
    })
    assert response.status_code == 200
    data = response.json()
    assert data["success_count"] == 2

    # Batch reactivate via status
    response = client.put("/api/v1/assets/batch/status", headers=auth_headers, json={
        "asset_ids": asset_ids,
        "status": "active"
    })
    assert response.status_code == 200
    assert response.json()["success_count"] == 2


def test_batch_export_assets(client, auth_headers, category_id):
    """Test batch exporting assets"""
    # Create assets
    asset_ids = []
    for i in range(3):
        response = client.post("/api/v1/assets", headers=auth_headers, json={
            "name": f"导出测试资产{i}",
            "category_id": category_id,
            "asset_type": "physical",
            "purchase_price": 10000 * (i + 1),
            "current_value": 12000 * (i + 1),
        })
        assert response.status_code == 201
        asset_ids.append(response.json()["id"])

    # Batch export
    response = client.post("/api/v1/assets/batch/export", headers=auth_headers, json={
        "asset_ids": asset_ids
    })
    assert response.status_code == 200
    data = response.json()
    assert data["format"] == "json"
    assert data["count"] == 3
    assert len(data["data"]) == 3

    # Verify export data structure
    exported = data["data"][0]
    assert "name" in exported
    assert "purchase_price" in exported
    assert "current_value" in exported


def test_batch_archive_cross_family_isolation(client, auth_headers, second_user_headers, category_id):
    """Test batch archive respects family isolation"""
    # Create asset with first user
    response = client.post("/api/v1/assets", headers=auth_headers, json={
        "name": "用户1资产",
        "category_id": category_id,
        "asset_type": "physical",
    })
    assert response.status_code == 201
    asset_id = response.json()["id"]

    # Second user tries to archive first user's asset
    response = client.post("/api/v1/assets/batch/archive", headers=second_user_headers, json={
        "asset_ids": [asset_id]
    })
    assert response.status_code == 200
    data = response.json()
    assert data["success_count"] == 0
    assert data["failed_count"] == 1
    assert len(data["errors"]) == 1
