"""Seed additional test data for UI audit skipped cases.

Populates data gaps identified in tests/reports/ui-audit-2026-10-13.md:
- C16.3: Beijing topics with multiple curriculum_standards
- C16.10: en-US child user for demouser's family
- C17.6: Locked progress records for 小宝 (prerequisites not met)
- C17.17-19: High age_group topic with unmet prereqs (already exists — verified)
- C17.21: Beijing topic with name_zh cleared (untranslated)

Run from server/ directory:
    uv run python scripts/seed_audit_test_data.py
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from apps.backend.app.database import SessionLocal
from apps.backend.app.models.user import User
from apps.backend.app.services.auth import hash_password
from packages.core.snowflake import next_id
from packages.db.models.learning.progress import LearningProgress
from packages.db.models.learning.topic import LearningDependency, LearningTopic


def seed_multi_standard_topics(db) -> int:
    """C16.3: Add multiple curriculum_standards to a few Beijing topics.

    The audit found 0 Beijing topics with >=2 standards. Pick 3 topics
    that already have 1 standard and duplicate it with a different code.
    """
    topics = db.query(LearningTopic).filter(
        LearningTopic.source_taxonomy == "beijing",
        LearningTopic.deprecated == False,  # noqa: E712
        LearningTopic.curriculum_standards_json.isnot(None),
    ).all()

    # Find topics with exactly 1 standard
    single_std_topics = []
    for t in topics:
        stds = json.loads(t.curriculum_standards_json or "[]")
        if len(stds) == 1:
            single_std_topics.append(t)

    if not single_std_topics:
        print("  WARNING: No Beijing topics with exactly 1 standard found")
        return 0

    updated = 0
    for t in single_std_topics[:3]:
        stds = json.loads(t.curriculum_standards_json)
        original = stds[0]
        # Create a second standard entry with a different code
        second = {
            "key": original.get("key", "") + "_extra",
            "name": original.get("name", "课程标准"),
            "code": "X" + original.get("code", "00")[1:] if original.get("code") else "X00",
        }
        stds.append(second)
        t.curriculum_standards_json = json.dumps(stds, ensure_ascii=False)
        updated += 1
        print(f"  Updated {t.topic_key} ({t.name_zh or t.name}): {len(stds)} standards")

    db.flush()
    return updated


def seed_en_us_child(db) -> User | None:
    """C16.10: Create an en-US child for demouser's family.

    Creates a child user with language='en-US' so the backend filters
    topics by source_taxonomy='os-taxonomy' for this child.
    """
    demouser = db.query(User).filter_by(username="demouser").first()
    if not demouser:
        print("  ERROR: demouser not found")
        return None

    # Check if en-US child already exists
    existing = (
        db.query(User)
        .filter_by(family_id=demouser.family_id, role="child", language="en-US")
        .first()
    )
    if existing:
        print(f"  en-US child already exists: {existing.display_name} (id={existing.id})")
        return existing

    child_id = next_id()
    child = User(
        id=child_id,
        username="EN_child",
        display_name="Emma",
        password_hash=hash_password("ChildPass123"),
        family_id=demouser.family_id,
        role="child",
        language="en-US",
        is_active=True,
        pin_hash=hash_password("1234"),  # simple PIN for testing
    )
    db.add(child)
    db.flush()
    print(f"  Created en-US child: Emma (id={child_id})")
    return child


def seed_locked_progress(db) -> int:
    """C17.6: Create locked progress records for 小宝.

    小宝 currently has mastered (1) and assessing (10) records but no
    locked ones. Find topics with hard prerequisites that 小宝 hasn't
    mastered and create locked progress entries.
    """
    demouser = db.query(User).filter_by(username="demouser").first()
    if not demouser:
        print("  ERROR: demouser not found")
        return 0

    xiaobao = (
        db.query(User)
        .filter_by(family_id=demouser.family_id, role="child")
        .order_by(User.id)
        .first()
    )
    if not xiaobao:
        print("  ERROR: No child found for demouser's family")
        return 0

    # Get mastered topic IDs
    mastered_ids = set(
        r[0]
        for r in db.query(LearningProgress.topic_id).filter_by(
            child_id=xiaobao.id, mastery_level="mastered"
        ).all()
    )

    # Get all topic IDs xiaobao already has progress for
    existing_topic_ids = set(
        r[0]
        for r in db.query(LearningProgress.topic_id)
        .filter_by(child_id=xiaobao.id)
        .all()
    )

    # Find Beijing topics with hard prereqs where prereq is NOT mastered
    candidates = (
        db.query(LearningTopic)
        .filter(
            LearningTopic.source_taxonomy == "beijing",
            LearningTopic.deprecated == False,  # noqa: E712
            ~LearningTopic.id.in_(existing_topic_ids),
        )
        .limit(200)
        .all()
    )

    locked_count = 0
    for topic in candidates:
        if locked_count >= 3:
            break
        hard_deps = (
            db.query(LearningDependency)
            .filter_by(topic_id=topic.id, strength="hard")
            .all()
        )
        if not hard_deps:
            continue
        # Check if at least one prereq is unmet
        unmet = [d for d in hard_deps if d.prerequisite_id not in mastered_ids]
        if not unmet:
            continue
        # Create locked progress
        progress = LearningProgress(
            id=next_id(),
            child_id=xiaobao.id,
            topic_id=topic.id,
            mastery_level="locked",
            mastery_score=0.0,
        )
        db.add(progress)
        locked_count += 1
        print(
            f"  Locked: {topic.topic_key} ({topic.name_zh or topic.name}) "
            f"— {len(unmet)} unmet hard prereqs"
        )

    db.flush()
    return locked_count


def seed_untranslated_topic(db) -> int:
    """C17.21: Clear name_zh for one Beijing topic to test translation button.

    Pick a low-centrality topic so it doesn't affect normal usage.
    """
    topic = (
        db.query(LearningTopic)
        .filter(
            LearningTopic.source_taxonomy == "beijing",
            LearningTopic.deprecated == False,  # noqa: E712
            LearningTopic.name_zh.isnot(None),
            LearningTopic.name_zh != "",
        )
        .order_by(LearningTopic.centrality.asc().nullslast())
        .first()
    )

    if not topic:
        print("  WARNING: No Beijing topic with name_zh found")
        return 0

    original_zh = topic.name_zh
    topic.name_zh = None
    topic.description_zh = None
    db.flush()
    print(f"  Cleared zh for {topic.topic_key} (was: {original_zh})")
    return 1


def verify_data_gaps(db) -> None:
    """Print current state of data gaps for reference."""
    print("\n=== Pre-seed verification ===")

    # C16.2: Topics without standards
    no_std = (
        db.query(LearningTopic)
        .filter(
            LearningTopic.curriculum_standards_json.in_(["[]", "null", None])
        )
        .count()
    )
    print(f"  C16.2 — Topics without standards: {no_std}")

    # C16.3: Multi-standard Beijing topics
    beijing = db.query(LearningTopic).filter_by(
        source_taxonomy="beijing", deprecated=False
    ).all()
    multi = sum(
        1 for t in beijing
        if len(json.loads(t.curriculum_standards_json or "[]")) >= 2
    )
    print(f"  C16.3 — Beijing topics with >=2 standards: {multi}")

    # C16.10: en-US children
    demouser = db.query(User).filter_by(username="demouser").first()
    en_us = (
        db.query(User)
        .filter_by(family_id=demouser.family_id, role="child", language="en-US")
        .count()
    )
    print(f"  C16.10 — en-US children in demouser family: {en_us}")

    # C17.6: Locked progress for xiaobao
    xiaobao = (
        db.query(User)
        .filter_by(family_id=demouser.family_id, role="child")
        .order_by(User.id)
        .first()
    )
    locked = (
        db.query(LearningProgress)
        .filter_by(child_id=xiaobao.id, mastery_level="locked")
        .count()
    )
    print(f"  C17.6 — Locked progress for {xiaobao.display_name}: {locked}")

    # C17.21: Untranslated Beijing topics
    no_zh = (
        db.query(LearningTopic)
        .filter(
            LearningTopic.source_taxonomy == "beijing",
            LearningTopic.deprecated == False,  # noqa: E712
            (LearningTopic.name_zh.is_(None)) | (LearningTopic.name_zh == ""),
        )
        .count()
    )
    print(f"  C17.21 — Beijing topics without name_zh: {no_zh}")


def main():
    print("=" * 60)
    print("Seeding UI audit test data...")
    print("=" * 60)

    db = SessionLocal()
    try:
        verify_data_gaps(db)

        print("\n[1] C16.3 — Multi-standard topics...")
        n = seed_multi_standard_topics(db)
        print(f"  → {n} topics updated")

        print("\n[2] C16.10 — en-US child...")
        child = seed_en_us_child(db)
        print(f"  → {'created' if child else 'skipped'}")

        print("\n[3] C17.6 — Locked progress...")
        n = seed_locked_progress(db)
        print(f"  → {n} locked records created")

        print("\n[4] C17.21 — Untranslated topic...")
        n = seed_untranslated_topic(db)
        print(f"  → {n} topic(s) cleared")

        db.commit()

        print("\n" + "=" * 60)
        print("Post-seed verification:")
        verify_data_gaps(db)
        print("=" * 60)
        print("\nDone! Skipped cases now have test data:")
        print("  C16.2  → 2844+ topics without standards (pre-existing)")
        print("  C16.3  → 3 Beijing topics with multiple standards")
        print("  C16.10 → en-US child 'Emma' (login: EN_child / ChildPass123)")
        print("  C17.3  → 大宝 has 0 progress (pre-existing)")
        print("  C17.6  → 3 locked topics for 小宝")
        print("  C17.17 → high age_group topics exist (physics, info tech)")
        print("  C17.18 → topic mtc_055 has unmet hard prereqs (pre-existing)")
        print("  C17.21 → 1 Beijing topic with name_zh cleared")

    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
