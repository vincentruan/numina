"""Practice system API endpoints."""

import json

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from apps.backend.app.auth.deps import get_current_user_or_child
from apps.backend.app.database import get_db
from apps.backend.app.errors import AppError, ErrorCode
from apps.backend.app.models.user import User
from apps.backend.app.schemas.practice import (
    CoverageResponse,
    PracticeAttemptResponse,
    PracticeResultResponse,
    PracticeSessionResponse,
    QuestionPublicResponse,
    RecommendResponse,
    SessionCreateRequest,
    SessionDetailResponse,
    SessionListItem,
    SubmitAnswerRequest,
    WeakTopicResponse,
)
from apps.backend.app.services.learning.adaptive_service import (
    RuleBasedMasteryEstimator,
    get_ability_dimensions,
    get_progress_trend,
    get_recommend_with_reason,
    select_questions,
)
from apps.backend.app.services.learning.practice_service import (
    create_session,
    finish_session,
    get_session,
    get_session_detail,
    get_weak_topics,
    list_sessions,
    submit_answer,
)
from apps.backend.app.services.learning.progress_service import (
    get_or_create_progress,
)
from apps.backend.app.services.learning.question_service import (
    get_coverage_stats,
    get_question,
    list_questions,
)
from packages.core.logging import get_logger
from packages.db.models.learning.topic import LearningTopic

logger = get_logger(__name__)

router = APIRouter(prefix="/practice", tags=["practice"])


class BatchQuestionsRequest(BaseModel):
    question_ids: list[int]


@router.get("/questions", response_model=list[QuestionPublicResponse])
def list_practice_questions(
    topic_id: int | None = None,
    difficulty: int | None = None,
    limit: int = 50,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user_or_child),
):
    """List approved questions (without answers), optionally filtered by topic/difficulty."""
    questions = list_questions(
        db=db, topic_id=topic_id, difficulty=difficulty, limit=limit
    )
    return questions


@router.post("/questions/batch", response_model=list[QuestionPublicResponse])
def batch_get_questions(
    req: BatchQuestionsRequest,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user_or_child),
):
    """Fetch specific questions by ID list (without answers)."""
    results = []
    for qid in req.question_ids:
        q = get_question(db, qid)
        if q and q.review_status == "approved":
            results.append(q)
    return results


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

    # Block locked topics
    if progress.mastery_level == "locked":
        raise AppError(ErrorCode.PRACTICE_TOPIC_LOCKED)

    # Select questions — use dynamic mastery estimator for adaptive difficulty
    questions = select_questions(
        db=db,
        topic_id=req.topic_id,
        mastery_level=progress.mastery_level,
        count=req.count,
        exclude_question_ids=[],
        exclude_recent_days=7,
        child_id=user.id,
        estimator=RuleBasedMasteryEstimator(),
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


@router.post("/sessions/{session_id}/answer", response_model=PracticeAttemptResponse)
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


@router.post("/sessions/{session_id}/finish", response_model=PracticeResultResponse)
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


# --- Phase 5: Weak points + history + recommend ---


@router.get("/weak-topics", response_model=list[WeakTopicResponse])
def get_weak_topics_endpoint(
    limit: int = 10,
    min_attempts: int = 3,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user_or_child),
):
    """Get topics where the child has low accuracy, sorted weakest first."""
    return get_weak_topics(db, child_id=user.id, limit=limit, min_attempts=min_attempts)


@router.get("/sessions", response_model=list[SessionListItem])
def list_practice_sessions(
    limit: int = 20,
    offset: int = 0,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user_or_child),
):
    """List practice sessions for the current child."""
    sessions = list_sessions(db, child_id=user.id, limit=limit, offset=offset)
    results = []
    for s in sessions:
        topic = db.query(LearningTopic).filter_by(id=s.topic_id).first()
        question_ids = json.loads(s.question_ids_json) if s.question_ids_json else []
        results.append(SessionListItem(
            id=s.id,
            topic_id=s.topic_id,
            topic_name=topic.name if topic else "",
            topic_name_zh=topic.name_zh if topic else None,
            session_mode=s.session_mode,
            total_score=s.total_score,
            completed_count=s.completed_count,
            total_count=len(question_ids),
            started_at=s.started_at,
            ended_at=s.ended_at,
        ))
    return results


@router.get("/sessions/{session_id}", response_model=SessionDetailResponse)
def get_practice_session_detail(
    session_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user_or_child),
):
    """Get full practice session detail with question-level attempts."""
    detail = get_session_detail(db, session_id=session_id, child_id=user.id)
    if not detail:
        raise AppError(ErrorCode.PRACTICE_SESSION_NOT_FOUND)
    return SessionDetailResponse(**detail)


@router.get("/recommend", response_model=list[RecommendResponse])
def get_practice_recommendations(
    topic_id: int | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user_or_child),
):
    """Recommend topics for practice — weak prerequisites or weak topics.

    If topic_id is provided, checks for weak prerequisites of that topic.
    Otherwise, returns the child's overall weakest topics.
    """
    if topic_id:
        from apps.backend.app.services.learning.adaptive_service import (
            find_weak_prerequisites,
        )

        weak_prereqs = find_weak_prerequisites(
            db, topic_id=topic_id, child_id=user.id
        )
        return [
            RecommendResponse(
                topic_id=r["topic_id"],
                topic_name=r["topic_name"],
                topic_name_zh=r["topic_name_zh"],
                mastery_level=r["mastery_level"],
                accuracy=r["accuracy"],
                is_prerequisite=True,
                prerequisite_of_topic_id=topic_id,
            )
            for r in weak_prereqs
        ]
    else:
        weak = get_weak_topics(db, child_id=user.id, limit=5, min_attempts=1)
        return [
            RecommendResponse(
                topic_id=r["topic_id"],
                topic_name=r["topic_name"],
                topic_name_zh=r["topic_name_zh"],
                mastery_level=r["mastery_level"],
                accuracy=r["accuracy"],
                is_prerequisite=False,
                prerequisite_of_topic_id=None,
            )
            for r in weak
        ]


@router.get("/coverage", response_model=CoverageResponse)
def get_practice_coverage(
    _user: User = Depends(get_current_user_or_child),
    db: Session = Depends(get_db),
):
    """Get knowledge point coverage statistics for the question bank."""
    stats = get_coverage_stats(db)
    return CoverageResponse(**stats)


@router.get("/ability-dimensions")
def get_child_ability_dimensions(
    user: User = Depends(get_current_user_or_child),
    db: Session = Depends(get_db),
):
    """Get per-domain accuracy breakdown for the current child."""
    return get_ability_dimensions(db, child_id=user.id)


@router.get("/progress-trend")
def get_child_progress_trend(
    topic_id: int,
    user: User = Depends(get_current_user_or_child),
    db: Session = Depends(get_db),
):
    """Get chronological attempt history for a child+topic."""
    return get_progress_trend(db, child_id=user.id, topic_id=topic_id)
