"""Tests for ItineraryItem and ItineraryItemType models (U1)."""

from datetime import date, time
from decimal import Decimal

import pytest
from sqlalchemy import inspect

from packages.db.models.expense_entry import ExpenseEntry
from packages.db.models.itinerary_item import ItineraryItem
from packages.db.models.itinerary_item_type import ItineraryItemType
from packages.db.models.trip import Trip


@pytest.fixture
def trip(db, test_family, test_user):
    """Create a test trip."""
    t = Trip(
        family_id=test_family.id,
        user_id=test_user.id,
        name="Test Trip",
        destination="Tokyo",
        departure_date=date(2026, 10, 1),
        return_date=date(2026, 10, 5),
        currency="CNY",
    )
    db.add(t)
    db.commit()
    db.refresh(t)
    return t


class TestItineraryItemModel:
    """ItineraryItem ORM model tests."""

    def test_create_with_required_fields(self, db, trip, test_family):
        """Create an itinerary item with only required fields, verify defaults."""
        item = ItineraryItem(
            trip_id=trip.id,
            family_id=test_family.id,
            date=date(2026, 10, 1),
            type="accommodation",
        )
        db.add(item)
        db.commit()
        db.refresh(item)

        assert item.id is not None
        assert item.trip_id == trip.id
        assert item.family_id == test_family.id
        assert item.date == date(2026, 10, 1)
        assert item.type == "accommodation"
        assert item.sort_order == 0
        assert item.start_time is None
        assert item.end_time is None
        assert item.location is None
        assert item.description is None
        assert item.cost_amount is None
        assert item.cost_currency is None
        assert item.custom_type_id is None
        assert item.type_metadata is None

    def test_create_with_cost_fields(self, db, trip, test_family):
        """Create an item with optional cost fields."""
        item = ItineraryItem(
            trip_id=trip.id,
            family_id=test_family.id,
            date=date(2026, 10, 2),
            type="dining",
            cost_amount=Decimal("280.00"),
            cost_currency="CNY",
        )
        db.add(item)
        db.commit()
        db.refresh(item)

        assert item.cost_amount == Decimal("280.00")
        assert item.cost_currency == "CNY"

    def test_create_with_time_and_metadata(self, db, trip, test_family):
        """Create an item with time fields and type_metadata."""
        item = ItineraryItem(
            trip_id=trip.id,
            family_id=test_family.id,
            date=date(2026, 10, 1),
            type="accommodation",
            start_time=time(14, 0),
            end_time=time(12, 0),
            location="Hotel Nikko Tokyo",
            description="Near Shinjuku station",
            type_metadata={"check_in_time": "14:00", "check_out_time": "12:00"},
        )
        db.add(item)
        db.commit()
        db.refresh(item)

        assert item.start_time == time(14, 0)
        assert item.end_time == time(12, 0)
        assert item.location == "Hotel Nikko Tokyo"
        assert item.type_metadata["check_in_time"] == "14:00"

    def test_all_core_types(self, db, trip, test_family):
        """Verify all four core types can be stored."""
        for t in ["accommodation", "dining", "transport", "activity"]:
            item = ItineraryItem(
                trip_id=trip.id,
                family_id=test_family.id,
                date=date(2026, 10, 1),
                type=t,
            )
            db.add(item)
        db.commit()

        items = db.query(ItineraryItem).filter(ItineraryItem.trip_id == trip.id).all()
        assert len(items) == 4
        assert {i.type for i in items} == {"accommodation", "dining", "transport", "activity"}

    def test_custom_type_stored(self, db, trip, test_family):
        """Verify type='custom' can be stored (custom_type_id validated separately)."""
        item = ItineraryItem(
            trip_id=trip.id,
            family_id=test_family.id,
            date=date(2026, 10, 3),
            type="custom",
        )
        db.add(item)
        db.commit()
        db.refresh(item)
        assert item.type == "custom"
        assert item.custom_type_id is None  # not yet linked


class TestItineraryItemTypeModel:
    """ItineraryItemType ORM model tests."""

    def test_create_family_scoped(self, db, test_family):
        """Create a family-scoped custom type."""
        iit = ItineraryItemType(
            family_id=test_family.id,
            name="Shopping",
            icon="shopping-cart",
            sort_order=1,
        )
        db.add(iit)
        db.commit()
        db.refresh(iit)

        assert iit.id is not None
        assert iit.family_id == test_family.id
        assert iit.name == "Shopping"
        assert iit.icon == "shopping-cart"
        assert iit.sort_order == 1

    def test_create_without_family(self, db):
        """Create a system-level type (family_id=null)."""
        iit = ItineraryItemType(name="System Type", icon="star")
        db.add(iit)
        db.commit()
        db.refresh(iit)

        assert iit.family_id is None
        assert iit.sort_order == 0

    def test_family_id_column_exists(self, db):
        """Verify family_id FK column exists and is nullable (null=system default)."""
        insp = inspect(db.get_bind())
        columns = {c["name"]: c for c in insp.get_columns("itinerary_item_types")}
        assert "family_id" in columns
        assert columns["family_id"]["nullable"] is True


class TestExpenseEntryItineraryLink:
    """Verify the itinerary_item_id column on ExpenseEntry."""

    def test_column_exists_and_nullable(self, db):
        """itinerary_item_id is nullable and defaults to None."""
        insp = inspect(db.get_bind())
        columns = {c["name"]: c for c in insp.get_columns("expense_entries")}
        assert "itinerary_item_id" in columns
        assert columns["itinerary_item_id"]["nullable"] is True

    def test_link_to_itinerary_item(self, db, trip, test_family, test_user):
        """Create an ExpenseEntry linked to an ItineraryItem."""
        item = ItineraryItem(
            trip_id=trip.id,
            family_id=test_family.id,
            date=date(2026, 10, 1),
            type="dining",
            cost_amount=Decimal("120.00"),
            cost_currency="CNY",
        )
        db.add(item)
        db.flush()

        entry = ExpenseEntry(
            family_id=test_family.id,
            transfer_id=12345,
            leg_type="debit",
            ref_id=trip.id,
            ref_type="trip",
            amount=Decimal("120.00"),
            currency="CNY",
            expense_date=date(2026, 10, 1),
            user_id=test_user.id,
            itinerary_item_id=item.id,
        )
        db.add(entry)
        db.commit()
        db.refresh(entry)

        assert entry.itinerary_item_id == item.id

    def test_null_itinerary_item_id(self, db, trip, test_family, test_user):
        """ExpenseEntry without itinerary_item_id works (standalone expense)."""
        entry = ExpenseEntry(
            family_id=test_family.id,
            transfer_id=67890,
            leg_type="debit",
            ref_id=trip.id,
            ref_type="trip",
            amount=Decimal("50.00"),
            currency="CNY",
            expense_date=date(2026, 10, 2),
            user_id=test_user.id,
        )
        db.add(entry)
        db.commit()
        db.refresh(entry)

        assert entry.itinerary_item_id is None
