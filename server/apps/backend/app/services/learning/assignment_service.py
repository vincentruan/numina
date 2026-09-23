"""Assignment service — create and manage learning assignments."""

from sqlalchemy.orm import Session

from apps.backend.app.errors import AppError, ErrorCode
from apps.backend.app.models.user import User
from apps.backend.app.schemas.learning import AssignmentCreate
from apps.backend.app.services.learning import progress_service
from packages.db.models.learning.assignment import LearningAssignment
from packages.db.models.learning.progress import LearningProgress
from packages.db.models.learning.topic import LearningTopic


def create_assignment(
    db: Session,
    user,
    req: AssignmentCreate,
) -> LearningAssignment:
    """Create a new learning assignment for a child.

    Validates that the topic exists, then creates the assignment record
    and a progress record for the child.
    """
    # Validate topic exists
    topic = db.query(LearningTopic).filter(LearningTopic.id == req.topic_id).first()
    if not topic:
        raise AppError(ErrorCode.LEARNING_TOPIC_NOT_FOUND)

    assignment = LearningAssignment(
        family_id=user.family_id,
        child_id=req.child_id,
        topic_id=req.topic_id,
        created_by=user.id,
        assignment_type=req.assignment_type,
        priority=req.priority,
        due_date=req.due_date,
    )
    db.add(assignment)

    # Create or retrieve progress record for this child+topic
    progress_service.get_or_create_progress(db, req.child_id, req.topic_id)

    db.flush()
    return assignment


def list_assignments(
    db: Session,
    child_id: int,
    status: str | None = None,
) -> list[LearningAssignment]:
    """List assignments for a child, optionally filtered by status."""
    q = db.query(LearningAssignment).filter(LearningAssignment.child_id == child_id)
    if status:
        q = q.filter(LearningAssignment.status == status)
    return q.order_by(LearningAssignment.priority.desc(), LearningAssignment.created_at.desc()).all()


def submit_for_review(
    db: Session,
    assignment_id: int,
    child_id: int,
) -> LearningProgress:
    """Submit an assignment for parent review.

    Transitions the child's progress to 'parent_review' state.
    """
    assignment = (
        db.query(LearningAssignment)
        .filter(
            LearningAssignment.id == assignment_id,
            LearningAssignment.child_id == child_id,
        )
        .first()
    )
    if not assignment:
        raise AppError(ErrorCode.LEARNING_ASSIGNMENT_NOT_FOUND)

    progress = (
        db.query(LearningProgress)
        .filter_by(child_id=child_id, topic_id=assignment.topic_id)
        .first()
    )
    if not progress:
        raise AppError(ErrorCode.LEARNING_PROGRESS_NOT_FOUND)

    # Transition to parent_review
    progress_service.validate_transition(progress.mastery_level, "parent_review")
    progress.mastery_level = "parent_review"
    assignment.status = "submitted"
    db.flush()
    return progress


def get_review_queue(db: Session, family_id: int) -> list[LearningProgress]:
    """Get all progress records in parent_review state for a family."""
    child_ids = [
        r.id
        for r in db.query(User.id).filter(
            User.family_id == family_id, User.role == "child"
        ).all()
    ]
    if not child_ids:
        return []

    return (
        db.query(LearningProgress)
        .filter(
            LearningProgress.child_id.in_(child_ids),
            LearningProgress.mastery_level == "parent_review",
        )
        .all()
    )
