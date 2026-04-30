"""Tests for admin child view switching."""


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
            "username": "testchild1",
            "display_name": "TestChild",
            "password": "ChildPass1",
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
            "username": "testchild1",
            "display_name": "TestChild",
            "password": "ChildPass1",
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


def test_admin_switch_child_cross_family_isolation(client, auth_headers):
    """Owner cannot switch to child from another family."""
    # Owner 1 creates their child
    child_resp = client.post(
        "/api/v1/family/children",
        headers=auth_headers,
        json={
            "username": "owner1child",
            "display_name": "Owner1Child",
            "password": "ChildPass1",
            "pin": ["🐱", "🐶", "🐸", "🦊"],
        },
    )
    assert child_resp.status_code == 201
    owner1_child_id = child_resp.json()["data"]["id"]

    # Get owner 1's invite code
    family_resp = client.get("/api/v1/family", headers=auth_headers)
    invite_code_1 = family_resp.json()["data"]["invite_code"]

    # Create a second family (owner2)
    register_resp = client.post(
        "/api/v1/auth/register",
        json={
            "username": "owner2_user",
            "display_name": "Owner 2",
            "password": "Owner2Pass123",
            "family_name": "Second Family",
            "family_invitation_code": "AUTO-ADMIN",
        },
    )
    assert register_resp.status_code == 200
    owner2_token = register_resp.json()["data"]["access_token"]
    owner2_headers = {"Authorization": f"Bearer {owner2_token}"}

    # Owner 2 creates their child
    child2_resp = client.post(
        "/api/v1/family/children",
        headers=owner2_headers,
        json={
            "username": "owner2child",
            "display_name": "Owner2Child",
            "password": "ChildPass1",
            "pin": ["🦁", "🐯", "🌟", "🌈"],
        },
    )
    assert child2_resp.status_code == 201
    owner2_child_id = child2_resp.json()["data"]["id"]

    # Owner 1 tries to switch to Owner 2's child - should fail with 404
    response = client.post(
        f"/api/v1/auth/admin/switch-child/{owner2_child_id}",
        headers=auth_headers,
    )

    assert response.status_code == 404
    detail = response.json().get("detail", response.json().get("message", ""))
    assert "孩子不存在" in detail or "资源不存在" in detail or "not found" in detail.lower()