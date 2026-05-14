"""资产时光机端到端集成测试。"""
from datetime import date

import pytest

from apps.backend.app.models.asset import Asset
from apps.backend.app.models.category import Category
from apps.backend.app.models.liability import Liability


@pytest.fixture
def family_with_assets(client, auth_headers, db):
    """创建一个有资产和负债的家庭。"""
    me = client.get("/api/v1/auth/me", headers=auth_headers).json()
    family_id = me["data"]["family_id"]
    user_id = me["data"]["id"]

    physical_cat = db.query(Category).filter_by(name="车辆").first()
    financial_cat = db.query(Category).filter_by(name="基金").first()

    car = Asset(
        user_id=user_id,
        family_id=family_id,
        category_id=physical_cat.id,
        name="家用车",
        asset_type="physical",
        purchase_price=200000.0,
        current_value=150000.0,
        purchase_date=date(2022, 6, 1),
        annual_maintenance_cost=8000.0,
        expected_lifespan_days=3650,
    )
    fund = Asset(
        user_id=user_id,
        family_id=family_id,
        category_id=financial_cat.id,
        name="指数基金",
        asset_type="financial",
        purchase_price=100000.0,
        current_value=120000.0,
        purchase_date=date(2023, 1, 1),
        interest_rate=0.08,
    )
    db.add_all([car, fund])

    loan = Liability(
        user_id=user_id,
        family_id=family_id,
        name="车贷",
        category="car_loan",
        original_amount=150000.0,
        remaining_amount=80000.0,
        monthly_payment=3000.0,
        interest_rate=0.045,
        start_date=date(2022, 6, 1),
        end_date=date(2027, 6, 1),
        is_active=True,
    )
    db.add(loan)
    db.commit()
    db.refresh(car)
    db.refresh(fund)
    return {"car_id": car.id, "fund_id": fund.id}


def test_whatif_sell_car(client, auth_headers, family_with_assets):
    """What-if: 卖掉车，资金转投基金。"""
    car_id = family_with_assets["car_id"]
    resp = client.post(
        "/api/v1/ai/whatif",
        json={
            "actions": [
                {"action_type": "sell", "asset_id": car_id, "liquidation_rate": 0.7},
                {"action_type": "invest", "amount": 100000.0, "annual_return_rate": 0.06},
            ],
            "projection_years": 10,
        },
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert len(data["projection"]) == 11
    assert isinstance(data["total_difference"], float)
    assert data["summary"] is None  # AI not enabled in tests


def test_projection_with_assets(client, auth_headers, family_with_assets):
    """财务推演：有资产和负债的家庭。"""
    resp = client.post(
        "/api/v1/ai/projection",
        json={"projection_years": 5, "inflation_rate": 0.03},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert len(data["forecast"]) == 6
    assert data["forecast"][0]["total_assets"] > 0
    # Real net worth should be <= nominal in future years
    assert data["forecast"][5]["real_net_worth"] <= data["forecast"][5]["net_worth"]


def test_purchasing_power_api(client, auth_headers):
    """购买力计算 API。"""
    resp = client.get(
        "/api/v1/ai/purchasing-power",
        params={"amount": 50000, "from_year": 2010, "to_year": 2025},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["adjusted_amount"] > 50000
    assert data["cumulative_inflation"] > 0


def test_asset_purchasing_power(client, auth_headers, family_with_assets):
    """资产级购买力端点。"""
    car_id = family_with_assets["car_id"]
    resp = client.get(
        f"/api/v1/assets/{car_id}/purchasing-power",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["original_amount"] == 200000.0
    assert data["from_year"] == 2022


def test_whatif_invalid_asset(client, auth_headers, family_with_assets):
    """What-if: 引用不存在的资产应返回 404。"""
    resp = client.post(
        "/api/v1/ai/whatif",
        json={
            "actions": [{"action_type": "sell", "asset_id": 999999999}],
            "projection_years": 5,
        },
        headers=auth_headers,
    )
    assert resp.status_code == 404


def test_whatif_empty_actions(client, auth_headers):
    """What-if: 空 actions 应返回 422。"""
    resp = client.post(
        "/api/v1/ai/whatif",
        json={"actions": [], "projection_years": 5},
        headers=auth_headers,
    )
    assert resp.status_code == 422


def test_projection_empty_family(client, auth_headers):
    """财务推演：无资产家庭返回全零曲线。"""
    resp = client.post(
        "/api/v1/ai/projection",
        json={"projection_years": 3, "inflation_rate": 0.03},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert len(data["forecast"]) == 4
    assert "assumptions" in data
