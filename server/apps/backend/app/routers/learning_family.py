"""Family (parent) learning endpoints — manage children's learning."""

import contextlib
import json
from typing import Literal

import httpx
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import func as sa_func
from sqlalchemy.orm import Session

from apps.backend.app.auth.deps import require_adult
from apps.backend.app.database import SessionLocal, get_db
from apps.backend.app.errors import AppError, ErrorCode
from apps.backend.app.models.user import User
from apps.backend.app.schemas.learning import (
    AIReviewStatusResponse,
    AssignmentCreate,
    AssignmentResponse,
    BridgeResponse,
    CastleIndexResponse,
    ChildLearningOverview,
    ChildSessionLogResponse,
    ClusterResponse,
    ParentChildLearningStats,
    ParentPracticeSessionItem,
    ParentWeakTopicItem,
    PathCreate,
    PathResponse,
    ProgressResponse,
    RecommendationPathDetail,
    RecommendationPathResponse,
    RecommendedTopicItem,
    ReviewItemResponse,
    ReviewOverrideRequest,
    SmartTutorSessionDetailResponse,
    SmartTutorSessionResponse,
    TeachBackSessionDetailResponse,
    TopicResponse,
)
from apps.backend.app.services.learning import (
    assignment_service,
    castle_service,
    path_service,
    practice_service,
    progress_service,
    stats_service,
)
from apps.backend.app.services.learning.recommendation_service import (
    generate_recommendation_path,
)
from apps.backend.app.services.learning.topic_service import (
    get_cross_subject_bridges,
    get_effective_source_taxonomy,
    list_clusters_with_topic_counts,
)
from apps.backend.app.services.notification.dispatcher import (
    notify_learning_approved,
    notify_learning_assignment_created,
    notify_learning_rejected,
)
from packages.db.models.learning.assignment import LearningAssignment
from packages.db.models.learning.path import LearningPath
from packages.db.models.learning.progress import LearningProgress
from packages.db.models.learning.session import LearningSession
from packages.db.models.learning.stats import ChildLearningStats
from packages.db.models.learning.topic import LearningTopic

router = APIRouter(prefix="/family/learning", tags=["learning-family"])


def _require_family_child(db: Session, child_id: int, user: User) -> User:
    """Load a child that belongs to the caller's family, or raise 404.

    The child row is returned so callers pass ``child.id`` to services —
    never the parent's own ``user.id``, which would read the parent's data.
    """
    child = (
        db.query(User)
        .filter(User.id == child_id, User.family_id == user.family_id, User.role == "child")
        .first()
    )
    if not child:
        raise AppError(ErrorCode.AUTH_CHILD_NOT_FOUND)
    return child


@router.get("/children", response_model=list[ChildLearningOverview])
def list_children(
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    """List children in the family with their learning overview."""
    children = (
        db.query(User)
        .filter(User.family_id == user.family_id, User.role == "child")
        .all()
    )
    if not children:
        return []

    child_ids = [c.id for c in children]

    # Batch progress overview: single GROUP BY query
    overview_rows = (
        db.query(
            LearningProgress.child_id,
            LearningProgress.mastery_level,
            sa_func.count(LearningProgress.id).label("cnt"),
        )
        .filter(LearningProgress.child_id.in_(child_ids))
        .group_by(LearningProgress.child_id, LearningProgress.mastery_level)
        .all()
    )
    # Build per-child overview dicts
    overviews: dict[int, dict[str, int]] = {cid: {} for cid in child_ids}
    for row in overview_rows:
        overviews[row.child_id][row.mastery_level] = row.cnt

    # Batch study time: single GROUP BY query (exclude in-progress sessions)
    study_rows = (
        db.query(
            LearningSession.child_id,
            sa_func.coalesce(sa_func.sum(LearningSession.duration_seconds), 0),
        )
        .filter(
            LearningSession.child_id.in_(child_ids),
            LearningSession.ended_at.isnot(None),
        )
        .group_by(LearningSession.child_id)
        .all()
    )
    study_seconds = {row.child_id: int(row[1]) for row in study_rows}

    # Batch stats: single query for all children
    stats_rows = (
        db.query(ChildLearningStats)
        .filter(ChildLearningStats.child_id.in_(child_ids))
        .all()
    )
    stats_map = {s.child_id: s for s in stats_rows}

    result = []
    for child in children:
        ov = overviews.get(child.id, {})
        stats = stats_map.get(child.id)
        level_info = stats_service.get_level_info(stats.level) if stats else stats_service.get_level_info(1)
        result.append(
            ChildLearningOverview(
                child_id=child.id,
                child_name=child.display_name or child.username or "",
                mastered_count=ov.get("mastered", 0),
                learning_count=ov.get("learning", 0),
                available_count=ov.get("available", 0),
                locked_count=ov.get("locked", 0),
                review_count=ov.get("review", 0),
                total_study_minutes=study_seconds.get(child.id, 0) // 60,
                cumulative_xp=stats.cumulative_xp if stats else 0,
                level=stats.level if stats else 1,
                level_name_zh=level_info["name_zh"],
                learning_streak_days=stats.learning_streak_days if stats else 0,
                current_zone=stats.current_zone if stats else "growth",
            )
        )
    return result


@router.get("/children/{child_id}/map", response_model=list[ProgressResponse])
def get_child_map(
    child_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    """Get child's knowledge map with mastery levels.

    Locale filter applied: progress rows for topics that no longer belong
    to the parent's source taxonomy are hidden.
    """
    # Verify child belongs to this family
    child = (
        db.query(User)
        .filter(User.id == child_id, User.family_id == user.family_id, User.role == "child")
        .first()
    )
    if not child:
        raise AppError(ErrorCode.AUTH_CHILD_NOT_FOUND)

    taxonomy = get_effective_source_taxonomy(db, user.language)
    return (
        db.query(LearningProgress)
        .outerjoin(LearningTopic, LearningTopic.id == LearningProgress.topic_id)
        .filter(
            LearningProgress.child_id == child_id,
            LearningTopic.source_taxonomy == taxonomy,
        )
        .all()
    )


@router.get("/children/{child_id}/progress", response_model=list[ProgressResponse])
def get_child_progress(
    child_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    """Get child's progress details.

    Locale filter applied: progress rows for topics that no longer belong
    to the parent's source taxonomy are hidden.
    """
    child = (
        db.query(User)
        .filter(User.id == child_id, User.family_id == user.family_id, User.role == "child")
        .first()
    )
    if not child:
        raise AppError(ErrorCode.AUTH_CHILD_NOT_FOUND)

    taxonomy = get_effective_source_taxonomy(db, user.language)
    return (
        db.query(LearningProgress)
        .outerjoin(LearningTopic, LearningTopic.id == LearningProgress.topic_id)
        .filter(
            LearningProgress.child_id == child_id,
            LearningTopic.source_taxonomy == taxonomy,
        )
        .order_by(LearningProgress.updated_at.desc())
        .all()
    )


@router.get("/children/{child_id}/sessions", response_model=list[ChildSessionLogResponse])
def get_child_sessions(
    child_id: int,
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    """Get child's recent learning sessions for parent review."""
    child = (
        db.query(User)
        .filter(User.id == child_id, User.family_id == user.family_id, User.role == "child")
        .first()
    )
    if not child:
        raise AppError(ErrorCode.AUTH_CHILD_NOT_FOUND)

    sessions = (
        db.query(LearningSession)
        .filter(LearningSession.child_id == child_id)
        .order_by(LearningSession.started_at.desc())
        .limit(limit)
        .all()
    )

    # Batch-fetch topic names
    topic_ids = list({s.topic_id for s in sessions})
    # Locale filter applied: session log topics scoped to parent's taxonomy.
    taxonomy = get_effective_source_taxonomy(db, user.language)
    topics = (
        db.query(LearningTopic)
        .filter(
            LearningTopic.id.in_(topic_ids),
            LearningTopic.source_taxonomy == taxonomy,
        )
        .all()
    ) if topic_ids else []
    topic_map = {t.id: t for t in topics}

    result = []
    for s in sessions:
        topic = topic_map.get(s.topic_id)
        result.append(
            ChildSessionLogResponse(
                session_id=s.id,
                topic_id=s.topic_id,
                topic_name=topic.name if topic else "",
                topic_name_zh=topic.name_zh if topic else None,
                session_type=s.session_type,
                score=s.score,
                duration_seconds=s.duration_seconds,
                started_at=s.started_at,
                ended_at=s.ended_at,
            )
        )
    return result


@router.get("/children/{child_id}/learning-stats", response_model=ParentChildLearningStats)
def get_child_learning_stats(
    child_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    """Get child's learning stats for parent view."""
    child = _require_family_child(db, child_id, user)

    # Read-only path: list_children already handles a missing stats row with
    # sensible defaults, and get_or_create_stats would INSERT+commit as a side
    # effect of a GET — keep the write path reserved for XP awards.
    stats = (
        db.query(ChildLearningStats)
        .filter(ChildLearningStats.child_id == child.id)
        .first()
    )
    level = stats.level if stats else 1
    level_info = stats_service.get_level_info(level)
    overview = progress_service.get_child_progress_overview(db, child.id)
    minutes = progress_service.aggregate_study_minutes(db, child.id)

    return ParentChildLearningStats(
        child_id=child.id,
        cumulative_xp=stats.cumulative_xp if stats else 0,
        level=level,
        level_name_zh=level_info["name_zh"],
        level_name_en=level_info["name_en"],
        level_emoji=level_info["emoji"],
        next_level_threshold=level_info["next_threshold"],
        next_level_name_zh=level_info["next_level_name_zh"],
        next_level_name_en=level_info["next_level_name_en"],
        learning_streak_days=stats.learning_streak_days if stats else 0,
        total_study_minutes=minutes["total_study_minutes"],
        today_study_minutes=minutes["today_study_minutes"],
        mastered_count=overview["mastered"],
        learning_count=overview["learning"],
        available_count=overview["available"],
        review_count=overview["review"],
    )


@router.get("/children/{child_id}/weak-topics", response_model=list[ParentWeakTopicItem])
def get_child_weak_topics(
    child_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    """Get child's weak topics for parent view."""
    child = _require_family_child(db, child_id, user)

    weak_topics = practice_service.get_weak_topics(
        db=db,
        child_id=child.id,
        **practice_service.PARENT_WEAK_TOPIC_POLICY,
    )

    return [ParentWeakTopicItem(**wt) for wt in weak_topics]


@router.get(
    "/children/{child_id}/practice-sessions",
    response_model=list[ParentPracticeSessionItem],
)
def get_child_practice_sessions(
    child_id: int,
    limit: int = Query(10, ge=1, le=50),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    """Get child's recent practice sessions for parent view."""
    child = _require_family_child(db, child_id, user)

    sessions = practice_service.list_sessions(db, child.id, limit, offset)

    # Batch-fetch topic names (no taxonomy filter — records describe what the
    # child actually practiced, and filtering by parent language would blank
    # the name out).
    topic_ids = list({s.topic_id for s in sessions})
    topics = (
        db.query(LearningTopic).filter(LearningTopic.id.in_(topic_ids)).all()
        if topic_ids
        else []
    )
    topic_map = {t.id: t for t in topics}

    result = []
    for s in sessions:
        topic = topic_map.get(s.topic_id)
        question_ids = json.loads(s.question_ids_json) if s.question_ids_json else []
        result.append(
            ParentPracticeSessionItem(
                session_id=s.id,
                topic_id=s.topic_id,
                topic_name=topic.name if topic else "",
                topic_name_zh=topic.name_zh if topic else None,
                session_mode=s.session_mode,
                total_score=s.total_score,
                completed_count=s.completed_count,
                total_count=len(question_ids),
                started_at=s.started_at,
                ended_at=s.ended_at,
            )
        )
    return result


@router.get("/children/{child_id}/recommendations", response_model=RecommendationPathResponse)
def get_recommendations(
    child_id: int,
    limit: int = Query(20, ge=1, le=100, description="Max topics to return (default 20)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_adult),
):
    """Get personalized learning recommendations for a child.

    Returns up to ``limit`` topics ranked by priority
    (知识断点 > 课标必会 > 高基础度 > 需要复习).
    """
    # Verify child belongs to this family
    child = (
        db.query(User)
        .filter(User.id == child_id, User.family_id == current_user.family_id, User.role == "child")
        .first()
    )
    if not child:
        raise AppError(ErrorCode.AUTH_CHILD_NOT_FOUND, details={"child_id": child_id})

    path = generate_recommendation_path(db, child_id, limit=limit)
    topics = [
        RecommendedTopicItem(
            topic_id=t.topic_id,
            topic_name=t.topic_name,
            reasons=t.reasons,
            centrality=t.centrality,
            prerequisites_met=t.prerequisites_met,
            suggested_position=t.suggested_position,
        )
        for t in path.topics
    ]
    return RecommendationPathResponse(
        path=RecommendationPathDetail(
            name=path.name,
            topics=topics,
            total_count=path.total_count,
        )
    )


@router.get("/topics/{topic_id}", response_model=TopicResponse)
def get_topic_detail(
    topic_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    """Get topic detail (parent view — no per-child progress embedded).

    Locale filter applied: topic must belong to the parent's source taxonomy.
    """
    taxonomy = get_effective_source_taxonomy(db, user.language)
    topic = (
        db.query(LearningTopic)
        .filter(
            LearningTopic.id == topic_id,
            LearningTopic.source_taxonomy == taxonomy,
        )
        .first()
    )
    if not topic:
        raise AppError(ErrorCode.LEARNING_TOPIC_NOT_FOUND)
    return topic


@router.post("/assignments", response_model=AssignmentResponse, status_code=201)
def create_assignment(
    req: AssignmentCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    # Verify child belongs to this family
    child = (
        db.query(User)
        .filter(User.id == req.child_id, User.family_id == user.family_id, User.role == "child")
        .first()
    )
    if not child:
        raise AppError(ErrorCode.AUTH_CHILD_NOT_FOUND)

    assignment = assignment_service.create_assignment(db, user, req)
    # Fire notification — child name resolved from DB
    child = db.query(User).filter(User.id == req.child_id).first()
    # Locale filter applied: assignment topic scoped to parent's taxonomy.
    taxonomy = get_effective_source_taxonomy(db, user.language)
    topic = (
        db.query(LearningTopic)
        .filter(
            LearningTopic.id == req.topic_id,
            LearningTopic.source_taxonomy == taxonomy,
        )
        .first()
    )
    if child and topic:
        child_name = child.display_name or child.username or ""
        topic_name = topic.name_zh or topic.name or ""
        with contextlib.suppress(Exception):
            notify_learning_assignment_created(db, user.family_id, child_name, topic_name)
    return assignment


@router.get("/assignments", response_model=list[AssignmentResponse])
def list_assignments(
    child_id: int | None = Query(None),
    status: str | None = Query(None),
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    """List assignments. If child_id not given, return all for the family."""
    if child_id:
        # Verify child belongs to family
        child = (
            db.query(User)
            .filter(User.id == child_id, User.family_id == user.family_id, User.role == "child")
            .first()
        )
        if not child:
            raise AppError(ErrorCode.AUTH_CHILD_NOT_FOUND)
        return assignment_service.list_assignments(db, child_id, status)

    # All children in family
    child_ids = [
        r.id
        for r in db.query(User.id).filter(
            User.family_id == user.family_id, User.role == "child"
        ).all()
    ]
    if not child_ids:
        return []

    q = db.query(LearningAssignment).filter(LearningAssignment.child_id.in_(child_ids))
    if status:
        q = q.filter(LearningAssignment.status == status)
    return q.order_by(LearningAssignment.priority.desc(), LearningAssignment.created_at.desc()).all()


@router.get("/reviews", response_model=list[ReviewItemResponse])
def review_queue(
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    """Get review queue — all progress items awaiting parent review."""
    progress_items = assignment_service.get_review_queue(db, user.family_id)
    if not progress_items:
        return []

    # Batch-fetch child names and topic info to avoid N+1 queries
    # Locale filter applied: review topics scoped to parent's taxonomy.
    taxonomy = get_effective_source_taxonomy(db, user.language)
    child_ids = {p.child_id for p in progress_items}
    topic_ids = {p.topic_id for p in progress_items}

    children = {
        u.id: u
        for u in db.query(User).filter(User.id.in_(child_ids)).all()
    }
    topics = {
        t.id: t
        for t in db.query(LearningTopic)
        .filter(
            LearningTopic.id.in_(topic_ids),
            LearningTopic.source_taxonomy == taxonomy,
        )
        .all()
    }

    # Aggregate study duration per (child_id, topic_id) from sessions
    session_rows = (
        db.query(
            LearningSession.child_id,
            LearningSession.topic_id,
            sa_func.coalesce(sa_func.sum(LearningSession.duration_seconds), 0),
        )
        .filter(
            LearningSession.child_id.in_(list(child_ids)),
            LearningSession.topic_id.in_(list(topic_ids)),
        )
        .group_by(LearningSession.child_id, LearningSession.topic_id)
        .all()
    )
    duration_map = {
        (r.child_id, r.topic_id): int(r[2]) for r in session_rows
    }

    result = []
    for p in progress_items:
        child = children.get(p.child_id)
        topic = topics.get(p.topic_id)
        result.append(
            ReviewItemResponse(
                progress_id=p.id,
                child_id=p.child_id,
                child_name=child.display_name if child else "",
                topic_id=p.topic_id,
                topic_name=(topic.name_zh or topic.name or "") if topic else "",
                topic_description=(topic.description_zh or topic.description or "") if topic else "",
                evidence=topic.evidence if topic else [],
                evidence_zh=topic.evidence_zh if topic else None,
                attempts=p.attempts,
                study_duration_seconds=duration_map.get((p.child_id, p.topic_id), 0),
                submitted_at=p.updated_at,
            )
        )
    return result


@router.post("/reviews/{progress_id}/approve", response_model=ProgressResponse)
def approve_review(
    progress_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    """Approve mastery — atomic CAS: parent_review -> mastered."""
    progress = db.query(LearningProgress).filter(LearningProgress.id == progress_id).first()
    if not progress:
        raise AppError(ErrorCode.LEARNING_PROGRESS_NOT_FOUND)

    child = (
        db.query(User)
        .filter(User.id == progress.child_id, User.family_id == user.family_id)
        .first()
    )
    if not child:
        raise AppError(ErrorCode.AUTH_CHILD_NOT_FOUND)

    progress = progress_service.approve_parent_review(db, progress, user.family_id)

    # Fire notification — child approved
    # Locale filter applied: notification topic scoped to parent's taxonomy.
    child_name = child.display_name or child.username or ""
    taxonomy = get_effective_source_taxonomy(db, user.language)
    topic = (
        db.query(LearningTopic)
        .filter(
            LearningTopic.id == progress.topic_id,
            LearningTopic.source_taxonomy == taxonomy,
        )
        .first()
    )
    topic_name = (topic.name_zh or topic.name or "") if topic else ""
    with contextlib.suppress(Exception):
        notify_learning_approved(db, user.family_id, child_name, topic_name)

    return progress


@router.post("/reviews/{progress_id}/reject", response_model=ProgressResponse)
def reject_review(
    progress_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    """Reject — return progress from parent_review back to learning."""
    progress = db.query(LearningProgress).filter(LearningProgress.id == progress_id).first()
    if not progress:
        raise AppError(ErrorCode.LEARNING_PROGRESS_NOT_FOUND)

    child = (
        db.query(User)
        .filter(User.id == progress.child_id, User.family_id == user.family_id)
        .first()
    )
    if not child:
        raise AppError(ErrorCode.AUTH_CHILD_NOT_FOUND)

    progress_service.transition_to_learning(db, progress)

    # Fire notification — child rejected, needs more work
    # Locale filter applied: notification topic scoped to parent's taxonomy.
    child_name = child.display_name or child.username or ""
    taxonomy = get_effective_source_taxonomy(db, user.language)
    topic = (
        db.query(LearningTopic)
        .filter(
            LearningTopic.id == progress.topic_id,
            LearningTopic.source_taxonomy == taxonomy,
        )
        .first()
    )
    topic_name = (topic.name_zh or topic.name or "") if topic else ""
    with contextlib.suppress(Exception):
        notify_learning_rejected(db, user.family_id, child_name, topic_name)

    db.commit()
    return progress


@router.post("/reviews/{progress_id}/override", response_model=ProgressResponse)
def override_review_endpoint(
    progress_id: int,
    req: ReviewOverrideRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_adult),
):
    """Parent overrides AI assessment decision (auto-pass or rejection)."""
    progress = db.query(LearningProgress).filter(LearningProgress.id == progress_id).first()
    if not progress:
        raise AppError(ErrorCode.LEARNING_PROGRESS_NOT_FOUND)

    child = (
        db.query(User)
        .filter(User.id == progress.child_id, User.family_id == current_user.family_id)
        .first()
    )
    if not child:
        raise AppError(ErrorCode.AUTH_CHILD_NOT_FOUND)

    result = progress_service.override_review(
        db, progress_id, current_user.id, req.new_decision, req.reason
    )
    db.commit()
    return result


@router.get(
    "/children/{child_id}/ai-review-status",
    response_model=AIReviewStatusResponse,
)
def get_ai_review_status(
    child_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_adult),
):
    """Get AI auto-pass status for a child (paused? consecutive override count?)."""
    child = (
        db.query(User)
        .filter(User.id == child_id, User.family_id == current_user.family_id, User.role == "child")
        .first()
    )
    if not child:
        raise AppError(ErrorCode.AUTH_CHILD_NOT_FOUND)

    paused = progress_service.is_ai_auto_pass_paused(db, child_id)
    count = progress_service.get_consecutive_override_count(db, child_id)
    return AIReviewStatusResponse(
        ai_auto_pass_paused=paused,
        consecutive_overrides=count,
    )


@router.post(
    "/children/{child_id}/ai-review-resume",
    response_model=AIReviewStatusResponse,
)
def resume_ai_review(
    child_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_adult),
):
    """Resume AI auto-pass after parent paused it (reset override counter)."""
    child = (
        db.query(User)
        .filter(User.id == child_id, User.family_id == current_user.family_id, User.role == "child")
        .first()
    )
    if not child:
        raise AppError(ErrorCode.AUTH_CHILD_NOT_FOUND)

    stats = stats_service.get_or_create_stats(db, child_id, current_user.family_id)
    stats.consecutive_ai_overrides = 0
    db.flush()
    db.commit()
    return AIReviewStatusResponse(
        ai_auto_pass_paused=False,
        consecutive_overrides=0,
    )


# ---------------------------------------------------------------------------
# Learning Path endpoints
# ---------------------------------------------------------------------------



@router.post("/paths", response_model=PathResponse, status_code=201)
def create_path(
    req: PathCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    """Create a learning path for a child."""
    # Verify child belongs to this family
    child = (
        db.query(User)
        .filter(User.id == req.child_id, User.family_id == user.family_id)
        .first()
    )
    if not child:
        raise AppError(ErrorCode.LEARNING_PATH_ACCESS_DENIED)

    path = path_service.create_path(
        db,
        family_id=user.family_id,
        child_id=req.child_id,
        created_by=user.id,
        name=req.name,
        name_zh=req.name_zh,
        description=req.description,
        description_zh=req.description_zh,
        topic_ids=req.topic_ids,
        per_task_score=req.per_task_score,
        bonus_score=req.bonus_score,
        milestone_scores=req.milestone_scores,
        due_date=req.due_date,
    )

    progress = path_service.get_path_progress(db, path.id, user.family_id)
    return path_service.build_path_response(path, progress)


@router.get("/paths", response_model=list[PathResponse])
def list_paths(
    child_id: int | None = Query(None),
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    """List learning paths, optionally filtered by child."""
    query = db.query(LearningPath).filter(LearningPath.family_id == user.family_id)
    if child_id:
        query = query.filter(LearningPath.child_id == child_id)
    paths = query.order_by(LearningPath.created_at.desc()).all()

    result = []
    for path in paths:
        progress = path_service.get_path_progress(db, path.id, user.family_id)
        result.append(path_service.build_path_response(path, progress))
    return result


@router.get("/paths/{path_id}", response_model=PathResponse)
def get_path(
    path_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    """Get path detail with items and progress."""
    progress = path_service.get_path_progress(db, path_id, user.family_id)
    return path_service.build_path_response(progress["path"], progress)


@router.post("/paths/{path_id}/archive", response_model=PathResponse)
def archive_path(
    path_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    """Archive a learning path.

    Any adult in the family can archive — paths are family-level resources
    (both parents may need to manage a child's learning plan).
    """
    path = (
        db.query(LearningPath)
        .filter(LearningPath.id == path_id, LearningPath.family_id == user.family_id)
        .first()
    )
    if not path:
        raise AppError(ErrorCode.LEARNING_PATH_NOT_FOUND)
    path.status = "archived"
    db.commit()
    db.refresh(path)
    progress = path_service.get_path_progress(db, path.id, user.family_id)
    return path_service.build_path_response(path, progress)


@router.get("/children/{child_id}/clusters", response_model=list[ClusterResponse])
def get_child_clusters(
    child_id: int,
    subject: str | None = Query(None),
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    """List clusters enriched with topic counts for a specific child's taxonomy.

    Parents can see the same cluster territory layout their children use,
    helping them understand the learning progression structure.
    """
    child = (
        db.query(User)
        .filter(User.id == child_id, User.family_id == user.family_id, User.role == "child")
        .first()
    )
    if not child:
        raise AppError(ErrorCode.AUTH_CHILD_NOT_FOUND)

    taxonomy = get_effective_source_taxonomy(db, user.language)
    return list_clusters_with_topic_counts(
        db, subject=subject, source_taxonomy=taxonomy
    )


@router.get("/children/{child_id}/bridges", response_model=list[BridgeResponse])
def get_child_bridges(
    child_id: int,
    subject: str | None = Query(None),
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    """List cross-subject bridge edges for a specific child's taxonomy.

    Parents can see bridge badges that connect cluster territories across
    subjects, helping them understand cross-subject connections.
    """
    child = (
        db.query(User)
        .filter(User.id == child_id, User.family_id == user.family_id, User.role == "child")
        .first()
    )
    if not child:
        raise AppError(ErrorCode.AUTH_CHILD_NOT_FOUND)

    taxonomy = get_effective_source_taxonomy(db, user.language)
    return get_cross_subject_bridges(db, source_taxonomy=taxonomy, subject=subject)


# ── Knowledge Castle (Parent View, Issue #235) ───────────────────────────────


@router.get(
    "/children/{child_id}/castle/index",
    response_model=CastleIndexResponse,
)
def get_child_castle(
    child_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    """Return aggregated castle data for a child (parent view).

    Reuses castle_service — the same data the child sees in their castle.
    Zero-progress children get empty tower skeletons (200, never 404).
    """
    child = (
        db.query(User)
        .filter(User.id == child_id, User.family_id == user.family_id, User.role == "child")
        .first()
    )
    if not child:
        raise AppError(ErrorCode.AUTH_CHILD_NOT_FOUND)

    data = castle_service.get_castle_index(db, child.id, user.family_id, user.language)
    return castle_service.to_response(data)


# ── Learning Topic Generator (Issue #190) ────────────────────────────────────


class _TopicPlanGenerateRequest(BaseModel):
    """Request body for AI topic plan generation."""

    topic_key: str
    age_group: Literal["low", "mid", "high"] = "mid"


@router.post("/topic-plan/generate")
async def generate_topic_plan(
    body: _TopicPlanGenerateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    """Generate a learning topic plan via AI agent.

    Triggers the ``learning-topic-generator`` skill to produce a structured
    learning plan JSON from os_taxonomy data. The plan includes objectives,
    outline, prerequisite chain, and recommended exercises.

    Returns task_id for SSE streaming via the bridge consumer.
    """
    import hashlib

    from apps.backend.app.services.agent_client import AgentClient
    from apps.backend.app.services.ai_task_service import AITaskService
    from apps.backend.app.services.bridge_consumer import (
        _spawn_lifecycle_consumer,
        get_shared_bridge,
        trigger_agent_run,
    )
    from packages.os_taxonomy import get_clusters, get_dependencies, get_topics

    family_id = user.family_id

    # 1. Build taxonomy context from os_taxonomy package
    all_topics = get_topics()
    topic_data = None
    for t in all_topics:
        if t["id"] == body.topic_key:
            topic_data = t
            break

    if topic_data is None:
        raise AppError(
            ErrorCode.LEARNING_TOPIC_NOT_FOUND,
            details={"topic_key": body.topic_key},
        )

    # Gather prerequisites
    all_deps = get_dependencies()
    prereqs = []
    for dep in all_deps:
        if dep["topicId"] == body.topic_key:
            prereq_topic = next(
                (t for t in all_topics if t["id"] == dep["prerequisiteId"]),
                None,
            )
            prereqs.append(
                {
                    "topic_key": dep["prerequisiteId"],
                    "name": prereq_topic.get("name", "") if prereq_topic else "",
                    "name_zh": prereq_topic.get("nameZh", "") if prereq_topic else "",
                    "strength": dep.get("strength", "soft"),
                    "reason": dep.get("reason", ""),
                }
            )

    # Find cluster context
    all_clusters = get_clusters()
    subject = topic_data.get("subject", "")
    domain = topic_data.get("domain", "")
    cluster_summary = ""
    for c in all_clusters:
        if c.get("subject") == subject and c.get("domain") == domain:
            cluster_summary = c.get("summaryZh") or c.get("summary", "")
            break

    # 2. Build deterministic thread_id (family + topic + age_group)
    thread_hash = hashlib.sha256(
        f"{family_id}:{body.topic_key}:{body.age_group}".encode()
    ).hexdigest()[:16]
    thread_id = f"topic-gen-{thread_hash}"

    # 3. Construct trigger message with taxonomy context
    agent_content = json.dumps(
        {
            "topic_key": topic_data["id"],
            "subject": subject,
            "domain": domain,
            "age_group": body.age_group,
            "topic_name": topic_data.get("name", ""),
            "topic_name_zh": topic_data.get("nameZh", ""),
            "topic_description": topic_data.get("description", ""),
            "topic_description_zh": topic_data.get("descriptionZh", ""),
            "evidence": topic_data.get("evidenceZh") or topic_data.get("evidence", []),
            "prerequisites": prereqs,
            "cluster_summary": cluster_summary,
            "locale": user.language or "zh-CN",
        },
        ensure_ascii=False,
    )

    agent_body = {
        "family_id": str(family_id),
        "user_id": str(user.id),
        "input": {
            "messages": [{"role": "user", "content": agent_content}],
        },
        "on_disconnect": "continue",
        "metadata": {
            "app": "learning-topic-generator",
            "topic_key": body.topic_key,
            "age_group": body.age_group,
            "language": user.language or "zh-CN",
        },
    }

    # 4. Create AITask
    task = AITaskService.create_task(
        family_id=family_id,
        skill_id="learning-topic-generator",
        session_id=None,
        db=db,
    )
    task.progress = {"topic_key": body.topic_key, "age_group": body.age_group}
    db.commit()
    task_id = str(task.id)

    # 5. Trigger agent
    agent_client = AgentClient(family_id=str(family_id), user_id=str(user.id))
    try:
        result = await trigger_agent_run(
            agent_client=agent_client,
            agent_url=f"/internal/gateway/runs/learning-topic-generator/{thread_id}",
            json_body=agent_body,
            task_id=task_id,
        )
    except httpx.HTTPStatusError as e:
        _fdb = SessionLocal()
        try:
            AITaskService.fail_task(
                task_id, f"agent trigger failed: {type(e).__name__}", _fdb
            )
        finally:
            _fdb.close()
        if e.response.status_code == 409:
            raise AppError(ErrorCode.AI_TASK_IN_PROGRESS) from e
        raise AppError(
            ErrorCode.AI_SERVICE_UNAVAILABLE, details={"reason": str(e)}
        ) from e
    except Exception as e:
        _fdb = SessionLocal()
        try:
            AITaskService.fail_task(
                task_id, f"agent trigger failed: {type(e).__name__}", _fdb
            )
        finally:
            _fdb.close()
        raise AppError(
            ErrorCode.AI_SERVICE_UNAVAILABLE, details={"reason": str(e)}
        ) from e

    # 6. Attach run_id + spawn lifecycle consumer
    AITaskService.extract_and_attach_run_id(
        task_id, result["content_location"], family_id
    )
    shared_bridge = get_shared_bridge()
    _spawn_lifecycle_consumer(
        task_id=task_id,
        family_id=family_id,
        run_id=result["run_id"],
        bridge=shared_bridge,
    )

    return {
        "task_id": task_id,
        "thread_id": thread_id,
        "topic_key": body.topic_key,
        "age_group": body.age_group,
    }


# ── Smart Tutor (Parent View, Issue #194) ────────────────────────────────────


def _parse_smart_tutor_steps(
    session: LearningSession,
) -> tuple[list[dict], str | None, list[dict]]:
    """Parse Smart Tutor session data from progress_json.

    Returns:
        Tuple of (steps, final_phase, misconceptions_detected)
        where misconceptions_detected is a deduplicated list of
        {misconception_id, category, description} dicts derived from
        step records (replaces the old int count).
    """
    steps: list[dict] = []
    final_phase: str | None = None
    misconceptions: list[dict] = []
    seen_misconception_ids: set[int] = set()

    if session.progress_json:
        try:
            raw_steps = json.loads(session.progress_json)
            if isinstance(raw_steps, list):
                steps = raw_steps
                # Final phase is the next_phase of the last step
                if steps:
                    final_phase = steps[-1].get("next_phase")
                # Derive deduplicated misconceptions from step records.
                # Each step may carry a 'misconception' sub-dict with
                # {id, category, description}.
                for s in steps:
                    m = s.get("misconception")
                    if not m or not isinstance(m, dict):
                        continue
                    mid = m.get("id")
                    if mid is None or mid in seen_misconception_ids:
                        continue
                    seen_misconception_ids.add(mid)
                    misconceptions.append({
                        "misconception_id": str(mid),
                        "category": m.get("category", ""),
                        "description": m.get("description", ""),
                    })
        except (json.JSONDecodeError, TypeError):
            pass

    return steps, final_phase, misconceptions


def _parse_teach_back_steps(session: LearningSession) -> list[dict]:
    """Parse teach-back turns from progress_json.

    Returns list of teach_back_turn records (child explanation + verdict).
    """
    turns: list[dict] = []
    if session.progress_json:
        try:
            raw_steps = json.loads(session.progress_json)
            if isinstance(raw_steps, list):
                turns = [
                    s for s in raw_steps
                    if isinstance(s, dict) and s.get("type") == "teach_back_turn"
                ]
        except (json.JSONDecodeError, TypeError):
            pass
    return turns


def _determine_outcome(
    session: LearningSession, final_phase: str | None
) -> str | None:
    """Determine session outcome based on completion state."""
    if session.ended_at is None:
        return "in_progress"
    if final_phase == "end":
        return "completed"
    if session.score:
        return "needs_review"
    return "abandoned"


@router.get(
    "/children/{child_id}/smart-tutor/sessions",
    response_model=list[SmartTutorSessionResponse],
)
def list_child_smart_tutor_sessions(
    child_id: int,
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    """Get child's Smart Tutor sessions for parent review.

    Returns session summaries with phase, step count, and outcome.
    """
    # Verify child belongs to this family
    child = (
        db.query(User)
        .filter(User.id == child_id, User.family_id == user.family_id, User.role == "child")
        .first()
    )
    if not child:
        raise AppError(ErrorCode.AUTH_CHILD_NOT_FOUND)

    # Query sessions with Smart Tutor data (session_type = 'smart_tutor' or has progress_json)
    sessions = (
        db.query(LearningSession)
        .filter(
            LearningSession.child_id == child_id,
            LearningSession.session_type == "smart_tutor",
        )
        .order_by(LearningSession.started_at.desc())
        .limit(limit)
        .all()
    )

    # Batch-fetch topic names
    topic_ids = list({s.topic_id for s in sessions})
    taxonomy = get_effective_source_taxonomy(db, user.language)
    topics = (
        db.query(LearningTopic)
        .filter(
            LearningTopic.id.in_(topic_ids),
            LearningTopic.source_taxonomy == taxonomy,
        )
        .all()
    ) if topic_ids else []
    topic_map = {t.id: t for t in topics}

    result = []
    for s in sessions:
        topic = topic_map.get(s.topic_id)
        steps, final_phase, misconceptions = _parse_smart_tutor_steps(s)
        outcome = _determine_outcome(s, final_phase)
        result.append(
            SmartTutorSessionResponse(
                session_id=s.id,
                topic_id=s.topic_id,
                topic_name=topic.name if topic else "",
                topic_name_zh=topic.name_zh if topic else None,
                subject=topic.subject if topic else "",
                started_at=s.started_at,
                completed_at=s.ended_at,
                final_phase=final_phase,
                total_steps=len(steps),
                misconceptions_detected=misconceptions,
                outcome=outcome,
            )
        )
    return result


@router.get(
    "/children/{child_id}/smart-tutor/sessions/{session_id}",
    response_model=SmartTutorSessionDetailResponse,
)
def get_child_smart_tutor_session(
    child_id: int,
    session_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    """Get detailed Smart Tutor session with step-by-step records.

    Returns full session data including AI evaluation and step history.
    """
    # Verify child belongs to this family
    child = (
        db.query(User)
        .filter(User.id == child_id, User.family_id == user.family_id, User.role == "child")
        .first()
    )
    if not child:
        raise AppError(ErrorCode.AUTH_CHILD_NOT_FOUND)

    # Load session
    session = (
        db.query(LearningSession)
        .filter(
            LearningSession.id == session_id,
            LearningSession.child_id == child_id,
            LearningSession.session_type == "smart_tutor",
        )
        .first()
    )
    if not session:
        raise AppError(ErrorCode.LEARNING_SESSION_NOT_FOUND)

    # Load topic
    taxonomy = get_effective_source_taxonomy(db, user.language)
    topic = (
        db.query(LearningTopic)
        .filter(
            LearningTopic.id == session.topic_id,
            LearningTopic.source_taxonomy == taxonomy,
        )
        .first()
    )

    steps, final_phase, misconceptions = _parse_smart_tutor_steps(session)
    outcome = _determine_outcome(session, final_phase)

    # Parse AI evaluation if present
    ai_eval = None
    if session.ai_evaluation_json:
        with contextlib.suppress(json.JSONDecodeError, TypeError):
            ai_eval = json.loads(session.ai_evaluation_json)

    return SmartTutorSessionDetailResponse(
        session_id=session.id,
        topic_id=session.topic_id,
        topic_name=topic.name if topic else "",
        topic_name_zh=topic.name_zh if topic else None,
        subject=topic.subject if topic else "",
        started_at=session.started_at,
        completed_at=session.ended_at,
        final_phase=final_phase,
        total_steps=len(steps),
        misconceptions_detected=misconceptions,
        outcome=outcome,
        steps=steps,
        ai_evaluation=ai_eval,
    )


@router.get(
    "/children/{child_id}/teach-back/sessions/{session_id}",
    response_model=TeachBackSessionDetailResponse,
)
def get_child_teach_back_session(
    child_id: int,
    session_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    """Get detailed teach-back session transcript for parent review.

    Issue #216. Returns the child's explanations and per-confusion verdicts.
    """
    # Verify child belongs to this family
    child = (
        db.query(User)
        .filter(User.id == child_id, User.family_id == user.family_id, User.role == "child")
        .first()
    )
    if not child:
        raise AppError(ErrorCode.AUTH_CHILD_NOT_FOUND)

    # Load session
    session = (
        db.query(LearningSession)
        .filter(
            LearningSession.id == session_id,
            LearningSession.child_id == child_id,
            LearningSession.session_type == "teach_back",
        )
        .first()
    )
    if not session:
        raise AppError(ErrorCode.LEARNING_SESSION_NOT_FOUND)

    # Load topic
    taxonomy = get_effective_source_taxonomy(db, user.language)
    topic = (
        db.query(LearningTopic)
        .filter(
            LearningTopic.id == session.topic_id,
            LearningTopic.source_taxonomy == taxonomy,
        )
        .first()
    )

    turns = _parse_teach_back_steps(session)
    last_phase = turns[-1].get("next_phase") if turns else None
    outcome = _determine_outcome(session, last_phase)

    return {
        "session_id": str(session.id),
        "topic_id": str(session.topic_id),
        "topic_name": topic.name if topic else "",
        "topic_name_zh": topic.name_zh if topic else None,
        "subject": topic.subject if topic else "",
        "started_at": session.started_at,
        "completed_at": session.ended_at,
        "outcome": outcome,
        "total_turns": len(turns),
        "turns": turns,
    }
