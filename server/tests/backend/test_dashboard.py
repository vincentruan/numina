import pytest


@pytest.fixture
def setup_test_data(client, auth_headers):
    """Create test assets and liabilities for dashboard tests"""
    # Get categories
    cat_response = client.get("/api/v1/categories", headers=auth_headers)
    categories = cat_response.json()["data"]
    physical_cat = [c for c in categories if c["asset_type"] == "physical"][0]
    financial_cat = [c for c in categories if c["asset_type"] == "financial"][0]

    # Create assets
    client.post("/api/v1/assets", headers=auth_headers, json={
        "name": "房产",
        "category_id": physical_cat["id"],
        "asset_type": "physical",
        "purchase_price": 3000000,
        "current_value": 3500000,
        "purchase_date": "2020-01-01",
        "expected_lifespan_days": 25550,
        "annual_maintenance_cost": 12000,
        "usage_frequency": "daily"
    })

    client.post("/api/v1/assets", headers=auth_headers, json={
        "name": "基金",
        "category_id": financial_cat["id"],
        "asset_type": "financial",
        "purchase_price": 200000,
        "current_value": 225000,
        "institution": "天天基金"
    })

    client.post("/api/v1/assets", headers=auth_headers, json={
        "name": "闲置跑步机",
        "category_id": physical_cat["id"],
        "asset_type": "physical",
        "purchase_price": 5000,
        "current_value": 3000,
        "purchase_date": "2023-01-01",
        "usage_frequency": "idle"
    })

    # Create liability
    client.post("/api/v1/liabilities", headers=auth_headers, json={
        "name": "房贷",
        "category": "mortgage",
        "original_amount": 2000000,
        "remaining_amount": 1800000,
        "monthly_payment": 12000
    })


def test_dashboard_overview(client, auth_headers, setup_test_data):
    """Test dashboard overview endpoint"""
    response = client.get("/api/v1/dashboard/overview", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()["data"]

    assert "total_assets" in data
    assert "total_liabilities" in data
    assert "net_worth" in data
    assert "asset_count" in data

    # total_assets = 3500000 + 225000 + 3000 = 3728000
    assert data["total_assets"] == 3728000
    # total_liabilities = 1800000
    assert data["total_liabilities"] == 1800000
    # net_worth = 3728000 - 1800000 = 1928000
    assert data["net_worth"] == 1928000
    assert data["asset_count"] == 3


def test_dashboard_allocation(client, auth_headers, setup_test_data):
    """Test asset allocation endpoint"""
    response = client.get("/api/v1/dashboard/allocation", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()["data"]

    assert "items" in data
    assert "total" in data
    assert len(data["items"]) >= 2  # At least 2 categories
    total_percentage = sum(item["percentage"] for item in data["items"])
    assert abs(total_percentage - 100.0) < 0.1  # Should sum to 100%


def test_dashboard_trend(client, auth_headers, setup_test_data):
    """Test net worth trend endpoint"""
    # Generate a snapshot first
    client.post("/api/v1/family/snapshots/generate", headers=auth_headers)

    response = client.get("/api/v1/dashboard/trend?period=month", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()["data"]

    assert "points" in data
    points = data["points"]
    assert isinstance(points, list)
    if len(points) > 0:
        assert "date" in points[0]
        assert "net_worth" in points[0]


def test_dashboard_top_assets(client, auth_headers, setup_test_data):
    """Test top assets endpoint"""
    response = client.get("/api/v1/dashboard/top-assets?limit=5", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()["data"]

    assert len(data) == 3  # We created 3 assets
    # Should be sorted by value descending
    assert data[0]["name"] == "房产"
    assert data[0]["current_value"] == 3500000
    assert data[1]["name"] == "基金"
    assert data[1]["current_value"] == 225000


def test_dashboard_daily_cost_ranking(client, auth_headers, setup_test_data):
    """Test daily cost ranking endpoint"""
    response = client.get("/api/v1/dashboard/daily-cost-ranking", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()["data"]

    # Should have assets with daily_cost calculated
    assert len(data) >= 1
    for item in data:
        assert "name" in item
        assert "daily_cost" in item
        assert "days_used" in item
        assert item["daily_cost"] > 0


def test_dashboard_low_usage_assets(client, auth_headers, setup_test_data):
    """Test low usage assets endpoint"""
    response = client.get("/api/v1/dashboard/low-usage-assets", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()["data"]

    # Should find the idle treadmill
    assert len(data) >= 1
    idle_assets = [a for a in data if a["name"] == "闲置跑步机"]
    assert len(idle_assets) == 1
    assert idle_assets[0]["usage_frequency"] == "idle"


def test_dashboard_investment_returns(client, auth_headers, setup_test_data):
    """Test investment returns endpoint"""
    response = client.get("/api/v1/dashboard/investment-returns", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()["data"]

    # Should only have financial assets
    assert len(data) == 1
    assert data[0]["name"] == "基金"
    assert "return_rate" in data[0]
    assert "profit" in data[0]
    # return_rate = (225000 - 200000) / 200000 * 100 = 12.5
    assert abs(data[0]["return_rate"] - 12.5) < 0.1
    assert data[0]["profit"] == 25000
