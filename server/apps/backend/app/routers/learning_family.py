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
    AssignmentCreate,
    AssignmentResponse,
    ChildLearningOverview,
    ProgressResponse,
    ReviewItemResponse,
    TopicResponse,
)
from apps.backend.app.services.learning import (
    assignment_service,
    progress_service,
)
from apps.backend.app.services.notification.dispatcher import (
    notify_learning_approved,
    notify_learning_assignment_created,
    notify_learning_rejected,
)
from packages.db.models.learning.assignment import LearningAssignment
from packages.db.models.learning.progress import LearningProgress
from packages.db.models.learning.session import LearningSession
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

    # Batch study time: single GROUP BY query
    study_rows = (
        db.query(
            LearningSession.child_id,
            sa_func.coalesce(sa_func.sum(LearningSession.duration_seconds), 0),
        )
        .filter(LearningSession.child_id.in_(child_ids))
        .group_by(LearningSession.child_id)
        .all()
    )
    study_seconds = {row.child_id: int(row[1]) for row in study_rows}

    result = []
    for child in children:
        ov = overviews.get(child.id, {})
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
            )
        )
    return result


@router.get("/children/{child_id}/map", response_model=list[ProgressResponse])
def get_child_map(
    child_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    """Get child's knowledge map with mastery levels."""
    # Verify child belongs to this family
    child = (
        db.query(User)
        .filter(User.id == child_id, User.family_id == user.family_id, User.role == "child")
        .first()
    )
    if not child:
        raise AppError(ErrorCode.NOT_FOUND)

    return (
        db.query(LearningProgress)
        .filter(LearningProgress.child_id == child_id)
        .all()
    )


@router.get("/children/{child_id}/progress", response_model=list[ProgressResponse])
def get_child_progress(
    child_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    """Get child's progress details."""
    child = (
        db.query(User)
        .filter(User.id == child_id, User.family_id == user.family_id, User.role == "child")
        .first()
    )
    if not child:
        raise AppError(ErrorCode.NOT_FOUND)

    return (
        db.query(LearningProgress)
        .filter(LearningProgress.child_id == child_id)
        .order_by(LearningProgress.updated_at.desc())
        .all()
    )


@router.get("/topics/{topic_id}", response_model=TopicResponse)
def get_topic_detail(
    topic_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
    """Get topic detail (parent view — no per-child progress embedded)."""
    topic = db.query(LearningTopic).filter(LearningTopic.id == topic_id).first()
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
        raise AppError(ErrorCode.NOT_FOUND)

    assignment = assignment_service.create_assignment(db, user, req)
    # Fire notification — child name resolved from DB
    child = db.query(User).filter(User.id == req.child_id).first()
    topic = db.query(LearningTopic).filter(LearningTopic.id == req.topic_id).first()
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
            raise AppError(ErrorCode.NOT_FOUND)
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
    child_ids = {p.child_id for p in progress_items}
    topic_ids = {p.topic_id for p in progress_items}

    children = {
        u.id: u
        for u in db.query(User).filter(User.id.in_(child_ids)).all()
    }
    topics = {
        t.id: t
        for t in db.query(LearningTopic).filter(LearningTopic.id.in_(topic_ids)).all()
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
        raise AppError(ErrorCode.NOT_FOUND)

    progress = progress_service.approve_parent_review(db, progress, user.family_id)

    # Fire notification — child approved
    child_name = child.display_name or child.username or ""
    topic = db.query(LearningTopic).filter(LearningTopic.id == progress.topic_id).first()
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
        raise AppError(ErrorCode.NOT_FOUND)

    progress_service.transition_to_learning(db, progress)

    # Fire notification — child rejected, needs more work
    child_name = child.display_name or child.username or ""
    topic = db.query(LearningTopic).filter(LearningTopic.id == progress.topic_id).first()
    topic_name = (topic.name_zh or topic.name or "") if topic else ""
    with contextlib.suppress(Exception):
        notify_learning_rejected(db, user.family_id, child_name, topic_name)

    return progress
