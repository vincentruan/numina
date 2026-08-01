"""A1b /ai/context endpoint: per-source summary + family-scope 404 (Plan B T6)."""
import pytest

# ---------------------------------------------------------------------------
# Local fixtures (the shared conftest has no liability/wish fixtures).
# ---------------------------------------------------------------------------

def _register(client, username: str, family_name: str, code: str) -> dict:
    resp = client.post(
        "/api/v1/auth/register",
        json={
            "username": username,
            "display_name": username,
            "password": "TestPass123",
            "family_name": family_name,
            "family_invitation_code": code,
        },
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    return {"Authorization": f"Bearer {data['access_token']}"}


def _create_liability(client, headers: dict, **kwargs) -> dict:
    payload = {
        "name": "测试负债",
        "category": "mortgage",
        "original_amount": 100000,
        "remaining_amount": 80000,
        "monthly_payment": 5000,
        "interest_rate": 4.5,
        **kwargs,
    }
    resp = client.post("/api/v1/liabilities", headers=headers, json=payload)
    assert resp.status_code == 201, resp.text
    return resp.json()["data"]


def _create_wish(client, headers: dict, **kwargs) -> dict:
    payload = {
        "name": "测试心愿",
        "expected_price": 10000,
        "priority": "high",
        **kwargs,
    }
    resp = client.post("/api/v1/wishes", headers=headers, json=payload)
    assert resp.status_code == 201, resp.text
    return resp.json()["data"]


@pytest.fixture
def auth_headers(client):
    return _register(client, "aictx_user", "AiCtx Family", "AUT01")


@pytest.fixture
def owned_liability_id(client, auth_headers):
    return _create_liability(client, auth_headers)["id"]


@pytest.fixture
def owned_wish_id(client, auth_headers):
    return _create_wish(client, auth_headers)["id"]


@pytest.fixture
def other_family_liability_id(client, db):
    """A liability owned by a different family — must 404 for the caller."""
    from apps.backend.app.models.family import Family
    from apps.backend.app.models.liability import Liability
    from apps.backend.app.models.user import User
    from apps.backend.app.utils.snowflake import next_id

    family = Family(id=next_id(), name="Other Liab Family", created_by=next_id())
    db.add(family)
    db.commit()
    db.refresh(family)
    user = User(
        id=next_id(),
        username="other_liab_user",
        display_name="Other",
        password_hash="x",
        family_id=family.id,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    liability = Liability(
        id=next_id(),
        user_id=user.id,
        family_id=family.id,
        category="mortgage",
        name="他人负债",
        original_amount=50000,
        remaining_amount=40000,
        monthly_payment=2000,
    )
    db.add(liability)
    db.commit()
    db.refresh(liability)
    return str(liability.id)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_liability_detail_returns_summary(client, auth_headers, owned_liability_id):
    resp = client.get(
        f"/api/v1/ai/context?source=liability_detail&id={owned_liability_id}",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    body = resp.json()["data"]
    assert body["source"] == "liability_detail"
    assert "summary" in body and isinstance(body["summary"], str)
    # Structured JSON format: parse and verify fields.
    import json
    data = json.loads(body["summary"])
    assert data["type"] == "liability_detail"
    assert data["category"] == "房贷"
    assert "remaining_amount" in data
    assert "monthly_payment" in data
    assert "currency" in data
    assert data["currency"] == "CNY"


def test_wish_detail_returns_summary(client, auth_headers, owned_wish_id):
    resp = client.get(
        f"/api/v1/ai/context?source=wish_detail&id={owned_wish_id}",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["source"] == "wish_detail"


def test_liability_strategy_returns_all_active_summary(client, auth_headers):
    resp = client.get(
        "/api/v1/ai/context?source=liability_strategy&id=0", headers=auth_headers
    )
    assert resp.status_code == 200
    assert "summary" in resp.json()["data"]


def test_wish_advice_returns_all_pending_summary(client, auth_headers):
    resp = client.get(
        "/api/v1/ai/context?source=wish_advice&id=0", headers=auth_headers
    )
    assert resp.status_code == 200


def test_other_family_entity_returns_404(client, auth_headers, other_family_liability_id):
    resp = client.get(
        f"/api/v1/ai/context?source=liability_detail&id={other_family_liability_id}",
        headers=auth_headers,
    )
    assert resp.status_code == 404


def test_unknown_source_returns_422(client, auth_headers):
    resp = client.get("/api/v1/ai/context?source=bogus&id=1", headers=auth_headers)
    # VALIDATION_ERROR → 422 (repo convention: AppError, not bare HTTPException).
    assert resp.status_code == 422
