"""skill-cache isolation + invalidation (Plan A T7)."""
from datetime import timedelta

from apps.backend.app.services.finance_coach_cache import (
    SKILL_TTL,
    invalidate_skill,
    latest_by_skill,
    upsert_skill_result,
)


async def test_latest_by_skill_isolates_finance_coach_from_report(db_session):
    """finance_coach and report rows do not cross-pollute (spec §7.2 core issue 1)."""
    # A 'report' row exists for the family.
    upsert_skill_result(db_session, "1001", "asset-report", {"score": 80})
    # A 'finance_coach' row exists for the same family.
    upsert_skill_result(db_session, "1001", "finance-coach", {"suggestions": []})

    report_latest = await latest_by_skill(db_session, "1001", "asset-report")
    coach_latest = await latest_by_skill(db_session, "1001", "finance-coach")

    assert report_latest is not None and report_latest.skill_id == "asset-report"
    assert coach_latest is not None and coach_latest.skill_id == "finance-coach"
    # The two latest rows are NOT the same row.
    assert report_latest.id != coach_latest.id


async def test_invalidate_skill_deletes_only_that_skill(db_session):
    """Invalidating finance_coach does not touch the family's report row."""
    upsert_skill_result(db_session, "1002", "asset-report", {"score": 90})
    upsert_skill_result(db_session, "1002", "finance-coach", {"suggestions": [{"id": "s1"}]})

    invalidate_skill(db_session, "1002", "finance-coach")

    assert await latest_by_skill(db_session, "1002", "finance-coach") is None
    assert await latest_by_skill(db_session, "1002", "asset-report") is not None  # untouched


async def test_invalidate_skill_scoped_to_one_family(db_session):
    """Invalidating fam-3's finance_coach does not delete fam-4's finance_coach."""
    upsert_skill_result(db_session, "1003", "finance-coach", {"suggestions": []})
    upsert_skill_result(db_session, "1004", "finance-coach", {"suggestions": []})

    invalidate_skill(db_session, "1003", "finance-coach")

    assert await latest_by_skill(db_session, "1003", "finance-coach") is None
    assert await latest_by_skill(db_session, "1004", "finance-coach") is not None


async def test_capability_ttl_has_report_and_finance_coach_entries():
    assert "asset-report" in SKILL_TTL
    assert "finance-coach" in SKILL_TTL
    assert SKILL_TTL["asset-report"] == timedelta(hours=1)
    assert SKILL_TTL["finance-coach"] == timedelta(hours=8)


async def test_upsert_skill_result_sets_skill_id_column(db_session):
    row = upsert_skill_result(db_session, "1005", "finance-coach", {"suggestions": []})
    assert row.skill_id == "finance-coach"
    assert row.status == "completed"
    assert row.family_id == 1005 or str(row.family_id) == "1005"
