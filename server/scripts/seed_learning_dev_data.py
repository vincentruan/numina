#!/usr/bin/env python3
"""Seed learning dev data — populate question bank + bootstrap child progress.

Solves two dev/test blockers:
1. Questions table sparse → seed from all 62 templates
2. Challenge topics all locked → bootstrap root-topic mastery to cascade-unlock

Usage:
    cd server && uv run python scripts/seed_learning_dev_data.py
    cd server && uv run python scripts/seed_learning_dev_data.py --count 5
    cd server && uv run python scripts/seed_learning_dev_data.py --questions-only
    cd server && uv run python scripts/seed_learning_dev_data.py --progress-only
"""

import argparse
import sys
from collections import deque
from datetime import UTC, datetime
from pathlib import Path

# Ensure server/ is on sys.path so packages/apps resolve
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select  # noqa: E402

# Trigger @register_template decorators for all 62 templates
import packages.domain.question_templates  # noqa: E402, F401
from packages.core.logging import get_logger  # noqa: E402
from packages.db.models.learning.progress import LearningProgress  # noqa: E402
from packages.db.models.learning.topic import (  # noqa: E402
    LearningDependency,
    LearningTopic,
)
from packages.db.models.user import User  # noqa: E402
from packages.db.session import SessionLocal  # noqa: E402

logger = get_logger(__name__)


# ── Part 1: Question seeding ────────────────────────────────────────────


def seed_question_bank(db, count_per_template: int = 10) -> None:
    """Seed questions from all registered templates."""
    from apps.backend.app.services.learning.question_seeder import (
        seed_questions_from_templates,
    )

    result = seed_questions_from_templates(
        db, count_per_template=count_per_template
    )
    print(f"  Generated:        {result.generated}")
    print(f"  Skipped (dup):    {result.skipped_duplicate}")
    print(f"  Skipped (topic):  {result.skipped_no_topic}")
    print(f"  Failed:           {result.failed}")


# ── Part 2: Bootstrap child progress ────────────────────────────────────


def _find_root_topic_ids(db) -> list[int]:
    """Find topics with no hard prerequisites (root nodes in dep graph)."""
    hard_prereq_topic_ids = select(LearningDependency.topic_id).filter_by(
        strength="hard"
    )
    all_topic_ids = select(LearningTopic.id).filter(
        LearningTopic.deprecated.is_(False)
    )
    root_ids = all_topic_ids.except_(hard_prereq_topic_ids)
    return [row[0] for row in db.execute(root_ids).all()]


def _find_existing_child_ids(db) -> list[int]:
    """Find all child users."""
    return [
        row[0]
        for row in db.query(User.id).filter(User.role == "child").all()
    ]


def _build_hard_dep_forward_graph(db) -> dict[int, list[int]]:
    """Build prerequisite → [dependent_topics] map for hard edges only."""
    edges = (
        db.query(LearningDependency.prerequisite_id, LearningDependency.topic_id)
        .filter_by(strength="hard")
        .all()
    )
    fwd: dict[int, list[int]] = {}
    for prereq_id, dep_id in edges:
        fwd.setdefault(prereq_id, []).append(dep_id)
    return fwd


def _all_hard_prereqs_met(
    db, topic_id: int, mastered_set: set[int]
) -> bool:
    """Check if all hard prereqs of a topic are in the mastered set."""
    hard_prereqs = [
        row.prerequisite_id
        for row in db.query(LearningDependency.prerequisite_id)
        .filter_by(topic_id=topic_id, strength="hard")
        .all()
    ]
    if not hard_prereqs:
        return True
    return all(pid in mastered_set for pid in hard_prereqs)


def bootstrap_child_progress(db) -> None:
    """Master root topics for each child, then BFS cascade-unlock dependents."""
    root_topic_ids = _find_root_topic_ids(db)
    child_ids = _find_existing_child_ids(db)

    if not root_topic_ids:
        print("  No root topics found — run seed_learning_topics first")
        return
    if not child_ids:
        print("  No child users found — nothing to bootstrap")
        return

    print(f"  Root topics: {len(root_topic_ids)}")
    print(f"  Children:    {len(child_ids)}")

    # Build forward dependency graph once (shared across children)
    fwd = _build_hard_dep_forward_graph(db)

    total_mastered = 0
    total_available = 0

    for child_id in child_ids:
        # Load existing mastered set for this child
        mastered_set: set[int] = set(
            row.topic_id
            for row in db.query(LearningProgress.topic_id)
            .filter_by(child_id=child_id, mastery_level="mastered")
            .all()
        )

        # 1. Create mastered progress for root topics
        mastered_count = 0
        for topic_id in root_topic_ids:
            if topic_id in mastered_set:
                continue
            existing = (
                db.query(LearningProgress)
                .filter_by(child_id=child_id, topic_id=topic_id)
                .first()
            )
            if existing:
                continue
            progress = LearningProgress(
                child_id=child_id,
                topic_id=topic_id,
                mastery_level="mastered",
                mastery_score=1.0,
                completed_via="dev_seed",
                first_mastered_at=datetime.now(UTC),
            )
            db.add(progress)
            mastered_set.add(topic_id)
            mastered_count += 1

        db.flush()
        total_mastered += mastered_count

        # 2. BFS cascade: unlock all reachable dependents
        #    Start from all mastered topics, walk forward through hard deps
        queue: deque[int] = deque()
        visited: set[int] = set()

        # Seed queue with dependents of all mastered topics
        for tid in mastered_set:
            for dep_id in fwd.get(tid, []):
                if dep_id not in visited and dep_id not in mastered_set:
                    queue.append(dep_id)
                    visited.add(dep_id)

        available_count = 0
        while queue:
            dep_id = queue.popleft()
            # Check if all hard prereqs are now met
            if not _all_hard_prereqs_met(
                db, dep_id, mastered_set
            ):
                continue
            # Get or create progress and set to available
            existing = (
                db.query(LearningProgress)
                .filter_by(child_id=child_id, topic_id=dep_id)
                .first()
            )
            if existing is None:
                progress = LearningProgress(
                    child_id=child_id,
                    topic_id=dep_id,
                    mastery_level="available",
                )
                db.add(progress)
            elif existing.mastery_level == "locked":
                existing.mastery_level = "available"
            else:
                continue  # already available/learning/mastered
            mastered_set.add(dep_id)  # treat as "resolved" so we don't revisit
            available_count += 1
            # Enqueue further dependents
            for further_id in fwd.get(dep_id, []):
                if further_id not in visited and further_id not in mastered_set:
                    queue.append(further_id)
                    visited.add(further_id)

        db.flush()
        total_available += available_count

        print(
            f"  Child {child_id}: "
            f"+{mastered_count} mastered, +{available_count} unlocked"
        )

    # Summary
    locked_count = (
        db.query(LearningProgress)
        .filter(LearningProgress.mastery_level == "locked")
        .count()
    )
    available_count = (
        db.query(LearningProgress)
        .filter(LearningProgress.mastery_level == "available")
        .count()
    )
    print(f"  Total mastered (seed):  {total_mastered}")
    print(f"  Total newly available:  {total_available}")
    print(f"  Remaining locked:       {locked_count}")
    print(f"  Available to learn:     {available_count}")


# ── Main ────────────────────────────────────────────────────────────────


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Seed learning dev data (questions + child progress)"
    )
    parser.add_argument(
        "--count",
        type=int,
        default=10,
        help="Questions per template (default: 10)",
    )
    parser.add_argument(
        "--questions-only",
        action="store_true",
        help="Only seed questions, skip progress bootstrap",
    )
    parser.add_argument(
        "--progress-only",
        action="store_true",
        help="Only bootstrap progress, skip question seeding",
    )
    args = parser.parse_args()

    db = SessionLocal()
    try:
        if not args.questions_only:
            print("=== Bootstrap child progress ===")
            bootstrap_child_progress(db)

        if not args.progress_only:
            print("\n=== Seed question bank ===")
            seed_question_bank(db, count_per_template=args.count)

        db.commit()
        print("\n✓ Done (committed)")
        return 0
    except Exception:
        logger.exception("Seed failed")
        db.rollback()
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
