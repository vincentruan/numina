"""W1 savings service: invariant + authz + reconciliation (Plan B T2)."""
from datetime import date
from decimal import Decimal

import pytest

from apps.backend.app.errors import AppError, ErrorCode
from apps.backend.app.services.wish_savings import (
    delete_savings,
    list_savings,
    recompute_saved_amount,
    record_savings,
)


def test_record_savings_updates_saved_amount_in_transaction(db_session, wish_owner_user, owned_wish):
    """POST savings writes log + updates saved_amount atomically."""
    record_savings(db_session, wish_owner_user, str(owned_wish.id),
                   amount=Decimal("100"), log_date=date(2026, 7, 19), note="first")
    db_session.refresh(owned_wish)
    assert owned_wish.saved_amount == Decimal("100")
    logs = list_savings(db_session, wish_owner_user, str(owned_wish.id))
    assert len(logs) == 1
    assert logs[0].amount == Decimal("100")


def test_negative_savings_decrements(db_session, wish_owner_user, owned_wish):
    """A negative amount (withdrawal) decrements saved_amount."""
    record_savings(db_session, wish_owner_user, str(owned_wish.id), amount=Decimal("100"), log_date=date(2026, 7, 19))
    record_savings(db_session, wish_owner_user, str(owned_wish.id), amount=Decimal("-30"), log_date=date(2026, 7, 20))
    db_session.refresh(owned_wish)
    assert owned_wish.saved_amount == Decimal("70")


def test_delete_savings_reverses_amount(db_session, wish_owner_user, owned_wish):
    """DELETE subtracts the log's amount from saved_amount in-transaction."""
    log = record_savings(db_session, wish_owner_user, str(owned_wish.id), amount=Decimal("50"), log_date=date(2026, 7, 19))
    delete_savings(db_session, wish_owner_user, str(owned_wish.id), str(log.id))
    db_session.refresh(owned_wish)
    assert owned_wish.saved_amount == Decimal("0")
    assert list_savings(db_session, wish_owner_user, str(owned_wish.id)) == []


def test_delete_savings_forbidden_for_non_recorder(db_session, wish_owner_user, other_adult_in_family, owned_wish, recorder_log):
    """A different family adult (not the recorder, not owner) cannot delete the log."""
    with pytest.raises(AppError) as exc:
        delete_savings(db_session, other_adult_in_family, str(owned_wish.id), str(recorder_log.id))
    assert exc.value.code == ErrorCode.FORBIDDEN


def test_delete_savings_allowed_for_family_owner(db_session, family_owner, owned_wish, recorder_log_by_other):
    """The family owner can delete any family member's savings log."""
    delete_savings(db_session, family_owner, str(owned_wish.id), str(recorder_log_by_other.id))  # no raise


def test_recompute_saved_amount_equals_sum(db_session, wish_owner_user, owned_wish):
    """recompute_saved_amount == SUM(log.amount) — the invariant."""
    record_savings(db_session, wish_owner_user, str(owned_wish.id), amount=Decimal("100"), log_date=date(2026, 7, 19))
    record_savings(db_session, wish_owner_user, str(owned_wish.id), amount=Decimal("50"), log_date=date(2026, 7, 20))
    record_savings(db_session, wish_owner_user, str(owned_wish.id), amount=Decimal("-20"), log_date=date(2026, 7, 21))
    db_session.refresh(owned_wish)
    assert owned_wish.saved_amount == recompute_saved_amount(db_session, owned_wish.id)
    assert recompute_saved_amount(db_session, owned_wish.id) == Decimal("130")


def test_record_savings_other_family_wish_404(db_session, wish_owner_user, other_family_wish):
    """A wish not in the caller's family returns NOT_FOUND (family filter)."""
    with pytest.raises(AppError) as exc:
        record_savings(db_session, wish_owner_user, str(other_family_wish.id), amount=Decimal("10"), log_date=date(2026, 7, 19))
    assert exc.value.code == ErrorCode.NOT_FOUND
