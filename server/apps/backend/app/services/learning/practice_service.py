"""Practice session management service."""

import json
from datetime import UTC, datetime

from sqlalchemy import case
from sqlalchemy import func as sa_func
from sqlalchemy.orm import Session

from apps.backend.app.errors import AppError, ErrorCode
from apps.backend.app.services.learning.scoring_service import (
    calculate_session_score,
    check_answer,
)
from packages.core.logging import get_logger
from packages.db.models.learning.practice import PracticeAttempt, PracticeSession
from packages.db.models.learning.progress import LearningProgress
from packages.db.models.learning.question import Question
from packages.db.models.learning.topic import LearningTopic

logger = get_logger(__name__)


def create_session(
    db: Session,
    child_id: int,
    topic_id: int,
    session_mode: str,
    question_ids: list[int],
) -> PracticeSession:
    """Create a new practice session with selected questions."""
    session = PracticeSession(
        child_id=child_id,
        topic_id=topic_id,
        session_mode=session_mode,
        question_ids_json=json.dumps(question_ids),
        source="adaptive",
    )
    db.add(session)
    db.flush()
    logger.info(
        "Practice session created: session_id=%s, child_id=%s, topic_id=%s, count=%d",
        session.id,
        child_id,
        topic_id,
        len(question_ids),
    )
    return session


def submit_answer(
    db: Session,
    session_id: int,
    question_id: int,
    child_id: int,
    topic_id: int,
    user_answer: dict,
    time_spent_seconds: int | None,
) -> PracticeAttempt:
    """Submit an answer for a question in a practice session.

    Raises:
        AppError(PRACTICE_DUPLICATE_ATTEMPT): if question already answered.
        AppError(PRACTICE_QUESTION_NOT_IN_SESSION): if question not in session.
        AppError(PRACTICE_QUESTION_NOT_FOUND): if question doesn't exist.
    """
    # Load session for question list validation
    session = db.query(PracticeSession).filter_by(id=session_id).first()
    if not session:
        raise AppError(ErrorCode.PRACTICE_SESSION_NOT_FOUND)

    # Verify question belongs to this session
    session_question_ids: list[int] = json.loads(session.question_ids_json)
    if question_id not in session_question_ids:
        raise AppError(ErrorCode.PRACTICE_QUESTION_NOT_IN_SESSION)

    # Check for duplicate
    existing = (
        db.query(PracticeAttempt)
        .filter_by(session_id=session_id, question_id=question_id)
        .first()
    )
    if existing:
        raise AppError(ErrorCode.PRACTICE_DUPLICATE_ATTEMPT)

    # Get question for scoring
    question = db.query(Question).filter_by(id=question_id).first()
    if not question:
        raise AppError(ErrorCode.PRACTICE_QUESTION_NOT_FOUND)

    is_correct = check_answer(question.question_type, question.answer, user_answer)

    # Count attempt number for this child+question
    attempt_num = (
        db.query(PracticeAttempt)
        .filter_by(child_id=child_id, question_id=question_id)
        .count()
        + 1
    )

    attempt = PracticeAttempt(
        session_id=session_id,
        question_id=question_id,
        child_id=child_id,
        topic_id=topic_id,
        user_answer_json=json.dumps(user_answer),
        is_correct=is_correct,
        time_spent_seconds=time_spent_seconds,
        attempt_number=attempt_num,
    )
    db.add(attempt)

    # Update session completed_count
    session.completed_count += 1

    db.flush()
    return attempt


def finish_session(
    db: Session,
    session_id: int,
    child_id: int,
) -> dict:
    """Finish a practice session and calculate score.

    Raises:
        AppError(PRACTICE_SESSION_ALREADY_ENDED): if session already ended.
        AppError(PRACTICE_SESSION_NOT_FOUND): if session doesn't exist.
    """
    session = db.query(PracticeSession).filter_by(id=session_id).first()
    if not session:
        raise AppError(ErrorCode.PRACTICE_SESSION_NOT_FOUND)
    if session.child_id != child_id:
        raise AppError(ErrorCode.PRACTICE_SESSION_NOT_FOUND)
    if session.ended_at is not None:
        raise AppError(ErrorCode.PRACTICE_SESSION_ALREADY_ENDED)

    # Calculate score
    attempts = db.query(PracticeAttempt).filter_by(session_id=session_id).all()
    correct = sum(1 for a in attempts if a.is_correct)
    total = len(attempts)
    score = calculate_session_score(correct, total)

    session.ended_at = datetime.now(UTC)
    session.total_score = score
    db.flush()

    logger.info(
        "Practice session finished: session_id=%s, score=%.2f, correct=%d/%d",
        session_id,
        score,
        correct,
        total,
    )

    return {
        "session_id": session_id,
        "total_score": score,
        "correct_count": correct,
        "total_count": total,
    }


def get_session(db: Session, session_id: int) -> PracticeSession | None:
    """Get a practice session by ID."""
    return db.query(PracticeSession).filter_by(id=session_id).first()


# --- Phase 5: Weak points + history ---


def get_weak_topics(
    db: Session, child_id: int, limit: int = 10, min_attempts: int = 3
) -> list[dict]:
    """Find topics where the child has low accuracy (sorted by accuracy ASC).

    Only includes topics with >= min_attempts total attempts.
    """
    rows = (
        db.query(
            PracticeAttempt.topic_id,
            sa_func.count(PracticeAttempt.id).label("total"),
            sa_func.sum(case((PracticeAttempt.is_correct, 1), else_=0)).label("correct"),
            sa_func.max(PracticeAttempt.created_at).label("last_at"),
        )
        .filter(PracticeAttempt.child_id == child_id)
        .group_by(PracticeAttempt.topic_id)
        .having(sa_func.count(PracticeAttempt.id) >= min_attempts)
        .all()
    )

    results = []
    for row in rows:
        topic = db.query(LearningTopic).filter_by(id=row.topic_id).first()
        progress = (
            db.query(LearningProgress)
            .filter_by(child_id=child_id, topic_id=row.topic_id)
            .first()
        )
        correct = row.correct or 0
        accuracy = correct / row.total if row.total > 0 else 0.0
        results.append({
            "topic_id": row.topic_id,
            "topic_name": topic.name if topic else "",
            "topic_name_zh": topic.name_zh if topic else None,
            "total_attempts": row.total,
            "correct_attempts": correct,
            "accuracy": accuracy,
            "last_practice_at": row.last_at,
            "mastery_level": progress.mastery_level if progress else "available",
        })

    results.sort(key=lambda r: r["accuracy"])
    return results[:limit]


def list_sessions(
    db: Session, child_id: int, limit: int = 20, offset: int = 0
) -> list[PracticeSession]:
    """List practice sessions for a child, most recent first."""
    return (
        db.query(PracticeSession)
        .filter(PracticeSession.child_id == child_id)
        .order_by(PracticeSession.started_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )


def get_session_detail(
    db: Session, session_id: int, child_id: int
) -> dict | None:
    """Get full session detail with attempts and question context."""
    session = (
        db.query(PracticeSession)
        .filter_by(id=session_id, child_id=child_id)
        .first()
    )
    if not session:
        return None

    topic = db.query(LearningTopic).filter_by(id=session.topic_id).first()
    attempts = (
        db.query(PracticeAttempt)
        .filter_by(session_id=session_id)
        .order_by(PracticeAttempt.created_at.asc())
        .all()
    )

    attempt_details = []
    for a in attempts:
        q = db.query(Question).filter_by(id=a.question_id).first()
        attempt_details.append({
            "id": a.id,
            "question_id": a.question_id,
            "question_stem": q.stem if q else "",
            "question_type": q.question_type if q else "",
            "user_answer": a.user_answer,
            "is_correct": a.is_correct,
            "time_spent_seconds": a.time_spent_seconds,
            "attempt_number": a.attempt_number,
            "created_at": a.created_at,
        })

    question_ids = json.loads(session.question_ids_json) if session.question_ids_json else []

    return {
        "id": session.id,
        "topic_id": session.topic_id,
        "topic_name": topic.name if topic else "",
        "topic_name_zh": topic.name_zh if topic else None,
        "session_mode": session.session_mode,
        "total_score": session.total_score,
        "completed_count": session.completed_count,
        "total_count": len(question_ids),
        "started_at": session.started_at,
        "ended_at": session.ended_at,
        "attempts": attempt_details,
    }
