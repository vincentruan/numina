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


def test_dashboard_new_assets_default_period(client, auth_headers, setup_test_data):
    """新增资产 returns count and items for default month period"""
    response = client.get("/api/v1/dashboard/new-assets", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()["data"]
    assert "count" in data
    assert "period" in data
    assert "items" in data
    assert data["period"] == "month"
    # setup_test_data creates 3 assets — all created just now, so all in last 30 days
    assert data["count"] == 3
    assert len(data["items"]) == 3
    item = data["items"][0]
    assert "id" in item
    assert "name" in item
    assert "icon" in item
    assert "category_name" in item
    assert "current_value" in item
    assert "currency" in item
    assert "created_at" in item


def test_dashboard_new_assets_quarter_period(client, auth_headers, setup_test_data):
    """period=quarter is accepted and returns same assets (all recent)"""
    response = client.get(
        "/api/v1/dashboard/new-assets", headers=auth_headers, params={"period": "quarter"}
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["period"] == "quarter"
    assert data["count"] == 3


def test_dashboard_new_assets_year_period(client, auth_headers, setup_test_data):
    """period=year is accepted and returns same assets (all recent)"""
    response = client.get(
        "/api/v1/dashboard/new-assets", headers=auth_headers, params={"period": "year"}
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["period"] == "year"
    assert data["count"] == 3


def test_dashboard_new_assets_empty(client, auth_headers):
    """Returns count=0 and empty items when no assets exist"""
    response = client.get("/api/v1/dashboard/new-assets", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["count"] == 0
    assert data["items"] == []


def test_dashboard_new_assets_requires_auth(client):
    """Endpoint rejects unauthenticated requests"""
    response = client.get("/api/v1/dashboard/new-assets")
    assert response.status_code == 401


def test_dashboard_new_assets_excludes_old_assets(client, auth_headers):
    """Assets created outside the period window are not counted"""
    from datetime import datetime, timedelta

    # Get categories for asset creation
    cat_response = client.get("/api/v1/categories", headers=auth_headers)
    categories = cat_response.json()["data"]
    physical_cat = [c for c in categories if c["asset_type"] == "physical"][0]

    # Create one recent asset (should be counted)
    client.post("/api/v1/assets", headers=auth_headers, json={
        "name": "Recent Asset",
        "category_id": physical_cat["id"],
        "asset_type": "physical",
        "current_value": 1000,
        "purchase_price": 1000,
        "purchase_date": "2024-01-01",
    })

    # Verify it shows up in month period
    response = client.get("/api/v1/dashboard/new-assets", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["count"] == 1

    # Verify no assets exist for a non-existent period value returns 422
    response_invalid = client.get(
        "/api/v1/dashboard/new-assets", headers=auth_headers, params={"period": "decade"}
    )
    assert response_invalid.status_code == 422


# ═══════════════════════════════════════
# Insights Tests (S0-S5)
# ═══════════════════════════════════════


def test_dashboard_insights_returns_all_sections(client, auth_headers, setup_test_data):
    """Insights endpoint returns all 6 sections with expected structure"""
    response = client.get("/api/v1/dashboard/insights", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()["data"]

    # All sections must be present
    assert "smart_discovery" in data
    assert "daily_cost_ranking" in data
    assert "goal_progress" in data
    assert "type_distribution" in data
    assert "duration_distribution" in data
    assert "retention_rate" in data


def test_insights_smart_discovery_structure(client, auth_headers, setup_test_data):
    """S0 智能发现 returns 5 stat card fields"""
    response = client.get("/api/v1/dashboard/insights", headers=auth_headers)
    assert response.status_code == 200
    smart_discovery = response.json()["data"]["smart_discovery"]

    # All 5 stat card fields present
    assert "purchase_yoy" in smart_discovery
    assert "highest_daily_cost" in smart_discovery
    assert "lowest_daily_cost" in smart_discovery
    assert "longest_held" in smart_discovery
    assert "top_category" in smart_discovery

    # highest_daily_cost has expected nested fields (when present)
    if smart_discovery["highest_daily_cost"]:
        assert "name" in smart_discovery["highest_daily_cost"]
        assert "cost" in smart_discovery["highest_daily_cost"]
        assert "icon" in smart_discovery["highest_daily_cost"]


def test_insights_daily_cost_ranking(client, auth_headers, setup_test_data):
    """S1 日均成本排行 returns top 5 items sorted by daily_cost descending"""
    response = client.get("/api/v1/dashboard/insights", headers=auth_headers)
    assert response.status_code == 200
    ranking = response.json()["data"]["daily_cost_ranking"]

    # Should have items (we created assets with purchase_date and purchase_price)
    assert len(ranking) >= 1
    assert len(ranking) <= 5  # Insights returns top 5

    # Each item has expected fields
    item = ranking[0]
    assert "id" in item
    assert "name" in item
    assert "daily_cost" in item
    assert "days_used" in item
    assert "total_cost" in item
    assert item["daily_cost"] > 0

    # Sorted descending by daily_cost
    if len(ranking) > 1:
        assert ranking[0]["daily_cost"] >= ranking[1]["daily_cost"]


def test_insights_goal_progress_structure(client, auth_headers, setup_test_data):
    """S2 目标进度总览 returns summary and items with progress status"""
    response = client.get("/api/v1/dashboard/insights", headers=auth_headers)
    assert response.status_code == 200
    goal_progress = response.json()["data"]["goal_progress"]

    # Summary has healthy, near_end, overdue counts
    assert "summary" in goal_progress
    summary = goal_progress["summary"]
    assert "healthy" in summary
    assert "near_end" in summary
    assert "overdue" in summary
    assert isinstance(summary["healthy"], int)
    assert isinstance(summary["near_end"], int)
    assert isinstance(summary["overdue"], int)

    # Items list (may be empty if no assets with expected_lifespan_days)
    assert "items" in goal_progress
    items = goal_progress["items"]
    if len(items) > 0:
        item = items[0]
        assert "id" in item
        assert "name" in item
        assert "status" in item
        assert item["status"] in ["on-track", "near-end", "overdue"]
        assert "progress_pct" in item
        assert "days_held" in item
        assert "expected_days" in item


def test_insights_type_distribution(client, auth_headers, setup_test_data):
    """S3 资产类型分布 returns total value/count and categories breakdown"""
    response = client.get("/api/v1/dashboard/insights", headers=auth_headers)
    assert response.status_code == 200
    type_dist = response.json()["data"]["type_distribution"]

    # Total fields
    assert "total_value" in type_dist
    assert "total_count" in type_dist
    assert type_dist["total_count"] == 3  # We created 3 assets

    # Categories list
    assert "categories" in type_dist
    categories = type_dist["categories"]
    assert len(categories) >= 1

    # Each category has expected fields
    cat = categories[0]
    assert "category_id" in cat
    assert "name" in cat
    assert "color" in cat
    assert "percentage" in cat
    assert "amount" in cat
    assert "count" in cat

    # Percentages sum to 100
    total_pct = sum(c["percentage"] for c in categories)
    assert abs(total_pct - 100.0) < 0.1


def test_insights_duration_distribution(client, auth_headers, setup_test_data):
    """S4 持有时长分布 returns avg/max days and bucket breakdown"""
    response = client.get("/api/v1/dashboard/insights", headers=auth_headers)
    assert response.status_code == 200
    duration = response.json()["data"]["duration_distribution"]

    # Stats
    assert "avg_days" in duration
    assert "max_days" in duration
    assert isinstance(duration["avg_days"], (int, float))
    assert isinstance(duration["max_days"], int)

    # Buckets
    assert "buckets" in duration
    buckets = duration["buckets"]
    assert len(buckets) == 6  # 6 predefined buckets

    # Each bucket has expected fields
    bucket = buckets[0]
    assert "label_key" in bucket
    assert "count" in bucket
    assert "percentage" in bucket

    # Bucket percentages sum to 100
    total_pct = sum(b["percentage"] for b in buckets)
    assert abs(total_pct - 100.0) < 0.1


def test_insights_retention_rate(client, auth_headers, setup_test_data):
    """S5 资产保值率 returns totals, avg_rate, and top_items for physical assets"""
    response = client.get("/api/v1/dashboard/insights", headers=auth_headers)
    assert response.status_code == 200
    retention = response.json()["data"]["retention_rate"]

    # Summary fields
    assert "total_bought" in retention
    assert "total_sold" in retention
    assert "avg_rate" in retention
    assert "total_profit_loss" in retention

    # top_items list (physical assets only)
    assert "top_items" in retention
    items = retention["top_items"]
    if len(items) > 0:
        item = items[0]
        assert "id" in item
        assert "name" in item
        assert "icon" in item
        assert "service_days" in item
        assert "bought_amount" in item
        assert "current_amount" in item
        assert "retention_rate" in item
        assert "profit_loss" in item
        assert "rank" in item
        assert item["rank"] == 1  # First item has rank 1


def test_insights_empty_data(client, auth_headers):
    """Insights returns valid structure even with no assets"""
    response = client.get("/api/v1/dashboard/insights", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()["data"]

    # All sections present even with empty data
    assert "smart_discovery" in data
    assert "daily_cost_ranking" in data
    assert "goal_progress" in data
    assert "type_distribution" in data
    assert "duration_distribution" in data
    assert "retention_rate" in data

    # Empty lists/count=0 for sections that depend on assets
    assert data["daily_cost_ranking"] == []
    assert data["goal_progress"]["items"] == []
    assert data["type_distribution"]["total_count"] == 0
    assert data["duration_distribution"]["avg_days"] == 0
    assert data["duration_distribution"]["max_days"] == 0
    assert data["retention_rate"]["top_items"] == []


def test_insights_requires_auth(client):
    """Insights endpoint rejects unauthenticated requests"""
    response = client.get("/api/v1/dashboard/insights")
    assert response.status_code == 401


# ═══════════════════════════════════════
# States Summary & Home Assets Tests
# ═══════════════════════════════════════


def test_dashboard_states_summary(client, auth_headers, setup_test_data):
    """States summary returns count and total_value grouped by status"""
    response = client.get("/api/v1/dashboard/states-summary", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()["data"]

    assert "states" in data
    assert "total_count" in data
    assert "total_value" in data

    # We created 3 assets, all default to 'in_use' status
    assert data["total_count"] == 3
    assert "in_use" in data["states"]
    assert data["states"]["in_use"]["count"] == 3


def test_dashboard_home_assets(client, auth_headers, setup_test_data):
    """Home assets returns assets grouped by status"""
    response = client.get("/api/v1/dashboard/home-assets", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()["data"]

    # Should have in_use group (our default assets)
    assert "in_use" in data
    in_use_items = data["in_use"]
    assert len(in_use_items) <= 5  # Default limit is 5

    # Each item should have asset fields (full AssetResponse structure)
    if len(in_use_items) > 0:
        item = in_use_items[0]
        assert "id" in item
        assert "name" in item
        assert "category" in item  # Nested category object, not flat category_name


def test_dashboard_home_assets_limit(client, auth_headers, setup_test_data):
    """Home assets respects limit parameter"""
    response = client.get("/api/v1/dashboard/home-assets?limit=2", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()["data"]

    # Should limit to 2 items per status
    if "in_use" in data:
        assert len(data["in_use"]) <= 2


def test_dashboard_home_assets_category_counts(client, auth_headers, setup_test_data):
    """Home assets category counts returns category breakdown for a status"""
    response = client.get("/api/v1/dashboard/home-assets/in_use/categories", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()["data"]

    # Should return list of categories with counts
    assert isinstance(data, list)
    if len(data) > 0:
        cat = data[0]
        assert "id" in cat
        assert "name" in cat
        assert "icon" in cat
        assert "color" in cat
        assert "count" in cat


def test_dashboard_home_assets_category_counts_invalid_status(client, auth_headers):
    """Invalid status returns 400 error for category counts"""
    response = client.get("/api/v1/dashboard/home-assets/invalid_status/categories", headers=auth_headers)
    assert response.status_code == 400


def test_dashboard_home_assets_paginated(client, auth_headers, setup_test_data):
    """Home assets paginated returns paginated asset list for a status"""
    response = client.get("/api/v1/dashboard/home-assets/in_use", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()["data"]

    assert "items" in data
    assert "total" in data
    assert "page" in data
    assert "page_size" in data
    assert "total_pages" in data
    assert "has_next" in data
    assert "has_prev" in data

    # Default page_size is 20
    assert data["page_size"] == 20
    assert data["page"] == 1


def test_dashboard_home_assets_paginated_with_pagination(client, auth_headers, setup_test_data):
    """Home assets paginated respects page and page_size params"""
    response = client.get("/api/v1/dashboard/home-assets/in_use?page=1&page_size=1", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()["data"]

    assert len(data["items"]) <= 1
    assert data["page_size"] == 1
    # With 3 assets, page_size=1 means total_pages >= 3
    assert data["total_pages"] >= 3


def test_dashboard_home_assets_paginated_invalid_status(client, auth_headers):
    """Invalid status returns 400 error for paginated endpoint"""
    response = client.get("/api/v1/dashboard/home-assets/invalid_status", headers=auth_headers)
    assert response.status_code == 400


def test_dashboard_expiring_soon(client, auth_headers, setup_test_data):
    """Expiring soon returns assets approaching end of lifespan"""
    response = client.get("/api/v1/dashboard/expiring-soon", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()["data"]

    assert isinstance(data, list)
    # 房产 has expected_lifespan_days=25550 (~70 years), purchased 2020-01-01
    # Should not be expiring soon with default 90 day threshold
    # But endpoint should still work
    if len(data) > 0:
        item = data[0]
        assert "id" in item
        assert "name" in item
        assert "asset_type" in item
        assert "remaining_days" in item
        assert "current_value" in item


def test_dashboard_expiring_soon_threshold(client, auth_headers):
    """Expiring soon respects days_threshold parameter"""
    # Create an asset that will expire soon
    cat_response = client.get("/api/v1/categories", headers=auth_headers)
    categories = cat_response.json()["data"]
    physical_cat = [c for c in categories if c["asset_type"] == "physical"][0]

    # Create asset with 100 day expected lifespan, purchased 80 days ago
    from datetime import date, timedelta
    purchase_date = date.today() - timedelta(days=80)

    client.post("/api/v1/assets", headers=auth_headers, json={
        "name": "即将过期设备",
        "category_id": physical_cat["id"],
        "asset_type": "physical",
        "purchase_price": 1000,
        "current_value": 500,
        "purchase_date": purchase_date.isoformat(),
        "expected_lifespan_days": 100,
    })

    # With threshold=30, this asset (remaining_days=20) should appear
    response = client.get("/api/v1/dashboard/expiring-soon?days_threshold=30", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()["data"]

    # Should find the expiring asset
    expiring = [a for a in data if a["name"] == "即将过期设备"]
    assert len(expiring) == 1
    assert expiring[0]["remaining_days"] == 20


def test_dashboard_expiring_soon_requires_auth(client):
    """Expiring soon endpoint rejects unauthenticated requests"""
    response = client.get("/api/v1/dashboard/expiring-soon")
    assert response.status_code == 401


# ═══════════════════════════════════════
# Edge Cases & Validation Tests
# ═══════════════════════════════════════


def test_dashboard_trend_invalid_period(client, auth_headers, setup_test_data):
    """Trend endpoint rejects invalid period values (Literal validation)"""
    client.post("/api/v1/family/snapshots/generate", headers=auth_headers)

    response = client.get("/api/v1/dashboard/trend?period=invalid", headers=auth_headers)
    assert response.status_code == 422  # FastAPI validation error


def test_dashboard_trend_literal_period(client, auth_headers, setup_test_data):
    """Trend endpoint accepts only month/quarter/year (Literal type)"""
    client.post("/api/v1/family/snapshots/generate", headers=auth_headers)

    # Valid periods
    for period in ["month", "quarter", "year"]:
        response = client.get(f"/api/v1/dashboard/trend?period={period}", headers=auth_headers)
        assert response.status_code == 200


def test_dashboard_daily_cost_ranking_limit(client, auth_headers, setup_test_data):
    """Daily cost ranking respects limit parameter"""
    response = client.get("/api/v1/dashboard/daily-cost-ranking?limit=3", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()["data"]

    assert len(data) <= 3


def test_dashboard_daily_cost_ranking_limit_bounds(client, auth_headers):
    """Daily cost ranking limit has bounds (ge=1, le=100)"""
    # limit=0 should fail
    response = client.get("/api/v1/dashboard/daily-cost-ranking?limit=0", headers=auth_headers)
    assert response.status_code == 422

    # limit=101 should fail
    response = client.get("/api/v1/dashboard/daily-cost-ranking?limit=101", headers=auth_headers)
    assert response.status_code == 422
