"""Question generation strategy router.

Routes topics → generation method based on explicit configuration.
Phase 7 first version: config table mapping domain → method.
"""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from packages.core.logging import get_logger
from packages.db.models.learning.topic import LearningTopic

logger = get_logger(__name__)

# Explicit routing config: domain → preferred generation method
ROUTING_RULES: dict[str, str] = {
    # Math domains → template (parameterizable, deterministic answers)
    "Addition & Subtraction": "template",
    "Multiplication & Division": "template",
    "Fractions": "template",
    "Number Representation & Place Value": "template",
    "Measurement": "template",
    "Geometry": "template",
    "Algebra": "template",
    "Data & Statistics": "template",
    "Ratio & Proportion": "template",
    "Probability": "template",
    "Counting & Cardinality": "template",
    # Math reasoning → LLM (no parameterized template)
    "Mathematical Thinking": "llm",
    "reasoning": "llm",
    # Science pilot domains
    "Organisms & Life Processes": "template",
    "Matter & Materials": "template",
    # English pilot domains
    "Grammar & Punctuation": "template",
    "Reading Comprehension": "template",
    # Chinese pilot domains
    "Pinyin": "template",
    "Literacy": "template",
}

DEFAULT_METHOD = "template"


@dataclass
class RoutingResult:
    topic_id: int
    topic_key: str
    method: str  # "template" | "llm" | "external"
    recommended_count: int
    target_difficulty: list[int]
    target_bloom: list[str]


@dataclass
class ProductionTask:
    topic_id: int
    method: str
    count: int
    target_difficulty: list[int]
    target_bloom: list[str]


@dataclass
class ProductionResult:
    generated: int = 0
    validated: int = 0
    failed: int = 0
    details: list[str] = None  # type: ignore[assignment]

    def __post_init__(self):
        if self.details is None:
            self.details = []


def route(db: Session, topic_id: int) -> RoutingResult:
    """Determine generation method for a topic."""
    topic = db.get(LearningTopic, topic_id)
    if topic is None:
        raise ValueError(f"Topic {topic_id} not found")

    domain = topic.domain or ""
    method = ROUTING_RULES.get(domain, DEFAULT_METHOD)

    existing_count = _count_approved_questions(db, topic_id)
    recommended = max(1, 5 - existing_count)

    target_difficulty = _target_difficulty_for_topic(db, topic_id)
    target_bloom = _target_bloom_for_topic(topic)

    return RoutingResult(
        topic_id=topic_id,
        topic_key=topic.topic_key,
        method=method,
        recommended_count=recommended,
        target_difficulty=target_difficulty,
        target_bloom=target_bloom,
    )


def generate_production_plan(
    db: Session,
    gaps: list[dict],
    weekly_capacity: int = 200,
) -> list[ProductionTask]:
    """Generate a production plan from gap report."""
    sorted_gaps = sorted(gaps, key=lambda g: -g.get("prerequisite_value", 0))

    plan = []
    remaining = weekly_capacity

    for gap in sorted_gaps:
        if remaining <= 0:
            break

        routing = route(db, gap["topic_id"])
        count = min(routing.recommended_count, remaining)

        plan.append(ProductionTask(
            topic_id=gap["topic_id"],
            method=routing.method,
            count=count,
            target_difficulty=routing.target_difficulty,
            target_bloom=routing.target_bloom,
        ))
        remaining -= count

    return plan


def _count_approved_questions(db: Session, topic_id: int) -> int:
    from packages.db.models.learning.question import Question
    return (
        db.query(Question)
        .filter(Question.topic_id == topic_id, Question.review_status == "approved")
        .count()
    )


def _target_difficulty_for_topic(db: Session, topic_id: int) -> list[int]:
    from packages.db.models.learning.question import Question
    existing = (
        db.query(Question.difficulty)
        .filter(Question.topic_id == topic_id, Question.review_status == "approved")
        .distinct()
        .all()
    )
    existing_levels = {d[0] for d in existing}
    missing = [d for d in [1, 2, 3] if d not in existing_levels]
    return missing if missing else [2]


def _target_bloom_for_topic(topic: LearningTopic) -> list[str]:
    if topic.subject == "mathematics":
        return ["remember", "understand", "apply", "analyze"]
    return ["remember", "understand", "apply"]
