import json

import pytest


@pytest.fixture
def category_id(client, auth_headers):
    categories = client.get("/api/v1/categories", headers=auth_headers).json()
    return next(c["id"] for c in categories if c["asset_type"] == "physical")


@pytest.fixture
def financial_category_id(client, auth_headers):
    categories = client.get("/api/v1/categories", headers=auth_headers).json()
    return next(c["id"] for c in categories if c["asset_type"] == "financial")


def test_export_assets_csv_empty(client, auth_headers):
    response = client.get("/api/v1/export/assets/csv", headers=auth_headers)
    assert response.status_code == 200
    assert "text/csv" in response.headers["content-type"]
    # Should have header row only
    lines = response.text.strip().splitlines()
    assert len(lines) == 1  # header only


def test_export_assets_csv_with_data(client, auth_headers, category_id):
    client.post("/api/v1/assets", headers=auth_headers, json={
        "name": "导出测试房产",
        "category_id": category_id,
        "asset_type": "physical",
        "purchase_price": 2000000,
        "current_value": 2500000,
    })

    response = client.get("/api/v1/export/assets/csv", headers=auth_headers)
    assert response.status_code == 200
    assert "导出测试房产" in response.text
    lines = response.text.strip().splitlines()
    assert len(lines) == 2  # header + 1 data row


def test_export_liabilities_csv_empty(client, auth_headers):
    response = client.get("/api/v1/export/liabilities/csv", headers=auth_headers)
    assert response.status_code == 200
    assert "text/csv" in response.headers["content-type"]
    lines = response.text.strip().splitlines()
    assert len(lines) == 1  # header only


def test_export_liabilities_csv_with_data(client, auth_headers):
    client.post("/api/v1/liabilities", headers=auth_headers, json={
        "name": "房贷",
        "category": "mortgage",
        "original_amount": 1000000,
        "remaining_amount": 800000,
        "monthly_payment": 5000,
        "interest_rate": 4.5,
    })

    response = client.get("/api/v1/export/liabilities/csv", headers=auth_headers)
    assert response.status_code == 200
    assert "房贷" in response.text


def test_export_all_json(client, auth_headers, category_id):
    client.post("/api/v1/assets", headers=auth_headers, json={
        "name": "JSON导出资产",
        "category_id": category_id,
        "asset_type": "physical",
        "purchase_price": 50000,
    })

    response = client.get("/api/v1/export/all/json", headers=auth_headers)
    assert response.status_code == 200
    assert "application/json" in response.headers["content-type"]

    data = json.loads(response.text)
    assert "export_version" in data
    assert "export_date" in data
    assert "assets" in data
    assert "liabilities" in data
    assert "categories" in data
    assert "tags" in data

    assert len(data["assets"]) == 1
    assert data["assets"][0]["name"] == "JSON导出资产"


def test_export_json_family_isolation(client, auth_headers, second_user_headers, category_id):
    client.post("/api/v1/assets", headers=auth_headers, json={
        "name": "家庭1资产",
        "category_id": category_id,
        "asset_type": "physical",
    })

    response = client.get("/api/v1/export/all/json", headers=second_user_headers)
    data = json.loads(response.text)
    assert len(data["assets"]) == 0


def test_export_requires_auth(client):
    assert client.get("/api/v1/export/assets/csv").status_code == 401
    assert client.get("/api/v1/export/liabilities/csv").status_code == 401
    assert client.get("/api/v1/export/all/json").status_code == 401
