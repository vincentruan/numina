"""Backend tests for travel module — expense ledger (double-entry, multi-currency, reversal)."""

import pytest

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def trip(client, auth_headers):
    """Create a trip to attach expenses to."""
    response = client.post(
        "/api/v1/trips",
        headers=auth_headers,
        json={
            "name": "测试旅行",
            "destination": "北京",
            "departure_date": "2026-10-01",
            "return_date": "2026-10-03",
            "planned_budget": 5000,
        },
    )
    assert response.status_code == 201
    return response.json()["data"]


@pytest.fixture
def expense(client, auth_headers, trip):
    """Create a single expense on the trip."""
    trip_id = trip["id"]
    response = client.post(
        f"/api/v1/trips/{trip_id}/expenses",
        headers=auth_headers,
        json={
            "amount": 500,
            "currency": "CNY",
            "expense_date": "2026-10-01",
            "description": "酒店住宿",
        },
    )
    assert response.status_code == 201
    return response.json()["data"]


@pytest.fixture
def second_expense(client, auth_headers, trip):
    """Second expense for list tests."""
    trip_id = trip["id"]
    response = client.post(
        f"/api/v1/trips/{trip_id}/expenses",
        headers=auth_headers,
        json={
            "amount": 200,
            "currency": "CNY",
            "expense_date": "2026-10-02",
            "description": "餐饮",
        },
    )
    assert response.status_code == 201
    return response.json()["data"]


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------


def test_create_expense(client, auth_headers, trip):
    """Create an expense and verify double-entry response (debit leg returned)."""
    trip_id = trip["id"]
    response = client.post(
        f"/api/v1/trips/{trip_id}/expenses",
        headers=auth_headers,
        json={
            "amount": 350,
            "currency": "CNY",
            "expense_date": "2026-10-01",
            "description": "交通费用",
        },
    )
    assert response.status_code == 201
    data = response.json()["data"]
    assert data["amount"] == "350.00"
    assert data["amount_cny"] == "350.00"
    assert data["currency"] == "CNY"
    assert data["leg_type"] == "debit"
    assert data["ref_id"] == trip_id
    assert data["ref_type"] == "trip"
    assert isinstance(data["id"], str)
    assert isinstance(data["transfer_id"], str)


def test_create_expense_negative_amount_rejected(client, auth_headers, trip):
    """Amount must be positive — 422 on negative."""
    trip_id = trip["id"]
    response = client.post(
        f"/api/v1/trips/{trip_id}/expenses",
        headers=auth_headers,
        json={
            "amount": -100,
            "currency": "CNY",
            "expense_date": "2026-10-01",
        },
    )
    assert response.status_code == 422


def test_list_expenses(client, auth_headers, trip, expense, second_expense):
    """List expenses returns debit legs only, ordered by date desc."""
    trip_id = trip["id"]
    response = client.get(f"/api/v1/trips/{trip_id}/expenses", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()["data"]
    assert len(data) == 2
    # All should be debit legs
    assert all(e["leg_type"] == "debit" for e in data)


def test_get_expense_detail(client, auth_headers, trip, expense):
    """Get a single expense by ID."""
    trip_id = trip["id"]
    entry_id = expense["id"]
    response = client.get(
        f"/api/v1/trips/{trip_id}/expenses/{entry_id}", headers=auth_headers
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["amount"] == "500.00"
    assert data["description"] == "酒店住宿"


def test_delete_expense(client, auth_headers, trip, expense):
    """Delete (reverse) an expense creates offsetting entries."""
    trip_id = trip["id"]
    entry_id = expense["id"]
    response = client.delete(
        f"/api/v1/trips/{trip_id}/expenses/{entry_id}", headers=auth_headers
    )
    assert response.status_code == 200


# ---------------------------------------------------------------------------
# Double-entry validation (DB-level)
# ---------------------------------------------------------------------------


def test_expense_creates_debit_credit_pair(client, auth_headers, trip, db):
    """Creating an expense produces exactly one debit and one credit entry in DB."""
    from packages.db.models.expense_entry import ExpenseEntry

    trip_id = trip["id"]
    # Create expense
    client.post(
        f"/api/v1/trips/{trip_id}/expenses",
        headers=auth_headers,
        json={
            "amount": 100,
            "currency": "CNY",
            "expense_date": "2026-10-01",
            "description": "DB pair test",
        },
    )

    # Query all entries for this transfer
    entries = (
        db.query(ExpenseEntry)
        .filter(ExpenseEntry.ref_id == int(trip_id), ExpenseEntry.ref_type == "trip")
        .all()
    )
    debit_legs = [e for e in entries if e.leg_type == "debit"]
    credit_legs = [e for e in entries if e.leg_type == "credit"]
    assert len(debit_legs) == 1
    assert len(credit_legs) == 1
    assert debit_legs[0].transfer_id == credit_legs[0].transfer_id
    assert debit_legs[0].amount == credit_legs[0].amount


# ---------------------------------------------------------------------------
# Trip actual_spend tracking
# ---------------------------------------------------------------------------


def test_actual_spend_updates_on_expense(client, auth_headers, trip, expense):
    """Trip.actual_spend increases when expense is created."""
    trip_id = trip["id"]
    detail = client.get(f"/api/v1/trips/{trip_id}", headers=auth_headers)
    data = detail.json()["data"]
    assert data["actual_spend"] == "500.00"


def test_actual_spend_decreases_on_delete(client, auth_headers, trip, expense):
    """Trip.actual_spend decreases when expense is reversed."""
    trip_id = trip["id"]
    entry_id = expense["id"]
    client.delete(f"/api/v1/trips/{trip_id}/expenses/{entry_id}", headers=auth_headers)

    detail = client.get(f"/api/v1/trips/{trip_id}", headers=auth_headers)
    data = detail.json()["data"]
    assert data["actual_spend"] == "0.00"


# ---------------------------------------------------------------------------
# Cross-family isolation
# ---------------------------------------------------------------------------


def test_cross_family_expense_404(client, auth_headers, second_user_headers, trip, expense):
    """Another family cannot access trip expenses."""
    trip_id = trip["id"]
    entry_id = expense["id"]
    response = client.get(
        f"/api/v1/trips/{trip_id}/expenses/{entry_id}",
        headers=second_user_headers,
    )
    assert response.status_code == 404
