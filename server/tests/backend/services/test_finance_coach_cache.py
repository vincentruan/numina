"""capability-cache isolation + invalidation (Plan A T7)."""
from datetime import timedelta

from apps.backend.app.services.finance_coach_cache import (
    CAPABILITY_TTL,
    invalidate_capability,
    latest_by_capability,
    upsert_capability_result,
)


def test_latest_by_capability_isolates_finance_coach_from_report(db_session):
    """finance_coach and report rows do not cross-pollute (spec §7.2 core issue 1)."""
    # A 'report' row exists for the family.
    upsert_capability_result(db_session, "1001", "report", {"score": 80})
    # A 'finance_coach' row exists for the same family.
    upsert_capability_result(db_session, "1001", "finance_coach", {"suggestions": []})

    report_latest = latest_by_capability(db_session, "1001", "report")
    coach_latest = latest_by_capability(db_session, "1001", "finance_coach")

    assert report_latest is not None and report_latest.capability == "report"
    assert coach_latest is not None and coach_latest.capability == "finance_coach"
    # The two latest rows are NOT the same row.
    assert report_latest.id != coach_latest.id


def test_invalidate_capability_deletes_only_that_capability(db_session):
    """Invalidating finance_coach does not touch the family's report row."""
    upsert_capability_result(db_session, "1002", "report", {"score": 90})
    upsert_capability_result(db_session, "1002", "finance_coach", {"suggestions": [{"id": "s1"}]})

    invalidate_capability(db_session, "1002", "finance_coach")

    assert latest_by_capability(db_session, "1002", "finance_coach") is None
    assert latest_by_capability(db_session, "1002", "report") is not None  # untouched


def test_invalidate_capability_scoped_to_one_family(db_session):
    """Invalidating fam-3's finance_coach does not delete fam-4's finance_coach."""
    upsert_capability_result(db_session, "1003", "finance_coach", {"suggestions": []})
    upsert_capability_result(db_session, "1004", "finance_coach", {"suggestions": []})

    invalidate_capability(db_session, "1003", "finance_coach")

    assert latest_by_capability(db_session, "1003", "finance_coach") is None
    assert latest_by_capability(db_session, "1004", "finance_coach") is not None


def test_capability_ttl_has_report_and_finance_coach_entries():
    assert "report" in CAPABILITY_TTL
    assert "finance_coach" in CAPABILITY_TTL
    assert CAPABILITY_TTL["report"] == timedelta(hours=8)
    assert CAPABILITY_TTL["finance_coach"] == timedelta(hours=8)


def test_upsert_capability_result_sets_capability_column(db_session):
    row = upsert_capability_result(db_session, "1005", "finance_coach", {"suggestions": []})
    assert row.capability == "finance_coach"
    assert row.status == "completed"
    assert row.family_id == 1005 or str(row.family_id) == "1005"
