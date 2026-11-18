"""Misconception service — detection recording and summary queries.

Extracts the detection-and-record block from the practice router into a
reusable service function, and provides a summary query for the child
misconceptions endpoint.
"""

import json

from sqlalchemy import func as sa_func
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from apps.backend.app.schemas.practice import (
    MisconceptionFeedbackResponse,
    MisconceptionSummaryResponse,
)
from apps.backend.app.services.learning.misconception_detector import (
    detect_misconception,
)
from packages.core.logging import get_logger
from packages.db.models.learning.misconception import (
    Misconception,
    MisconceptionDetection,
)
from packages.db.models.learning.question import Question

logger = get_logger(__name__)


def detect_and_record_misconception(
    db: Session,
    child_id: int,
    topic_id: int,
    question_id: int,
    user_answer: dict,
) -> tuple[int, MisconceptionFeedbackResponse] | None:
    """Run misconception detection and record the result.

    On match: creates a MisconceptionDetection row (wrapped in a savepoint so a
    failure here does not roll back the answer submission), and returns a tuple
    of ``(misconception_id, feedback_response)``.  The caller uses
    ``misconception_id`` to annotate the PracticeAttempt before commit.

    Returns None on no match or when the question is not found.
    """
    question = db.query(Question).filter_by(id=question_id).first()
    if not question:
        return None

    misconception = detect_misconception(
        db,
        topic_id=topic_id,
        wrong_answer=user_answer,
        question=question,
    )
    if misconception is None:
        return None

    # The MisconceptionDetection history row is wrapped in a savepoint:
    # a failure here (concurrent misconception deletion, constraint error)
    # rolls back only this row, not the answer submission.
    try:
        with db.begin_nested():
            db.add(MisconceptionDetection(
                child_id=child_id,
                topic_id=topic_id,
                misconception_id=misconception.id,
                question_id=question_id,
                wrong_answer_json=json.dumps(user_answer),
            ))
            db.flush()
    except (SQLAlchemyError, IntegrityError):
        logger.warning(
            "MisconceptionDetection write failed; attempt annotation preserved",
            exc_info=True,
        )

    # Build feedback response.
    diag_stem = None
    diag_stem_zh = None
    if misconception.diagnostic_question_id:
        diag_q = db.query(Question).filter_by(
            id=misconception.diagnostic_question_id
        ).first()
        if diag_q:
            diag_stem = diag_q.stem
            diag_stem_zh = diag_q.stem_zh

    return (
        misconception.id,
        MisconceptionFeedbackResponse(
            misconception_id=misconception.id,
            description=misconception.description,
            description_zh=misconception.description_zh,
            diagnostic_question_id=misconception.diagnostic_question_id,
            diagnostic_question_stem=diag_stem,
            diagnostic_question_stem_zh=diag_stem_zh,
        ),
    )


def get_child_misconceptions_summary(
    db: Session,
    child_id: int,
) -> list[MisconceptionSummaryResponse]:
    """Get the child's detected misconceptions grouped by topic.

    Returns a list of misconception summaries with detection counts,
    ordered by most recently detected first.
    """
    rows = (
        db.query(
            MisconceptionDetection.misconception_id,
            Misconception.topic_id,
            Misconception.description,
            Misconception.description_zh,
            sa_func.count(MisconceptionDetection.id).label("detection_count"),
            sa_func.max(MisconceptionDetection.created_at).label("last_detected_at"),
        )
        .join(Misconception, Misconception.id == MisconceptionDetection.misconception_id)
        .filter(MisconceptionDetection.child_id == child_id)
        .group_by(
            MisconceptionDetection.misconception_id,
            Misconception.topic_id,
            Misconception.description,
            Misconception.description_zh,
        )
        .order_by(sa_func.max(MisconceptionDetection.created_at).desc())
        .all()
    )

    return [
        MisconceptionSummaryResponse(
            misconception_id=row.misconception_id,
            topic_id=row.topic_id,
            description=row.description,
            description_zh=row.description_zh,
            detection_count=row.detection_count,
            last_detected_at=row.last_detected_at,
        )
        for row in rows
    ]
