"""Backend tests for travel module — wish-to-trip graduation pipeline."""

import pytest


@pytest.fixture
def travel_wish(client, auth_headers):
    """Create a travel wish (converts_to_asset=False) for graduation."""
    response = client.post(
        "/api/v1/wishes",
        headers=auth_headers,
        json={
            "name": "家庭旅行基金",
            "expected_price": 20000,
            "priority": "high",
            "currency": "CNY",
            "converts_to_asset": False,
            "target_date": "2026-12-01",
        },
    )
    assert response.status_code == 201
    return response.json()["data"]


# ---------------------------------------------------------------------------
# Graduation
# ---------------------------------------------------------------------------


def test_graduate_wish_to_trip(client, auth_headers, travel_wish):
    """Graduate a pending travel wish into a Trip."""
    wish_id = travel_wish["id"]
    response = client.post(
        "/api/v1/trips/graduate",
        headers=auth_headers,
        json={"wish_id": int(wish_id)},
    )
    assert response.status_code == 201
    data = response.json()["data"]
    assert data["name"] == "家庭旅行基金"
    assert data["status"] == "planning"
    assert data["planned_budget"] == "20000.00"
    assert data["currency"] == "CNY"
    # wish_id is preserved
    assert data["wish_id"] == wish_id
    assert isinstance(data["id"], str)


def test_graduate_nonexistent_wish_returns_404(client, auth_headers):
    """Graduating a non-existent wish returns 404."""
    response = client.post(
        "/api/v1/trips/graduate",
        headers=auth_headers,
        json={"wish_id": 999999999},
    )
    assert response.status_code == 404


def test_graduate_already_realized_wish_fails(client, auth_headers, travel_wish):
    """Cannot graduate a wish that is already realized."""
    wish_id = travel_wish["id"]

    # Graduate once
    response = client.post(
        "/api/v1/trips/graduate",
        headers=auth_headers,
        json={"wish_id": int(wish_id)},
    )
    assert response.status_code == 201

    # Try to graduate again — wish is now "realized", not "pending"
    response2 = client.post(
        "/api/v1/trips/graduate",
        headers=auth_headers,
        json={"wish_id": int(wish_id)},
    )
    # Should fail because wish status is no longer "pending"
    assert response2.status_code == 422


def test_graduate_creates_trip_in_same_family(client, auth_headers, travel_wish):
    """Graduated trip belongs to the same family as the wish."""
    wish_id = travel_wish["id"]
    response = client.post(
        "/api/v1/trips/graduate",
        headers=auth_headers,
        json={"wish_id": int(wish_id)},
    )
    trip_data = response.json()["data"]
    assert trip_data["family_id"] == travel_wish["family_id"]


# ---------------------------------------------------------------------------
# Cancel reverts wish
# ---------------------------------------------------------------------------


def test_cancel_trip_reverts_wish_status(client, auth_headers, travel_wish):
    """Cancelling a graduated trip reverts the wish to pending."""
    wish_id = travel_wish["id"]

    # Graduate
    grad_response = client.post(
        "/api/v1/trips/graduate",
        headers=auth_headers,
        json={"wish_id": int(wish_id)},
    )
    trip_id = grad_response.json()["data"]["id"]

    # Cancel the trip
    cancel_response = client.post(
        f"/api/v1/trips/{trip_id}/cancel",
        headers=auth_headers,
    )
    assert cancel_response.status_code == 200

    # Verify wish is back to pending — try graduating again
    re_grad = client.post(
        "/api/v1/trips/graduate",
        headers=auth_headers,
        json={"wish_id": int(wish_id)},
    )
    assert re_grad.status_code == 201


# ---------------------------------------------------------------------------
# Cross-family isolation
# ---------------------------------------------------------------------------


def test_cross_family_graduate_fails(client, auth_headers, second_user_headers):
    """Cannot graduate another family's wish."""
    # Create a wish with user 1
    response = client.post(
        "/api/v1/wishes",
        headers=auth_headers,
        json={
            "name": "User1的旅行",
            "expected_price": 5000,
            "priority": "medium",
            "currency": "CNY",
            "converts_to_asset": False,
            "target_date": "2026-11-01",
        },
    )
    wish_id = response.json()["data"]["id"]

    # Try to graduate with user 2 (different family)
    response2 = client.post(
        "/api/v1/trips/graduate",
        headers=second_user_headers,
        json={"wish_id": int(wish_id)},
    )
    # Should fail — wish not found in second user's family
    assert response2.status_code == 404
