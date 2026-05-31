"""Tests for GET /api/v1/dashboard/upcoming-payments (Track A)."""

import calendar
from datetime import date, timedelta

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _register_and_login(client, username: str, family_name: str, code: str) -> dict:
    resp = client.post("/api/v1/auth/register", json={
        "username": username,
        "display_name": username,
        "password": "TestPass123",
        "family_name": family_name,
        "family_invitation_code": code,
    })
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    return {"Authorization": f"Bearer {data['access_token']}"}


def _create_liability(client, headers: dict, **kwargs) -> dict:
    """POST /api/v1/liabilities and return the created object."""
    payload = {
        "name": "测试负债",
        "category": "mortgage",
        "original_amount": 100000,
        "remaining_amount": 80000,
        "monthly_payment": 5000,
        **kwargs,
    }
    resp = client.post("/api/v1/liabilities", headers=headers, json=payload)
    assert resp.status_code == 201, resp.text
    return resp.json()["data"]


def _upcoming(client, headers: dict, days: int = 7) -> dict:
    resp = client.get(f"/api/v1/dashboard/upcoming-payments?days={days}", headers=headers)
    assert resp.status_code == 200, resp.text
    return resp.json()["data"]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def headers(client):
    return _register_and_login(client, "up_user", "Up Family", "AUTO-TEST")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_empty_when_no_liabilities(client, headers):
    """Returns empty list when the family has no liabilities."""
    data = _upcoming(client, headers)
    assert data["items"] == []
    assert data["total_amount"] == 0.0


def test_returns_liability_due_within_window(client, headers):
    """A liability whose next payment date falls within 7 days is returned."""
    today = date.today()
    # Use a start_date whose day-of-month matches today → due today
    start = date(today.year - 1, today.month, today.day)
    _create_liability(client, headers, name="房贷", start_date=start.isoformat(), monthly_payment=8000)

    data = _upcoming(client, headers)
    assert len(data["items"]) == 1
    item = data["items"][0]
    assert item["name"] == "房贷"
    assert item["due_date"] == today.isoformat()
    assert item["amount"] == 8000
    assert data["total_amount"] == 8000


def test_excludes_liability_with_null_start_date(client, headers):
    """Liabilities without a start_date are excluded."""
    _create_liability(client, headers, name="无开始日期负债", monthly_payment=3000)
    # No start_date → should not appear
    data = _upcoming(client, headers)
    assert data["items"] == []


def test_excludes_inactive_liability(client, db, headers):
    """Inactive liabilities (is_active=False) are excluded.

    LiabilityCreate does not expose is_active, so we insert directly into the
    DB and then flip is_active=False to simulate a fully-repaid liability.
    """
    from apps.backend.app.models.liability import Liability
    from apps.backend.app.models.user import User
    from apps.backend.app.utils.snowflake import next_id

    today = date.today()
    start = date(today.year - 1, today.month, today.day)

    # Resolve the authenticated user's family_id from the DB
    me_resp = client.get("/api/v1/auth/me", headers=headers)
    assert me_resp.status_code == 200
    me = me_resp.json()["data"]
    user = db.query(User).filter(User.id == int(me["id"])).first()

    liability = Liability(
        id=next_id(),
        user_id=user.id,
        family_id=user.family_id,
        category="mortgage",
        name="已结清负债",
        original_amount=100000,
        remaining_amount=0,
        monthly_payment=2000,
        start_date=start,
        is_active=False,
    )
    db.add(liability)
    db.commit()

    data = _upcoming(client, headers)
    assert data["items"] == []


def test_excludes_liability_past_end_date(client, headers):
    """Liabilities whose end_date is in the past are excluded."""
    today = date.today()
    start = date(today.year - 2, today.month, today.day)
    past_end = (today - timedelta(days=1)).isoformat()
    _create_liability(
        client, headers,
        name="已到期负债",
        start_date=start.isoformat(),
        end_date=past_end,
        monthly_payment=4000,
    )
    data = _upcoming(client, headers)
    assert data["items"] == []


def test_excludes_liability_outside_window(client, headers):
    """A liability due more than 7 days away is not returned."""
    today = date.today()
    # Pick a day that is 15 days from now (guaranteed outside 7-day window)
    future_day_date = today + timedelta(days=15)
    # Build a start_date in a prior year with the same day-of-month
    start = date(today.year - 1, future_day_date.month, future_day_date.day)
    _create_liability(
        client, headers,
        name="远期负债",
        start_date=start.isoformat(),
        monthly_payment=6000,
    )
    data = _upcoming(client, headers, days=7)
    assert data["items"] == []


def test_month_end_clamping(client, headers):
    """start_date day=31 is clamped to the last day of months with fewer days."""
    today = date.today()

    # Find a month that has fewer than 31 days and is within the next 7 days
    # Strategy: set start_date to Jan 31 of a prior year.
    # In February the clamp fires (28/29 days).
    # We need the clamped date to fall within the test window, so we pick
    # a start_date whose day (31) would be clamped to today or within 7 days.
    #
    # Simplest approach: use a start_date with day=31 and pick a month where
    # the clamped value equals today (if today is the last day of a short month)
    # OR just verify the logic directly via the service helper.
    #
    # For an integration test we pick a concrete scenario:
    # If today is in a month with 31 days, the next occurrence of day 31 is
    # this month's 31st. We create the liability and verify the due_date is
    # the 31st (no clamping needed this month).
    # If today is in a month with <31 days, the clamped date is the last day
    # of this month.

    last_day_this_month = calendar.monthrange(today.year, today.month)[1]
    # Use a start_date from a prior year with day=31
    # Pick a year/month that had 31 days for the start_date
    start = date(today.year - 1, 1, 31)  # January always has 31 days

    _create_liability(
        client, headers,
        name="月末负债",
        start_date=start.isoformat(),
        monthly_payment=9000,
    )

    # The next payment date for day=31 from today:
    # - If this month has 31 days and today <= 31st → due this month on 31st
    # - If this month has <31 days → clamped to last_day_this_month
    expected_day = min(31, last_day_this_month)
    expected_due = date(today.year, today.month, expected_day)
    if expected_due < today:
        # Already passed this month → next month
        if today.month == 12:
            next_month_last = calendar.monthrange(today.year + 1, 1)[1]
            expected_due = date(today.year + 1, 1, min(31, next_month_last))
        else:
            next_month_last = calendar.monthrange(today.year, today.month + 1)[1]
            expected_due = date(today.year, today.month + 1, min(31, next_month_last))

    days_until = (expected_due - today).days
    data = _upcoming(client, headers, days=days_until + 1)

    matching = [i for i in data["items"] if i["name"] == "月末负债"]
    assert len(matching) == 1, f"Expected 1 matching item, got {len(matching)}; items={data['items']}"
    assert matching[0]["due_date"] == expected_due.isoformat()


def test_multiple_liabilities_returned_individually(client, headers):
    """Multiple liabilities due within the window are all returned individually."""
    today = date.today()
    start = date(today.year - 1, today.month, today.day)

    _create_liability(client, headers, name="负债A", start_date=start.isoformat(), monthly_payment=1000)
    _create_liability(client, headers, name="负债B", start_date=start.isoformat(), monthly_payment=2000)

    data = _upcoming(client, headers)
    names = {i["name"] for i in data["items"]}
    assert "负债A" in names
    assert "负债B" in names
    assert data["total_amount"] == 3000


def test_today_counts_as_within_zero_days(client, headers):
    """A liability due today is included even when days=0."""
    today = date.today()
    start = date(today.year - 1, today.month, today.day)
    _create_liability(client, headers, name="今日到期", start_date=start.isoformat(), monthly_payment=500)

    data = _upcoming(client, headers, days=0)
    assert len(data["items"]) == 1
    assert data["items"][0]["due_date"] == today.isoformat()


def test_days_negative_returns_422(client, headers):
    """days=-1 violates the Query ge=0 constraint and returns 422."""
    resp = client.get(
        "/api/v1/dashboard/upcoming-payments?days=-1",
        headers=headers,
    )
    assert resp.status_code == 422


def test_days_over_365_returns_422(client, headers):
    """days=366 violates the Query le=365 constraint and returns 422."""
    resp = client.get(
        "/api/v1/dashboard/upcoming-payments?days=366",
        headers=headers,
    )
    assert resp.status_code == 422


def test_upcoming_payments_cross_family_isolation(client, headers, db):
    """A liability belonging to a different family must not appear."""
    from apps.backend.app.models.family import Family
    from apps.backend.app.models.liability import Liability
    from apps.backend.app.models.user import User
    from apps.backend.app.utils.snowflake import next_id

    today = date.today()
    start = date(today.year - 1, today.month, today.day)

    # Create another family + user
    other_family = Family(id=next_id(), name="隔离家庭", created_by=next_id())
    db.add(other_family)
    db.flush()

    other_user = User(
        id=next_id(),
        username="isolated_user",
        display_name="Isolated User",
        password_hash="test_hash",
        family_id=other_family.id,
    )
    db.add(other_user)
    db.flush()

    # Insert a liability directly into the other family
    liability = Liability(
        id=next_id(),
        user_id=other_user.id,
        family_id=other_family.id,
        category="mortgage",
        name="他家庭负债",
        original_amount=500000,
        remaining_amount=400000,
        monthly_payment=10000,
        start_date=start,
        is_active=True,
    )
    db.add(liability)
    db.commit()

    # The authenticated user's family should see zero upcoming payments
    data = _upcoming(client, headers)
    assert data["items"] == []
