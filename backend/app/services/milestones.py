"""Milestone check and record service.

Checks whether a child has earned a new milestone after a chore approval
or wish realization, and records it in child_milestones.

All logic is wrapped in try/except — a milestone failure never blocks
the primary approval or wish-realize flow.
"""

import logging
from datetime import UTC, datetime

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.child_milestone import ChildMilestone
from app.services.coin_transactions import get_total_earned

logger = logging.getLogger(__name__)
_audit_logger = logging.getLogger("audit.milestones")

# Milestone types that can only trigger once per child (lifetime)
_ONCE_PER_CHILD = {"first_chore", "first_wish_realized", "coins_50", "coins_200"}

# Milestone types that re-trigger each new streak cycle
_PER_CYCLE = {"streak_7", "streak_14", "streak_30"}

# Streak thresholds for per-cycle milestones
_STREAK_MILESTONES = {7: "streak_7", 14: "streak_14", 30: "streak_30"}


def check_and_record_milestones(
    db: Session,
    child_user_id: str,
    family_id: str,
    context: dict,
) -> str | None:
    """Check and record any newly earned milestones.

    Args:
        context: dict with optional keys:
            'instance': ChoreInstance (for chore-triggered milestones)
            'wish': ChildWish (for wish-triggered milestones)

    Returns:
        The first newly triggered milestone_type, or None.
    """
    try:
        return _check_milestones(db, child_user_id, family_id, context)
    except Exception:
        logger.exception("Milestone check failed for child %s — ignoring", child_user_id)
        return None


def _check_milestones(
    db: Session,
    child_user_id: str,
    family_id: str,
    context: dict,
) -> str | None:
    instance = context.get("instance")
    wish = context.get("wish")
    triggered: list[str] = []

    # Batch-fetch all existing once-per-child milestones in one query (eliminates N+1)
    existing_once_per_child = set(
        m.milestone_type
        for m in db.query(ChildMilestone).filter(
            ChildMilestone.child_user_id == child_user_id,
            ChildMilestone.family_id == family_id,
            ChildMilestone.milestone_type.in_(_ONCE_PER_CHILD),
        ).all()
    )

    # 1. first_chore — triggered by any chore approval
    if instance is not None:
        if _try_record_once_cached(
            db, child_user_id, family_id, "first_chore", instance.id, "chore_instance", existing_once_per_child
        ):
            triggered.append("first_chore")

    # 2. streak milestones — per cycle, triggered by chore approval
    if instance is not None:
        streak = getattr(instance, "streak_count", 0)
        eligible = [mtype for threshold, mtype in sorted(_STREAK_MILESTONES.items()) if streak >= threshold]
        if eligible:
            # Batch-fetch all last streak milestones in one query (eliminates N+1)
            last_streak_milestones = {
                m.milestone_type: m
                for m in db.query(ChildMilestone).filter(
                    ChildMilestone.child_user_id == child_user_id,
                    ChildMilestone.family_id == family_id,
                    ChildMilestone.milestone_type.in_(eligible),
                ).order_by(ChildMilestone.triggered_at.desc()).all()
            }
            # Batch-fetch all ref instances in one query
            ref_ids = [m.ref_id for m in last_streak_milestones.values() if m.ref_id]
            from app.models.chore import ChoreInstance as CI
            prev_instances: dict[str, CI] = {}
            if ref_ids:
                prev_instances = {
                    ci.id: ci
                    for ci in db.query(CI).filter(
                        CI.id.in_(ref_ids),
                        CI.template_id == instance.template_id,
                        CI.child_user_id == child_user_id,
                    ).all()
                }
            for mtype in eligible:
                last = last_streak_milestones.get(mtype)
                prev = prev_instances.get(last.ref_id) if last and last.ref_id else None
                if _try_record_streak_cycle_cached(
                    db, child_user_id, family_id, mtype, instance, last, prev
                ):
                    triggered.append(mtype)

    # 3. coins_50 / coins_200 — triggered by chore approval or wish realize
    if instance is not None or wish is not None:
        ref_id = instance.id if instance else wish.id
        ref_type = "chore_instance" if instance else "child_wish"
        total = get_total_earned(db, child_user_id, family_id)
        for threshold, mtype in [(50, "coins_50"), (200, "coins_200")]:
            if total >= threshold:
                if _try_record_once_cached(
                    db, child_user_id, family_id, mtype, ref_id, ref_type, existing_once_per_child
                ):
                    triggered.append(mtype)

    # 4. first_wish_realized — triggered by wish realization
    if wish is not None:
        if _try_record_once_cached(
            db, child_user_id, family_id, "first_wish_realized", wish.id, "child_wish", existing_once_per_child
        ):
            triggered.append("first_wish_realized")

    # Return the most notable milestone for the UI toast (priority order)
    _priority = ["first_chore", "streak_7", "streak_14", "streak_30", "coins_50", "coins_200", "first_wish_realized"]
    if triggered:
        db.commit()  # single commit for all milestone inserts
    for m in _priority:
        if m in triggered:
            return m
    return None


def _try_record_once_cached(
    db: Session,
    child_user_id: str,
    family_id: str,
    milestone_type: str,
    ref_id: str,
    ref_type: str,
    existing_cache: set[str],
) -> bool:
    """Record a once-per-child milestone using pre-fetched cache. Returns True if newly recorded."""
    if milestone_type in existing_cache:
        return False
    try:
        _insert_milestone(db, child_user_id, family_id, milestone_type, ref_id, ref_type)
        existing_cache.add(milestone_type)  # update cache to prevent duplicate in same call
        return True
    except IntegrityError:
        db.rollback()
        _audit_logger.debug(
            "milestone_dedup_race | child=%s family=%s type=%s — IntegrityError caught",
            child_user_id, family_id, milestone_type,
        )
        return False


def _try_record_once(
    db: Session,
    child_user_id: str,
    family_id: str,
    milestone_type: str,
    ref_id: str,
    ref_type: str,
) -> bool:
    """Record a once-per-child milestone. Returns True if newly recorded."""
    existing = db.query(ChildMilestone).filter(
        ChildMilestone.child_user_id == child_user_id,
        ChildMilestone.family_id == family_id,
        ChildMilestone.milestone_type == milestone_type,
    ).first()
    if existing:
        return False
    try:
        _insert_milestone(db, child_user_id, family_id, milestone_type, ref_id, ref_type)
        return True
    except IntegrityError:
        db.rollback()
        _audit_logger.debug(
            "milestone_dedup_race | child=%s family=%s type=%s — IntegrityError caught",
            child_user_id, family_id, milestone_type,
        )
        return False


def _try_record_streak_cycle_cached(
    db: Session,
    child_user_id: str,
    family_id: str,
    milestone_type: str,
    instance,
    last: "ChildMilestone | None",
    prev_instance,
) -> bool:
    """Record a per-cycle streak milestone using pre-fetched last milestone and prev instance.

    A new cycle is detected when the current streak_count is less than the streak_count
    of the instance that triggered the previous milestone of this type.
    """
    threshold = {v: k for k, v in _STREAK_MILESTONES.items()}[milestone_type]

    if last is not None:
        if prev_instance is not None:
            if instance.streak_count >= prev_instance.streak_count:
                return False  # same cycle
        else:
            if instance.streak_count >= threshold:
                return False  # conservative: no ref data, assume same cycle
    try:
        _insert_milestone(db, child_user_id, family_id, milestone_type, instance.id, "chore_instance")
        return True
    except IntegrityError:
        db.rollback()
        _audit_logger.debug(
            "milestone_dedup_race | child=%s family=%s type=%s — IntegrityError caught",
            child_user_id, family_id, milestone_type,
        )
        return False


def _try_record_streak_cycle(
    db: Session,
    child_user_id: str,
    family_id: str,
    milestone_type: str,
    instance,
) -> bool:
    """Record a per-cycle streak milestone. Returns True if newly recorded for this cycle.

    A new cycle is detected when the current streak_count is less than the streak_count
    of the instance that triggered the previous milestone of this type — meaning the streak
    was reset and rebuilt since the last trigger.
    """
    from app.models.chore import ChoreInstance

    threshold = {v: k for k, v in _STREAK_MILESTONES.items()}[milestone_type]

    last = (
        db.query(ChildMilestone)
        .filter(
            ChildMilestone.child_user_id == child_user_id,
            ChildMilestone.family_id == family_id,
            ChildMilestone.milestone_type == milestone_type,
        )
        .order_by(ChildMilestone.triggered_at.desc())
        .first()
    )

    prev_instance = None
    if last is not None and last.ref_id:
        prev_instance = db.query(ChoreInstance).filter(
            ChoreInstance.id == last.ref_id,
            ChoreInstance.template_id == instance.template_id,
            ChoreInstance.child_user_id == child_user_id,
        ).first()

    return _try_record_streak_cycle_cached(
        db, child_user_id, family_id, milestone_type, instance, last, prev_instance
    )


_VALID_MILESTONE_TYPES = _ONCE_PER_CHILD | _PER_CYCLE


def _insert_milestone(
    db: Session,
    child_user_id: str,
    family_id: str,
    milestone_type: str,
    ref_id: str,
    ref_type: str,
) -> ChildMilestone:
    if milestone_type not in _VALID_MILESTONE_TYPES:
        raise ValueError(f"Unknown milestone_type: {milestone_type!r}")
    m = ChildMilestone(
        family_id=family_id,
        child_user_id=child_user_id,
        milestone_type=milestone_type,
        triggered_at=datetime.now(UTC),
        ref_id=ref_id,
        ref_type=ref_type,
    )
    db.add(m)
    db.flush()  # assign PK without committing; caller owns the transaction boundary
    _audit_logger.info(
        "milestone_granted | child=%s family=%s type=%s ref_id=%s ref_type=%s",
        child_user_id, family_id, milestone_type, ref_id, ref_type,
    )
    return m


def list_milestones(db: Session, child_user_id: str, family_id: str | None = None) -> list[ChildMilestone]:
    """Return all milestones for a child, newest first."""
    q = db.query(ChildMilestone).filter(ChildMilestone.child_user_id == child_user_id)
    if family_id is not None:
        q = q.filter(ChildMilestone.family_id == family_id)
    return q.order_by(ChildMilestone.triggered_at.desc()).all()
