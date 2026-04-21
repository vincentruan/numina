"""Tests for admin child view switching."""
import pytest


def test_admin_switch_child_requires_owner(client, auth_headers):
    """Only owner can switch to child view."""
    # Get family info and invite code from owner
    family_resp = client.get("/api/v1/family", headers=auth_headers)
    assert family_resp.status_code == 200
    invite_code = family_resp.json()["data"]["invite_code"]

    # Create a child account as owner
    child_resp = client.post(
        "/api/v1/family/children",
        headers=auth_headers,
        json={
            "display_name": "TestChild",
            "pin": ["🐱", "🐶", "🐸", "🦊"],  # Required 4-emoji PIN
        },
    )
    assert child_resp.status_code == 201
    child_id = child_resp.json()["data"]["id"]

    # Join as a member (non-owner)
    join_resp = client.post(
        "/api/v1/auth/family/join",
        json={
            "username": "member_user",
            "display_name": "Member User",
            "password": "MemberPass123",
            "invite_code": invite_code,
        },
    )
    assert join_resp.status_code == 200
    member_token = join_resp.json()["data"]["access_token"]
    member_headers = {"Authorization": f"Bearer {member_token}"}

    # Member tries to switch to child view - should fail with 403
    response = client.post(
        f"/api/v1/auth/admin/switch-child/{child_id}",
        headers=member_headers,
    )
    assert response.status_code == 403
    # Check for appropriate error message
    detail = response.json().get("detail", response.json().get("message", ""))
    assert "仅家庭管理员" in detail or "Forbidden" in detail or "forbidden" in detail.lower()


def test_admin_switch_child_success(client, auth_headers):
    """Owner can successfully switch to child view."""
    # Get family info from owner
    family_resp = client.get("/api/v1/family", headers=auth_headers)
    assert family_resp.status_code == 200

    # Create a child account as owner
    child_resp = client.post(
        "/api/v1/family/children",
        headers=auth_headers,
        json={
            "display_name": "TestChild",
            "pin": ["🐱", "🐶", "🐸", "🦊"],  # Required 4-emoji PIN
        },
    )
    assert child_resp.status_code == 201
    child_id = child_resp.json()["data"]["id"]

    # Owner switches to child view
    response = client.post(
        f"/api/v1/auth/admin/switch-child/{child_id}",
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data["data"]
    assert "refresh_token" in data["data"]

    # Verify child cookies are set (optional - backend sets cookies)
    # The endpoint should set child_auth cookies