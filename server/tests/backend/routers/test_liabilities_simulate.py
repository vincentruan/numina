"""L2 /liabilities/simulate endpoint (Plan B T4)."""
from decimal import Decimal


def test_simulate_returns_interest_and_months(client, auth_headers):
    resp = client.post(
        "/api/v1/liabilities/simulate",
        json={"remaining": "100000", "annual_rate": "12", "monthly_payment": "3000"},
        headers=auth_headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()["data"]
    assert Decimal(body["total_interest"]) > 0
    assert body["months"] > 0


def test_simulate_with_extra_returns_comparison(client, auth_headers):
    resp = client.post(
        "/api/v1/liabilities/simulate",
        json={
            "remaining": "100000",
            "annual_rate": "12",
            "monthly_payment": "3000",
            "extra_monthly": "500",
        },
        headers=auth_headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()["data"]
    assert body["baseline_total_interest"] is not None
    assert body["savings_vs_baseline"] is not None
    assert Decimal(body["savings_vs_baseline"]) > 0
    assert body["months_saved"] > 0


def test_simulate_zero_rate_returns_warning(client, auth_headers):
    resp = client.post(
        "/api/v1/liabilities/simulate",
        json={"remaining": "100000", "annual_rate": "0", "monthly_payment": "3000"},
        headers=auth_headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()["data"]
    assert body["warning"] is not None
    assert body["total_interest"] == "0.00"


def test_simulate_min_payment_mode(client, auth_headers):
    """monthly_payment None → min-payment mode (credit-card style)."""
    resp = client.post(
        "/api/v1/liabilities/simulate",
        json={"remaining": "10000", "annual_rate": "18"},
        headers=auth_headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()["data"]
    assert body["months"] > 0
    # min-payment mode returns monthly_payment=None (computed internally each month)
    assert body["monthly_payment"] is None
