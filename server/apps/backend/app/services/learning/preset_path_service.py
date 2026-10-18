"""Preset learning path service — generation, assignment, and listing."""

from __future__ import annotations

import json

from sqlalchemy import or_
from sqlalchemy.orm import Session

from packages.core.logging import get_logger
from packages.db.models.learning.path import LearningPath, LearningPathItem
from packages.db.models.learning.preset_path import PresetLearningPath
from packages.db.models.learning.topic import LearningDependency, LearningTopic

from .path_service import sort_topics_by_prerequisites

logger = get_logger(__name__)

# Age group to grade mapping
AGE_GROUP_TO_GRADE = {
    "low": (1, 2),  # ages 6-8
    "mid": (3, 4),  # ages 9-10
    "high": (5, 6),  # ages 11-12
}

# Semester determination based on topic position (simplified heuristic)
SEMESTER_OPTIONS = ["fall", "spring"]


def generate_preset_paths(db: Session) -> list[PresetLearningPath]:
    """Generate preset paths from topics with curriculum_standards_json.

    Groups topics by (age_group mapped to grade, subject), sorts by dependencies,
    and creates preset paths. Clears existing presets before regeneration.

    Returns: list of created PresetLearningPath objects.
    """
    # Clear existing presets (regeneration strategy)
    db.query(PresetLearningPath).delete()
    db.flush()

    # Find all topics with curriculum standards
    topics_with_curriculum = (
        db.query(LearningTopic)
        .filter(
            LearningTopic.deprecated == False,  # noqa: E712
            LearningTopic.curriculum_standards_json.isnot(None),
            LearningTopic.curriculum_standards_json != "[]",
            LearningTopic.curriculum_standards_json != "",
        )
        .all()
    )

    if not topics_with_curriculum:
        logger.info("No topics with curriculum standards found")
        return []

    # Group topics by (grade_range, subject)
    groups: dict[tuple[tuple[int, int], str], list[int]] = {}
    for topic in topics_with_curriculum:
        grade_range = AGE_GROUP_TO_GRADE.get(topic.age_group, (3, 4))
        key = (grade_range, topic.subject)
        groups.setdefault(key, []).append(topic.id)

    # Create preset paths for each group
    created_paths: list[PresetLearningPath] = []

    for (grade_range, subject), topic_ids in groups.items():
        if not topic_ids:
            continue

        # Sort topics by prerequisites
        sorted_topic_ids = sort_topics_by_prerequisites(db, topic_ids)

        # Load topics for metadata
        topics = {
            t.id: t
            for t in db.query(LearningTopic)
            .filter(LearningTopic.id.in_(sorted_topic_ids))
            .all()
        }

        # Create preset for each semester (simplified: distribute topics evenly)
        for semester in SEMESTER_OPTIONS:
            # Split topics roughly in half for each semester
            mid = len(sorted_topic_ids) // 2
            if semester == "fall":
                semester_topic_ids = sorted_topic_ids[:mid] if mid > 0 else sorted_topic_ids
            else:  # spring
                semester_topic_ids = sorted_topic_ids[mid:] if mid > 0 else sorted_topic_ids

            if not semester_topic_ids:
                continue

            # Build name from first topic
            first_topic = topics.get(semester_topic_ids[0])
            grade_min, grade_max = grade_range
            grade_label = f"{grade_min}-{grade_max}"

            # Determine age_group from topics
            age_groups = {topics[tid].age_group for tid in semester_topic_ids if tid in topics}
            age_group = next(iter(age_groups), "mid")

            # Determine source_taxonomy
            taxonomies = {topics[tid].source_taxonomy for tid in semester_topic_ids if tid in topics}
            source_taxonomy = next(iter(taxonomies), "os-taxonomy")

            preset = PresetLearningPath(
                grade=grade_min,  # Use minimum grade in range
                semester=semester,
                subject=subject,
                name=f"Grade {grade_label} {semester.title()} · {subject.title()}",
                name_zh=f"{grade_min}-{grade_max}年级 {semester} · {subject}",
                description=f"Preset learning path for {subject} ({grade_label} {semester})",
                topic_ids_json=json.dumps(semester_topic_ids),
                topic_count=len(semester_topic_ids),
                age_group=age_group,
                source_taxonomy=source_taxonomy,
                is_active=True,
            )
            db.add(preset)
            created_paths.append(preset)

    db.commit()

    # Refresh all created paths
    for preset in created_paths:
        db.refresh(preset)

    logger.info("Generated %d preset learning paths", len(created_paths))
    return created_paths


def assign_preset_path(
    db: Session,
    preset_id: int,
    child_id: int,
    parent_id: int,
) -> LearningPath:
    """Create a LearningPath + LearningPathItems from a preset.

    Args:
        db: Database session
        preset_id: ID of the preset to assign
        child_id: ID of the child receiving the path
        parent_id: ID of the parent creating the path

    Returns:
        Created LearningPath with items
    """
    from apps.backend.app.errors import AppError, ErrorCode

    # Load preset
    preset = db.query(PresetLearningPath).filter(PresetLearningPath.id == preset_id).first()
    if not preset:
        raise AppError(ErrorCode.LEARNING_PATH_NOT_FOUND, details={"preset_id": str(preset_id)})

    if not preset.is_active:
        raise AppError(
            ErrorCode.LEARNING_PATH_NOT_FOUND,
            details={"reason": "preset is not active", "preset_id": str(preset_id)},
        )

    # Get child's family_id
    from packages.db.models.user import User

    child = db.query(User).filter(User.id == child_id).first()
    if not child:
        raise AppError(ErrorCode.USER_NOT_FOUND, details={"child_id": str(child_id)})

    family_id = child.family_id

    # Parse topic IDs
    topic_ids = json.loads(preset.topic_ids_json)

    # Create LearningPath
    path = LearningPath(
        family_id=family_id,
        child_id=child_id,
        created_by=parent_id,
        name=preset.name,
        name_zh=preset.name_zh,
        description=preset.description or "",
        per_task_score=5,
        bonus_score=10,
        milestone_scores_json="[]",
    )
    db.add(path)
    db.flush()  # Get path.id

    # Create LearningPathItems
    for order, topic_id in enumerate(topic_ids):
        item = LearningPathItem(
            path_id=path.id,
            topic_id=topic_id,
            sort_order=order,
            status="pending",
        )
        db.add(item)

    db.commit()
    db.refresh(path)

    logger.info(
        "Assigned preset %s to child %s → path %s with %d items",
        preset_id,
        child_id,
        path.id,
        len(topic_ids),
    )

    return path


def list_preset_paths(
    db: Session,
    grade: int | None,
    semester: str | None,
    subject: str | None,
) -> list[PresetLearningPath]:
    """List preset paths with optional filters.

    Args:
        db: Database session
        grade: Filter by grade (1-6)
        semester: Filter by semester ("fall" | "spring")
        subject: Filter by subject (e.g., "mathematics", "chinese")

    Returns:
        List of PresetLearningPath objects matching filters
    """
    query = db.query(PresetLearningPath).filter(PresetLearningPath.is_active == True)  # noqa: E712

    if grade is not None:
        query = query.filter(PresetLearningPath.grade == grade)

    if semester is not None:
        query = query.filter(PresetLearningPath.semester == semester)

    if subject is not None:
        query = query.filter(PresetLearningPath.subject == subject)

    return query.order_by(PresetLearningPath.grade, PresetLearningPath.semester).all()
