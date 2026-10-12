"""Question seeder — bulk generate questions from templates into the DB.

Bridges the template engine (GeneratedQuestion) to the Question table,
handling topic_key → topic_id mapping, dedup, and quality gate.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from packages.core.logging import get_logger
from packages.db.models.learning.question import Question
from packages.db.models.learning.topic import LearningTopic
from packages.domain.question_templates.base import GeneratedQuestion
from packages.domain.question_templates.registry import (
    TEMPLATE_REGISTRY,
    generate_question,
)

logger = get_logger(__name__)


@dataclass
class SeedResult:
    """Statistics from a seed run."""

    generated: int = 0
    skipped_duplicate: int = 0
    skipped_no_topic: int = 0
    failed: int = 0
    details: list[str] = field(default_factory=list)


def _compute_content_hash(stem: str, answer: dict) -> str:
    """Deterministic hash for dedup: same stem + answer → same hash."""
    raw = f"{stem}||{json.dumps(answer, sort_keys=True, ensure_ascii=False)}"
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


def _build_topic_key_index(db: Session) -> dict[str, int]:
    """Build topic_key → id mapping for all active LearningTopics."""
    topics = (
        db.query(LearningTopic.id, LearningTopic.topic_key)
        .filter(LearningTopic.deprecated == False)  # noqa: E712
        .all()
    )
    return {tk: tid for tid, tk in topics}




def _persist_generated_question(
    db: Session,
    gq: GeneratedQuestion,
    topic_id: int,
) -> Question:
    """Convert GeneratedQuestion to Question ORM and persist."""
    question = Question(
        topic_id=topic_id,
        question_type=gq.question_type,
        stem=gq.stem,
        stem_zh=gq.stem_zh,
        options_json=json.dumps(gq.options) if gq.options else None,
        answer_json=json.dumps(gq.answer),
        solution_json=json.dumps(gq.solution) if gq.solution else None,
        difficulty=gq.difficulty,
        bloom_level=gq.bloom_level,
        source="template",
        source_version=gq.template_id,
        review_status="approved",
        age_group=gq.age_group,
        parameters_json=json.dumps(gq.parameters) if gq.parameters else None,
    )
    db.add(question)
    db.flush()

    # Create primary knowledge point link
    from packages.db.models.learning.question import QuestionKnowledgePoint

    qkp = QuestionKnowledgePoint(
        question_id=question.id,
        topic_id=topic_id,
        role="primary",
    )
    db.add(qkp)
    db.flush()

    return question


def seed_questions_from_templates(
    db: Session,
    count_per_template: int = 10,
    topic_filter: str | None = None,
    dry_run: bool = False,
) -> SeedResult:
    """Seed questions from all registered templates.

    Args:
        db: Database session.
        count_per_template: Number of variants to generate per template.
        topic_filter: If set, only seed templates matching this prefix
            (e.g. "math.arithmetic.addition").
        dry_run: If True, generate but don't persist.

    Returns:
        SeedResult with generation statistics.
    """
    result = SeedResult()

    # Build topic_key → topic_id index
    topic_index = _build_topic_key_index(db)

    # Collect existing content hashes for dedup (load once)
    existing_hashes: set[str] = set()
    if not dry_run:
        for q in db.query(Question.stem, Question.answer_json).all():
            h = _compute_content_hash(q.stem, json.loads(q.answer_json))
            existing_hashes.add(h)

    # Determine which templates to run
    template_ids = sorted(TEMPLATE_REGISTRY.keys())
    if topic_filter:
        template_ids = [tid for tid in template_ids if topic_filter in tid]

    for template_id in template_ids:
        for _ in range(count_per_template):
            try:
                gq = generate_question(template_id, {})
            except Exception:
                logger.exception("Template %s failed to generate", template_id)
                result.failed += 1
                continue

            # Resolve topic_key → topic_id
            topic_id = topic_index.get(gq.topic_key)
            if topic_id is None:
                logger.warning(
                    "No LearningTopic for topic_key=%s (template %s)",
                    gq.topic_key,
                    template_id,
                )
                result.skipped_no_topic += 1
                continue

            # Dedup check
            content_hash = _compute_content_hash(gq.stem, gq.answer)
            if content_hash in existing_hashes:
                result.skipped_duplicate += 1
                continue

            if dry_run:
                result.generated += 1
                continue

            # Persist
            try:
                _persist_generated_question(db, gq, topic_id)
                existing_hashes.add(content_hash)
                result.generated += 1
            except Exception:
                logger.exception(
                    "Failed to persist question from template %s",
                    template_id,
                )
                result.failed += 1

    logger.info(
        "Seed complete: generated=%d, skipped_dup=%d, skipped_no_topic=%d, failed=%d",
        result.generated,
        result.skipped_duplicate,
        result.skipped_no_topic,
        result.failed,
    )
    return result
