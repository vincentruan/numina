from app.services.projection import calculate_projection


def test_basic_projection():
    """基本推演：有资产和负债的家庭。"""
    result = calculate_projection(
        assets=[
            {"current_value": 100000.0, "asset_type": "physical",
             "annual_depreciation": 0.1, "annual_return": 0.0},
            {"current_value": 200000.0, "asset_type": "financial",
             "annual_depreciation": 0.0, "annual_return": 0.06},
        ],
        liabilities=[
            {"remaining_amount": 50000.0, "monthly_payment": 2000.0, "end_year": 2028},
        ],
        history_points=[],
        projection_years=5,
        inflation_rate=0.03,
        current_year=2026,
    )
    assert len(result["forecast"]) == 6
    assert result["forecast"][5]["total_assets"] > 0
    assert result["forecast"][5]["real_net_worth"] < result["forecast"][5]["net_worth"]
    assert "assumptions" in result


def test_projection_empty_assets():
    result = calculate_projection(
        assets=[], liabilities=[], history_points=[],
        projection_years=3, inflation_rate=0.03, current_year=2026,
    )
    assert len(result["forecast"]) == 4
    for pt in result["forecast"]:
        assert pt["net_worth"] == 0


def test_projection_api(client, auth_headers, db):
    from datetime import date

    from app.models.asset import Asset
    from app.models.category import Category

    me = client.get("/api/v1/auth/me", headers=auth_headers).json()
    family_id = me["data"]["family_id"]
    user_id = me["data"]["id"]

    cat = db.query(Category).filter_by(name="存款").first()
    asset = Asset(
        user_id=user_id, family_id=family_id, category_id=cat.id,
        name="银行存款", asset_type="financial",
        purchase_price=100000.0, current_value=100000.0,
        purchase_date=date(2024, 1, 1),
    )
    db.add(asset)
    db.commit()

    resp = client.post(
        "/api/v1/ai/projection",
        json={"projection_years": 3, "inflation_rate": 0.03},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert len(data["forecast"]) == 4
    assert data["forecast"][0]["total_assets"] > 0
    assert "assumptions" in data
