"""Tests for family endpoints."""

import pytest


def test_get_family_info(client, auth_headers):
    """GET /family returns family info with members list."""
    response = client.get("/api/v1/family", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()["data"]
    assert "id" in data
    assert "name" in data
    assert "invite_code" in data
    assert isinstance(data["members"], list)
    assert len(data["members"]) >= 1


def test_get_family_info_unauthorized(client):
    """GET /family without auth returns 401."""
    response = client.get("/api/v1/family")
    assert response.status_code == 401


def test_get_family_members(client, auth_headers):
    """GET /family/members returns list of members."""
    response = client.get("/api/v1/family/members", headers=auth_headers)
    assert response.status_code == 200
    members = response.json()["data"]
    assert isinstance(members, list)
    assert len(members) >= 1
    member = members[0]
    assert "id" in member
    assert "username" in member
    assert "display_name" in member
    assert "role" in member


def test_get_family_members_unauthorized(client):
    """GET /family/members without auth returns 401."""
    response = client.get("/api/v1/family/members")
    assert response.status_code == 401


def test_get_family_aggregate_empty(client, auth_headers):
    """GET /family/aggregate returns zeros when no assets/liabilities."""
    response = client.get("/api/v1/family/aggregate", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["total_assets"] == 0
    assert data["total_liabilities"] == 0
    assert data["net_worth"] == 0
    assert data["asset_count"] == 0


def test_get_family_aggregate_with_assets(client, auth_headers):
    """GET /family/aggregate reflects created assets."""
    # Get a category
    cats = client.get("/api/v1/categories", headers=auth_headers).json()["data"]
    cat_id = next(c["id"] for c in cats if c["asset_type"] == "physical")

    client.post("/api/v1/assets", headers=auth_headers, json={
        "name": "测试房产",
        "category_id": cat_id,
        "asset_type": "physical",
        "purchase_price": 1000000,
        "current_value": 1200000,
    })

    response = client.get("/api/v1/family/aggregate", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["total_assets"] == 1200000
    assert data["asset_count"] == 1
    assert data["net_worth"] == 1200000


def test_regenerate_invite_code(client, auth_headers):
    """POST /family/invite-code regenerates the invite code (owner only)."""
    # Get original invite code
    original = client.get("/api/v1/family", headers=auth_headers).json()["data"]["invite_code"]

    response = client.post("/api/v1/family/invite-code", headers=auth_headers)
    assert response.status_code == 200
    new_code = response.json()["data"]["invite_code"]
    assert new_code != original
    assert len(new_code) > 0


def test_regenerate_invite_code_non_owner_forbidden(client, auth_headers):
    """Non-owner member cannot regenerate invite code."""
    # Get invite code and join as a member (non-owner)
    invite_code = client.get("/api/v1/family", headers=auth_headers).json()["data"]["invite_code"]
    join_resp = client.post("/api/v1/auth/family/join", json={
        "username": "member2",
        "display_name": "Member Two",
        "password": "MemberPass123",
        "invite_code": invite_code,
    })
    assert join_resp.status_code == 200
    member_token = join_resp.json()["data"]["access_token"]
    member_headers = {"Authorization": f"Bearer {member_token}"}

    response = client.post("/api/v1/family/invite-code", headers=member_headers)
    assert response.status_code == 403


def test_cross_family_isolation_family_info(client, auth_headers, second_user_headers):
    """Family A user cannot see Family B's data via /family endpoint."""
    resp_a = client.get("/api/v1/family", headers=auth_headers).json()["data"]
    resp_b = client.get("/api/v1/family", headers=second_user_headers).json()["data"]
    assert resp_a["id"] != resp_b["id"]
    assert resp_a["invite_code"] != resp_b["invite_code"]


def test_cross_family_isolation_members(client, auth_headers, second_user_headers):
    """Family A members list does not include Family B members."""
    members_a = client.get("/api/v1/family/members", headers=auth_headers).json()["data"]
    members_b = client.get("/api/v1/family/members", headers=second_user_headers).json()["data"]
    ids_a = {m["id"] for m in members_a}
    ids_b = {m["id"] for m in members_b}
    assert ids_a.isdisjoint(ids_b)


def test_cross_family_isolation_aggregate(client, auth_headers, second_user_headers):
    """Family A aggregate does not include Family B assets."""
    cats = client.get("/api/v1/categories", headers=auth_headers).json()["data"]
    cat_id = next(c["id"] for c in cats if c["asset_type"] == "physical")

    # Create asset in family A
    client.post("/api/v1/assets", headers=auth_headers, json={
        "name": "家庭A资产",
        "category_id": cat_id,
        "asset_type": "physical",
        "purchase_price": 500000,
        "current_value": 500000,
    })

    # Family B aggregate should still be zero
    agg_b = client.get("/api/v1/family/aggregate", headers=second_user_headers).json()["data"]
    assert agg_b["total_assets"] == 0
    assert agg_b["asset_count"] == 0
