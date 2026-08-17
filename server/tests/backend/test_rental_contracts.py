import pytest


@pytest.fixture
def category_id(client, auth_headers):
    """Get a physical category ID for creating assets (linked property)."""
    response = client.get("/api/v1/categories", headers=auth_headers)
    assert response.status_code == 200
    physical = [c for c in response.json()["data"] if c["asset_type"] == "physical"]
    assert len(physical) > 0
    return physical[0]["id"]


@pytest.fixture
def sample_contract(client, auth_headers):
    """Create a sample landlord rental contract."""
    response = client.post("/api/v1/rental-contracts", headers=auth_headers, json={
        "role": "landlord",
        "monthly_rent": 5000,
        "deposit": 10000,
        "start_date": "2026-01-01",
        "end_date": "2026-12-31",
        "counterparty": "小王",
        "notes": "主卧出租",
    })
    assert response.status_code == 201
    return response.json()["data"]


@pytest.fixture
def sample_tenant_contract(client, auth_headers):
    response = client.post("/api/v1/rental-contracts", headers=auth_headers, json={
        "role": "tenant",
        "monthly_rent": 3000,
        "deposit": 6000,
        "start_date": "2026-02-01",
    })
    assert response.status_code == 201
    return response.json()["data"]


def test_create_landlord_contract(client, auth_headers):
    """Landlord contract: role=landlord, money fields str on the wire."""
    response = client.post("/api/v1/rental-contracts", headers=auth_headers, json={
        "role": "landlord",
        "monthly_rent": 5000,
        "deposit": 10000,
        "start_date": "2026-01-01",
    })
    assert response.status_code == 201
    data = response.json()["data"]
    assert data["role"] == "landlord"
    assert data["monthly_rent"] == "5000.00"
    assert data["deposit"] == "10000.00"
    assert data["is_active"] is True
    # SnowflakeBase: id serialized as str
    assert isinstance(data["id"], str)


def test_create_tenant_contract(client, auth_headers):
    """Tenant contract: role=tenant, open-ended (end_date null)."""
    response = client.post("/api/v1/rental-contracts", headers=auth_headers, json={
        "role": "tenant",
        "monthly_rent": 3000,
        "start_date": "2026-01-01",
    })
    assert response.status_code == 201
    data = response.json()["data"]
    assert data["role"] == "tenant"
    assert data["end_date"] is None
    # deposit defaults to 0
    assert data["deposit"] == "0.00"


def test_create_invalid_role_rejected(client, auth_headers):
    """role must be landlord/tenant (422 from schema validator)."""
    response = client.post("/api/v1/rental-contracts", headers=auth_headers, json={
        "role": "agent",
        "monthly_rent": 5000,
        "start_date": "2026-01-01",
    })
    assert response.status_code == 422


def test_list_contracts(client, auth_headers, sample_contract, sample_tenant_contract):
    response = client.get("/api/v1/rental-contracts", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()["data"]
    assert len(data) == 2


def test_list_filter_by_role(client, auth_headers, sample_contract, sample_tenant_contract):
    response = client.get(
        "/api/v1/rental-contracts", headers=auth_headers, params={"role": "landlord"}
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert len(data) == 1
    assert data[0]["role"] == "landlord"


def test_summary_aggregates_income_expense(client, auth_headers, sample_contract, sample_tenant_contract):
    """Summary: landlord=income, tenant=expense; net = income - expense."""
    response = client.get("/api/v1/rental-contracts/summary", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["monthly_income"] == "5000.00"
    assert data["monthly_expense"] == "3000.00"
    assert data["net_cash_flow"] == "2000.00"
    assert data["total_deposit"] == "16000.00"


def test_get_contract_detail(client, auth_headers, sample_contract):
    cid = sample_contract["id"]
    response = client.get(f"/api/v1/rental-contracts/{cid}", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["data"]["counterparty"] == "小王"


def test_update_contract(client, auth_headers, sample_contract):
    cid = sample_contract["id"]
    response = client.patch(
        f"/api/v1/rental-contracts/{cid}", headers=auth_headers, json={"monthly_rent": 5500}
    )
    assert response.status_code == 200
    assert response.json()["data"]["monthly_rent"] == "5500.00"


def test_delete_soft_deactivates(client, auth_headers, sample_contract):
    """DELETE = soft end (is_active=False); contract still queryable."""
    cid = sample_contract["id"]
    response = client.delete(f"/api/v1/rental-contracts/{cid}", headers=auth_headers)
    assert response.status_code == 200

    detail = client.get(f"/api/v1/rental-contracts/{cid}", headers=auth_headers)
    assert detail.status_code == 200
    assert detail.json()["data"]["is_active"] is False

    # Inactive contracts excluded from active_only listing
    active = client.get(
        "/api/v1/rental-contracts", headers=auth_headers, params={"active_only": True}
    )
    assert active.status_code == 200
    ids = [c["id"] for c in active.json()["data"]]
    assert cid not in ids


def test_deactivated_excluded_from_summary(client, auth_headers, sample_contract):
    cid = sample_contract["id"]
    client.delete(f"/api/v1/rental-contracts/{cid}", headers=auth_headers)

    response = client.get("/api/v1/rental-contracts/summary", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["monthly_income"] == "0.00"
    assert data["total_deposit"] == "0.00"


def test_404_on_missing_contract(client, auth_headers):
    response = client.get("/api/v1/rental-contracts/999999", headers=auth_headers)
    assert response.status_code == 404
    assert response.json()["code"] == "RENTAL_CONTRACT_NOT_FOUND"


def test_landlord_linked_asset_validation(client, auth_headers):
    """Landlord contract with foreign-family asset id -> 400 INVALID_ASSET."""
    response = client.post("/api/v1/rental-contracts", headers=auth_headers, json={
        "role": "landlord",
        "monthly_rent": 5000,
        "start_date": "2026-01-01",
        "linked_asset_id": 123456789012345,
    })
    assert response.status_code == 400
    assert response.json()["code"] == "RENTAL_CONTRACT_INVALID_ASSET"


def test_role_change_to_tenant_clears_linked_asset(client, auth_headers, category_id):
    """PATCH role landlord->tenant must clear linked_asset_id (invariant)."""
    # Create an asset first to link
    asset_resp = client.post("/api/v1/assets", headers=auth_headers, json={
        "name": "出租公寓",
        "category_id": category_id,
        "asset_type": "physical",
        "current_value": 1000000,
        "currency": "CNY",
    })
    assert asset_resp.status_code == 201
    asset_id = asset_resp.json()["data"]["id"]

    # Landlord contract linked to the asset
    resp = client.post("/api/v1/rental-contracts", headers=auth_headers, json={
        "role": "landlord",
        "monthly_rent": 5000,
        "start_date": "2026-01-01",
        "linked_asset_id": int(asset_id),
    })
    assert resp.status_code == 201
    assert resp.json()["data"]["linked_asset_id"] == asset_id

    # Switch role to tenant -> linked_asset_id must be cleared
    cid = resp.json()["data"]["id"]
    patch = client.patch(
        f"/api/v1/rental-contracts/{cid}", headers=auth_headers, json={"role": "tenant"}
    )
    assert patch.status_code == 200
    data = patch.json()["data"]
    assert data["role"] == "tenant"
    assert data["linked_asset_id"] is None


def test_valid_linked_asset_accepted(client, auth_headers, category_id):
    """Landlord contract with own-family asset id -> 201, linked_asset_id returned."""
    asset_resp = client.post("/api/v1/assets", headers=auth_headers, json={
        "name": "学区房",
        "category_id": category_id,
        "asset_type": "physical",
        "current_value": 2000000,
        "currency": "CNY",
    })
    assert asset_resp.status_code == 201
    asset_id = asset_resp.json()["data"]["id"]

    resp = client.post("/api/v1/rental-contracts", headers=auth_headers, json={
        "role": "landlord",
        "monthly_rent": 6000,
        "start_date": "2026-01-01",
        "linked_asset_id": int(asset_id),
    })
    assert resp.status_code == 201
    assert resp.json()["data"]["linked_asset_id"] == asset_id


def test_negative_monthly_rent_rejected(client, auth_headers):
    """monthly_rent <= 0 and deposit < 0 must be rejected (422)."""
    resp = client.post("/api/v1/rental-contracts", headers=auth_headers, json={
        "role": "landlord",
        "monthly_rent": -100,
        "start_date": "2026-01-01",
    })
    assert resp.status_code == 422

    resp = client.post("/api/v1/rental-contracts", headers=auth_headers, json={
        "role": "landlord",
        "monthly_rent": 100,
        "deposit": -50,
        "start_date": "2026-01-01",
    })
    assert resp.status_code == 422


def test_update_negative_amount_rejected(client, auth_headers, sample_contract):
    """PATCH with negative monthly_rent must be rejected (422)."""
    cid = sample_contract["id"]
    resp = client.patch(
        f"/api/v1/rental-contracts/{cid}", headers=auth_headers, json={"monthly_rent": -1}
    )
    assert resp.status_code == 422
