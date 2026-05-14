import pytest

from apps.backend.app.services.whatif import calculate_whatif


def test_sell_asset_improves_net_worth():
    """卖掉高维护成本资产，长期净资产应该更高。"""
    result = calculate_whatif(
        current_net_worth=500000.0,
        assets=[{
            "id": 1, "current_value": 50000.0, "asset_type": "physical",
            "annual_depreciation": 0.15, "annual_maintenance_cost": 5000.0,
            "annual_return": 0.0,
        }],
        liabilities=[],
        actions=[{
            "action_type": "sell", "asset_id": 1, "liquidation_rate": 0.8,
        }],
        projection_years=10,
        inflation_rate=0.03,
    )
    assert len(result["projection"]) == 11
    assert result["total_difference"] > 0
    # Year 0 includes sell income, so scenario is already higher
    assert result["projection"][0]["scenario_net_worth"] > result["projection"][0]["baseline_net_worth"]


def test_invest_scenario():
    """投资场景：初始减少现金，长期通过收益增长。"""
    result = calculate_whatif(
        current_net_worth=200000.0,
        assets=[],
        liabilities=[],
        actions=[{"action_type": "invest", "amount": 50000.0, "annual_return_rate": 0.08}],
        projection_years=5,
        inflation_rate=0.03,
    )
    assert result["projection"][0]["difference"] == -50000.0  # invest outflow at year 0
    # Year 1: scenario still behind baseline
    assert result["projection"][1]["scenario_net_worth"] < result["projection"][1]["baseline_net_worth"]


def test_stop_expense():
    result = calculate_whatif(
        current_net_worth=100000.0,
        assets=[{
            "id": 1, "current_value": 10000.0, "asset_type": "physical",
            "annual_depreciation": 0.1, "annual_maintenance_cost": 2000.0,
            "annual_return": 0.0,
        }],
        liabilities=[],
        actions=[{"action_type": "stop_expense", "asset_id": 1}],
        projection_years=5,
        inflation_rate=0.03,
    )
    assert result["total_difference"] > 0


def test_empty_actions_validation():
    """actions 为空应该在 schema 层面被拒绝。"""
    from pydantic import ValidationError

    from apps.backend.app.schemas.whatif import WhatIfRequest

    with pytest.raises(ValidationError):
        WhatIfRequest(actions=[], projection_years=10)


def test_whatif_api(client, auth_headers, db):
    from datetime import date

    from apps.backend.app.models.asset import Asset
    from apps.backend.app.models.category import Category

    me = client.get("/api/v1/auth/me", headers=auth_headers).json()
    family_id = me["data"]["family_id"]
    user_id = me["data"]["id"]

    cat = db.query(Category).filter_by(name="车辆").first()
    asset = Asset(
        user_id=user_id, family_id=family_id, category_id=cat.id,
        name="测试车", asset_type="physical",
        purchase_price=200000.0, current_value=150000.0,
        purchase_date=date(2022, 1, 1),
        annual_maintenance_cost=10000.0,
    )
    db.add(asset)
    db.commit()
    db.refresh(asset)

    resp = client.post(
        "/api/v1/ai/whatif",
        json={
            "actions": [{"action_type": "sell", "asset_id": asset.id, "liquidation_rate": 0.7}],
            "projection_years": 5,
        },
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert len(data["projection"]) == 6
    assert "total_difference" in data


def test_whatif_api_validation(client, auth_headers):
    resp = client.post(
        "/api/v1/ai/whatif",
        json={"actions": [], "projection_years": 5},
        headers=auth_headers,
    )
    assert resp.status_code == 422


def test_whatif_api_invalid_asset(client, auth_headers):
    resp = client.post(
        "/api/v1/ai/whatif",
        json={
            "actions": [{"action_type": "sell", "asset_id": 999999999}],
            "projection_years": 5,
        },
        headers=auth_headers,
    )
    assert resp.status_code == 404
