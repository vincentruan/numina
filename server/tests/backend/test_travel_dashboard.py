"""Backend tests for travel module — dashboard travel_float computation (AE6 scenario)."""


import pytest


@pytest.fixture
def planning_trip(client, auth_headers):
    """Create a planning-status trip for travel_float testing."""
    response = client.post(
        "/api/v1/trips",
        headers=auth_headers,
        json={
            "name": "规划中的旅行",
            "destination": "三亚",
            "departure_date": "2026-12-01",
            "planned_budget": 8000,
        },
    )
    assert response.status_code == 201
    return response.json()["data"]


def test_travel_float_null_when_no_trips(client, auth_headers):
    """travel_float is null when family has no travel activity."""
    response = client.get("/api/v1/dashboard/overview", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()["data"]
    # No travel activity → travel_float should be None or "0.00"
    assert data.get("travel_float") is None or data.get("travel_float") == "0.00"


def test_travel_float_positive_with_prepaid_expenses(client, auth_headers, planning_trip, db):
    """travel_float = prepaid on planning trips when no unsettled settlements.

    Create an expense on a planning trip → travel_float should be positive.
    """
    trip_id = planning_trip["id"]

    # Add expense
    client.post(
        f"/api/v1/trips/{trip_id}/expenses",
        headers=auth_headers,
        json={
            "amount": 1500,
            "currency": "CNY",
            "expense_date": "2026-12-01",
            "description": "预付款",
        },
    )

    # Check overview
    response = client.get("/api/v1/dashboard/overview", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()["data"]
    travel_float = data.get("travel_float")
    # Should be positive (prepaid > 0, no settlements)
    assert travel_float is not None
    assert float(travel_float) > 0


def test_travel_float_cross_family_isolated(
    client, auth_headers, second_user_headers, planning_trip
):
    """Travel float for user 2 should not include user 1's trip expenses."""
    trip_id = planning_trip["id"]

    # Add expense for user 1
    client.post(
        f"/api/v1/trips/{trip_id}/expenses",
        headers=auth_headers,
        json={
            "amount": 2000,
            "currency": "CNY",
            "expense_date": "2026-12-01",
        },
    )

    # User 2's overview should not reflect user 1's expense
    response = client.get("/api/v1/dashboard/overview", headers=second_user_headers)
    data = response.json()["data"]
    travel_float = data.get("travel_float")
    # User 2 has no trips → null or zero
    assert travel_float is None or float(travel_float) == 0.0
