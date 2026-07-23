"""Wish savings fields + WishSavingsLog model (Plan B W1)."""
from datetime import date
from decimal import Decimal

from apps.backend.app.models.wish import Wish
from apps.backend.app.models.wish_savings_log import WishSavingsLog


def test_wish_has_savings_fields(db_session):
    """Wish model exposes the 4 new fields + NUMERIC expected_price."""
    w = Wish(family_id=1, user_id=1, name="x", expected_price=Decimal("100.50"),
             saved_amount=Decimal("30.00"), monthly_saving=Decimal("10.00"),
             target_date=date(2026, 12, 31), ignore_debt_warning=True)
    db_session.add(w)
    db_session.commit()
    db_session.refresh(w)
    assert w.saved_amount == Decimal("30.00")
    assert w.monthly_saving == Decimal("10.00")
    assert w.target_date == date(2026, 12, 31)
    assert w.ignore_debt_warning is True
    assert isinstance(w.expected_price, Decimal)


def test_wish_defaults(db_session):
    """New wish has zeroed savings + ignore_debt_warning=False."""
    w = Wish(family_id=1, user_id=1, name="y")
    db_session.add(w)
    db_session.commit()
    db_session.refresh(w)
    assert w.saved_amount == Decimal("0")
    assert w.monthly_saving == Decimal("0")
    assert w.target_date is None
    assert w.ignore_debt_warning is False


def test_wish_savings_log_model(db_session):
    log = WishSavingsLog(wish_id=1, family_id=1, user_id=1,
                         amount=Decimal("50.00"), log_date=date(2026, 7, 19), note="seed")
    db_session.add(log)
    db_session.commit()
    db_session.refresh(log)
    assert log.id is not None
    assert log.amount == Decimal("50.00")
    assert log.note == "seed"
    assert log.created_at is not None
