"""Family (parent) learning endpoints — manage children's learning."""

import contextlib

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func as sa_func
from sqlalchemy.orm import Session

from apps.backend.app.auth.deps import require_adult
from apps.backend.app.database import get_db
from apps.backend.app.errors import AppError, ErrorCode
from apps.backend.app.models.user import User
from apps.backend.app.schemas.learning import (
    AIReviewStatusResponse,
    AssignmentCreate,
    AssignmentResponse,
    BridgeResponse,
    ChildLearningOverview,
    ChildSessionLogResponse,
    ClusterResponse,
    PathCreate,
    PathResponse,
    ProgressResponse,
    RecommendationPathDetail,
    RecommendationPathResponse,
    RecommendedTopicItem,
    ReviewItemResponse,
    ReviewOverrideRequest,
    TopicResponse,
)
from apps.backend.app.services.learning import (
    assignment_service,
    path_service,
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
