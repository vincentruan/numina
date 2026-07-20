import pytest


@pytest.fixture
def sample_liability(client, auth_headers):
    """Create a sample liability"""
    response = client.post("/api/v1/liabilities", headers=auth_headers, json={
        "name": "招商银行房贷",
        "category": "mortgage",
        "original_amount": 2000000,
        "remaining_amount": 1800000,
        "monthly_payment": 12000,
        "interest_rate": 4.2,
        "start_date": "2020-01-01",
        "end_date": "2050-01-01",
        "institution": "招商银行"
    })
    assert response.status_code == 201
    return response.json()["data"]


def test_create_liability(client, auth_headers):
    """Test creating a liability"""
    response = client.post("/api/v1/liabilities", headers=auth_headers, json={
        "name": "车贷",
        "category": "car_loan",
        "original_amount": 200000,
        "remaining_amount": 150000,
        "monthly_payment": 5000,
        "interest_rate": 3.8,
        "institution": "工商银行"
    })
    assert response.status_code == 201
    data = response.json()["data"]
    assert data["name"] == "车贷"
    assert data["category"] == "car_loan"
    # Money fields are str on the wire (money-as-str convention).
    assert data["original_amount"] == "200000.00"
    assert data["remaining_amount"] == "150000.00"
    assert data["is_active"] is True


def test_list_liabilities(client, auth_headers, sample_liability):
    """Test listing liabilities"""
    response = client.get("/api/v1/liabilities", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()["data"]
    assert len(data) >= 1
    assert data[0]["name"] == "招商银行房贷"


def test_get_liability_detail(client, auth_headers, sample_liability):
    """Test getting liability detail"""
    lid = sample_liability["id"]
    response = client.get(f"/api/v1/liabilities/{lid}", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["name"] == "招商银行房贷"
    assert data["interest_rate"] == 4.2


def test_update_liability(client, auth_headers, sample_liability):
    """Test updating a liability"""
    lid = sample_liability["id"]
    response = client.put(f"/api/v1/liabilities/{lid}", headers=auth_headers, json={
        "monthly_payment": 13000
    })
    assert response.status_code == 200
    assert response.json()["data"]["monthly_payment"] == "13000.00"


def test_record_payment(client, auth_headers, sample_liability):
    """Test recording a payment"""
    lid = sample_liability["id"]
    response = client.put(f"/api/v1/liabilities/{lid}/payment", headers=auth_headers, json={
        "amount": 12000
    })
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["remaining_amount"] == "1788000.00"  # 1800000 - 12000
    assert data["is_active"] is True


def test_get_payments_returns_str_amount(client, auth_headers, sample_liability):
    """GET /liabilities/{id}/payments returns money as str (money-as-str).
    Regression for #9: PaymentRecord.amount migrated Float->Numeric(18,2);
    the response must serialize Decimal as str without crashing."""
    lid = sample_liability["id"]
    client.put(f"/api/v1/liabilities/{lid}/payment", headers=auth_headers, json={"amount": 12000})

    resp = client.get(f"/api/v1/liabilities/{lid}/payments", headers=auth_headers)
    assert resp.status_code == 200, resp.text
    rows = resp.json()["data"]
    assert len(rows) >= 1
    assert rows[0]["amount"] == "12000.00"  # str, 2 decimals
    assert rows[0]["liability_id"] == lid


def test_record_payment_full_payoff(client, auth_headers):
    """Test that paying off fully marks liability as inactive"""
    # Create a small liability
    create_response = client.post("/api/v1/liabilities", headers=auth_headers, json={
        "name": "小额借款",
        "category": "personal_loan",
        "original_amount": 1000,
        "remaining_amount": 500,
        "monthly_payment": 500
    })
    assert create_response.status_code == 201
    lid = create_response.json()["data"]["id"]

    # Pay it off completely
    response = client.put(f"/api/v1/liabilities/{lid}/payment", headers=auth_headers, json={
        "amount": 500
    })
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["remaining_amount"] == "0.00"
    assert data["is_active"] is False


def test_delete_liability(client, auth_headers, sample_liability):
    """Test deleting a liability"""
    lid = sample_liability["id"]
    response = client.delete(f"/api/v1/liabilities/{lid}", headers=auth_headers)
    assert response.status_code == 200

    # Verify it's gone
    get_response = client.get(f"/api/v1/liabilities/{lid}", headers=auth_headers)
    assert get_response.status_code == 404


def test_cross_family_liability_isolation(client, auth_headers, second_user_headers, sample_liability):
    """Test that users from different families cannot access each other's liabilities"""
    lid = sample_liability["id"]
    response = client.get(f"/api/v1/liabilities/{lid}", headers=second_user_headers)
    assert response.status_code == 404
