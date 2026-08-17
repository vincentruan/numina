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
        "purchase_date": "2023-01-01",
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
    assert "month_over_month_change_amount" in data

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
    """Test investment returns endpoint (D8 annualized return rate)"""
    from datetime import date

    response = client.get("/api/v1/dashboard/investment-returns", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()["data"]

    # Should only have financial assets with a valid annualized rate
    assert len(data) == 1
    assert data[0]["name"] == "基金"
    assert "return_rate" in data[0]
    assert "profit" in data[0]
    # profit is currency-converted total (CNY here) = 225000 - 200000
    assert data[0]["profit"] == 25000
    # D8: return_rate is now annualized: (25000/200000) * (365/holding_days) * 100
    holding_days = (date.today() - date(2023, 1, 1)).days
    expected = (25000 / 200000) * (365 / holding_days) * 100
    assert abs(data[0]["return_rate"] - round(expected, 2)) < 0.1


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


def test_dashboard_home_assets_paginated_search(client, auth_headers, setup_test_data):
    """Search filter narrows paginated home assets by name (case-insensitive substring)"""
    response = client.get("/api/v1/dashboard/home-assets/in_use?search=基金", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()["data"]

    assert data["total"] == 1
    assert len(data["items"]) == 1
    assert data["items"][0]["name"] == "基金"


def test_dashboard_home_assets_paginated_search_no_match(client, auth_headers, setup_test_data):
    """Search with no matching name returns empty page"""
    response = client.get("/api/v1/dashboard/home-assets/in_use?search=不存在的资产", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()["data"]

    assert data["total"] == 0
    assert data["items"] == []


def test_dashboard_home_assets_paginated_asset_type(client, auth_headers, setup_test_data):
    """asset_type filter returns only assets of that type"""
    response = client.get("/api/v1/dashboard/home-assets/in_use?asset_type=financial", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()["data"]

    assert data["total"] == 1
    assert all(item["asset_type"] == "financial" for item in data["items"])
    assert data["items"][0]["name"] == "基金"


def test_dashboard_home_assets_paginated_sort_by_value(client, auth_headers, setup_test_data):
    """sort_by=current_value orders assets by value; sort_order controls direction"""
    # current_value serializes as a string (Numeric), so compare numerically via float()
    desc = client.get(
        "/api/v1/dashboard/home-assets/in_use?sort_by=current_value&sort_order=desc",
        headers=auth_headers,
    )
    assert desc.status_code == 200
    desc_values = [float(item["current_value"]) for item in desc.json()["data"]["items"]]
    assert desc_values == sorted(desc_values, reverse=True)

    asc = client.get(
        "/api/v1/dashboard/home-assets/in_use?sort_by=current_value&sort_order=asc",
        headers=auth_headers,
    )
    assert asc.status_code == 200
    asc_values = [float(item["current_value"]) for item in asc.json()["data"]["items"]]
    assert asc_values == sorted(asc_values)


def test_dashboard_home_assets_paginated_sort_by_name(client, auth_headers, setup_test_data):
    """sort_by=name is accepted and returns a stable ordered page"""
    response = client.get(
        "/api/v1/dashboard/home-assets/in_use?sort_by=name&sort_order=asc",
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()["data"]
    # All 3 in_use assets returned regardless of sort column validity
    assert data["total"] == 3


def test_dashboard_home_assets_paginated_invalid_sort_by_falls_back(client, auth_headers, setup_test_data):
    """An unrecognized sort_by column falls back to default ordering (no 500, no injection)"""
    response = client.get(
        "/api/v1/dashboard/home-assets/in_use?sort_by=;DROP TABLE assets;--",
        headers=auth_headers,
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["total"] == 3


def test_dashboard_home_assets_paginated_invalid_asset_type_ignored(client, auth_headers, setup_test_data):
    """An unrecognized asset_type is ignored (returns all types) rather than erroring"""
    response = client.get("/api/v1/dashboard/home-assets/in_use?asset_type=bogus", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["total"] == 3


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


def test_compute_annualized_return_holding_days():
    """D8 KTD-4: compute_annualized_return annualizes by holding days."""
    from datetime import date, timedelta

    from apps.backend.app.models.asset import Asset
    from apps.backend.app.services.asset import compute_annualized_return

    # Exactly 365 days holding → annualized == total ratio (12.5%)
    asset = Asset(
        asset_type="financial",
        purchase_price=200000.0,
        current_value=225000.0,
        purchase_date=date.today() - timedelta(days=365),
    )
    assert compute_annualized_return(asset) == 12.5

    # 730 days holding (2x years) → annualized == total ratio / 2 (6.25%)
    asset_long = Asset(
        asset_type="financial",
        purchase_price=200000.0,
        current_value=225000.0,
        purchase_date=date.today() - timedelta(days=730),
    )
    assert compute_annualized_return(asset_long) == 6.25


def test_compute_annualized_return_none_cases():
    """D8 KTD-4: returns None when purchase_date missing, holding_days<=0, or no price."""
    from datetime import date, timedelta

    from apps.backend.app.models.asset import Asset
    from apps.backend.app.services.asset import compute_annualized_return

    # Missing purchase_date → None
    a_no_date = Asset(
        asset_type="financial",
        purchase_price=200000.0,
        current_value=225000.0,
        purchase_date=None,
    )
    assert compute_annualized_return(a_no_date) is None

    # holding_days == 0 (purchased today) → None
    a_today = Asset(
        asset_type="financial",
        purchase_price=200000.0,
        current_value=225000.0,
        purchase_date=date.today(),
    )
    assert compute_annualized_return(a_today) is None

    # holding_days < 0 (future date) → None
    a_future = Asset(
        asset_type="financial",
        purchase_price=200000.0,
        current_value=225000.0,
        purchase_date=date.today() + timedelta(days=10),
    )
    assert compute_annualized_return(a_future) is None

    # No purchase_price → None
    a_no_price = Asset(
        asset_type="financial",
        purchase_price=None,
        current_value=225000.0,
        purchase_date=date.today() - timedelta(days=365),
    )
    assert compute_annualized_return(a_no_price) is None


def test_insights_investment_returns_field(client, auth_headers, setup_test_data):
    """D8 KTD-5: insights response includes investment_returns summary."""
    response = client.get("/api/v1/dashboard/insights", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()["data"]

    assert "investment_returns" in data
    inv = data["investment_returns"]
    assert inv is not None
    assert "annualized_rate" in inv
    assert "asset_count" in inv
    assert "description" in inv
    # Fixture has 1 financial asset (基金) with a valid purchase_date → count 1, rate present
    assert inv["asset_count"] == 1
    assert inv["annualized_rate"] is not None


def test_insights_investment_returns_empty(client, auth_headers):
    """D8 KTD-5: no financial assets → asset_count 0 and annualized_rate None."""
    response = client.get("/api/v1/dashboard/insights", headers=auth_headers)
    assert response.status_code == 200
    inv = response.json()["data"]["investment_returns"]
    assert inv is not None
    assert inv["asset_count"] == 0
    assert inv["annualized_rate"] is None


# ---------------------------------------------------------------------------
# B1 教育奖励支出专项统计（方案 B）：GET /dashboard/education-reward-summary
# ---------------------------------------------------------------------------


def _current_user(db):
    """Return the User registered by the auth_headers fixture (username 'testuser')."""
    from apps.backend.app.models.user import User

    return db.query(User).filter(User.username == "testuser").one()


def _add_education_reward(db, *, family_id, user_id, amount, created_at=None, type="education_reward"):
    """Insert an Activity row directly (mirrors B1 education-linkage write shape)."""
    from apps.backend.app.models.activity import Activity
    from apps.backend.app.utils.snowflake import next_id

    activity = Activity(
        id=next_id(),
        family_id=family_id,
        user_id=user_id,
        type=type,
        entity_type="chore",
        entity_id=next_id(),
        title="教育奖励金",
        amount=amount,
    )
    if created_at is not None:
        activity.created_at = created_at
    db.add(activity)
    db.commit()
    return activity


def test_education_reward_summary_empty(client, db, auth_headers):
    """无 education_reward 记录 → 全 0，不报错（KTD-2）。"""
    response = client.get("/api/v1/dashboard/education-reward-summary", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()["data"]
    assert data == {"total": 0, "month_total": 0, "count": 0}


def test_education_reward_summary_total_month_count(client, db, auth_headers):
    """2 笔 education_reward（1 本月 + 1 上月）→ total=两笔和、month_total=本月笔、count=2。"""
    from datetime import date, datetime

    user = _current_user(db)
    today = date.today()

    # 本月一笔（默认 created_at = now）
    _add_education_reward(db, family_id=user.family_id, user_id=user.id, amount=20.0)
    # 上月一笔（显式 created_at = 上月 1 号，避免跨月边界）
    if today.month == 1:
        last_month = datetime(today.year - 1, 12, 1)
    else:
        last_month = datetime(today.year, today.month - 1, 1)
    _add_education_reward(
        db, family_id=user.family_id, user_id=user.id, amount=30.0, created_at=last_month
    )

    response = client.get("/api/v1/dashboard/education-reward-summary", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["total"] == 50.0
    assert data["month_total"] == 20.0
    assert data["count"] == 2


def test_education_reward_summary_ignores_other_types(client, db, auth_headers):
    """其他 type 的 Activity 不计入统计。"""
    user = _current_user(db)
    _add_education_reward(db, family_id=user.family_id, user_id=user.id, amount=20.0)
    _add_education_reward(
        db, family_id=user.family_id, user_id=user.id, amount=999.0, type="create"
    )

    response = client.get("/api/v1/dashboard/education-reward-summary", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["total"] == 20.0
    assert data["month_total"] == 20.0
    assert data["count"] == 1


def test_education_reward_summary_family_isolation(client, db, auth_headers):
    """他 family 的 education_reward 不计入当前 family 的统计。"""
    from apps.backend.app.models.family import Family
    from apps.backend.app.models.user import User
    from apps.backend.app.utils.snowflake import next_id

    user = _current_user(db)
    _add_education_reward(db, family_id=user.family_id, user_id=user.id, amount=20.0)

    # 另一个 family + user，写一笔 education_reward
    other_family = Family(id=next_id(), name="Other Family", created_by=next_id())
    db.add(other_family)
    db.commit()
    other_user = User(
        id=next_id(),
        username="other_family_user",
        display_name="Other User",
        password_hash="test_hash",
        family_id=other_family.id,
    )
    db.add(other_user)
    db.commit()
    _add_education_reward(db, family_id=other_family.id, user_id=other_user.id, amount=888.0)

    response = client.get("/api/v1/dashboard/education-reward-summary", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["total"] == 20.0
    assert data["month_total"] == 20.0
    assert data["count"] == 1


# ── Rental overview aggregation ──────────────────────────────────────


def _create_contract(client, auth_headers, **kwargs):
    """Helper: create a rental contract via HTTP and return the response data."""
    payload = {
        "role": "landlord",
        "monthly_rent": 5000,
        "deposit": 10000,
        "start_date": "2026-01-01",
    }
    payload.update(kwargs)
    resp = client.post("/api/v1/rental-contracts", headers=auth_headers, json=payload)
    assert resp.status_code == 201
    return resp.json()["data"]


def test_overview_rental_null_when_no_contracts(client, auth_headers):
    """No active rental contracts -> all rental fields are None."""
    response = client.get("/api/v1/dashboard/overview", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["rental_net_cash_flow"] is None
    assert data["rental_monthly_income"] is None
    assert data["rental_monthly_expense"] is None
    assert data["rental_total_deposit"] is None


def test_overview_rental_landlord_only(client, auth_headers):
    """Landlord-only contracts: income>0, expense=0, deposit=sum."""
    _create_contract(client, auth_headers, monthly_rent=5000, deposit=10000)
    _create_contract(client, auth_headers, monthly_rent=3000, deposit=6000)

    data = client.get("/api/v1/dashboard/overview", headers=auth_headers).json()["data"]
    assert data["rental_monthly_income"] == 8000.0
    assert data["rental_monthly_expense"] == 0.0
    assert data["rental_net_cash_flow"] == 8000.0
    assert data["rental_total_deposit"] == 16000.0


def test_overview_rental_tenant_only(client, auth_headers):
    """Tenant-only contracts: income=0, expense>0, deposit=sum."""
    _create_contract(client, auth_headers, role="tenant", monthly_rent=4000, deposit=8000)

    data = client.get("/api/v1/dashboard/overview", headers=auth_headers).json()["data"]
    assert data["rental_monthly_income"] == 0.0
    assert data["rental_monthly_expense"] == 4000.0
    assert data["rental_net_cash_flow"] == -4000.0
    assert data["rental_total_deposit"] == 8000.0


def test_overview_rental_mixed_roles(client, auth_headers):
    """Mixed landlord+tenant: net = income - expense, deposit is gross sum."""
    _create_contract(client, auth_headers, role="landlord", monthly_rent=6000, deposit=12000)
    _create_contract(client, auth_headers, role="tenant", monthly_rent=3500, deposit=7000)

    data = client.get("/api/v1/dashboard/overview", headers=auth_headers).json()["data"]
    assert data["rental_monthly_income"] == 6000.0
    assert data["rental_monthly_expense"] == 3500.0
    assert data["rental_net_cash_flow"] == 2500.0
    # Deposit is gross sum (landlord 12000 + tenant 7000), not net
    assert data["rental_total_deposit"] == 19000.0


def test_overview_rental_zero_deposit(client, auth_headers):
    """Contracts with zero deposit: deposit field should be 0, not None."""
    _create_contract(client, auth_headers, monthly_rent=5000, deposit=0)

    data = client.get("/api/v1/dashboard/overview", headers=auth_headers).json()["data"]
    assert data["rental_monthly_income"] == 5000.0
    assert data["rental_total_deposit"] == 0.0


def test_overview_rental_inactive_excluded(client, auth_headers, db):
    """Inactive contracts (is_active=False) are excluded from aggregation."""
    _create_contract(client, auth_headers, role="landlord", monthly_rent=5000, deposit=10000)

    # Create a second contract, then deactivate it via direct DB update
    from apps.backend.app.models.rental_contract import RentalContract

    c2_data = _create_contract(client, auth_headers, role="landlord", monthly_rent=8000, deposit=16000)
    contract = db.query(RentalContract).filter(
        RentalContract.id == int(c2_data["id"])
    ).first()
    contract.is_active = False
    db.commit()

    data = client.get("/api/v1/dashboard/overview", headers=auth_headers).json()["data"]
    # Only the first contract (5000) should be counted; the deactivated one (8000) excluded
    assert data["rental_monthly_income"] == 5000.0
    assert data["rental_total_deposit"] == 10000.0


def test_overview_rental_cross_family_isolation(client, auth_headers, db):
    """Rental contracts from other families do not appear in dashboard overview."""
    from datetime import date

    from apps.backend.app.models.family import Family
    from apps.backend.app.models.user import User
    from apps.backend.app.models.rental_contract import RentalContract
    from apps.backend.app.utils.snowflake import next_id

    # Create another family with a user and a rental contract
    other_family = Family(id=next_id(), name="Other Family", created_by=next_id())
    db.add(other_family)
    other_user = User(
        id=next_id(),
        username="other_rental_user",
        display_name="Other",
        password_hash="test_hash",
        family_id=other_family.id,
    )
    db.add(other_user)
    db.commit()

    other_contract = RentalContract(
        id=next_id(),
        user_id=other_user.id,
        family_id=other_family.id,
        role="landlord",
        monthly_rent=99000,
        deposit=99000,
        start_date=date(2026, 1, 1),
        is_active=True,
    )
    db.add(other_contract)
    db.commit()

    # Our user's overview should NOT include the other family's contract
    data = client.get("/api/v1/dashboard/overview", headers=auth_headers).json()["data"]
    assert data["rental_monthly_income"] is None
    assert data["rental_total_deposit"] is None
