"""Practice system API endpoints."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from apps.backend.app.auth.deps import get_current_user_or_child
from apps.backend.app.database import get_db
from apps.backend.app.errors import AppError, ErrorCode
from apps.backend.app.models.user import User
from apps.backend.app.schemas.practice import (
    PracticeAttemptResponse,
    PracticeResultResponse,
    PracticeSessionResponse,
    SessionCreateRequest,
    SubmitAnswerRequest,
)
from apps.backend.app.services.learning.adaptive_service import select_questions
from apps.backend.app.services.learning.practice_service import (
    create_session,
    finish_session,
    get_session,
    submit_answer,
)
from apps.backend.app.services.learning.progress_service import get_or_create_progress
from packages.core.logging import get_logger
from packages.db.models.learning.topic import LearningTopic

logger = get_logger(__name__)

router = APIRouter(prefix="/practice", tags=["practice"])


@router.post("/sessions", response_model=PracticeSessionResponse)
def create_practice_session(
    req: SessionCreateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user_or_child),
):
    """Create a new practice session with adaptive question selection."""
    topic = db.query(LearningTopic).filter_by(id=req.topic_id).first()
    if not topic:
        raise AppError(ErrorCode.PRACTICE_TOPIC_NOT_FOUND)

    # Get child's mastery level for adaptive selection
    progress = get_or_create_progress(db, user.id, req.topic_id)

    # Select questions
    questions = select_questions(
        db=db,
        topic_id=req.topic_id,
        mastery_level=progress.mastery_level,
        count=req.count,
        exclude_question_ids=[],
        exclude_recent_days=7,
        child_id=user.id,
    )

    if not questions:
        raise AppError(ErrorCode.PRACTICE_NO_QUESTIONS_AVAILABLE)

    session = create_session(
        db=db,
        child_id=user.id,
        topic_id=req.topic_id,
        session_mode=req.session_mode,
        question_ids=[q.id for q in questions],
    )
    return session


@router.post(
    "/sessions/{session_id}/answer", response_model=PracticeAttemptResponse
)
def submit_practice_answer(
    session_id: int,
    req: SubmitAnswerRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user_or_child),
):
    """Submit an answer for a question in a practice session."""
    session = get_session(db, session_id)
    if not session or session.child_id != user.id:
        raise AppError(ErrorCode.PRACTICE_SESSION_NOT_FOUND)
    if session.ended_at is not None:
        raise AppError(ErrorCode.PRACTICE_SESSION_ALREADY_ENDED)

    attempt = submit_answer(
        db=db,
        session_id=session_id,
        question_id=req.question_id,
        child_id=user.id,
        topic_id=session.topic_id,
        user_answer=req.user_answer,
        time_spent_seconds=req.time_spent_seconds,
    )
    return attempt


@router.post(
    "/sessions/{session_id}/finish", response_model=PracticeResultResponse
)
def finish_practice_session(
    session_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user_or_child),
):
    """Finish a practice session and calculate final score."""
    # Verify ownership first
    session = get_session(db, session_id)
    if not session or session.child_id != user.id:
        raise AppError(ErrorCode.PRACTICE_SESSION_NOT_FOUND)

    result = finish_session(db=db, session_id=session_id, child_id=user.id)

    # Try to update progress state machine
    mastery_changed = False
    new_mastery_level = None
    try:
        from apps.backend.app.services.learning.practice_progress_integration import (
            update_progress_from_session,
        )

        progress_result = update_progress_from_session(
            db=db, session_id=session_id, child_id=user.id
        )
        mastery_changed = progress_result["mastery_changed"]
        new_mastery_level = progress_result["new_mastery_level"]
    except Exception:
        logger.warning(
            "Progress integration failed for session %s", session_id, exc_info=True
        )

    return PracticeResultResponse(
        session_id=session_id,
        total_score=result["total_score"],
        correct_count=result["correct_count"],
        total_count=result["total_count"],
        xp_earned=10 if mastery_changed else 0,
        coins_earned=10 if mastery_changed else 0,
        mastery_changed=mastery_changed,
        new_mastery_level=new_mastery_level,
    )
