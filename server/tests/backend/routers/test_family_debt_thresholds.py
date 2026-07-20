"""W5 debt-threshold config: owner-only PUT + default values (Plan B T8)."""


def _get_debt_thresholds(client, headers):
    return client.get("/api/v1/family/debt-thresholds", headers=headers)


def test_get_debt_thresholds_default(client, auth_headers):
    resp = _get_debt_thresholds(client, auth_headers)
    assert resp.status_code == 200
    th = resp.json()["data"]["thresholds"]
    assert th["credit_card"] == 12
    assert th["personal_loan"] == 10
    assert th["mortgage"] == 6
    assert th["other"] == 10


def test_put_debt_thresholds_owner_only(client, auth_headers):
    # Owner PUT succeeds.
    resp = client.put(
        "/api/v1/family/debt-thresholds",
        json={"thresholds": {"credit_card": 15, "personal_loan": 10, "mortgage": 6, "other": 10}},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["thresholds"]["credit_card"] == 15

    # Non-owner adult is FORBIDDEN (spec §5.1 security-lens). Join the same
    # family as a member (non-owner) to get an adult token.
    invite_code = client.get("/api/v1/family", headers=auth_headers).json()["data"]["invite_code"]
    join_resp = client.post(
        "/api/v1/auth/family/join",
        json={
            "username": "member_debt",
            "display_name": "Member Debt",
            "password": "MemberPass123",
            "invite_code": invite_code,
        },
    )
    assert join_resp.status_code == 200
    member_token = join_resp.json()["data"]["access_token"]
    member_headers = {"Authorization": f"Bearer {member_token}"}

    resp2 = client.put(
        "/api/v1/family/debt-thresholds",
        json={"thresholds": {"credit_card": 20}},
        headers=member_headers,
    )
    assert resp2.status_code == 403


def test_get_visible_to_all_family_members(client, auth_headers):
    """Read is visible to all family members (not just owner)."""
    # Owner reads first (default).
    resp = _get_debt_thresholds(client, auth_headers)
    assert resp.status_code == 200

    # A member of the same family can also read.
    invite_code = client.get("/api/v1/family", headers=auth_headers).json()["data"]["invite_code"]
    join_resp = client.post(
        "/api/v1/auth/family/join",
        json={
            "username": "member_read",
            "display_name": "Member Read",
            "password": "MemberPass123",
            "invite_code": invite_code,
        },
    )
    assert join_resp.status_code == 200
    member_token = join_resp.json()["data"]["access_token"]
    member_headers = {"Authorization": f"Bearer {member_token}"}

    resp2 = _get_debt_thresholds(client, member_headers)
    assert resp2.status_code == 200
    assert resp2.json()["data"]["thresholds"]["credit_card"] == 12


def test_put_merges_with_defaults(client, auth_headers):
    """A partial PUT merges with defaults (missing keys keep defaults)."""
    resp = client.put(
        "/api/v1/family/debt-thresholds",
        json={"thresholds": {"credit_card": 18}},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    th = resp.json()["data"]["thresholds"]
    assert th["credit_card"] == 18
    # Unspecified keys retain defaults.
    assert th["personal_loan"] == 10
    assert th["mortgage"] == 6
    assert th["other"] == 10
