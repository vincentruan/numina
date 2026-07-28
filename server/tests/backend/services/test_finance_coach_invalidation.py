"""Entity-change invalidation of the finance_coach cache (Plan A T9).

Spec §7.2: any asset/liability/wish write must invalidate the family's
finance_coach cache row so the next dashboard load regenerates with fresh
data (event-driven invalidation, not pure TTL).

Each write endpoint calls ``invalidate_skill(db, user.family_id,
"finance_coach")`` before its final ``db.commit()``. These tests mock
``invalidate_skill`` at each service module's import path and assert
the call happens with the user's ``family_id`` and ``"finance_coach"``.
"""
from datetime import date
from unittest.mock import patch

from apps.backend.app.models.family import Family
from apps.backend.app.models.user import User
from apps.backend.app.schemas.asset import AssetCreate
from apps.backend.app.schemas.liability import LiabilityCreate
from apps.backend.app.schemas.wish import WishCreate, WishUpdate
from apps.backend.app.services import asset as asset_service
from apps.backend.app.services import liability as liability_service
from apps.backend.app.services import wish as wish_service
from apps.backend.app.services.finance_coach_cache import upsert_skill_result
from apps.backend.app.utils.snowflake import next_id


def _make_user(db_session) -> User:
    """Build a minimal Family + User directly via the ORM (no HTTP)."""
    family = Family(id=next_id(), name="T9 Family", created_by=next_id())
    db_session.add(family)
    db_session.commit()
    db_session.refresh(family)

    user = User(
        id=next_id(),
        username=f"t9_user_{family.id}",
        display_name="T9 User",
        password_hash="x",
        family_id=family.id,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def _seed_cache(db_session, family_id) -> None:
    upsert_skill_result(db_session, family_id, "finance_coach", {"suggestions": []})
    db_session.commit()


def test_wish_create_invalidates_finance_coach_cache(db_session):
    user = _make_user(db_session)
    _seed_cache(db_session, str(user.family_id))
    req = WishCreate(name="MacBook", expected_price=15000, priority="high")

    with patch("apps.backend.app.services.wish.invalidate_skill") as inv:
        wish_service.create_wish(db_session, user, req)

    # W4 (Plan B T7): wish writes bust finance_coach, wish_advice, and dashboard-narrative caches.
    assert inv.call_count == 3
    caps = {call.args[2] for call in inv.call_args_list}
    assert caps == {"finance_coach", "wish_advice", "dashboard-narrative"}
    for call in inv.call_args_list:
        assert str(call.args[1]) == str(user.family_id)


def test_wish_update_invalidates_finance_coach_cache(db_session):
    user = _make_user(db_session)
    _seed_cache(db_session, str(user.family_id))
    wish = wish_service.create_wish(
        db_session, user, WishCreate(name="Camera", expected_price=8000)
    )
    req = WishUpdate(name="Camera Pro")

    with patch("apps.backend.app.services.wish.invalidate_skill") as inv:
        wish_service.update_wish(db_session, user, str(wish.id), req)

    assert inv.call_count == 3
    caps = {call.args[2] for call in inv.call_args_list}
    assert caps == {"finance_coach", "wish_advice", "dashboard-narrative"}
    for call in inv.call_args_list:
        assert str(call.args[1]) == str(user.family_id)


def test_wish_delete_invalidates_finance_coach_cache(db_session):
    user = _make_user(db_session)
    _seed_cache(db_session, str(user.family_id))
    wish = wish_service.create_wish(
        db_session, user, WishCreate(name="Bike", expected_price=2000)
    )

    with patch("apps.backend.app.services.wish.invalidate_skill") as inv:
        wish_service.delete_wish(db_session, user, str(wish.id))

    assert inv.call_count == 3
    caps = {call.args[2] for call in inv.call_args_list}
    assert caps == {"finance_coach", "wish_advice", "dashboard-narrative"}
    for call in inv.call_args_list:
        assert str(call.args[1]) == str(user.family_id)


def test_liability_write_invalidates_finance_coach_cache(db_session):
    user = _make_user(db_session)
    _seed_cache(db_session, str(user.family_id))
    req = LiabilityCreate(
        category="car_loan",
        name="车贷",
        original_amount=200000,
        remaining_amount=150000,
    )

    with patch("apps.backend.app.services.liability.invalidate_skill") as inv:
        liability_service.create_liability(db_session, user, req)

    # Dashboard narrative cache is also invalidated on liability writes.
    assert inv.call_count == 2
    caps = {call.args[2] for call in inv.call_args_list}
    assert caps == {"finance_coach", "dashboard-narrative"}
    for call in inv.call_args_list:
        assert str(call.args[1]) == str(user.family_id)


def test_asset_write_invalidates_finance_coach_cache(db_session):
    user = _make_user(db_session)
    _seed_cache(db_session, str(user.family_id))
    # Need a valid category_id (conftest seeds categories).
    from apps.backend.app.models.category import Category

    category = db_session.query(Category).first()
    assert category is not None
    req = AssetCreate(
        category_id=category.id,
        name="Test Asset",
        asset_type="physical",
        purchase_price=1000,
        current_value=1000,
        purchase_date=date(2024, 1, 1),
    )

    with patch("apps.backend.app.services.asset.invalidate_skill") as inv:
        asset_service.create_asset(db_session, user, req)

    # Dashboard narrative cache is also invalidated on asset writes.
    assert inv.call_count == 2
    caps = {call.args[2] for call in inv.call_args_list}
    assert caps == {"finance_coach", "dashboard-narrative"}
    for call in inv.call_args_list:
        assert str(call.args[1]) == str(user.family_id)
