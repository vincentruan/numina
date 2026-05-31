"""Tests for GET /family/children/{child_id}/earning-rate."""

from datetime import UTC, datetime, timedelta
from math import ceil

import pytest

from apps.backend.app.models.coin_transaction import CoinTransaction
from apps.backend.app.utils.snowflake import next_id

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _data(resp):
    body = resp.json()
    return body.get("data", body)


def _create_child(client, auth_headers, username="earner1"):
    from apps.backend.app.constants.pin import ALLOWED_EMOJIS

    pin = list(ALLOWED_EMOJIS)[:4]
    resp = client.post("/api/v1/family/children", headers=auth_headers, json={
        "username": username,
        "display_name": "小明",
        "password": "ChildPass1",
        "avatar_color": "#FF5733",
        "pin": pin,
    })
    assert resp.status_code == 201
    child = _data(resp)
    return child["id"]


def _insert_tx(db, child_id, family_id, amount, tx_type, days_ago=0):
    """Insert a CoinTransaction with created_at offset by days_ago from today."""
    created = datetime.now(UTC).replace(tzinfo=None) - timedelta(days=days_ago)
    tx = CoinTransaction(
        id=next_id(),
        family_id=family_id,
        child_user_id=child_id,
        amount=amount,
        transaction_type=tx_type,
        created_at=created,
    )
    db.add(tx)
    db.flush()
    return tx


def _get_family_id(client, auth_headers):
    resp = client.get("/api/v1/family", headers=auth_headers)
    assert resp.status_code == 200
    return _data(resp)["id"]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def child_id(client, auth_headers):
    return _create_child(client, auth_headers)


@pytest.fixture
def family_id(client, auth_headers):
    return _get_family_id(client, auth_headers)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_no_transactions_returns_zero(client, auth_headers, child_id):
    """No earning transactions → data_days=0, all suggestions=0."""
    resp = client.get(f"/api/v1/family/children/{child_id}/earning-rate", headers=auth_headers)
    assert resp.status_code == 200
    data = _data(resp)
    assert data["data_days"] == 0
    assert data["daily_avg"] == 0.0
    assert data["suggested_7d"] == 0
    assert data["suggested_14d"] == 0
    assert data["suggested_30d"] == 0


def test_fewer_than_3_days_returns_zero_suggestions(client, auth_headers, child_id, family_id, db):
    """2 distinct earning days → data_days=2, suggestions=0 (insufficient data)."""
    _insert_tx(db, child_id, family_id, 10, "chore_earn", days_ago=1)
    _insert_tx(db, child_id, family_id, 20, "parent_grant", days_ago=2)

    resp = client.get(f"/api/v1/family/children/{child_id}/earning-rate", headers=auth_headers)
    assert resp.status_code == 200
    data = _data(resp)
    assert data["data_days"] == 2
    assert data["daily_avg"] == 0.0
    assert data["suggested_7d"] == 0
    assert data["suggested_14d"] == 0
    assert data["suggested_30d"] == 0


def test_correct_earning_rate_with_3_days(client, auth_headers, child_id, family_id, db):
    """3 distinct days, 30 coins total → daily_avg=30/7 (fixed 7-day window divisor)."""
    _insert_tx(db, child_id, family_id, 10, "chore_earn", days_ago=1)
    _insert_tx(db, child_id, family_id, 10, "chore_earn", days_ago=2)
    _insert_tx(db, child_id, family_id, 10, "parent_grant", days_ago=3)

    resp = client.get(f"/api/v1/family/children/{child_id}/earning-rate", headers=auth_headers)
    assert resp.status_code == 200
    data = _data(resp)
    expected_avg = 30 / 7.0
    assert data["data_days"] == 3
    assert data["daily_avg"] == pytest.approx(expected_avg)
    assert data["suggested_7d"] == ceil(expected_avg * 7)   # 30
    assert data["suggested_14d"] == ceil(expected_avg * 14)  # 60
    assert data["suggested_30d"] == ceil(expected_avg * 30)  # 129


def test_uses_fixed_7day_window_as_divisor(client, auth_headers, child_id, family_id, db):
    """5 distinct days, 50 coins → daily_avg = 50/7 (fixed 7-day window, not distinct days)."""
    for d in range(1, 6):
        _insert_tx(db, child_id, family_id, 10, "chore_earn", days_ago=d)

    resp = client.get(f"/api/v1/family/children/{child_id}/earning-rate", headers=auth_headers)
    assert resp.status_code == 200
    data = _data(resp)
    assert data["data_days"] == 5
    # daily_avg = 50 / 7 (fixed window divisor)
    assert data["daily_avg"] == pytest.approx(50 / 7.0)


def test_caps_suggestions_at_9999(client, auth_headers, child_id, family_id, db):
    """Very high earning rate → suggestions capped at 9999."""
    # 3 days, 10000 coins each → daily_avg = 10000, 30d suggestion would be 300000
    for d in range(1, 4):
        _insert_tx(db, child_id, family_id, 10000, "chore_earn", days_ago=d)

    resp = client.get(f"/api/v1/family/children/{child_id}/earning-rate", headers=auth_headers)
    assert resp.status_code == 200
    data = _data(resp)
    assert data["suggested_7d"] == 9999
    assert data["suggested_14d"] == 9999
    assert data["suggested_30d"] == 9999


def test_ignores_spend_transactions(client, auth_headers, child_id, family_id, db):
    """wish_spend and negative amounts are excluded from earning rate."""
    # 3 earning days
    for d in range(1, 4):
        _insert_tx(db, child_id, family_id, 10, "chore_earn", days_ago=d)
    # spend transactions should not count
    _insert_tx(db, child_id, family_id, -50, "wish_spend", days_ago=1)
    _insert_tx(db, child_id, family_id, -20, "gift_sent", days_ago=2)

    resp = client.get(f"/api/v1/family/children/{child_id}/earning-rate", headers=auth_headers)
    assert resp.status_code == 200
    data = _data(resp)
    # Only 30 coins from 3 earning days, divided by fixed 7-day window
    assert data["daily_avg"] == pytest.approx(30 / 7.0)
    assert data["data_days"] == 3


def test_ignores_transactions_older_than_7_days(client, auth_headers, child_id, family_id, db):
    """Transactions older than 7 days are excluded."""
    # 3 days within window
    for d in range(1, 4):
        _insert_tx(db, child_id, family_id, 10, "chore_earn", days_ago=d)
    # Old transactions outside window
    _insert_tx(db, child_id, family_id, 1000, "chore_earn", days_ago=8)
    _insert_tx(db, child_id, family_id, 1000, "parent_grant", days_ago=10)

    resp = client.get(f"/api/v1/family/children/{child_id}/earning-rate", headers=auth_headers)
    assert resp.status_code == 200
    data = _data(resp)
    assert data["data_days"] == 3
    assert data["daily_avg"] == pytest.approx(30 / 7.0)


def test_minimum_suggestion_is_1(client, auth_headers, child_id, family_id, db):
    """Very small daily_avg still produces suggested_7d = 1 (ceil floor)."""
    # 3 days, 0.01 coin each → daily_avg = 0.03/7 ≈ 0.00429, ceil(0.00429 * 7) = 1
    for d in range(1, 4):
        _insert_tx(db, child_id, family_id, 0.01, "chore_earn", days_ago=d)

    resp = client.get(f"/api/v1/family/children/{child_id}/earning-rate", headers=auth_headers)
    assert resp.status_code == 200
    data = _data(resp)
    assert data["suggested_7d"] == 1
    assert data["suggested_14d"] >= 1
    assert data["suggested_30d"] >= 1


def test_child_not_in_family_returns_403(client, auth_headers, second_user_headers, db):
    """Requesting earning rate for a child in another family returns 404."""
    # Create a child in the second family
    from apps.backend.app.constants.pin import ALLOWED_EMOJIS
    pin = list(ALLOWED_EMOJIS)[:4]
    resp = client.post("/api/v1/family/children", headers=second_user_headers, json={
        "username": "otherchild99",
        "display_name": "外家孩子",
        "password": "ChildPass1",
        "avatar_color": "#AABBCC",
        "pin": pin,
    })
    assert resp.status_code == 201
    other_child_id = _data(resp)["id"]

    # First user tries to query the other family's child
    resp = client.get(
        f"/api/v1/family/children/{other_child_id}/earning-rate",
        headers=auth_headers,
    )
    assert resp.status_code == 404
