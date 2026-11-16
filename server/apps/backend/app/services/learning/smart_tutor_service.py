"""Smart Tutor service — Socratic guided problem-solving business logic.

Extracted from router to follow service layer pattern.
"""

import json

from sqlalchemy.orm import Session

from apps.backend.app.errors import AppError, ErrorCode
from apps.backend.app.models.user import User
from apps.backend.app.services.learning.topic_service import (
    get_effective_source_taxonomy,
)
from packages.db.models.learning.question import Question
from packages.db.models.learning.session import LearningSession
from packages.db.models.learning.topic import LearningTopic


def validate_smart_tutor_request(
    db: Session,
    session_id: int,
    child: User,
    question_id: int | None,
    is_follow_up: bool,
) -> tuple[LearningSession, Question | None, LearningTopic]:
    """Validate smart tutor request and return session, question, topic.

    Returns:
        Tuple of (session, question_or_none, topic)

    Raises:
        AppError: If validation fails
    """
    # Load session
    from apps.backend.app.services.learning import session_service

    session = session_service.get_session(db, session_id, child.id)

    # Handle follow-up vs initial call
    if is_follow_up:
        if not session.thread_id:
            raise AppError(ErrorCode.LEARNING_SESSION_NOT_FOUND)

        # Load question if question_id provided
        question = None
        if question_id:
            question = db.query(Question).filter(Question.id == question_id).first()
    else:
        # Initial call requires question_id
        if not question_id:
            raise AppError(
                ErrorCode.VALIDATION_ERROR,
                details={
                    "field": "question_id",
                    "message": "question_id is required for initial call",
                },
            )
        question = db.query(Question).filter(Question.id == question_id).first()
        if not question:
            raise AppError(ErrorCode.LEARNING_TOPIC_NOT_FOUND)

    # Load topic for context
    taxonomy = get_effective_source_taxonomy(db, child.language)
    topic = (
        db.query(LearningTopic)
        .filter(
            LearningTopic.id == session.topic_id,
            LearningTopic.source_taxonomy == taxonomy,
        )
        .first()
    )
    if not topic:
        raise AppError(ErrorCode.LEARNING_TOPIC_NOT_FOUND)

    return session, question, topic


def build_agent_payload(
    session: LearningSession,
    question: Question | None,
    topic: LearningTopic,
    child: User,
    session_id: int,
    question_id: int | None,
    child_answer: str | None,
    is_follow_up: bool,
) -> dict:
    """Build the agent trigger payload for smart tutor.

    Returns:
        Dict with agent_body ready for agent dispatch
    """
    family_id = child.family_id

    if is_follow_up:
        q_id = question_id or (question.id if question else 0)
        agent_content = json.dumps(
            {
                "action": "continue_guidance",
                "child_answer": child_answer,
                "question_id": str(q_id),
                "topic_id": str(topic.id),
                "child_id": str(child.id),
                "session_id": str(session_id),
            },
            ensure_ascii=False,
        )
    else:
        assert question is not None
        agent_content = json.dumps(
            {
                "action": "start_guidance",
                "question_id": str(question.id),
                "question_stem": question.stem,
                "question_stem_zh": question.stem_zh,
                "question_type": question.question_type,
                "options": question.options,
                "difficulty": question.difficulty,
                "bloom_level": question.bloom_level,
                "age_group": question.age_group,
                "topic_id": str(topic.id),
                "topic_name": topic.name,
                "topic_name_zh": topic.name_zh,
                "subject": topic.subject,
                "child_id": str(child.id),
                "child_name": child.display_name or child.username or "",
                "session_id": str(session_id),
            },
            ensure_ascii=False,
        )

    return {
        "family_id": str(family_id),
        "user_id": str(child.id),
        "input": {
            "messages": [{"role": "user", "content": agent_content}],
        },
        "on_disconnect": "continue",
        "metadata": {
            "app": "learning-smart-tutor",
            "session_id": str(session_id),
            "question_id": str(question_id or (question.id if question else 0)),
            "topic_id": str(topic.id),
            "language": child.language or "zh-CN",
        },
    }
