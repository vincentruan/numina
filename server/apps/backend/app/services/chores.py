"""Service layer for chore templates and instances."""

from datetime import datetime, timedelta
from typing import cast

from fastapi import HTTPException, status
from sqlalchemy import or_, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from apps.backend.app.errors import AppError, ErrorCode
from apps.backend.app.models.chore import (
    ChoreInstance,
    ChoreTemplate,
    chore_template_assignees,
)
from apps.backend.app.models.coin_transaction import CoinTransaction
from apps.backend.app.models.family import Family
from apps.backend.app.models.user import User
from apps.backend.app.schemas.chore import ChoreTemplateCreate, ChoreTemplateUpdate
from apps.backend.app.services.notification_bus import fire_notification

# ---------------------------------------------------------------------------
# Template CRUD
# ---------------------------------------------------------------------------

def create_template(db: Session, user: User, req: ChoreTemplateCreate) -> ChoreTemplate:
    """Create a chore template. Validates assignees belong to same family and are children."""
    if req.assignment_type == "assigned":
        if not req.assignee_ids:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "指定孩子分配方式必须选择至少一个孩子")
        _validate_assignees(db, user.family_id, req.assignee_ids)

    template = ChoreTemplate(
        family_id=user.family_id,
        created_by=user.id,
        name=req.name,
        emoji=req.emoji,
        coin_reward=req.coin_reward,
        frequency=req.frequency,
        assignment_type=req.assignment_type,
    )
    db.add(template)
    db.flush()  # get template.id before adding assignees

    if req.assignment_type == "assigned":
        for child_id in req.assignee_ids:
            db.execute(
                chore_template_assignees.insert().values(
                    template_id=template.id, child_user_id=child_id
                )
            )

    db.commit()
    db.refresh(template)
    return template


def list_templates(db: Session, user: User) -> list[ChoreTemplate]:
    return (
        db.query(ChoreTemplate)
        .filter(ChoreTemplate.family_id == user.family_id)
        .order_by(ChoreTemplate.frequency, ChoreTemplate.name)
        .all()
    )


def get_template(db: Session, user: User, template_id: str) -> ChoreTemplate:
    t = db.query(ChoreTemplate).filter(
        ChoreTemplate.id == template_id,
        ChoreTemplate.family_id == user.family_id,
    ).first()
    if not t:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "家务模板不存在")
    return t


def update_template(db: Session, user: User, template_id: str, req: ChoreTemplateUpdate) -> ChoreTemplate:
    t = get_template(db, user, template_id)
    if req.name is not None:
        t.name = req.name
    if req.emoji is not None:
        t.emoji = req.emoji
    if req.coin_reward is not None:
        t.coin_reward = req.coin_reward
    if req.assignee_ids is not None:
        _validate_assignees(db, user.family_id, req.assignee_ids)
        db.execute(
            chore_template_assignees.delete().where(
                chore_template_assignees.c.template_id == template_id
            )
        )
        for child_id in req.assignee_ids:
            db.execute(
                chore_template_assignees.insert().values(
                    template_id=template_id, child_user_id=child_id
                )
            )
    db.commit()
    db.refresh(t)
    return t


def toggle_template(db: Session, user: User, template_id: str, is_active: bool) -> ChoreTemplate:
    t = get_template(db, user, template_id)
    t.is_active = is_active
    db.commit()
    db.refresh(t)
    return t


def delete_template(db: Session, user: User, template_id: str) -> None:
    t = get_template(db, user, template_id)
    # Clear ORM relationship so SQLAlchemy doesn't cascade-delete already-removed rows
    t.assignees.clear()
    db.flush()
    db.delete(t)
    db.commit()


# ---------------------------------------------------------------------------
# Instance generation (on-demand, idempotent)
# ---------------------------------------------------------------------------

def _date_to_bucket(date_str: str, frequency: str) -> str:
    """Convert YYYY-MM-DD to date_bucket string."""
    d = datetime.strptime(date_str, "%Y-%m-%d").date()
    if frequency == "daily":
        return date_str
    else:  # weekly — ISO week format YYYY-Www
        return f"{d.isocalendar()[0]}-W{d.isocalendar()[1]:02d}"


def get_or_create_instances(db: Session, child_user: User, date_str: str) -> list[ChoreInstance]:
    """Return all chore instances visible to a child on a given date, creating missing ones.

    Returns:
    1. Instances where child_user_id == child.id (personal/claimed/hard-assigned)
    2. Instances where child_user_id == family_id AND assigned_by_user_id IS NULL (unclaimed pool)

    Does NOT return instances hard-assigned to a different child
    (child_user_id != child.id AND child_user_id != family_id, or
     child_user_id == family_id AND assigned_by_user_id IS NOT NULL pointing elsewhere).
    """
    # Find all active templates for this child
    templates = _get_templates_for_child(db, child_user)

    for template in templates:
        bucket = _date_to_bucket(date_str, template.frequency)
        # Pool chores use family_id as the instance owner so all children share one instance.
        # Assigned chores use the child's own user_id.
        owner_id = child_user.family_id if template.assignment_type == "pool" else child_user.id
        _get_or_create_instance(db, template, owner_id, child_user.family_id, bucket)

    # Now fetch all instances visible to this child:
    # - personal/claimed/hard-assigned: child_user_id == child.id
    # - unclaimed pool: child_user_id == family_id AND assigned_by_user_id IS NULL
    bucket_daily = date_str
    bucket_weekly = _date_to_bucket(date_str, "weekly")

    instances: list[ChoreInstance] = cast(
        list[ChoreInstance],
        db.query(ChoreInstance)
        .filter(
            ChoreInstance.family_id == child_user.family_id,
            ChoreInstance.date_bucket.in_([bucket_daily, bucket_weekly]),
            or_(
                ChoreInstance.child_user_id == child_user.id,
                (
                    (ChoreInstance.child_user_id == child_user.family_id)
                    & (ChoreInstance.assigned_by_user_id.is_(None))
                ),
            ),
        )
        .all()
    )

    # Set is_pool_unclaimed transient attribute on each instance
    for instance in instances:
        instance._is_pool_unclaimed = (
            instance.child_user_id == child_user.family_id
            and instance.assigned_by_user_id is None
        )

    return instances


def _get_templates_for_child(db: Session, child_user: User) -> list[ChoreTemplate]:
    """Get all active templates applicable to this child (assigned or pool)."""
    # Pool templates
    pool_templates = db.query(ChoreTemplate).filter(
        ChoreTemplate.family_id == child_user.family_id,
        ChoreTemplate.assignment_type == "pool",
        ChoreTemplate.is_active.is_(True),
    ).all()

    # Assigned templates for this child
    assigned_templates = (
        db.query(ChoreTemplate)
        .join(chore_template_assignees, ChoreTemplate.id == chore_template_assignees.c.template_id)
        .filter(
            ChoreTemplate.family_id == child_user.family_id,
            ChoreTemplate.assignment_type == "assigned",
            ChoreTemplate.is_active.is_(True),
            chore_template_assignees.c.child_user_id == child_user.id,
        )
        .all()
    )

    return pool_templates + assigned_templates


def _get_or_create_instance(
    db: Session,
    template: ChoreTemplate,
    child_user_id: str,
    family_id: str,
    bucket: str,
) -> ChoreInstance | None:
    """Idempotent: create instance or return existing one."""
    instance = ChoreInstance(
        template_id=template.id,
        family_id=family_id,
        child_user_id=child_user_id,
        chore_name=template.name,
        chore_emoji=template.emoji,
        coin_reward=template.coin_reward,
        date_bucket=bucket,
    )
    try:
        db.add(instance)
        db.flush()
        db.commit()
        db.refresh(instance)
        return instance
    except IntegrityError:
        db.rollback()
        return db.query(ChoreInstance).filter_by(
            template_id=template.id,
            child_user_id=child_user_id,
            date_bucket=bucket,
        ).first()


# ---------------------------------------------------------------------------
# Instance status transitions
# ---------------------------------------------------------------------------

def mark_complete(db: Session, child_user: User, instance_id: str) -> ChoreInstance:
    instance = _get_child_instance(db, child_user, instance_id)
    if instance.status != "available":
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "该家务实例当前不可标记完成")
    instance.status = "pending_approval"
    instance.submitted_at = datetime.utcnow()
    instance.submitted_by_user_id = child_user.id
    db.commit()
    db.refresh(instance)
    fire_notification(child_user.family_id, {
        "type": "chore_pending_approval",
        "instance_id": instance.id,
        "chore_name": instance.chore_name,
        "child_name": child_user.display_name,
        "message": f"{child_user.display_name} 完成了「{instance.chore_name}」，待审批",
    })
    return instance


async def approve_instance_async(db: Session, parent_user: User, instance_id: str) -> ChoreInstance:
    """Approve a chore instance atomically and write CoinTransaction."""
    from apps.backend.app.services.chore_narrative import generate_narrative

    instance = _get_family_instance(db, parent_user, instance_id)
    if instance.status != "pending_approval":
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "该实例不在待审批状态")

    # Atomic status transition — only succeeds if still pending_approval
    rows = db.execute(
        text(
            "UPDATE chore_instances SET status='approved', approved_at=:now "
            "WHERE id=:id AND status='pending_approval'"
        ),
        {"now": datetime.utcnow().isoformat(), "id": instance_id},
    )
    if rows.rowcount != 1:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "审批状态已变更，请刷新后重试")

    # Compute streak and multiplier
    streak = _compute_streak(db, instance)
    multiplier = _get_streak_multiplier(streak)
    actual_amount = int(instance.coin_reward * multiplier)
    bonus = actual_amount - instance.coin_reward
    db.execute(
        text("UPDATE chore_instances SET streak_count=:streak, streak_bonus=:bonus WHERE id=:id"),
        {"streak": streak, "bonus": bonus, "id": instance_id},
    )

    # Generate narrative before committing (async, 2s timeout, fallback on error)
    family = db.query(Family).filter(Family.id == parent_user.family_id).first()
    # For pool chores child_user_id == family_id; use submitted_by_user_id for the actual child
    coin_recipient_id = instance.submitted_by_user_id or instance.child_user_id
    child = db.query(User).filter(User.id == coin_recipient_id).first()
    if not family or not child:
        narrative, emoji = f"你完成了{instance.chore_name}！获得 {actual_amount} 颗星", "⭐"
    else:
        narrative, emoji = await generate_narrative(
            family, child.display_name, instance.chore_name, actual_amount, streak, multiplier
        )

    # Single commit: status + streak + CoinTransaction all atomic
    tx = CoinTransaction(
        family_id=parent_user.family_id,
        child_user_id=coin_recipient_id,
        amount=actual_amount,
        transaction_type="chore_earn",
        ref_id=instance_id,
        narrative=narrative,
        narrative_emoji=emoji,
        streak_bonus=bonus,
    )
    try:
        db.add(tx)
        db.commit()
    except IntegrityError:
        db.rollback()  # already written (idempotent)

    db.refresh(instance)

    # Check milestones after primary transaction — failure never blocks approval
    from apps.backend.app.services.milestones import check_and_record_milestones
    milestone = check_and_record_milestones(
        db, coin_recipient_id, parent_user.family_id,
        {"instance": instance},
    )
    instance._milestone_triggered = milestone  # transient attr for response

    fire_notification(parent_user.family_id, {
        "type": "chore_approved",
        "instance_id": instance_id,
        "chore_name": instance.chore_name,
        "coins_earned": actual_amount,
        "message": f"任务「{instance.chore_name}」已批准，获得 {actual_amount} 颗星币！",
        "target_user_id": coin_recipient_id,
    })

    return instance


def assign_instance(db: Session, parent_user: User, instance_id: str, target_child_id: str) -> ChoreInstance:
    """Assign (or reassign) a pool chore instance to a specific child.

    Works for both first-time assign (pool unclaimed) and reassign (already claimed/assigned).
    Status must be 'available'; target must be role=child in the same family.
    """
    instance = _get_family_instance(db, parent_user, instance_id)
    if instance.status != "available":
        raise AppError(ErrorCode.CHORE_INSTANCE_STATUS_CONFLICT)

    # Validate target child belongs to same family, has role=child, and is active
    target = db.query(User).filter(
        User.id == target_child_id,
        User.family_id == parent_user.family_id,
        User.is_active.is_(True),
    ).first()
    if not target:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "目标用户不存在或已禁用")
    if target.role != "child":
        raise AppError(ErrorCode.CHORE_ASSIGN_TARGET_INVALID)

    instance.child_user_id = target_child_id
    instance.assigned_by_user_id = parent_user.id
    instance.claimed_at = None
    db.commit()
    db.refresh(instance)
    return instance


def claim_instance(db: Session, child_user: User, instance_id: str) -> ChoreInstance:
    """Claim an unclaimed pool chore instance for this child.

    Concurrency-safe via SELECT FOR UPDATE (no-op on SQLite, serialized writes).
    Guard: instance must be visible to this child (child_user_id == family_id AND
    assigned_by_user_id IS NULL) and status must be 'available'.
    Raises 409 if already claimed by another child.
    """
    instance = (
        db.query(ChoreInstance)
        .filter(
            ChoreInstance.id == instance_id,
            ChoreInstance.family_id == child_user.family_id,
        )
        .with_for_update()
        .first()
    )
    if not instance:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "家务实例不存在")

    # Hard-assigned to a different child (assigned_by_user_id set, child_user_id != this child)
    # → invisible to this child, treat as 404
    if instance.assigned_by_user_id is not None and instance.child_user_id != child_user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "家务实例不存在")

    # Claimed by another child (child_user_id is a real child id, not family_id, not this child)
    # → visible but already taken, 409
    if instance.child_user_id != child_user.family_id and instance.child_user_id != child_user.id:
        raise AppError(ErrorCode.CHORE_ALREADY_CLAIMED)

    # Already claimed by this child or is their personal assigned chore — nothing to claim
    if instance.child_user_id == child_user.id:
        raise AppError(ErrorCode.CHORE_ALREADY_CLAIMED)

    # At this point: child_user_id == family_id AND assigned_by_user_id IS NULL → unclaimed pool
    # (the only remaining case)

    if instance.status != "available":
        raise AppError(ErrorCode.CHORE_INSTANCE_STATUS_CONFLICT)

    instance.child_user_id = child_user.id
    instance.claimed_at = datetime.utcnow()
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise AppError(ErrorCode.CHORE_INSTANCE_STATUS_CONFLICT)
    db.refresh(instance)
    return instance


def abandon_instance(db: Session, child_user: User, instance_id: str) -> ChoreInstance:
    """Abandon a claimed or hard-assigned chore instance, returning it to the pool.

    Guard: instance.child_user_id must equal child.id; status must be 'available'.
    Raises 409 otherwise.
    Effect: reset child_user_id to family_id, clear claimed_at and assigned_by_user_id.
    """
    instance = (
        db.query(ChoreInstance)
        .filter(
            ChoreInstance.id == instance_id,
            ChoreInstance.family_id == child_user.family_id,
        )
        .with_for_update()
        .first()
    )
    if not instance:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "家务实例不存在")

    if instance.child_user_id != child_user.id:
        raise AppError(ErrorCode.CHORE_NOT_YOURS)

    if instance.status != "available":
        raise AppError(ErrorCode.CHORE_INSTANCE_STATUS_CONFLICT)

    instance.child_user_id = child_user.family_id
    instance.claimed_at = None
    instance.assigned_by_user_id = None
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise AppError(ErrorCode.CHORE_INSTANCE_STATUS_CONFLICT)
    db.refresh(instance)
    fire_notification(child_user.family_id, {
        "type": "chore_abandoned",
        "instance_id": instance.id,
        "chore_name": instance.chore_name,
        "child_name": child_user.display_name,
        "message": f"{child_user.display_name} 放弃了「{instance.chore_name}」，任务已回到任务池",
    })
    return instance


def void_instance(db: Session, parent_user: User, instance_id: str) -> None:
    """Hard-delete a chore instance. Status must be 'available'."""
    instance = _get_family_instance(db, parent_user, instance_id)
    if instance.status != "available":
        raise AppError(ErrorCode.CHORE_INSTANCE_STATUS_CONFLICT)
    db.delete(instance)
    db.commit()


def reject_instance(db: Session, parent_user: User, instance_id: str, return_to_redo: bool = False) -> ChoreInstance:
    instance = _get_family_instance(db, parent_user, instance_id)
    if instance.status != "pending_approval":
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "该实例不在待审批状态")
    instance.status = "available" if return_to_redo else "rejected"
    db.commit()
    db.refresh(instance)
    recipient_id = instance.submitted_by_user_id or instance.child_user_id
    fire_notification(parent_user.family_id, {
        "type": "chore_rejected",
        "instance_id": instance_id,
        "chore_name": instance.chore_name,
        "message": f"任务「{instance.chore_name}」被退回，请重新完成。",
        "target_user_id": recipient_id,
    })
    return instance


def list_pending_approvals(db: Session, parent_user: User) -> list[ChoreInstance]:
    """Return pending approvals, triggering auto-approve for timed-out instances.

    Attaches child identity fields (_child_display_name, _child_avatar_color) to
    each instance so the response schema can expose them without a second query.
    """
    family = db.query(Family).filter(Family.id == parent_user.family_id).first()
    if family is None:
        return []

    from apps.backend.app.models.child_economy_config import ChildEconomyConfig
    economy = db.query(ChildEconomyConfig).filter_by(family_id=parent_user.family_id).first()
    auto_approve_hours = economy.auto_approve_hours if economy else 24
    pending = (
        db.query(ChoreInstance)
        .filter(
            ChoreInstance.family_id == parent_user.family_id,
            ChoreInstance.status == "pending_approval",
        )
        .order_by(ChoreInstance.submitted_at)
        .all()
    )

    now = datetime.utcnow()
    result = []
    for instance in pending:
        if (
            instance.submitted_at
            and instance.submitted_at + timedelta(hours=auto_approve_hours) <= now
        ):
            _auto_approve(db, instance, family)
        else:
            result.append(instance)

    # Batch-fetch child users to avoid N+1.
    # For pool chores child_user_id == family_id (not a real user), so always prefer
    # submitted_by_user_id when set; only fall back to child_user_id for assigned chores
    # where child_user_id is a real user ID.
    submitter_ids = {
        i.submitted_by_user_id if i.submitted_by_user_id else (
            i.child_user_id if i.child_user_id != i.family_id else None
        )
        for i in result
    } - {None}
    child_map: dict[str, User] = {}
    if submitter_ids:
        children = db.query(User).filter(User.id.in_(submitter_ids)).all()
        child_map = {u.id: u for u in children}

    for instance in result:
        # For pool chores child_user_id == family_id — use submitted_by_user_id instead
        lookup_id = instance.submitted_by_user_id or (
            instance.child_user_id if instance.child_user_id != instance.family_id else None
        )
        child = child_map.get(lookup_id) if lookup_id else None
        instance._child_display_name = child.display_name if child else None
        instance._child_avatar_color = child.avatar_color if child else None
        instance._child_user_id = lookup_id  # actual child's user ID (for pool chores)

    return result


def _auto_approve(db: Session, instance: ChoreInstance, family: Family) -> None:
    """Auto-approve a timed-out instance. Uses fixed narrative (no AI)."""
    rows = db.execute(
        text(
            "UPDATE chore_instances SET status='approved', approved_at=:now "
            "WHERE id=:id AND status='pending_approval'"
        ),
        {"now": datetime.utcnow().isoformat(), "id": instance.id},
    )
    if rows.rowcount != 1:
        return  # already processed

    streak = _compute_streak(db, instance)
    multiplier = _get_streak_multiplier(streak)
    actual_amount = int(instance.coin_reward * multiplier)
    bonus = actual_amount - instance.coin_reward
    db.execute(
        text("UPDATE chore_instances SET streak_count=:streak, streak_bonus=:bonus WHERE id=:id"),
        {"streak": streak, "bonus": bonus, "id": instance.id},
    )

    if multiplier >= 2.0:
        narrative = f"你完成了{instance.chore_name}！连续打卡双倍奖励，获得 {actual_amount} 颗星 🔥🔥"
    elif multiplier >= 1.5:
        narrative = f"你完成了{instance.chore_name}！连续打卡加成，获得 {actual_amount} 颗星 🔥"
    else:
        narrative = f"你完成了{instance.chore_name}！获得 {actual_amount} 颗星"
    # For pool chores child_user_id == family_id; use submitted_by_user_id for the actual child
    coin_recipient_id = instance.submitted_by_user_id or instance.child_user_id
    tx = CoinTransaction(
        family_id=family.id,
        child_user_id=coin_recipient_id,
        amount=actual_amount,
        transaction_type="chore_earn",
        ref_id=instance.id,
        narrative=narrative,
        narrative_emoji="🔥" if multiplier > 1.0 else "⭐",
        streak_bonus=bonus,
    )
    try:
        db.add(tx)
        db.commit()
    except IntegrityError:
        db.rollback()
        return

    db.refresh(instance)

    # Check milestones — failure never blocks auto-approve
    from apps.backend.app.services.milestones import check_and_record_milestones
    check_and_record_milestones(db, coin_recipient_id, family.id, {"instance": instance})


# ---------------------------------------------------------------------------
# streak_count computation
# ---------------------------------------------------------------------------


def _get_streak_multiplier(streak: int) -> float:
    """Return coin multiplier based on streak count."""
    if streak >= 14:
        return 2.0
    if streak >= 7:
        return 1.5
    return 1.0

def _compute_streak(db: Session, instance: ChoreInstance) -> int:
    """Compute streak count based on previous approved instances."""
    prev = (
        db.query(ChoreInstance)
        .filter(
            ChoreInstance.template_id == instance.template_id,
            ChoreInstance.child_user_id == instance.child_user_id,
            ChoreInstance.status == "approved",
            ChoreInstance.date_bucket < instance.date_bucket,
        )
        .order_by(ChoreInstance.date_bucket.desc())
        .first()
    )
    if not prev:
        return 1

    # Check if consecutive
    template = db.query(ChoreTemplate).filter(ChoreTemplate.id == instance.template_id).first()
    if _is_consecutive(prev.date_bucket, instance.date_bucket, template.frequency):
        return prev.streak_count + 1
    return 1


def _is_consecutive(prev_bucket: str, curr_bucket: str, frequency: str) -> bool:
    """Check if two date buckets are consecutive periods."""
    if frequency == "daily":
        prev_d = datetime.strptime(prev_bucket, "%Y-%m-%d").date()
        curr_d = datetime.strptime(curr_bucket, "%Y-%m-%d").date()
        return (curr_d - prev_d).days == 1
    else:  # weekly
        # Format: YYYY-Www — convert to a real Monday date for correct year-boundary arithmetic
        def parse_week(s: str):
            year, week = s.split("-W")
            return datetime.strptime(f"{year}-W{int(week):02d}-1", "%G-W%V-%u").date()
        prev_d = parse_week(prev_bucket)
        curr_d = parse_week(curr_bucket)
        return (curr_d - prev_d).days == 7


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _validate_assignees(db: Session, family_id: str, assignee_ids: list[str]) -> None:
    for uid in assignee_ids:
        user = db.query(User).filter(User.id == uid, User.family_id == family_id).first()
        if not user:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, f"用户 {uid} 不属于该家庭")
        if user.role != "child":
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, f"用户 {uid} 不是孩子角色")


def _get_child_instance(db: Session, child_user: User, instance_id: str) -> ChoreInstance:
    """Fetch a chore instance accessible to this child.

    Assigned chores use child_user_id = child.id.
    Pool chores use child_user_id = family_id (shared instance).
    Both are valid for a child to act on.
    """
    instance = db.query(ChoreInstance).filter(
        ChoreInstance.id == instance_id,
        ChoreInstance.family_id == child_user.family_id,
        or_(
            ChoreInstance.child_user_id == child_user.id,
            ChoreInstance.child_user_id == child_user.family_id,
        ),
    ).first()
    if not instance:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "家务实例不存在")
    return instance


def _get_family_instance(db: Session, parent_user: User, instance_id: str) -> ChoreInstance:
    instance = db.query(ChoreInstance).filter(
        ChoreInstance.id == instance_id,
        ChoreInstance.family_id == parent_user.family_id,
    ).first()
    if not instance:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "家务实例不存在")
    return instance
