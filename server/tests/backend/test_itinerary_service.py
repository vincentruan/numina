"""Tests for itinerary service and API routes (U2)."""

from datetime import date, time
from decimal import Decimal

import pytest

from apps.backend.app.schemas.itinerary_item import (
    ItineraryItemCreate,
    ItineraryItemUpdate,
)
from apps.backend.app.services import itinerary as itinerary_service
from packages.db.models.expense_entry import ExpenseEntry
from packages.db.models.itinerary_item import ItineraryItem
from packages.db.models.trip import Trip

# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def trip(db, test_family, test_user):
    """Create a test trip."""
    t = Trip(
        family_id=test_family.id,
        user_id=test_user.id,
        name="Tokyo Trip",
        destination="Tokyo",
        departure_date=date(2026, 10, 1),
        return_date=date(2026, 10, 3),
        currency="CNY",
    )
    db.add(t)
    db.commit()
    db.refresh(t)
    return t


@pytest.fixture
def auth_headers(client):
    """Reuse the conftest auth_headers fixture."""
    return client.post("/api/v1/auth/register", json={
        "username": "itin_user",
        "display_name": "Itin User",
        "password": "TestPass123",
        "family_name": "Itin Family",
        "family_invitation_code": "AUT03"
    }).json()["data"]


@pytest.fixture
def authed_client(client, auth_headers):
    """Client with auth headers injected."""
    return client


@pytest.fixture
def trip_via_api(authed_client):
    """Create a trip via API and return its data."""
    resp = authed_client.post("/api/v1/trips", json={
        "name": "API Trip",
        "destination": "Tokyo",
        "departure_date": "2026-10-01",
        "return_date": "2026-10-03",
        "currency": "CNY",
    })
    assert resp.status_code == 201, resp.text
    return resp.json().get("data", resp.json())


# ─────────────────────────────────────────────────────────────────────────────
# Service tests (U2)
# ─────────────────────────────────────────────────────────────────────────────

class TestItineraryServiceCreate:
    """AE1: Create items of each core type, verify response shape."""

    def test_create_accommodation(self, db, trip, test_user):
        data = ItineraryItemCreate(
            date=date(2026, 10, 1),
            type="accommodation",
            start_time=time(14, 0),
            cost_amount=Decimal("500.00"),
            cost_currency="CNY",
            type_metadata={"check_in_time": "14:00"},
        )
        item = itinerary_service.create_item(db, trip, test_user.id, data)

        assert item.type == "accommodation"
        assert item.cost_amount == Decimal("500.00")
        assert item.start_time == time(14, 0)
        assert item.type_metadata["check_in_time"] == "14:00"

    def test_create_dining_with_diners(self, db, trip, test_user):
        data = ItineraryItemCreate(
            date=date(2026, 10, 1),
            type="dining",
            start_time=time(18, 30),
            cost_amount=Decimal("280.00"),
            cost_currency="CNY",
            type_metadata={"diners": 4},
        )
        item = itinerary_service.create_item(db, trip, test_user.id, data)

        assert item.type == "dining"
        assert item.type_metadata["diners"] == 4

    def test_create_activity_no_cost(self, db, trip, test_user):
        """R14: Items without costs are fully valid."""
        data = ItineraryItemCreate(
            date=date(2026, 10, 2),
            type="activity",
            description="Visit Senso-ji Temple",
        )
        item = itinerary_service.create_item(db, trip, test_user.id, data)

        assert item.type == "activity"
        assert item.cost_amount is None

    def test_create_transport(self, db, trip, test_user):
        data = ItineraryItemCreate(
            date=date(2026, 10, 3),
            type="transport",
            cost_amount=Decimal("120.00"),
            cost_currency="CNY",
            type_metadata={"origin": "Hotel", "destination": "Airport"},
        )
        item = itinerary_service.create_item(db, trip, test_user.id, data)
        assert item.type_metadata["destination"] == "Airport"


class TestExpenseLedgerIntegration:
    """R11-R12: Expense ledger auto-sync."""

    def test_create_item_with_cost_creates_expense_entries(self, db, trip, test_user):
        """R11: Item with cost → debit+credit entries created."""
        data = ItineraryItemCreate(
            date=date(2026, 10, 1),
            type="dining",
            cost_amount=Decimal("200.00"),
            cost_currency="CNY",
        )
        item = itinerary_service.create_item(db, trip, test_user.id, data)

        entries = (
            db.query(ExpenseEntry)
            .filter(ExpenseEntry.itinerary_item_id == item.id)
            .all()
        )
        assert len(entries) == 2
        legs = {e.leg_type for e in entries}
        assert legs == {"debit", "credit"}
        assert all(e.ref_type == "trip" for e in entries)
        assert all(e.ref_id == trip.id for e in entries)

    def test_create_item_without_cost_no_entries(self, db, trip, test_user):
        """Item without cost → no expense entries."""
        data = ItineraryItemCreate(date=date(2026, 10, 2), type="activity")
        item = itinerary_service.create_item(db, trip, test_user.id, data)

        entries = (
            db.query(ExpenseEntry)
            .filter(ExpenseEntry.itinerary_item_id == item.id)
            .all()
        )
        assert len(entries) == 0

    def test_update_cost_reverses_and_recreates(self, db, trip, test_user):
        """R12: Editing cost → old expense reversed, new created."""
        data = ItineraryItemCreate(
            date=date(2026, 10, 1),
            type="dining",
            cost_amount=Decimal("200.00"),
            cost_currency="CNY",
        )
        item = itinerary_service.create_item(db, trip, test_user.id, data)

        # Update cost
        update = ItineraryItemUpdate(cost_amount=Decimal("300.00"))
        updated = itinerary_service.update_item(db, item, test_user.id, update)

        assert updated.cost_amount == Decimal("300.00")

        # Linked debit entries: original 200 + new 300 (reversal entries don't carry itinerary_item_id)
        linked_debits = (
            db.query(ExpenseEntry)
            .filter(
                ExpenseEntry.itinerary_item_id == item.id,
                ExpenseEntry.leg_type == "debit",
            )
            .all()
        )
        amounts = sorted([d.amount for d in linked_debits])
        assert amounts == [Decimal("200.00"), Decimal("300.00")]

    def test_add_cost_to_previously_cost_free_item(self, db, trip, test_user):
        """Adding cost to an item that had no cost creates a linked expense."""
        # Create item without cost
        data = ItineraryItemCreate(
            date=date(2026, 10, 2),
            type="activity",
            description="Visit Senso-ji Temple",
        )
        item = itinerary_service.create_item(db, trip, test_user.id, data)
        assert item.cost_amount is None

        # Verify no expense entries
        entries_before = (
            db.query(ExpenseEntry)
            .filter(ExpenseEntry.itinerary_item_id == item.id)
            .all()
        )
        assert len(entries_before) == 0

        # Update: add cost
        db.refresh(trip)
        spend_before = trip.actual_spend

        update = ItineraryItemUpdate(cost_amount=Decimal("150.00"), cost_currency="CNY")
        updated = itinerary_service.update_item(db, item, test_user.id, update)

        assert updated.cost_amount == Decimal("150.00")
        assert updated.cost_currency == "CNY"

        # Verify expense entries created
        entries_after = (
            db.query(ExpenseEntry)
            .filter(ExpenseEntry.itinerary_item_id == item.id)
            .all()
        )
        assert len(entries_after) == 2
        legs = {e.leg_type for e in entries_after}
        assert legs == {"debit", "credit"}

        # Verify trip.actual_spend increased
        db.refresh(trip)
        assert trip.actual_spend == spend_before + Decimal("150.00")

    def test_remove_cost_reverses_only(self, db, trip, test_user):
        """Setting cost to None → old expense reversed, cost fields nulled."""
        data = ItineraryItemCreate(
            date=date(2026, 10, 1),
            type="dining",
            cost_amount=Decimal("200.00"),
            cost_currency="CNY",
        )
        item = itinerary_service.create_item(db, trip, test_user.id, data)

        update = ItineraryItemUpdate(cost_amount=None)
        updated = itinerary_service.update_item(db, item, test_user.id, update)

        assert updated.cost_amount is None
        assert updated.cost_currency is None

    def test_trip_actual_spend_updates(self, db, trip, test_user):
        """R12: trip.actual_spend updates correctly after cost change."""
        db.refresh(trip)
        initial_spend = trip.actual_spend

        data = ItineraryItemCreate(
            date=date(2026, 10, 1),
            type="dining",
            cost_amount=Decimal("200.00"),
            cost_currency="CNY",
        )
        itinerary_service.create_item(db, trip, test_user.id, data)

        db.refresh(trip)
        assert trip.actual_spend == initial_spend + Decimal("200.00")


class TestCrossDayAndPurchaseDate:
    """Cross-day items (end_date) and purchase_date for expense date."""

    def test_create_cross_day_item(self, db, trip, test_user):
        """Create item with end_date > date, verify response includes end_date."""
        data = ItineraryItemCreate(
            date=date(2026, 10, 1),
            end_date=date(2026, 10, 4),
            type="accommodation",
            cost_amount=Decimal("1500.00"),
            cost_currency="CNY",
        )
        item = itinerary_service.create_item(db, trip, test_user.id, data)

        assert item.end_date == date(2026, 10, 4)
        assert item.date == date(2026, 10, 1)

    def test_end_date_before_date_rejected(self):
        """end_date < date → 422 validation error."""
        from pydantic import ValidationError
        with pytest.raises(ValidationError, match="end_date"):
            ItineraryItemCreate(
                date=date(2026, 10, 5),
                end_date=date(2026, 10, 3),
                type="accommodation",
            )

    def test_cross_day_with_purchase_date_expense_on_purchase(self, db, trip, test_user):
        """Cross-day item with purchase_date → expense created on purchase_date."""
        data = ItineraryItemCreate(
            date=date(2026, 10, 5),
            end_date=date(2026, 10, 8),
            type="accommodation",
            cost_amount=Decimal("1500.00"),
            cost_currency="CNY",
            purchase_date=date(2026, 9, 20),
        )
        item = itinerary_service.create_item(db, trip, test_user.id, data)

        entries = (
            db.query(ExpenseEntry)
            .filter(
                ExpenseEntry.itinerary_item_id == item.id,
                ExpenseEntry.leg_type == "debit",
            )
            .all()
        )
        assert len(entries) == 1
        assert entries[0].expense_date == date(2026, 9, 20)

    def test_cross_day_without_purchase_date_expense_on_start(self, db, trip, test_user):
        """Cross-day item without purchase_date → expense on start date (backward compat)."""
        data = ItineraryItemCreate(
            date=date(2026, 10, 1),
            end_date=date(2026, 10, 4),
            type="accommodation",
            cost_amount=Decimal("1200.00"),
            cost_currency="CNY",
        )
        item = itinerary_service.create_item(db, trip, test_user.id, data)

        entries = (
            db.query(ExpenseEntry)
            .filter(
                ExpenseEntry.itinerary_item_id == item.id,
                ExpenseEntry.leg_type == "debit",
            )
            .all()
        )
        assert len(entries) == 1
        assert entries[0].expense_date == date(2026, 10, 1)

    def test_update_purchase_date_recreates_expense(self, db, trip, test_user):
        """Update purchase_date → expense recreated with new date."""
        data = ItineraryItemCreate(
            date=date(2026, 10, 5),
            type="accommodation",
            cost_amount=Decimal("800.00"),
            cost_currency="CNY",
        )
        item = itinerary_service.create_item(db, trip, test_user.id, data)

        # Verify initial expense on start date
        entries_before = (
            db.query(ExpenseEntry)
            .filter(
                ExpenseEntry.itinerary_item_id == item.id,
                ExpenseEntry.leg_type == "debit",
            )
            .all()
        )
        assert entries_before[0].expense_date == date(2026, 10, 5)

        # Update purchase_date
        update = ItineraryItemUpdate(purchase_date=date(2026, 9, 15))
        updated = itinerary_service.update_item(db, item, test_user.id, update)
        assert updated.purchase_date == date(2026, 9, 15)

        # New expense should be on purchase_date
        entries_after = (
            db.query(ExpenseEntry)
            .filter(
                ExpenseEntry.itinerary_item_id == item.id,
                ExpenseEntry.leg_type == "debit",
            )
            .all()
        )
        amounts = sorted([e.expense_date for e in entries_after])
        assert date(2026, 9, 15) in amounts


class TestDeleteModes:
    """AE3: Delete with cascade/unlink."""

    def _create_item_with_cost(self, db, trip, test_user):
        data = ItineraryItemCreate(
            date=date(2026, 10, 1),
            type="dining",
            cost_amount=Decimal("120.00"),
            cost_currency="CNY",
        )
        return itinerary_service.create_item(db, trip, test_user.id, data)

    def test_cascade_delete(self, db, trip, test_user):
        """Cascade: expense entries reversed, item deleted."""
        item = self._create_item_with_cost(db, trip, test_user)
        item_id = item.id

        db.refresh(trip)
        spend_before = trip.actual_spend

        itinerary_service.delete_item(db, item, test_user.id, "cascade")

        # Item deleted
        assert db.query(ItineraryItem).filter(ItineraryItem.id == item_id).first() is None
        # Spend decreased
        db.refresh(trip)
        assert trip.actual_spend == spend_before - Decimal("120.00")

    def test_unlink_delete(self, db, trip, test_user):
        """Unlink: expense entries remain, itinerary_item_id nulled, item deleted."""
        item = self._create_item_with_cost(db, trip, test_user)
        item_id = item.id

        db.refresh(trip)
        spend_before = trip.actual_spend

        itinerary_service.delete_item(db, item, test_user.id, "unlink")

        # Item deleted
        assert db.query(ItineraryItem).filter(ItineraryItem.id == item_id).first() is None
        # Expense entries still exist but itinerary_item_id is None
        entries = (
            db.query(ExpenseEntry)
            .filter(
                ExpenseEntry.ref_id == trip.id,
                ExpenseEntry.ref_type == "trip",
                ExpenseEntry.leg_type == "debit",
                ExpenseEntry.amount > 0,
            )
            .all()
        )
        unlinked = [e for e in entries if e.itinerary_item_id is None]
        assert len(unlinked) >= 1
        # Spend unchanged
        db.refresh(trip)
        assert trip.actual_spend == spend_before

    def test_delete_item_without_cost(self, db, trip, test_user):
        """No cost → just delete, no ledger interaction."""
        data = ItineraryItemCreate(date=date(2026, 10, 2), type="activity")
        item = itinerary_service.create_item(db, trip, test_user.id, data)
        item_id = item.id

        itinerary_service.delete_item(db, item, test_user.id, "cascade")
        assert db.query(ItineraryItem).filter(ItineraryItem.id == item_id).first() is None


# ─────────────────────────────────────────────────────────────────────────────
# API tests (U2)
# ─────────────────────────────────────────────────────────────────────────────

class TestItineraryAPI:
    """API route tests via TestClient."""

    def test_create_item_api(self, authed_client, trip_via_api):
        trip_id = trip_via_api["id"]
        resp = authed_client.post(f"/api/v1/trips/{trip_id}/itinerary", json={
            "date": "2026-10-01",
            "type": "accommodation",
            "cost_amount": "500.00",
            "cost_currency": "CNY",
        })
        assert resp.status_code == 201, resp.text
        data = resp.json().get("data", resp.json())
        assert data["type"] == "accommodation"
        assert data["cost_amount"] == "500.00"

    def test_list_items_api(self, authed_client, trip_via_api):
        trip_id = trip_via_api["id"]
        # Create two items
        authed_client.post(f"/api/v1/trips/{trip_id}/itinerary", json={
            "date": "2026-10-01", "type": "accommodation",
        })
        authed_client.post(f"/api/v1/trips/{trip_id}/itinerary", json={
            "date": "2026-10-02", "type": "activity",
        })

        resp = authed_client.get(f"/api/v1/trips/{trip_id}/itinerary")
        assert resp.status_code == 200
        data = resp.json().get("data", resp.json())
        assert len(data) == 2

    def test_update_item_api(self, authed_client, trip_via_api):
        trip_id = trip_via_api["id"]
        create_resp = authed_client.post(f"/api/v1/trips/{trip_id}/itinerary", json={
            "date": "2026-10-01", "type": "dining", "cost_amount": "100.00", "cost_currency": "CNY",
        })
        item_id = create_resp.json().get("data", create_resp.json())["id"]

        resp = authed_client.patch(f"/api/v1/trips/{trip_id}/itinerary/{item_id}", json={
            "cost_amount": "200.00",
        })
        assert resp.status_code == 200
        data = resp.json().get("data", resp.json())
        assert data["cost_amount"] == "200.00"

    def test_delete_cascade_api(self, authed_client, trip_via_api):
        trip_id = trip_via_api["id"]
        create_resp = authed_client.post(f"/api/v1/trips/{trip_id}/itinerary", json={
            "date": "2026-10-01", "type": "dining", "cost_amount": "100.00", "cost_currency": "CNY",
        })
        item_id = create_resp.json().get("data", create_resp.json())["id"]

        resp = authed_client.delete(f"/api/v1/trips/{trip_id}/itinerary/{item_id}?mode=cascade")
        assert resp.status_code == 200

    def test_delete_unlink_api(self, authed_client, trip_via_api):
        trip_id = trip_via_api["id"]
        create_resp = authed_client.post(f"/api/v1/trips/{trip_id}/itinerary", json={
            "date": "2026-10-01", "type": "dining", "cost_amount": "100.00", "cost_currency": "CNY",
        })
        item_id = create_resp.json().get("data", create_resp.json())["id"]

        resp = authed_client.delete(f"/api/v1/trips/{trip_id}/itinerary/{item_id}?mode=unlink")
        assert resp.status_code == 200

    def test_delete_without_mode_returns_422(self, authed_client, trip_via_api):
        trip_id = trip_via_api["id"]
        create_resp = authed_client.post(f"/api/v1/trips/{trip_id}/itinerary", json={
            "date": "2026-10-01", "type": "dining", "cost_amount": "100.00", "cost_currency": "CNY",
        })
        item_id = create_resp.json().get("data", create_resp.json())["id"]

        resp = authed_client.delete(f"/api/v1/trips/{trip_id}/itinerary/{item_id}")
        assert resp.status_code == 422  # missing required query param

    def test_create_invalid_type_returns_422(self, authed_client, trip_via_api):
        trip_id = trip_via_api["id"]
        resp = authed_client.post(f"/api/v1/trips/{trip_id}/itinerary", json={
            "date": "2026-10-01", "type": "invalid_type",
        })
        assert resp.status_code == 422

    def test_create_item_nonexistent_trip_returns_404(self, authed_client):
        resp = authed_client.post("/api/v1/trips/999999/itinerary", json={
            "date": "2026-10-01", "type": "activity",
        })
        assert resp.status_code == 404


class TestItineraryTypeAPI:
    """ItineraryItemType CRUD API tests."""

    def test_create_custom_type(self, authed_client):
        resp = authed_client.post("/api/v1/itinerary-types", json={
            "name": "Shopping",
            "icon": "shopping-cart",
        })
        assert resp.status_code == 201
        data = resp.json().get("data", resp.json())
        assert data["name"] == "Shopping"

    def test_list_custom_types(self, authed_client):
        authed_client.post("/api/v1/itinerary-types", json={"name": "Shopping"})
        authed_client.post("/api/v1/itinerary-types", json={"name": "Relaxation"})

        resp = authed_client.get("/api/v1/itinerary-types")
        assert resp.status_code == 200
        data = resp.json().get("data", resp.json())
        assert len(data) >= 2

    def test_delete_type_in_use_rejected(self, authed_client, trip_via_api):
        """ITINERARY_TYPE_IN_USE: reject delete if type is referenced."""
        # Create custom type
        type_resp = authed_client.post("/api/v1/itinerary-types", json={"name": "UniqueType"})
        type_id = type_resp.json().get("data", type_resp.json())["id"]

        # Create item using it
        trip_id = trip_via_api["id"]
        authed_client.post(f"/api/v1/trips/{trip_id}/itinerary", json={
            "date": "2026-10-01",
            "type": "custom",
            "custom_type_id": int(type_id),
        })

        # Try to delete type → should fail
        resp = authed_client.delete(f"/api/v1/itinerary-types/{type_id}")
        assert resp.status_code == 409
