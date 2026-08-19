"""U3: retroactive liability creation + balance correction tests."""
from datetime import date, timedelta
from decimal import Decimal

import pytest


@pytest.fixture
def sample_liability(client, auth_headers):
    """Create a sample liability for balance correction tests."""
    response = client.post("/api/v1/liabilities", headers=auth_headers, json={
        "name": "余额调整测试贷款",
        "category": "personal_loan",
        "original_amount": "100000",
        "remaining_amount": "80000",
        "monthly_payment": "5000",
        "interest_rate": 5.0,
        "start_date": "2024-01-01",
        "institution": "Test Bank",
    })
    assert response.status_code == 201
    return response.json()["data"]


def _months_ago(months: int) -> str:
    """Return a date string N months before today."""
    d = date.today()
    year = d.year - (months // 12)
    month = d.month - (months % 12)
    while month <= 0:
        month += 12
        year -= 1
    day = min(d.day, 28)
    return date(year, month, day).isoformat()


@pytest.fixture
def retroactive_liability(client, auth_headers):
    """Create a liability with retroactive history (3 years ago, equal_principal)."""
    response = client.post("/api/v1/liabilities", headers=auth_headers, json={
        "name": "回溯测试房贷",
        "category": "mortgage",
        "original_amount": "360000",
        "remaining_amount": "300000",
        "monthly_payment": "10000",
        "interest_rate": 6.0,
        "repayment_method": "equal_principal",
        "start_date": _months_ago(36),
        "end_date": "2050-01-01",
        "institution": "Test Bank",
        "generate_history": True,
        "total_periods": 360,
    })
    assert response.status_code == 201
    return response.json()["data"]


def test_retroactive_generates_payment_records(client, auth_headers, retroactive_liability):
    """R7: generate_history=True + start_date < today → system PaymentRecords."""
    lid = retroactive_liability["id"]
    response = client.get(f"/api/v1/liabilities/{lid}/payments", headers=auth_headers)
    assert response.status_code == 200
    payments = response.json()["data"]
    # 36 months of history → 36-37 system records (boundary: start_date + N months == today is included)
    system_payments = [p for p in payments if p["source"] == "system"]
    assert len(system_payments) >= 36


def test_retroactive_payment_records_have_correct_dates(client, auth_headers, retroactive_liability):
    """PaymentRecord paid_at dates should increment monthly from start_date."""
    lid = retroactive_liability["id"]
    response = client.get(f"/api/v1/liabilities/{lid}/payments", headers=auth_headers)
    payments = response.json()["data"]
    system_payments = sorted(
        [p for p in payments if p["source"] == "system"],
        key=lambda p: p["paid_at"],
    )
    # First payment should be close to start_date (36 months ago)
    # Last system payment should be close to today
    assert len(system_payments) >= 36
    # Verify ordered dates
    for i in range(1, len(system_payments)):
        assert system_payments[i]["paid_at"] >= system_payments[i - 1]["paid_at"]


def test_no_retroactive_without_flag(client, auth_headers):
    """generate_history=False → no system PaymentRecords created."""
    response = client.post("/api/v1/liabilities", headers=auth_headers, json={
        "name": "无回溯贷款",
        "category": "personal_loan",
        "original_amount": "50000",
        "remaining_amount": "50000",
        "interest_rate": 5.0,
        "repayment_method": "equal_principal",
        "start_date": _months_ago(12),
        "generate_history": False,
    })
    assert response.status_code == 201
    lid = response.json()["data"]["id"]
    payments_resp = client.get(f"/api/v1/liabilities/{lid}/payments", headers=auth_headers)
    payments = payments_resp.json()["data"]
    system_payments = [p for p in payments if p["source"] == "system"]
    assert len(system_payments) == 0


def test_no_retroactive_for_future_start(client, auth_headers):
    """start_date in the future → no retroactive records even with flag."""
    future = (date.today() + timedelta(days=30)).isoformat()
    response = client.post("/api/v1/liabilities", headers=auth_headers, json={
        "name": "未来贷款",
        "category": "car_loan",
        "original_amount": "100000",
        "remaining_amount": "100000",
        "interest_rate": 4.0,
        "repayment_method": "equal_principal",
        "start_date": future,
        "generate_history": True,
        "total_periods": 60,
    })
    assert response.status_code == 201
    lid = response.json()["data"]["id"]
    payments_resp = client.get(f"/api/v1/liabilities/{lid}/payments", headers=auth_headers)
    payments = payments_resp.json()["data"]
    system_payments = [p for p in payments if p["source"] == "system"]
    assert len(system_payments) == 0


def test_balance_correction_increases_remaining(client, auth_headers, sample_liability):
    """Positive correction increases remaining_amount."""
    lid = sample_liability["id"]
    original_remaining = Decimal(sample_liability["remaining_amount"])

    response = client.post(
        f"/api/v1/liabilities/{lid}/balance-correction",
        headers=auth_headers,
        json={"amount": "5000", "reason": "Interest recalculation"},
    )
    assert response.status_code == 201
    body = response.json()["data"]
    assert body["amount"] == "5000.00"
    assert body["reason"] == "Interest recalculation"

    # Verify remaining_amount was updated
    detail_resp = client.get(f"/api/v1/liabilities/{lid}", headers=auth_headers)
    updated_remaining = Decimal(detail_resp.json()["data"]["remaining_amount"])
    assert updated_remaining == original_remaining + Decimal("5000")


def test_balance_correction_decreases_remaining(client, auth_headers, sample_liability):
    """Negative correction decreases remaining_amount."""
    lid = sample_liability["id"]
    original_remaining = Decimal(sample_liability["remaining_amount"])

    response = client.post(
        f"/api/v1/liabilities/{lid}/balance-correction",
        headers=auth_headers,
        json={"amount": "-10000", "reason": "Overpayment adjustment"},
    )
    assert response.status_code == 201

    detail_resp = client.get(f"/api/v1/liabilities/{lid}", headers=auth_headers)
    updated_remaining = Decimal(detail_resp.json()["data"]["remaining_amount"])
    assert updated_remaining == original_remaining - Decimal("10000")


def test_balance_correction_list(client, auth_headers, sample_liability):
    """List corrections returns all corrections for a liability."""
    lid = sample_liability["id"]

    # Create two corrections
    client.post(
        f"/api/v1/liabilities/{lid}/balance-correction",
        headers=auth_headers,
        json={"amount": "1000"},
    )
    client.post(
        f"/api/v1/liabilities/{lid}/balance-correction",
        headers=auth_headers,
        json={"amount": "-500", "reason": "Adjustment"},
    )

    response = client.get(f"/api/v1/liabilities/{lid}/balance-corrections", headers=auth_headers)
    assert response.status_code == 200
    corrections = response.json()["data"]
    assert len(corrections) == 2


def test_payment_source_default_manual(client, auth_headers, sample_liability):
    """Manual payment records have source='manual' by default."""
    lid = sample_liability["id"]
    response = client.put(
        f"/api/v1/liabilities/{lid}/payment",
        headers=auth_headers,
        json={"amount": "1000"},
    )
    assert response.status_code == 200

    payments_resp = client.get(f"/api/v1/liabilities/{lid}/payments", headers=auth_headers)
    payments = payments_resp.json()["data"]
    manual_payments = [p for p in payments if p["source"] == "manual"]
    assert len(manual_payments) >= 1
