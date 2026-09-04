"""Skill-scoped cache layer on ai_reports (Plan A T7).

The existing report cache (ai_report.py `_latest_report` + `REPORT_CACHE_TTL`)
filters only by (family_id, status='completed') with NO skill distinction —
a finance_coach row would collide with the report row for the same family (spec
§7.2 core issue 1). This module adds skill-scoped read/write/invalidate so
the three cache keys coexist without pollution:

  - family_id:report         (existing asset-report, TTL 8h)
  - family_id:finance_coach  (D2 dashboard card, TTL 8h, entity-change invalidation)
  - family_id:wish_advice:{fingerprint}  (Plan B W4, separate cache key — not here)

Entity-change invalidation: any asset/liability/wish write (Task 9) calls
``invalidate_skill(family_id, "finance_coach", db)`` so the next dashboard
load regenerates with fresh data (spec §7.2: event-driven, not pure TTL).
"""
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy.orm import Session

from apps.backend.app.models.ai_report import AIReport
from apps.backend.app.utils.snowflake import next_id

# Parametric TTL per skill (spec §7.2: non-hardcoded).
# report: 1h — users wanted hourly deduplication; background generation keeps
# the task alive across page navigation, so the cache window is shortened to
# avoid stale reports and repeated prompts within the same hour.
SKILL_TTL: dict[str, timedelta] = {
    "report": timedelta(hours=1),
    "finance_coach": timedelta(hours=8),
}


def _family_id_int(family_id: str | int) -> int:
    """Coerce the str family_id (snowflake-as-string convention) to int for the
    BigInteger column."""
    return int(family_id)


def latest_by_skill(
    db: Session, family_id: str | int, skill_id: str
) -> AIReport | None:
    """Return the most recent completed AIReport for (family, skill_id), or None."""
    return (
        db.query(AIReport)
        .filter(
            AIReport.family_id == _family_id_int(family_id),
            AIReport.skill_id == skill_id,
            AIReport.status == "completed",
        )
        .order_by(AIReport.generated_at.desc())
        .first()
    )


def is_cache_fresh(
    row: AIReport | None,
    skill_id: str,
    family_id: str | int | None = None,
) -> bool:
    """True if the row exists and is younger than the skill_id's TTL.

    When family_id is provided, reads TTL from family_settings (with 5-min cache).
    Falls back to hardcoded SKILL_TTL when family_id is None.
    """
    if row is None or row.generated_at is None:
        return False
    if family_id is not None:
        from apps.backend.app.services.config_registry import FAMILY_SETTING_DEFINITIONS
        from apps.backend.app.services.config_service import get_family_setting_cached

        config_key = f"ai_cache_ttl_{skill_id.replace('-', '_')}"
        if config_key in FAMILY_SETTING_DEFINITIONS:
            try:
                ttl_minutes = get_family_setting_cached(int(family_id), config_key)
                ttl = timedelta(minutes=ttl_minutes)
            except Exception:
                ttl = SKILL_TTL.get(skill_id, timedelta(hours=8))
        else:
            ttl = SKILL_TTL.get(skill_id, timedelta(hours=8))
    else:
        ttl = SKILL_TTL.get(skill_id, timedelta(hours=8))
    age = datetime.now(UTC) - row.generated_at
    return bool(age < ttl)


def upsert_skill_result(
    db: Session,
    family_id: str | int,
    skill_id: str,
    payload: dict[str, Any],
) -> AIReport:
    """Persist a skill_id result as a completed AIReport row and return it.

    The caller (Task 8 backend trigger) commits the transaction. We do NOT
    invalidate other skills here — cross-skill invalidation is the
    entity-change hook's job (Task 9).
    """
    row = AIReport(
        id=next_id(),
        family_id=_family_id_int(family_id),
        report_json=payload,
        status="completed",
        skill_id=skill_id,
        generated_at=datetime.now(UTC),
    )
    db.add(row)
    db.flush()  # get the id without committing (caller commits)
    return row


def invalidate_skill(
    db: Session, family_id: str | int, skill_id: str
) -> None:
    """Delete all completed rows for (family, skill_id).

    Called on entity-change (asset/liability/wish write — Task 9) so the next
    read regenerates. Deletes only the given skill_id (does not touch 'report'
    when invalidating 'finance_coach', and vice versa). The caller commits.
    """
    db.query(AIReport).filter(
        AIReport.family_id == _family_id_int(family_id),
        AIReport.skill_id == skill_id,
    ).delete(synchronize_session=False)
