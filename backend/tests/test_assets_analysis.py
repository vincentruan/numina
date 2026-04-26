import pytest


def test_buy_vs_rent_buy_cheaper(client, auth_headers):
    """买入总成本 < 租赁总成本时推荐购买。"""
    resp = client.post(
        "/api/v1/assets/buy-vs-rent",
        json={
            "purchase_price": 5000.0,
            "monthly_rent": 500.0,
            "usage_months": 24,
            "annual_maintenance_cost": 200.0,
            "depreciation_years": 10,
            "residual_value_rate": 0.1,
        },
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["buy_total"] < data["rent_total"]
    assert data["recommendation"] == "购买更划算"
    assert data["breakeven_months"] is not None


def test_buy_vs_rent_rent_cheaper(client, auth_headers):
    """租赁总成本 < 买入总成本时推荐租赁。"""
    resp = client.post(
        "/api/v1/assets/buy-vs-rent",
        json={
            "purchase_price": 50000.0,
            "monthly_rent": 200.0,
            "usage_months": 12,
        },
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["rent_total"] < data["buy_total"]
    assert data["recommendation"] == "租赁更划算"


def test_buy_vs_rent_breakeven_null_when_rent_le_maintenance(client, auth_headers):
    """月租 <= 月均维护费时 breakeven_months 为 null。"""
    resp = client.post(
        "/api/v1/assets/buy-vs-rent",
        json={
            "purchase_price": 10000.0,
            "monthly_rent": 50.0,
            "usage_months": 12,
            "annual_maintenance_cost": 1200.0,
        },
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["breakeven_months"] is None


def test_buy_vs_rent_validation(client, auth_headers):
    """缺少必填字段返回 422。"""
    resp = client.post(
        "/api/v1/assets/buy-vs-rent",
        json={"purchase_price": 1000.0},
        headers=auth_headers,
    )
    assert resp.status_code == 422


def test_cost_equivalence_full(client, auth_headers, db):
    """GET /assets/{id}/cost-equivalence 返回三种换算结果。"""
    from datetime import date, timedelta
    from app.models.asset import Asset
    from app.models.category import Category

    me = client.get("/api/v1/auth/me", headers=auth_headers).json()
    family_id = me["data"]["family_id"]
    user_id = me["data"]["id"]

    cat = db.query(Category).filter_by(asset_type="physical").first()
    asset = Asset(
        user_id=user_id,
        family_id=family_id,
        category_id=cat.id,
        name="测试笔记本",
        asset_type="physical",
        purchase_price=8000.0,
        annual_maintenance_cost=400.0,
        purchase_date=date.today() - timedelta(days=365),
    )
    db.add(asset)
    db.commit()
    db.refresh(asset)

    resp = client.get(
        f"/api/v1/assets/{asset.id}/cost-equivalence",
        params={"hourly_wage": 100.0, "yield_rate": 0.05, "years": 5},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["held_days"] == 365
    assert data["total_held_cost"] == pytest.approx(8400.0, rel=0.01)
    assert data["daily_cost"] == pytest.approx(8400.0 / 365, rel=0.01)
    assert data["time_cost_hours"] == pytest.approx(8400.0 / 100.0, rel=0.01)
    assert data["opportunity_cost"] == pytest.approx(8400.0 * (1.05 ** 5) - 8400.0, rel=0.01)


def test_cost_equivalence_null_when_no_purchase_price(client, auth_headers, db):
    """资产无 purchase_price 时返回 null 字段，不报错。"""
    from app.models.asset import Asset
    from app.models.category import Category

    me = client.get("/api/v1/auth/me", headers=auth_headers).json()
    family_id = me["data"]["family_id"]
    user_id = me["data"]["id"]

    cat = db.query(Category).filter_by(asset_type="physical").first()
    asset = Asset(
        user_id=user_id,
        family_id=family_id,
        category_id=cat.id,
        name="无价格资产",
        asset_type="physical",
    )
    db.add(asset)
    db.commit()
    db.refresh(asset)

    resp = client.get(
        f"/api/v1/assets/{asset.id}/cost-equivalence",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["daily_cost"] is None
    assert data["time_cost_hours"] is None
    assert data["opportunity_cost"] is None


def test_cost_equivalence_asset_not_found(client, auth_headers):
    """不存在的资产返回 404。"""
    resp = client.get("/api/v1/assets/99999/cost-equivalence", headers=auth_headers)
    assert resp.status_code == 404
