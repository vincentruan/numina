"""Teach-back service — post-mastery child-teaches-AI session logic.

Child who has mastered a topic explains it to an AI student persona.
Preset confusions (misconceptions) drive the dialogue.
"""

import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from apps.backend.app.errors import AppError, ErrorCode
from apps.backend.app.models.user import User
from packages.db.models.learning.confusion import TopicConfusion
from packages.db.models.learning.progress import LearningProgress
from packages.db.models.learning.session import LearningSession
from packages.db.models.learning.topic import LearningTopic

# Pilot topic keys — teach-back only enabled for these.
# TODO(issue-216): move to config / feature flag when expanding beyond pilot.
_PILOT_TOPIC_KEYS = frozenset({
    "mt_9KmVWCuh5_",  # Understanding fractions (age 10+)
    "mt_ndGqFPWyen",  # Fractions of a whole
    "mt_FP-mjXaq3B",  # Equivalent fractions (age 8+)
})


def get_approved_confusions(db: Session, topic_id: int, age_group: str = "mid") -> list[TopicConfusion]:
    """Return approved confusions for a topic, ordered by sequence."""
    rows = db.execute(
        select(TopicConfusion)
        .where(
            TopicConfusion.topic_id == topic_id,
            TopicConfusion.age_group == age_group,
            TopicConfusion.review_status == "approved",
        )
        .order_by(TopicConfusion.sequence)
    ).scalars().all()
    return list(rows)


def create_teach_back_session(
    db: Session,
    child: User,
    topic: LearningTopic,
) -> LearningSession:
    """Create a new teach-back LearningSession.

    Bypasses the general session_service.create_session (which auto-creates
    assignments and does available→learning transitions we don't want).
    """
    session = LearningSession(
        child_id=child.id,
        topic_id=topic.id,
        session_type="teach_back",
    )
    db.add(session)
    db.flush()
    # thread_id is set to session id for agent routing (same pattern as smart tutor)
    session.thread_id = str(session.id)
    db.commit()
    db.refresh(session)
    return session


def validate_teach_back_request(
    db: Session,
    child: User,
    session_id: int | None = None,
    topic_id: int | None = None,
    is_follow_up: bool = False,
) -> tuple[LearningSession, LearningTopic, list[TopicConfusion]]:
    """Validate teach-back request and return session, topic, confusions.

    For initial call: topic_id required, creates a new session.
    For follow-up: session_id required, loads existing session.

    Raises:
        AppError: If validation fails (not mastered, not pilot topic, no confusions).
    """
    if is_follow_up:
        if not session_id:
            raise AppError(
                ErrorCode.VALIDATION_ERROR,
                details={"field": "session_id", "message": "session_id required for follow-up"},
            )
        session = db.get(LearningSession, session_id)
        if not session or session.child_id != child.id:
            raise AppError(ErrorCode.LEARNING_SESSION_NOT_FOUND)
        if session.session_type != "teach_back":
            raise AppError(
                ErrorCode.VALIDATION_ERROR,
                details={"field": "session_id", "message": "not a teach-back session"},
            )
        topic = db.get(LearningTopic, session.topic_id)
        if not topic:
            raise AppError(ErrorCode.LEARNING_TOPIC_NOT_FOUND)
    else:
        # Initial call — topic_id required
        if not topic_id:
            raise AppError(
                ErrorCode.VALIDATION_ERROR,
                details={"field": "topic_id", "message": "topic_id required to start teach-back"},
            )
        topic = db.get(LearningTopic, topic_id)
        if not topic:
            raise AppError(ErrorCode.LEARNING_TOPIC_NOT_FOUND)

        # Check pilot scope
        if topic.topic_key not in _PILOT_TOPIC_KEYS:
            raise AppError(
                ErrorCode.VALIDATION_ERROR,
                details={"field": "topic_id", "message": "topic not in teach-back pilot"},
            )

        # Check mastery
        progress = db.execute(
            select(LearningProgress).where(
                LearningProgress.child_id == child.id,
                LearningProgress.topic_id == topic.id,
            )
        ).scalar_one_or_none()
        if not progress or progress.mastery_level != "mastered":
            raise AppError(
                ErrorCode.VALIDATION_ERROR,
                details={"field": "topic_id", "message": "topic not yet mastered"},
            )

        # Create session
        session = create_teach_back_session(db, child, topic)

    # Load approved confusions
    confusions = get_approved_confusions(db, topic.id)
    if not confusions:
        raise AppError(
            ErrorCode.LEARNING_TOPIC_NOT_FOUND,
            details={"detail": "no approved confusions for this topic"},
        )

    return session, topic, confusions


def build_teach_back_payload(
    session: LearningSession,
    topic: LearningTopic,
    child: User,
    confusions: list[TopicConfusion],
    child_answer: str | None = None,
    is_follow_up: bool = False,
) -> dict:
    """Build the agent trigger payload for teach-back.

    Uses the existing ``learning-smart-tutor`` app with a different action.
    """
    confusion_data = [
        {
            "id": c.id,
            "sequence": c.sequence,
            "text": c.confusion_text,
            "text_zh": c.confusion_text_zh,
            "rubric": c.rubric,
            "expected_expression": c.expected_expression,
        }
        for c in confusions
    ]

    if is_follow_up:
        agent_content = json.dumps(
            {
                "action": "answer_confusion",
                "child_answer": child_answer,
                "topic_id": str(topic.id),
                "child_id": str(child.id),
                "session_id": str(session.id),
            },
            ensure_ascii=False,
        )
    else:
        agent_content = json.dumps(
            {
                "action": "start_teach_back",
                "topic_id": str(topic.id),
                "topic_name": topic.name,
                "topic_name_zh": topic.name_zh,
                "subject": topic.subject,
                "child_id": str(child.id),
                "child_name": child.display_name or child.username or "",
                "session_id": str(session.id),
                "confusions": confusion_data,
            },
            ensure_ascii=False,
        )

    return {
        "family_id": str(child.family_id),
        "user_id": str(child.id),
        "input": {
            "messages": [{"role": "user", "content": agent_content}],
        },
        "on_disconnect": "continue",
        "metadata": {
            "app": "learning-smart-tutor",
            "session_id": str(session.id),
            "topic_id": str(topic.id),
            "language": child.language or "zh-CN",
        },
    }
