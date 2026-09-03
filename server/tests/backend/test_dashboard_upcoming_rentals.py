"""Tests for GET /api/v1/dashboard/upcoming-rentals."""

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


def _create_rental(client, headers: dict, **kwargs) -> dict:
    """POST /api/v1/rental-contracts and return the created object."""
    payload = {
        "role": "tenant",
        "monthly_rent": 3000,
        "deposit": 6000,
        "start_date": "2026-01-01",
        **kwargs,
    }
    resp = client.post("/api/v1/rental-contracts", headers=headers, json=payload)
    assert resp.status_code == 201, resp.text
    return dict(resp.json()["data"])


def _upcoming_rentals(client, headers: dict, days: int = 30) -> dict:
    resp = client.get(f"/api/v1/dashboard/upcoming-rentals?days={days}", headers=headers)
    assert resp.status_code == 200, resp.text
    return dict(resp.json()["data"])


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def headers(client):
    return _register_and_login(client, "rental_user", "Rental Family", "AUT01")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_empty_when_no_contracts(client, headers):
    """Returns empty list when the family has no rental contracts."""
    data = _upcoming_rentals(client, headers)
    assert data["items"] == []
    assert data["total_amount"] == 0.0


def test_tenant_contract_expiring_within_window(client, headers):
    """A tenant contract with end_date within 30 days appears as a renewal reminder."""
    today = date.today()
    end = today + timedelta(days=15)
    _create_rental(
        client, headers,
        role="tenant",
        monthly_rent=3000,
        start_date=(today - timedelta(days=60)).isoformat(),
        end_date=end.isoformat(),
        counterparty="房东张三",
    )

    data = _upcoming_rentals(client, headers)
    assert len(data["items"]) == 1
    item = data["items"][0]
    assert "续租" in item["name"]
    assert item["role"] == "tenant"
    assert item["due_date"] == end.isoformat()
    assert item["counterparty"] == "房东张三"


def test_tenant_contract_outside_window_excluded(client, headers):
    """A tenant contract with end_date beyond the window is excluded."""
    today = date.today()
    end = today + timedelta(days=60)
    _create_rental(
        client, headers,
        role="tenant",
        monthly_rent=3000,
        start_date=(today - timedelta(days=60)).isoformat(),
        end_date=end.isoformat(),
    )

    data = _upcoming_rentals(client, headers, days=30)
    assert data["items"] == []


def test_tenant_contract_expired_excluded(client, headers):
    """A tenant contract whose end_date has already passed is excluded."""
    today = date.today()
    past_end = today - timedelta(days=5)
    _create_rental(
        client, headers,
        role="tenant",
        monthly_rent=3000,
        start_date=(today - timedelta(days=120)).isoformat(),
        end_date=past_end.isoformat(),
    )

    data = _upcoming_rentals(client, headers)
    assert data["items"] == []


def test_tenant_open_ended_no_reminder(client, headers):
    """An open-ended tenant contract (end_date null) produces no renewal reminder."""
    _create_rental(
        client, headers,
        role="tenant",
        monthly_rent=3000,
        start_date=(date.today() - timedelta(days=60)).isoformat(),
        # end_date omitted → null
    )

    data = _upcoming_rentals(client, headers)
    assert data["items"] == []


def test_landlord_contract_within_window(client, headers):
    """A landlord contract with next rent day within window appears as collection reminder."""
    today = date.today()
    # Set start_date so the day-of-month falls within the next 30 days
    start = date(today.year - 1, today.month, min(today.day + 5, 28))
    _create_rental(
        client, headers,
        role="landlord",
        monthly_rent=5000,
        start_date=start.isoformat(),
        counterparty="租客李四",
    )

    data = _upcoming_rentals(client, headers, days=30)
    landlord_items = [i for i in data["items"] if i["role"] == "landlord"]
    assert len(landlord_items) >= 1
    item = landlord_items[0]
    assert "收租" in item["name"]
    assert item["counterparty"] == "租客李四"


def test_inactive_contract_excluded(client, headers, db):
    """Inactive rental contracts (is_active=False) are excluded."""
    from apps.backend.app.models.rental_contract import RentalContract
    from apps.backend.app.models.user import User
    from apps.backend.app.utils.snowflake import next_id

    today = date.today()

    me_resp = client.get("/api/v1/auth/me", headers=headers)
    user = db.query(User).filter(User.id == int(me_resp.json()["data"]["id"])).first()

    contract = RentalContract(
        id=next_id(),
        user_id=user.id,
        family_id=user.family_id,
        role="tenant",
        monthly_rent=3000,
        deposit=6000,
        start_date=today - timedelta(days=60),
        end_date=today + timedelta(days=10),
        currency="CNY",
        is_active=False,
    )
    db.add(contract)
    db.commit()

    data = _upcoming_rentals(client, headers)
    assert data["items"] == []


def test_cross_family_isolation(client, headers, db):
    """Rental contracts from another family must not appear."""
    from apps.backend.app.models.family import Family
    from apps.backend.app.models.rental_contract import RentalContract
    from apps.backend.app.models.user import User
    from apps.backend.app.utils.snowflake import next_id

    today = date.today()

    other_family = Family(id=next_id(), name="隔离租约家庭", created_by=next_id())
    db.add(other_family)
    db.flush()

    other_user = User(
        id=next_id(),
        username="isolated_rental_user",
        display_name="Isolated Rental User",
        password_hash="test_hash",
        family_id=other_family.id,
    )
    db.add(other_user)
    db.flush()

    contract = RentalContract(
        id=next_id(),
        user_id=other_user.id,
        family_id=other_family.id,
        role="tenant",
        monthly_rent=3000,
        deposit=6000,
        start_date=today - timedelta(days=60),
        end_date=today + timedelta(days=10),
        currency="CNY",
        is_active=True,
    )
    db.add(contract)
    db.commit()

    data = _upcoming_rentals(client, headers)
    assert data["items"] == []


def test_days_zero_includes_due_today(client, headers):
    """A contract due today is included when days=0."""
    today = date.today()
    _create_rental(
        client, headers,
        role="tenant",
        monthly_rent=3000,
        start_date=(today - timedelta(days=60)).isoformat(),
        end_date=today.isoformat(),
    )

    data = _upcoming_rentals(client, headers, days=0)
    assert len(data["items"]) == 1
    assert data["items"][0]["due_date"] == today.isoformat()


def test_multiple_contracts_returned_individually(client, headers):
    """Multiple contracts within the window are all returned individually."""
    today = date.today()

    _create_rental(
        client, headers,
        role="tenant",
        monthly_rent=3000,
        start_date=(today - timedelta(days=120)).isoformat(),
        end_date=(today + timedelta(days=10)).isoformat(),
        counterparty="房东A",
    )
    _create_rental(
        client, headers,
        role="tenant",
        monthly_rent=4000,
        start_date=(today - timedelta(days=90)).isoformat(),
        end_date=(today + timedelta(days=20)).isoformat(),
        counterparty="房东B",
    )

    data = _upcoming_rentals(client, headers)
    assert len(data["items"]) == 2
    names = {i["name"] for i in data["items"]}
    assert any("房东A" in n for n in names)
    assert any("房东B" in n for n in names)
    assert data["total_amount"] == 7000.0


def test_days_over_365_returns_422(client, headers):
    """days=366 violates the Query le=365 constraint and returns 422."""
    resp = client.get(
        "/api/v1/dashboard/upcoming-rentals?days=366",
        headers=headers,
    )
    assert resp.status_code == 422
