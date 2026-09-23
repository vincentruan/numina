"""Tests for GET /notification-channels/events endpoint.

Verifies the endpoint returns the registry-derived categorized event list
and that unauthenticated callers are rejected.
"""

from fastapi.testclient import TestClient


def test_get_events_returns_five_categories(client: TestClient, auth_headers):
    resp = client.get("/api/v1/notification-channels/events", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert len(data) == 5
    categories = [c["category"] for c in data]
    assert categories == ["asset", "ai_task", "children", "wish", "learning"]


def test_get_events_asset_category_has_three_events(client: TestClient, auth_headers):
    resp = client.get("/api/v1/notification-channels/events", headers=auth_headers)
    asset = next(c for c in resp.json()["data"] if c["category"] == "asset")
    assert len(asset["events"]) == 3
    types = [e["type"] for e in asset["events"]]
    assert "large_purchase" in types
    assert "expiring_soon" in types
    assert "maturity" in types


def test_get_events_requires_auth(client: TestClient):
    resp = client.get("/api/v1/notification-channels/events")
    assert resp.status_code in (401, 403)


def test_create_channel_persists_digest_fields(client: TestClient, auth_headers):
    resp = client.post(
        "/api/v1/notification-channels",
        headers=auth_headers,
        json={
            "channel_type": "telegram",
            "name": "Digest",
            "config": {"bot_token": "t", "chat_id": "1"},
            "is_enabled": True,
            "subscriptions": ["large_purchase"],
            "digest_mode": "daily",
            "digest_time": "08:30",
        },
    )
    assert resp.status_code == 201
    data = resp.json()["data"]
    assert data["digest_mode"] == "daily"
    assert data["digest_time"] == "08:30"


def test_create_channel_digest_defaults(client: TestClient, auth_headers):
    resp = client.post(
        "/api/v1/notification-channels",
        headers=auth_headers,
        json={
            "channel_type": "telegram",
            "name": "NoDigest",
            "config": {"bot_token": "t", "chat_id": "1"},
            "is_enabled": True,
            "subscriptions": [],
        },
    )
    assert resp.status_code == 201
    data = resp.json()["data"]
    assert data["digest_mode"] == "immediate"
    assert data["digest_time"] == "21:00"


def test_create_channel_accepts_registry_event_types(client: TestClient, auth_headers):
    """Registry-derived VALID_REMINDER_TYPES now accepts ai/children/wish events."""
    resp = client.post(
        "/api/v1/notification-channels",
        headers=auth_headers,
        json={
            "channel_type": "telegram",
            "name": "Multi",
            "config": {"bot_token": "t", "chat_id": "1"},
            "is_enabled": True,
            "subscriptions": [
                "ai_report_complete",
                "chore_completed",
                "wish_redeemed",
            ],
        },
    )
    assert resp.status_code == 201
    data = resp.json()["data"]
    assert set(data["subscriptions"]) == {
        "ai_report_complete",
        "chore_completed",
        "wish_redeemed",
    }
