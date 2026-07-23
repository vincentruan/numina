"""Tests for family endpoints."""



def test_get_family_info(client, auth_headers):
    """GET /family returns family info with members list."""
    response = client.get("/api/v1/family", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()["data"]
    assert "id" in data
    assert "name" in data
    assert "invite_code" in data
    assert "creator_code" in data
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


def test_get_member_summary_with_liability_and_asset(client, auth_headers):
    """GET /family/members/{id}/summary must not crash when the family has both
    Float asset values and Decimal (Numeric) liability amounts. Regression for the
    float - Decimal TypeError that the liability Float->Numeric migration introduced
    (get_member_summary was not fixed alongside get_aggregate)."""
    cats = client.get("/api/v1/categories", headers=auth_headers).json()["data"]
    cat_id = next(c["id"] for c in cats if c["asset_type"] == "physical")
    client.post("/api/v1/assets", headers=auth_headers, json={
        "name": "房产",
        "category_id": cat_id,
        "asset_type": "physical",
        "purchase_price": 1000000,
        "current_value": 1200000,
    })
    client.post("/api/v1/liabilities", headers=auth_headers, json={
        "name": "房贷",
        "category": "mortgage",
        "original_amount": 800000,
        "remaining_amount": 600000,
        "monthly_payment": 5000,
        "interest_rate": 4.2,
    })

    me = client.get("/api/v1/auth/me", headers=auth_headers).json()["data"]
    response = client.get(f"/api/v1/family/members/{me['id']}/summary", headers=auth_headers)
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["total_assets"] == 1200000
    assert data["total_liabilities"] == 600000
    assert data["net_worth"] == 600000


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


def test_regenerate_invite_code_rate_limit(client, auth_headers):
    """POST /family/invite-code returns 429 after 5 attempts per hour."""
    import jwt

    from apps.backend.app.auth.deps import ALGORITHM
    from apps.backend.app.config import settings
    from apps.backend.app.services import auth as auth_service
    from apps.backend.app.services.cache.factory import get_rate_limit_cache

    token = auth_headers["Authorization"].split(" ")[1]
    user_id = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])["sub"]

    cache = get_rate_limit_cache()
    key = f"invite_code_attempts:{user_id}"
    cache.set(key, auth_service._INVITE_CODE_RATE_LIMIT_PER_HOUR, ttl_seconds=3600)

    response = client.post("/api/v1/family/invite-code", headers=auth_headers)
    assert response.status_code == 429


def test_regenerate_invite_code_rate_limit_includes_retry_after(client, auth_headers):
    """Invite-code rate-limited response includes Retry-After header."""
    import jwt

    from apps.backend.app.auth.deps import ALGORITHM
    from apps.backend.app.config import settings
    from apps.backend.app.services import auth as auth_service
    from apps.backend.app.services.cache.factory import get_rate_limit_cache

    token = auth_headers["Authorization"].split(" ")[1]
    user_id = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])["sub"]

    # Exhaust the invite code rate limit
    cache = get_rate_limit_cache()
    key = f"invite_code_attempts:{user_id}"
    cache.set(key, auth_service._INVITE_CODE_RATE_LIMIT_PER_HOUR, ttl_seconds=3600)

    response = client.post("/api/v1/family/invite-code", headers=auth_headers)
    assert response.status_code == 429
    assert "retry-after" in response.headers
    assert int(response.headers["retry-after"]) > 0


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


def test_family_info_returns_correct_creator_code(client, db):
    """GET /family returns the correct creator_code that was used during registration."""
    from apps.backend.app.models.family_invitation_code import FamilyInvitationCode
    from apps.backend.app.schemas.auth import RegisterRequest
    from apps.backend.app.services.auth import register
    import random
    import string

    code_str = "".join(random.choices(string.ascii_uppercase, k=6))
    inv_code = FamilyInvitationCode(code=code_str)
    db.add(inv_code)
    db.commit()

    req = RegisterRequest(
        username=f"user_{code_str.lower()}",
        password="Password123",
        display_name="Creator User",
        family_name="Creator Family",
        family_invitation_code=code_str,
    )
    tokens = register(db, req, client_ip="127.0.0.1")
    headers = {"Authorization": f"Bearer {tokens.access_token}"}

    response = client.get("/api/v1/family", headers=headers)
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["creator_code"] == code_str

