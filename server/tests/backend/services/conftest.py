"""Fixtures for W1 wish-savings service tests (Plan B T2).

Builds the family/user/wish topology the savings-authz tests need: an owning
family with an owner + a second adult member, plus a second family whose wish is
off-limits. Savings logs are created via the service under test (record_savings),
so the fixtures only lay down the parent rows.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from apps.backend.app.models.wish import Wish
from apps.backend.app.models.wish_savings_log import WishSavingsLog
from apps.backend.app.utils.snowflake import next_id


@pytest.fixture
def wish_owner_user(db, test_family):
    """The owner of the wish's family (role=member by default — the recorder)."""
    from apps.backend.app.models.user import User

    user = User(
        id=next_id(),
        username="wish_owner",
        display_name="Wish Owner",
        password_hash="test_hash",
        family_id=test_family.id,
        role="member",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def family_owner(db, test_family):
    """The family owner (role=owner) — can delete any family member's log."""
    from apps.backend.app.models.user import User

    user = User(
        id=next_id(),
        username="family_owner",
        display_name="Family Owner",
        password_hash="test_hash",
        family_id=test_family.id,
        role="owner",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def other_adult_in_family(db, test_family):
    """A second adult in the same family (role=member, not owner, not recorder)."""
    from apps.backend.app.models.user import User

    user = User(
        id=next_id(),
        username="other_adult",
        display_name="Other Adult",
        password_hash="test_hash",
        family_id=test_family.id,
        role="member",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def owned_wish(db, test_family, wish_owner_user):
    """A wish owned by wish_owner_user in test_family."""
    wish = Wish(
        id=next_id(),
        family_id=test_family.id,
        user_id=wish_owner_user.id,
        name="Test Wish",
        expected_price=Decimal("1000.00"),
    )
    db.add(wish)
    db.commit()
    db.refresh(wish)
    return wish


@pytest.fixture
def other_family_wish(db, other_family):
    """A wish in another family — must be invisible to test_family callers."""
    from apps.backend.app.models.user import User

    user = User(
        id=next_id(),
        username="other_family_wish_owner",
        display_name="Other Family Wish Owner",
        password_hash="test_hash",
        family_id=other_family.id,
        role="member",
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    wish = Wish(
        id=next_id(),
        family_id=other_family.id,
        user_id=user.id,
        name="Other Family Wish",
        expected_price=Decimal("500.00"),
    )
    db.add(wish)
    db.commit()
    db.refresh(wish)
    return wish


@pytest.fixture
def recorder_log(db, test_family, wish_owner_user, owned_wish):
    """A savings log recorded by wish_owner_user on owned_wish."""
    log = WishSavingsLog(
        id=next_id(),
        wish_id=owned_wish.id,
        family_id=test_family.id,
        user_id=wish_owner_user.id,
        amount=Decimal("50.00"),
        log_date=date(2026, 7, 19),
        note="recorder log",
    )
    db.add(log)
    owned_wish.saved_amount = Decimal("50.00")
    db.commit()
    db.refresh(log)
    return log


@pytest.fixture
def recorder_log_by_other(db, test_family, other_adult_in_family, owned_wish):
    """A savings log recorded by other_adult_in_family (not the owner, not wish_owner)."""
    log = WishSavingsLog(
        id=next_id(),
        wish_id=owned_wish.id,
        family_id=test_family.id,
        user_id=other_adult_in_family.id,
        amount=Decimal("30.00"),
        log_date=date(2026, 7, 19),
        note="log by other adult",
    )
    db.add(log)
    owned_wish.saved_amount = Decimal("30.00")
    db.commit()
    db.refresh(log)
    return log
