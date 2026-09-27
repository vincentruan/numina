"""Learning path service — CRUD, topological sort, reward computation, coin emission."""

from __future__ import annotations

import os
from collections import deque
from datetime import UTC, date, datetime

from sqlalchemy import func
from sqlalchemy.orm import Session

from packages.db.models.child_economy.coin_transaction import CoinTransaction
from packages.db.models.learning.assignment import LearningAssignment
from packages.db.models.learning.path import LearningPath, LearningPathItem
from packages.db.models.learning.topic import LearningDependency, LearningTopic


def sort_topics_by_prerequisites(
    db: Session, topic_ids: list[int]
) -> list[int]:
    """Topological sort of topics based on prerequisite dependencies.

    Uses Kahn's algorithm with transitive-closure edge projection: even when
    intermediate topics are absent from *topic_ids*, ordering constraints they
    impose are preserved.  Only considers dependencies relevant to the given
    topic_ids.
    """
    if len(topic_ids) <= 1:
        return list(topic_ids)

    topic_set = set(topic_ids)

    # Load all dependency edges — the full graph is small (learning taxonomy)
    # and we need intermediate nodes outside topic_set for transitive ordering.
    all_deps = db.query(LearningDependency).all()

    # Build in-memory adjacency: prerequisite -> [topics that require it]
    prereq_forward: dict[int, list[int]] = {}
    # Also build reverse: topic -> [its direct prerequisites]
    topic_prereqs: dict[int, list[int]] = {}
    for dep in all_deps:
        prereq_forward.setdefault(dep.prerequisite_id, []).append(dep.topic_id)
        topic_prereqs.setdefault(dep.topic_id, []).append(dep.prerequisite_id)

    # For each topic in the set, backward-BFS through prereq_forward edges
    # (reversed) to find which other set-members are its transitive prerequisites.
    # effective_prereqs[tid] = set of topics in topic_set that must come before tid
    effective_prereqs: dict[int, set[int]] = {tid: set() for tid in topic_ids}

    for tid in topic_ids:
        visited: set[int] = set()
        queue = deque(topic_prereqs.get(tid, []))
        while queue:
            p = queue.popleft()
            if p in visited:
                continue
            visited.add(p)
            if p in topic_set:
                effective_prereqs[tid].add(p)
            # Continue BFS upward through p's prerequisites
            for pp in topic_prereqs.get(p, []):
                if pp not in visited:
                    queue.append(pp)

    # Build Kahn's graph using only effective (within-set) edges
    in_degree: dict[int, int] = {tid: 0 for tid in topic_ids}
    adjacency: dict[int, list[int]] = {tid: [] for tid in topic_ids}

    for tid, prereqs in effective_prereqs.items():
        for prereq in prereqs:
            adjacency[prereq].append(tid)
            in_degree[tid] += 1

    queue = deque(tid for tid in topic_ids if in_degree[tid] == 0)
    result: list[int] = []

    while queue:
        node = queue.popleft()
        result.append(node)
        for neighbor in adjacency[node]:
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                queue.append(neighbor)

    # Append any remaining (cyclic) topics at the end
    remaining = [tid for tid in topic_ids if tid not in result]
    result.extend(remaining)

    return result


def compute_path_rewards(
    path: LearningPath,
    completed_count: int,
    total_count: int,
) -> dict:
    """Compute reward breakdown for a path item completion.

    Returns: {
        "per_task": int,
        "milestone": int | None,
        "completion": int | None,
    }
    """
    rewards: dict = {
        "per_task": path.per_task_score,
        "milestone": None,
        "completion": None,
    }

    milestones = path.milestone_scores or []
    for entry in milestones:
        if completed_count == entry["threshold"]:
            rewards["milestone"] = entry["bonus"]
            break

    if completed_count == total_count:
        rewards["completion"] = path.bonus_score

    return rewards


def create_path(
    db: Session,
    *,
    family_id: int,
    child_id: int,
    created_by: int,
    name: str,
    name_zh: str | None = None,
    description: str = "",
    description_zh: str | None = None,
    topic_ids: list[int],
    per_task_score: int = 5,
    bonus_score: int = 10,
    milestone_scores: list[dict] | None = None,
    due_date: date | None = None,
) -> LearningPath:
    """Create a learning path with auto-sorted items and associated assignments."""
    # 1. Create the path record
    path = LearningPath(
        family_id=family_id,
        child_id=child_id,
        created_by=created_by,
        name=name,
        name_zh=name_zh,
        description=description,
        description_zh=description_zh,
        per_task_score=per_task_score,
        bonus_score=bonus_score,
        milestone_scores_json="[]",
        due_date=due_date,
    )
    if milestone_scores:
        path.milestone_scores = milestone_scores
    db.add(path)
    db.flush()  # get path.id

    # 2. Sort topics by prerequisite order
    sorted_ids = sort_topics_by_prerequisites(db, topic_ids)

    # 3. Create path items + assignments
    for order, tid in enumerate(sorted_ids):
        item = LearningPathItem(
            path_id=path.id,
            topic_id=tid,
            sort_order=order,
        )
        db.add(item)

        # Create assignment for notification/queue compatibility
        assignment = LearningAssignment(
            family_id=family_id,
            child_id=child_id,
            topic_id=tid,
            path_id=path.id,
            created_by=created_by,
            assignment_type="parent_assigned",
        )
        db.add(assignment)

    db.commit()
    db.refresh(path)
    return path


def _get_daily_learning_earned(db: Session, child_user_id: int, family_id: int) -> int:
    """Sum of learning-related coins earned today by this child."""
    today_start = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    result = (
        db.query(func.coalesce(func.sum(CoinTransaction.amount), 0))
        .filter(
            CoinTransaction.child_user_id == child_user_id,
            CoinTransaction.family_id == family_id,
            CoinTransaction.transaction_type.in_(
                ["learning_earn", "path_earn", "path_completion"]
            ),
            CoinTransaction.amount > 0,
            CoinTransaction.created_at >= today_start,
        )
        .scalar()
    )
    return int(result)


def advance_path_item(
    db: Session,
    path_id: int,
    topic_id: int,
    child_user_id: int,
    family_id: int,
) -> dict:
    """Mark a path item completed, compute rewards, emit coins.

    Idempotent: calling twice for the same topic returns early without emitting coins.
    Returns: {"item": LearningPathItem, "rewards": dict, "path": LearningPath}
    """
    DAILY_CAP = int(os.environ.get("DAILY_LEARNING_COIN_CAP", "50"))

    path = db.query(LearningPath).filter(LearningPath.id == path_id).first()
    if not path:
        from apps.backend.app.errors.codes import ErrorCode
        from apps.backend.app.errors.exceptions import AppError

        raise AppError(ErrorCode.LEARNING_PATH_NOT_FOUND)

    item = (
        db.query(LearningPathItem)
        .filter(
            LearningPathItem.path_id == path_id,
            LearningPathItem.topic_id == topic_id,
        )
        .first()
    )
    if not item:
        return {"item": None, "rewards": None, "path": path}

    # Idempotency: already completed — return early without emitting coins
    if item.status == "completed":
        return {"item": item, "rewards": None, "path": path}

    # Mark completed
    item.status = "completed"
    item.completed_at = datetime.now(UTC)

    # Count completions
    completed_count = (
        db.query(LearningPathItem)
        .filter(LearningPathItem.path_id == path_id, LearningPathItem.status == "completed")
        .count()
    )
    total_count = (
        db.query(LearningPathItem)
        .filter(LearningPathItem.path_id == path_id)
        .count()
    )

    rewards = compute_path_rewards(path, completed_count, total_count)
    daily_earned = _get_daily_learning_earned(db, child_user_id, family_id)
    remaining_cap = max(0, DAILY_CAP - daily_earned)

    # Get topic name for narrative
    topic = db.query(LearningTopic).filter(LearningTopic.id == topic_id).first()
    topic_label = topic.name_zh or topic.name if topic else f"topic:{topic_id}"

    # 1. Per-task coins
    per_task = min(rewards["per_task"], remaining_cap)
    if per_task > 0:
        tx = CoinTransaction(
            family_id=family_id,
            child_user_id=child_user_id,
            amount=per_task,
            transaction_type="path_earn",
            ref_id=item.id,
            narrative=f"路径任务：{topic_label}",
            narrative_emoji="📋",
        )
        db.add(tx)
        remaining_cap -= per_task

    # 2. Milestone coins (only if remaining_cap > 0 and milestone was hit)
    if rewards["milestone"] and remaining_cap > 0:
        milestone_amount = min(rewards["milestone"], remaining_cap)
        tx_ms = CoinTransaction(
            family_id=family_id,
            child_user_id=child_user_id,
            amount=milestone_amount,
            transaction_type="path_earn",
            ref_id=item.id,
            narrative=f"里程碑奖励：完成 {completed_count}/{total_count}",
            narrative_emoji="🏆",
        )
        db.add(tx_ms)
        remaining_cap -= milestone_amount

    # 3. Completion bonus
    if rewards["completion"] and remaining_cap > 0:
        completion_amount = min(rewards["completion"], remaining_cap)
        tx_cc = CoinTransaction(
            family_id=family_id,
            child_user_id=child_user_id,
            amount=completion_amount,
            transaction_type="path_completion",
            ref_id=path.id,
            narrative=f"路径完成奖励：{path.name}",
            narrative_emoji="🎉",
        )
        db.add(tx_cc)

    # Check if path is fully completed
    if completed_count == total_count:
        path.status = "completed"
        path.completed_at = datetime.now(UTC)

    db.commit()
    return {"item": item, "rewards": rewards, "path": path}


def get_path_progress(
    db: Session, path_id: int, family_id: int
) -> dict:
    """Get path progress with items, counts, and next milestone."""
    path = (
        db.query(LearningPath)
        .filter(LearningPath.id == path_id, LearningPath.family_id == family_id)
        .first()
    )
    if not path:
        from apps.backend.app.errors.codes import ErrorCode
        from apps.backend.app.errors.exceptions import AppError

        raise AppError(ErrorCode.LEARNING_PATH_NOT_FOUND)

    items = (
        db.query(LearningPathItem)
        .filter(LearningPathItem.path_id == path_id)
        .order_by(LearningPathItem.sort_order)
        .all()
    )

    completed_count = sum(1 for i in items if i.status == "completed")
    total_count = len(items)

    # Find next milestone
    next_milestone = None
    for entry in path.milestone_scores or []:
        if entry["threshold"] > completed_count:
            next_milestone = {
                "threshold": entry["threshold"],
                "bonus": entry["bonus"],
                "progress": f"{completed_count}/{entry['threshold']}",
            }
            break

    # Enrich items with topic names
    topic_ids = [i.topic_id for i in items]
    topics = {
        t.id: t
        for t in db.query(LearningTopic).filter(LearningTopic.id.in_(topic_ids)).all()
    }

    item_responses = []
    for i in items:
        t = topics.get(i.topic_id)
        item_responses.append({
            "id": i.id,
            "path_id": i.path_id,
            "topic_id": i.topic_id,
            "sort_order": i.sort_order,
            "status": i.status,
            "topic_name": t.name if t else None,
            "topic_name_zh": t.name_zh if t else None,
            "completed_at": i.completed_at,
        })

    return {
        "path": path,
        "items": item_responses,
        "completed_count": completed_count,
        "total_count": total_count,
        "next_milestone": next_milestone,
    }


def get_child_active_paths(
    db: Session, child_id: int, family_id: int
) -> list[LearningPath]:
    """List all active paths for a child. Validates family_id for tenant isolation."""
    return (
        db.query(LearningPath)
        .filter(
            LearningPath.child_id == child_id,
            LearningPath.family_id == family_id,
            LearningPath.status == "active",
        )
        .order_by(LearningPath.created_at.desc())
        .all()
    )


def try_advance_path_for_topic(
    db: Session, child_id: int, family_id: int, topic_id: int
) -> dict | None:
    """Check if topic belongs to an active path and advance it.

    Called when a topic is mastered via any path (self-selected, assessment, etc.)
    Returns the advance result or None if topic is not in any active path.
    """
    active_paths = get_child_active_paths(db, child_id, family_id)
    for path in active_paths:
        item = (
            db.query(LearningPathItem)
            .filter(
                LearningPathItem.path_id == path.id,
                LearningPathItem.topic_id == topic_id,
                LearningPathItem.status != "completed",
            )
            .first()
        )
        if item:
            return advance_path_item(
                db, path.id, topic_id, child_id, family_id
            )
    return None
