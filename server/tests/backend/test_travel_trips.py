"""Backend tests for travel module — trip CRUD, status transitions, permissions."""

import pytest

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_trip(client, auth_headers):
    """Create a sample trip via API."""
    response = client.post(
        "/api/v1/trips",
        headers=auth_headers,
        json={
            "name": "东京之旅",
            "destination": "东京",
            "departure_date": "2026-10-01",
            "return_date": "2026-10-07",
            "planned_budget": 15000,
            "currency": "CNY",
        },
    )
    assert response.status_code == 201
    return response.json()["data"]


@pytest.fixture
def second_trip(client, auth_headers):
    """Second trip for list tests."""
    response = client.post(
        "/api/v1/trips",
        headers=auth_headers,
        json={
            "name": "上海出差",
            "destination": "上海",
            "departure_date": "2026-11-15",
            "planned_budget": 3000,
        },
    )
    assert response.status_code == 201
    return response.json()["data"]


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------


def test_create_trip(client, auth_headers):
    """Create a trip and verify response shape."""
    response = client.post(
        "/api/v1/trips",
        headers=auth_headers,
        json={
            "name": "大阪自由行",
            "destination": "大阪",
            "departure_date": "2026-12-01",
            "return_date": "2026-12-05",
            "planned_budget": 10000,
            "currency": "JPY",
        },
    )
    assert response.status_code == 201
    data = response.json()["data"]
    assert data["name"] == "大阪自由行"
    assert data["destination"] == "大阪"
    assert data["status"] == "planning"
    assert data["planned_budget"] == "10000.00"
    assert data["currency"] == "JPY"
    assert data["is_active"] is True
    # SnowflakeBase: id serialized as str
    assert isinstance(data["id"], str)


def test_create_trip_minimal(client, auth_headers):
    """Create a trip with only required fields."""
    response = client.post(
        "/api/v1/trips",
        headers=auth_headers,
        json={
            "name": "周末游",
            "destination": "苏州",
            "departure_date": "2026-10-10",
        },
    )
    assert response.status_code == 201
    data = response.json()["data"]
    assert data["return_date"] is None
    assert data["planned_budget"] is None
    assert data["currency"] == "CNY"


def test_list_trips(client, auth_headers, sample_trip, second_trip):
    """List returns both trips ordered by departure_date desc."""
    response = client.get("/api/v1/trips", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()["data"]
    assert len(data) == 2


def test_list_trips_filter_status(client, auth_headers, sample_trip):
    """Filter by status returns matching trips only."""
    response = client.get(
        "/api/v1/trips",
        headers=auth_headers,
        params={"status": "planning"},
    )
    data = response.json()["data"]
    assert len(data) >= 1
    assert all(t["status"] == "planning" for t in data)


def test_get_trip_detail(client, auth_headers, sample_trip):
    """Get trip by ID returns full detail."""
    trip_id = sample_trip["id"]
    response = client.get(f"/api/v1/trips/{trip_id}", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["name"] == "东京之旅"
    assert data["destination"] == "东京"
    assert data["actual_spend"] == "0.00"


def test_update_trip(client, auth_headers, sample_trip):
    """Update trip fields."""
    trip_id = sample_trip["id"]
    response = client.patch(
        f"/api/v1/trips/{trip_id}",
        headers=auth_headers,
        json={"name": "东京秋季游", "planned_budget": 20000},
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["name"] == "东京秋季游"
    assert data["planned_budget"] == "20000.00"


def test_update_trip_status(client, auth_headers, sample_trip):
    """Status transition: planning -> active."""
    trip_id = sample_trip["id"]
    response = client.patch(
        f"/api/v1/trips/{trip_id}",
        headers=auth_headers,
        json={"status": "active"},
    )
    assert response.status_code == 200
    assert response.json()["data"]["status"] == "active"


def test_delete_trip(client, auth_headers, sample_trip):
    """Delete (soft) sets is_active=False."""
    trip_id = sample_trip["id"]
    response = client.delete(f"/api/v1/trips/{trip_id}", headers=auth_headers)
    assert response.status_code == 200

    # Verify is_active is False
    detail = client.get(f"/api/v1/trips/{trip_id}", headers=auth_headers)
    assert detail.json()["data"]["is_active"] is False


# ---------------------------------------------------------------------------
# Status transitions — cancel
# ---------------------------------------------------------------------------


def test_cancel_trip(client, auth_headers, sample_trip):
    """Cancel a planning trip sets status=cancelled and is_active=False."""
    trip_id = sample_trip["id"]
    response = client.post(f"/api/v1/trips/{trip_id}/cancel", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["status"] == "cancelled"
    assert data["is_active"] is False


def test_cancel_active_trip_fails(client, auth_headers, sample_trip):
    """Cannot cancel a trip that is not in planning status."""
    trip_id = sample_trip["id"]
    # Move to active first
    client.patch(
        f"/api/v1/trips/{trip_id}",
        headers=auth_headers,
        json={"status": "active"},
    )
    response = client.post(f"/api/v1/trips/{trip_id}/cancel", headers=auth_headers)
    # TRIP_STATUS_CONFLICT -> 409
    assert response.status_code == 409


# ---------------------------------------------------------------------------
# Cross-family isolation
# ---------------------------------------------------------------------------


def test_cross_family_trip_returns_404(client, auth_headers, second_user_headers, sample_trip):
    """Accessing another family's trip returns 404 (not 403 — no existence leak)."""
    trip_id = sample_trip["id"]
    response = client.get(f"/api/v1/trips/{trip_id}", headers=second_user_headers)
    assert response.status_code == 404


def test_cross_family_list_empty(client, second_user_headers, sample_trip):
    """Other family's trip list is empty — family isolation."""
    response = client.get("/api/v1/trips", headers=second_user_headers)
    assert response.status_code == 200
    data = response.json()["data"]
    assert len(data) == 0


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def test_create_trip_missing_required_fields(client, auth_headers):
    """Missing name/destination/departure_date returns 422."""
    response = client.post(
        "/api/v1/trips",
        headers=auth_headers,
        json={"name": "Incomplete"},
    )
    assert response.status_code == 422


def test_update_invalid_status_rejected(client, auth_headers, sample_trip):
    """Invalid status value returns 422."""
    trip_id = sample_trip["id"]
    response = client.patch(
        f"/api/v1/trips/{trip_id}",
        headers=auth_headers,
        json={"status": "invalid_status"},
    )
    assert response.status_code == 422
