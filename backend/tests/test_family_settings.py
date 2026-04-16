"""Tests for Family.auto_approve_hours settings endpoint."""

import pytest


@pytest.fixture
def child_token(client, auth_headers):
    """Create a child and return their Bearer token (no parent cookie)."""
    resp = client.post("/api/v1/family/children", headers=auth_headers, json={
        "display_name": "小明",
        "avatar_color": "#FF5733",
        "pin": ["🐱", "🌟", "🎈", "🐶"],
    })
    child_id = resp.json()["id"]
    login = client.post("/api/v1/auth/child/login", json={
        "child_id": child_id,
        "pin_sequence": ["🐱", "🌟", "🎈", "🐶"],
    })
    token = login.json()["access_token"]
    client.cookies.delete("access_token")
    return {"Authorization": f"Bearer {token}"}


def test_owner_can_update_auto_approve_hours(client, auth_headers):
    resp = client.patch("/api/v1/family/settings", headers=auth_headers, json={"auto_approve_hours": 48})
    assert resp.status_code == 200
    assert resp.json()["auto_approve_hours"] == 48


def test_auto_approve_hours_min_boundary(client, auth_headers):
    resp = client.patch("/api/v1/family/settings", headers=auth_headers, json={"auto_approve_hours": 1})
    assert resp.status_code == 200
    assert resp.json()["auto_approve_hours"] == 1


def test_auto_approve_hours_max_boundary(client, auth_headers):
    resp = client.patch("/api/v1/family/settings", headers=auth_headers, json={"auto_approve_hours": 168})
    assert resp.status_code == 200
    assert resp.json()["auto_approve_hours"] == 168


def test_auto_approve_hours_too_low(client, auth_headers):
    resp = client.patch("/api/v1/family/settings", headers=auth_headers, json={"auto_approve_hours": 0})
    assert resp.status_code == 422


def test_auto_approve_hours_too_high(client, auth_headers):
    resp = client.patch("/api/v1/family/settings", headers=auth_headers, json={"auto_approve_hours": 169})
    assert resp.status_code == 422


def test_child_cannot_update_settings(client, child_token):
    resp = client.patch("/api/v1/family/settings", headers=child_token, json={"auto_approve_hours": 48})
    assert resp.status_code == 403
