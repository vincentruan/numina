from app.services.purchasing_power import calculate_purchasing_power


def test_lookback_2015_to_2025():
    """2015年的10万元，到2025年应该增值（通胀侵蚀购买力）。"""
    result = calculate_purchasing_power(
        amount=100000.0, from_year=2015, to_year=2025
    )
    assert result["original_amount"] == 100000.0
    assert result["adjusted_amount"] > 100000.0
    assert result["cumulative_inflation"] > 0
    assert result["from_year"] == 2015
    assert result["to_year"] == 2025
    assert "explanation" in result


def test_lookback_same_year():
    result = calculate_purchasing_power(amount=50000.0, from_year=2020, to_year=2020)
    assert result["adjusted_amount"] == 50000.0
    assert result["cumulative_inflation"] == 0.0


def test_custom_inflation_rate():
    result = calculate_purchasing_power(
        amount=100000.0, from_year=2020, to_year=2025, custom_inflation_rate=0.05
    )
    expected = round(100000.0 * (1.05 ** 5), 2)
    assert abs(result["adjusted_amount"] - expected) < 0.01


def test_auto_swap_years():
    """from_year > to_year 时自动交换。"""
    result = calculate_purchasing_power(amount=10000.0, from_year=2025, to_year=2015)
    assert result["from_year"] == 2015
    assert result["to_year"] == 2025
    assert result["adjusted_amount"] > 10000.0


def test_purchasing_power_api(client, auth_headers):
    resp = client.get(
        "/api/v1/ai/purchasing-power",
        params={"amount": 100000, "from_year": 2015, "to_year": 2025},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["original_amount"] == 100000.0
    assert data["adjusted_amount"] > 100000.0
    assert "explanation" in data


def test_asset_purchasing_power(client, auth_headers, db):
    from datetime import date

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
        name="测试手机",
        asset_type="physical",
        purchase_price=5000.0,
        current_value=3000.0,
        purchase_date=date(2020, 1, 1),
    )
    db.add(asset)
    db.commit()
    db.refresh(asset)

    resp = client.get(
        f"/api/v1/assets/{asset.id}/purchasing-power",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["original_amount"] == 5000.0
    assert data["from_year"] == 2020


def test_asset_purchasing_power_no_date(client, auth_headers, db):
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
        name="无日期资产",
        asset_type="physical",
        purchase_price=None,
        current_value=1000.0,
    )
    db.add(asset)
    db.commit()
    db.refresh(asset)

    resp = client.get(
        f"/api/v1/assets/{asset.id}/purchasing-power",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["original_amount"] is None
