"""ChallengeGrant service for parent-initiated goal challenges.

All challenge operations are wrapped in try/except — failure never blocks
the approval flow.
"""

import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from apps.backend.app.models.bonus_draw import BonusDraw
from apps.backend.app.models.challenge_grant import ChallengeGrant
from apps.backend.app.utils.snowflake import next_id

logger = logging.getLogger(__name__)
_audit_logger = logging.getLogger("audit.challenges")


def create_challenge(
    db: Session,
    parent_user,
    child_id: str,
    target_type: str,
    target_value: int,
    deadline: datetime,
    message: str | None = None,
    chore_template_id: str | None = None,
) -> ChallengeGrant:
    """Create a new challenge for a child.

    Validates:
    - Child belongs to family and is_active=True
    - Less than 3 active challenges for this child
    - target_value > 0
    - deadline > now()
    - chore_template_id exists and belongs to family when target_type == 'specific_chore'

    Raises:
        ValueError: validation failure
    """
    family_id = parent_user.family_id

    # Validate child belongs to family and is active
    from apps.backend.app.models.user import User

    child = (
        db.query(User)
        .filter(
            User.id == child_id,
            User.family_id == family_id,
            User.is_active == True,
            User.role == "child",
        )
        .first()
    )
    if not child:
        raise ValueError("孩子不存在或不属于该家庭")

    # Check max 3 active challenges
    active_count = (
        db.query(ChallengeGrant)
        .filter(
            ChallengeGrant.child_user_id == child_id,
            ChallengeGrant.status == "active",
        )
        .count()
    )
    if active_count >= 3:
        raise ValueError("该孩子已有3个进行中的挑战")

    # Validate target_value
    if target_value <= 0:
        raise ValueError("目标值必须大于0")

    # Validate deadline
    if deadline <= datetime.now(UTC):
        raise ValueError("截止日期必须在未来")

    # Validate chore_template_id for specific_chore
    if target_type == "specific_chore":
        if not chore_template_id:
            raise ValueError("指定家务类型必须选择家务模板")
        from apps.backend.app.models.chore import ChoreTemplate

        template = (
            db.query(ChoreTemplate)
            .filter(
                ChoreTemplate.id == chore_template_id,
                ChoreTemplate.family_id == family_id,
            )
            .first()
        )
        if not template:
            raise ValueError("家务模板不存在或不属于该家庭")

    challenge = ChallengeGrant(
        id=next_id(),
        family_id=family_id,
        child_user_id=child_id,
        target_type=target_type,
        target_value=target_value,
        chore_template_id=chore_template_id
        if target_type == "specific_chore"
        else None,
        current_progress=0,
        deadline=deadline,
        message=message,
        status="active",
    )
    db.add(challenge)
    db.commit()
    db.refresh(challenge)
    _audit_logger.info(
        "challenge_created | family=%s child=%s type=%s target=%s deadline=%s",
        family_id,
        child_id,
        target_type,
        target_value,
        deadline,
    )
    return challenge


def check_challenge_progress(
    db: Session,
    child_user_id: int,
    family_id: int,
    instance,
) -> list[ChallengeGrant]:
    """Check and update challenge progress after approval.

    Called after db.commit() in approval flow. Wrapped in try/except — never blocks.

    Steps:
    1. Lazy expiration: mark expired any active challenges past deadline
    2. For each active challenge, update progress per type
    3. Check completion: if progress >= target, mark completed and create BonusDraw

    Returns:
        List of completed challenges (for potential notification)
    """
    try:
        return _check_challenge_progress_impl(db, child_user_id, family_id, instance)
    except Exception:
        logger.exception(
            "Challenge progress check failed for child %s — ignoring", child_user_id
        )
        return []


def _check_challenge_progress_impl(
    db: Session,
    child_user_id: int,
    family_id: int,
    instance,
) -> list[ChallengeGrant]:
    now = datetime.now(UTC)

    # 1. Lazy expiration
    expired = (
        db.query(ChallengeGrant)
        .filter(
            ChallengeGrant.child_user_id == child_user_id,
            ChallengeGrant.status == "active",
            ChallengeGrant.deadline < now,
        )
        .all()
    )
    for ch in expired:
        ch.status = "expired"
        _audit_logger.info(
            "challenge_expired | family=%s child=%s challenge=%s type=%s",
            family_id,
            child_user_id,
            ch.id,
            ch.target_type,
        )
    if expired:
        db.commit()

    # 2. Get active challenges
    active = (
        db.query(ChallengeGrant)
        .filter(
            ChallengeGrant.child_user_id == child_user_id,
            ChallengeGrant.family_id == family_id,
            ChallengeGrant.status == "active",
        )
        .all()
    )

    if not active:
        return []

    # 3. Update progress and check completion
    completed: list[ChallengeGrant] = []
    from apps.backend.app.models.user import User

    child = db.query(User).filter(User.id == child_user_id).first()

    for challenge in active:
        _update_progress_for_type(challenge, instance, child)
        db.flush()

        if challenge.current_progress >= challenge.target_value:
            challenge.status = "completed"
            challenge.completed_at = now
            # Create BonusDraw with 7-day expiry
            bonus = BonusDraw(
                id=next_id(),
                family_id=family_id,
                child_user_id=child_user_id,
                source_challenge_id=challenge.id,
                status="available",
                expires_at=now + timedelta(days=7),
            )
            db.add(bonus)
            completed.append(challenge)
            _audit_logger.info(
                "challenge_completed | family=%s child=%s challenge=%s type=%s bonus_id=%s",
                family_id,
                child_user_id,
                challenge.id,
                challenge.target_type,
                bonus.id,
            )

    if completed:
        db.commit()

    return completed


def _update_progress_for_type(challenge: ChallengeGrant, instance, child) -> None:
    """Update progress based on challenge target_type."""
    if challenge.target_type == "task_count":
        challenge.current_progress += 1
    elif challenge.target_type == "streak_length":
        # Progress tracks actual streak count toward target
        challenge.current_progress = min(instance.streak_count, challenge.target_value)
    elif challenge.target_type == "specific_chore":
        # Only increment if template matches
        if str(instance.template_id) == str(challenge.chore_template_id):
            challenge.current_progress += 1
    elif challenge.target_type == "star_earnings":
        # Sum coin_reward + streak_bonus
        challenge.current_progress += instance.coin_reward + getattr(
            instance, "streak_bonus", 0
        )


def cancel_challenge(
    db: Session,
    parent_user,
    challenge_id: str,
) -> ChallengeGrant:
    """Cancel an active challenge.

    Validates:
    - Challenge belongs to parent's family
    - Status is 'active'

    Raises:
        ValueError: validation failure
    """
    family_id = parent_user.family_id

    challenge = (
        db.query(ChallengeGrant)
        .filter(
            ChallengeGrant.id == challenge_id,
            ChallengeGrant.family_id == family_id,
        )
        .first()
    )
    if not challenge:
        raise ValueError("挑战不存在")

    if challenge.status != "active":
        raise ValueError("只能取消进行中的挑战")

    challenge.status = "cancelled"
    db.commit()
    db.refresh(challenge)
    _audit_logger.info(
        "challenge_cancelled | family=%s challenge=%s child=%s",
        family_id,
        challenge_id,
        challenge.child_user_id,
    )
    return challenge


def list_family_challenges(
    db: Session,
    family_id: str,
    status: str | None = None,
) -> list[ChallengeGrant]:
    """List all challenges for a family, optionally filtered by status."""
    q = db.query(ChallengeGrant).filter(ChallengeGrant.family_id == family_id)
    if status:
        q = q.filter(ChallengeGrant.status == status)
    return q.order_by(ChallengeGrant.created_at.desc()).all()


def list_child_active_challenges(
    db: Session,
    child_user_id: str,
    family_id: str,
) -> list[ChallengeGrant]:
    """List active challenges for a child (for child app display)."""
    return (
        db.query(ChallengeGrant)
        .filter(
            ChallengeGrant.child_user_id == child_user_id,
            ChallengeGrant.family_id == family_id,
            ChallengeGrant.status == "active",
        )
        .order_by(ChallengeGrant.deadline.asc())
        .all()
    )
