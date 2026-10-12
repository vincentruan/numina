"""Question CRUD and quality gate service."""

import json

from sqlalchemy.orm import Session

from apps.backend.app.errors import AppError, ErrorCode
from packages.core.logging import get_logger
from packages.db.models.learning.question import Question, QuestionKnowledgePoint
from packages.db.models.learning.topic import LearningTopic

logger = get_logger(__name__)


def validate_question(
    topic_id: int,
    question_type: str,
    stem: str,
    answer: dict,
    age_group: str,
    db: Session,
    options: list[dict] | None = None,
) -> list[str]:
    """Validate question data. Returns list of error messages (empty = valid)."""
    errors = []

    if not stem or not stem.strip():
        errors.append("Stem must not be empty")

    if not answer:
        errors.append("Answer must not be empty")

    # Topic existence check
    topic = db.query(LearningTopic).filter_by(id=topic_id).first()
    if not topic:
        errors.append(f"Topic {topic_id} does not exist")

    # Type-specific validation
    if question_type == "multiple_choice":
        if not options or len(options) < 2:
            errors.append("Multiple choice questions must have at least 2 options")
        if "key" not in answer:
            errors.append("Multiple choice answer must have 'key' field")

    if question_type == "calculation":
        if "answer" not in answer:
            errors.append("Calculation answer must have 'answer' field")

    return errors


def create_question(
    db: Session,
    topic_id: int,
    question_type: str,
    stem: str,
    answer: dict,
    difficulty: int,
    bloom_level: str,
    source: str,
    age_group: str,
    stem_zh: str | None = None,
    options: list[dict] | None = None,
    solution: dict | None = None,
    parameters: dict | None = None,
) -> Question:
    """Create a question with quality gate validation.

    Template-generated questions are auto-approved.
    LLM-generated questions start as 'pending'.
    """
    # Validate
    errors = validate_question(
        topic_id=topic_id,
        question_type=question_type,
        stem=stem,
        answer=answer,
        age_group=age_group,
        db=db,
        options=options,
    )
    if errors:
        raise AppError(ErrorCode.PRACTICE_QUESTION_INVALID, details="; ".join(errors))

    # Determine review status
    review_status = "approved" if source == "template" else "pending"

    question = Question(
        topic_id=topic_id,
        question_type=question_type,
        stem=stem,
        stem_zh=stem_zh,
        options_json=json.dumps(options) if options else None,
        answer_json=json.dumps(answer),
        solution_json=json.dumps(solution) if solution else None,
        difficulty=difficulty,
        bloom_level=bloom_level,
        source=source,
        review_status=review_status,
        age_group=age_group,
        parameters_json=json.dumps(parameters) if parameters else None,
    )
    db.add(question)
    db.flush()

    # Create primary knowledge point link
    qkp = QuestionKnowledgePoint(
        question_id=question.id,
        topic_id=topic_id,
        role="primary",
    )
    db.add(qkp)
    db.flush()

    logger.info(
        "Question created: id=%s, topic_id=%s, type=%s, source=%s",
        question.id,
        topic_id,
        question_type,
        source,
    )
    return question


def list_questions(
    db: Session,
    topic_id: int | None = None,
    question_type: str | None = None,
    difficulty: int | None = None,
    limit: int = 50,
) -> list[Question]:
    """List questions with optional filters."""
    query = db.query(Question).filter(Question.review_status == "approved")
    if topic_id is not None:
        query = query.filter(Question.topic_id == topic_id)
    if question_type:
        query = query.filter(Question.question_type == question_type)
    if difficulty is not None:
        query = query.filter(Question.difficulty == difficulty)
    return query.limit(limit).all()


def get_question(db: Session, question_id: int) -> Question | None:
    """Get a question by ID."""
    return db.query(Question).filter_by(id=question_id).first()
