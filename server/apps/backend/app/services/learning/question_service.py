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


def check_duplicate(db: Session, stem: str, answer: dict) -> bool:
    """Check if a question with same stem+answer already exists.

    Uses content hashing (SHA256 of stem + sorted answer JSON).
    """
    import hashlib

    raw = f"{stem}||{json.dumps(answer, sort_keys=True, ensure_ascii=False)}"
    content_hash = hashlib.sha256(raw.encode()).hexdigest()[:32]

    for q in db.query(Question.stem, Question.answer_json).all():
        existing_raw = f"{q.stem}||{q.answer_json}"
        existing_hash = hashlib.sha256(existing_raw.encode()).hexdigest()[:32]
        if existing_hash == content_hash:
            return True
    return False


def get_coverage_stats(db: Session) -> dict:
    """Compute knowledge point coverage statistics.

    Returns a dict with:
    - total_topics: total number of learning topics
    - covered_topics: number of topics with at least one approved question
    - coverage_rate: covered / total
    - by_subject: per-subject breakdown
    - by_difficulty: count per difficulty level
    """
    total_topics = db.query(LearningTopic).filter_by(deprecated=False).count()

    # Topics with at least one approved question
    covered_topic_ids = (
        db.query(Question.topic_id)
        .filter(Question.review_status == "approved")
        .distinct()
        .subquery()
    )
    covered_topics = db.query(covered_topic_ids).count()
    coverage_rate = covered_topics / total_topics if total_topics > 0 else 0.0

    # By subject
    from sqlalchemy import func as sa_func

    subject_stats = (
        db.query(
            LearningTopic.subject,
            sa_func.count(LearningTopic.id).label("total"),
        )
        .filter(LearningTopic.deprecated == False)  # noqa: E712
        .group_by(LearningTopic.subject)
        .all()
    )

    # Count covered per subject
    covered_by_subject_query = (
        db.query(LearningTopic.subject, sa_func.count(sa_func.distinct(Question.topic_id)).label("covered"))
        .join(Question, Question.topic_id == LearningTopic.id)
        .filter(
            LearningTopic.deprecated == False,  # noqa: E712
            Question.review_status == "approved",
        )
        .group_by(LearningTopic.subject)
        .all()
    )
    covered_by_subject = {row[0]: row[1] for row in covered_by_subject_query}

    by_subject = [
        {
            "subject": row.subject,
            "total": row.total,
            "covered": covered_by_subject.get(row.subject, 0),
            "rate": covered_by_subject.get(row.subject, 0) / row.total if row.total > 0 else 0.0,
        }
        for row in subject_stats
    ]

    # By difficulty
    difficulty_stats = (
        db.query(Question.difficulty, sa_func.count(Question.id))
        .filter(Question.review_status == "approved")
        .group_by(Question.difficulty)
        .all()
    )
    by_difficulty = {str(row[0]): row[1] for row in difficulty_stats}

    return {
        "total_topics": total_topics,
        "covered_topics": covered_topics,
        "coverage_rate": round(coverage_rate, 4),
        "by_subject": by_subject,
        "by_difficulty": by_difficulty,
    }
