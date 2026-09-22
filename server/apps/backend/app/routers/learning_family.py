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
from packages.db.models.child_economy.coin_transaction import CoinTransaction
from packages.db.models.learning.progress import LearningProgress
from packages.db.models.learning.session import LearningAssessmentAttempt
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
    result = []
    for child in children:
        overview = progress_service.get_child_progress_overview(db, child.id)
        # Calculate total study minutes from sessions
        from packages.db.models.learning.session import LearningSession

        total_seconds = (
            db.query(sa_func.coalesce(sa_func.sum(LearningSession.duration_seconds), 0))
            .filter(LearningSession.child_id == child.id)
            .scalar()
        )
        result.append(
            ChildLearningOverview(
                child_id=child.id,
                child_name=child.display_name or child.username or "",
                mastered_count=overview["mastered"],
                learning_count=overview["learning"],
                available_count=overview["available"],
                locked_count=overview["locked"],
                review_count=overview["review"],
                total_study_minutes=int(total_seconds) // 60,
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


@router.post("/assignments", response_model=AssignmentResponse, status_code=201)
def create_assignment(
    req: AssignmentCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_adult),
):
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
    from packages.db.models.learning.assignment import LearningAssignment

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
    result = []
    for p in progress_items:
        # Fetch child name
        child = db.query(User).filter(User.id == p.child_id).first()
        # Fetch topic info
        topic = db.query(LearningTopic).filter(LearningTopic.id == p.topic_id).first()
        result.append(
            ReviewItemResponse(
                progress_id=p.id,
                child_id=p.child_id,
                child_name=child.display_name if child else "",
                topic_id=p.topic_id,
                topic_name=topic.name_zh or topic.name or "" if topic else "",
                topic_description=topic.description_zh or topic.description or "" if topic else "",
                evidence=topic.evidence if topic else [],
                evidence_zh=topic.evidence_zh if topic else None,
                attempts=p.attempts,
                study_duration_seconds=0,  # TODO: aggregate from sessions
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
    # Verify child belongs to family
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

    # Atomic CAS: only transition if currently in parent_review
    result = db.execute(
        LearningProgress.__table__.update()
        .where(
            LearningProgress.id == progress_id,
            LearningProgress.mastery_level == "parent_review",
        )
        .values(mastery_level="mastered", completed_via="parent_approval")
    )
    if result.rowcount == 0:
        raise AppError(ErrorCode.LEARNING_INVALID_STATE_TRANSITION)

    # Refresh to get updated state
    db.refresh(progress)

    # Create coin reward transaction
    REWARD_COINS = 10
    txn = CoinTransaction(
        family_id=user.family_id,
        child_user_id=progress.child_id,
        amount=REWARD_COINS,
        transaction_type="learning_earn",
        narrative="掌握知识点奖励",
        narrative_emoji="🌟",
    )
    db.add(txn)

    # Create assessment attempt record
    attempt = LearningAssessmentAttempt(
        child_id=progress.child_id,
        topic_id=progress.topic_id,
        assessment_type="parent_approval",
        score=progress.mastery_score or 1.0,
        passed=True,
    )
    db.add(attempt)
    db.flush()

    # Link coin transaction to attempt for idempotency
    txn.ref_id = attempt.id

    # Fire notification — child approved
    child_name = child.display_name or child.username or ""
    topic = db.query(LearningTopic).filter(LearningTopic.id == progress.topic_id).first()
    topic_name = topic.name_zh or topic.name or "" if topic else ""
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

    progress_service._validate_transition(progress.mastery_level, "learning")
    progress.mastery_level = "learning"
    db.flush()

    # Fire notification — child rejected, needs more work
    child_name = child.display_name or child.username or ""
    topic = db.query(LearningTopic).filter(LearningTopic.id == progress.topic_id).first()
    topic_name = topic.name_zh or topic.name or "" if topic else ""
    with contextlib.suppress(Exception):
        notify_learning_rejected(db, user.family_id, child_name, topic_name)

    return progress
