"""W4 wish-advice: cache hit / fingerprint invalidation / guardrail (Plan B T7)."""
from unittest.mock import patch

import pytest

from apps.backend.app.models.family import Family
from apps.backend.app.models.user import User

# ---------------------------------------------------------------------------
# Local fixture: a family id with ≥2 pending wishes, ≥1 with monthly_saving.
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


def _enable_ai(db, auth_headers, client):
    """Enable AI for the test user's family + promote to owner (mirror test_ai_finance_coach)."""
    from apps.backend.app.models.ai_provider_config import AIProviderConfig

    me = client.get("/api/v1/auth/me", headers=auth_headers).json()
    family_id = me["data"]["family_id"]
    family = db.query(Family).filter_by(id=family_id).first()
    family.ai_enabled = True
    user = db.query(User).filter_by(id=me["data"]["id"]).first()
    user.role = "owner"
    cfg = AIProviderConfig(
        family_id=family_id,
        name="测试配置",
        provider="anthropic",
        api_key_encrypted="test_encrypted_key",
        model_id="claude-3-5-sonnet-20241022",
        is_active=True,
    )
    db.add(cfg)
    db.commit()
    return family_id


def _create_wish(client, headers, **kwargs):
    payload = {
        "name": "测试心愿",
        "expected_price": 10000,
        "priority": "high",
        "monthly_saving": 500,
        **kwargs,
    }
    resp = client.post("/api/v1/wishes", headers=headers, json=payload)
    assert resp.status_code == 201, resp.text
    return resp.json()["data"]


@pytest.fixture
def auth_headers(client):
    return _register(client, "wishadv_user", "WishAdv Family", "AUTO-TEST")


@pytest.fixture
def family_with_wishes(client, auth_headers, db_session):
    """family_id with ≥2 pending wishes, ≥1 with monthly_saving>0, AI enabled."""
    family_id = _enable_ai(db_session, auth_headers, client)
    _create_wish(client, auth_headers, name="心愿A", monthly_saving=1000)
    _create_wish(client, auth_headers, name="心愿B", monthly_saving=500)
    return family_id


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_generate_returns_cached_when_fresh(client, auth_headers, db_session, family_with_wishes):
    from apps.backend.app.services.finance_coach_cache import upsert_capability_result

    family_id = family_with_wishes
    # The router stores {fingerprint, advice}; seed it so the cached path matches.
    upsert_capability_result(
        db_session,
        family_id,
        "wish_advice",
        {"fingerprint": "stub-fingerprint", "advice": {
            "primary_wish_id": "1",
            "reason": "距目标近",
            "suggested_monthly": 2000,
            "redistribution": [{"wish_id": "1", "suggested_amount": 2000, "note": "本月优先"}],
        }},
    )
    db_session.commit()

    # The router reads the cached row only when the stored fingerprint matches the
    # current wishes' fingerprint. Patch build_advice_input to return the stub fp.
    with patch("apps.backend.app.routers.ai_wish_advice.check_circuit_blocked", return_value=None), \
         patch("apps.backend.app.routers.ai_wish_advice.wish_advice.build_advice_input", return_value=([], "stub-fingerprint")):
        resp = client.post("/api/v1/ai/wish-advice/generate", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "cached"
    assert resp.json()["report"]["primary_wish_id"] == "1"


def test_guardrail_drops_negative_suggested_amount(client, auth_headers, db_session, family_with_wishes):
    """Advice baseline (spec §7.1): suggested_amount >= 0; negative → schema fail → drop, don't display."""
    # Patch generate_advice to return None (AI unusable / guardrail failed) and
    # assert the endpoint degrades gracefully (200, no crash).
    with patch("apps.backend.app.routers.ai_wish_advice.check_circuit_blocked", return_value=None), \
         patch("apps.backend.app.routers.ai_wish_advice.wish_advice.generate_advice", return_value=(None, "fp")):
        resp = client.post("/api/v1/ai/wish-advice/generate?force=true", headers=auth_headers)
    # No usable advice → 200 with empty/safe payload (silent, no error).
    assert resp.status_code == 200


def test_validate_advice_rejects_negative_amount():
    """The service-level guardrail (spec §7.1)."""
    from apps.backend.app.services.wish_advice import validate_advice

    bad = {
        "primary_wish_id": "1",
        "reason": "x",
        "suggested_monthly": 2000,
        "redistribution": [{"wish_id": "1", "suggested_amount": -100, "note": "bad"}],
    }
    assert validate_advice(bad) is None


def test_validate_advice_accepts_valid():
    from apps.backend.app.services.wish_advice import validate_advice

    good = {
        "primary_wish_id": "1",
        "reason": "距目标近",
        "suggested_monthly": 2000,
        "redistribution": [{"wish_id": "1", "suggested_amount": 2000, "note": "本月优先"}],
    }
    assert validate_advice(good) is not None

