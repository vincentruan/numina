"""Tests for topic hook question service."""

import pytest
from sqlalchemy.orm import Session

from apps.backend.app.services.learning.hook_service import get_hook_question
from packages.db.models.learning.hook import TopicHookQuestion
from packages.db.models.learning.topic import LearningTopic


@pytest.fixture
def topic_with_hooks(db: Session):
    """Topic with all three age-layered hook questions."""
    topic = LearningTopic(
        topic_key="mt_hook_001",
        topic_type="CONCEPTUAL",
        subject="mathematics",
        domain="Fractions",
        name="Adding fractions",
        description="Adding fractions with the same denominator",
        age_range_start=8,
        age_range_end=10,
        age_group="mid",
        evidence_json="[]",
        standards_json="[]",
    )
    db.add(topic)
    db.flush()

    db.add_all(
        [
            TopicHookQuestion(
                topic_id=topic.id,
                review_status="approved",
                question_text="Can you split a cake into equal pieces?",
                question_text_zh="你能把蛋糕切成一样大的块吗？",
                age_group="low",
                difficulty="easy",
            ),
            TopicHookQuestion(
                topic_id=topic.id,
                review_status="approved",
                question_text="If you eat 2/5 and your friend eats 1/5, how much is gone?",
                question_text_zh="你吃了 2/5，朋友吃了 1/5，一共吃了多少？",
                age_group="mid",
                difficulty="medium",
            ),
            TopicHookQuestion(
                topic_id=topic.id,
                review_status="approved",
                question_text="Why do same-denominator fractions add only on top?",
                question_text_zh="为什么同分母分数只加分子？",
                age_group="high",
                difficulty="medium",
            ),
        ]
    )
    db.flush()
    return topic


@pytest.fixture
def topic_with_mid_only(db: Session):
    """Topic with only a mid-level hook question."""
    topic = LearningTopic(
        topic_key="mt_hook_002",
        topic_type="CONCEPTUAL",
        subject="mathematics",
        domain="Number",
        name="Prime numbers",
        description="Primes",
        age_range_start=9,
        age_range_end=10,
        age_group="mid",
        evidence_json="[]",
        standards_json="[]",
    )
    db.add(topic)
    db.flush()
    db.add(
        TopicHookQuestion(
            topic_id=topic.id,
            review_status="approved",
            question_text="Which numbers can't be split into two equal piles?",
            age_group="mid",
            difficulty="medium",
        )
    )
    db.flush()
    return topic


class TestGetHookQuestion:
    def test_returns_matching_age_group(self, db: Session, topic_with_hooks):
        hook = get_hook_question(db, topic_with_hooks.id, age_group="low")
        assert hook is not None
        assert hook.age_group == "low"
        assert hook.question_text == "Can you split a cake into equal pieces?"

    def test_returns_high_age_group(self, db: Session, topic_with_hooks):
        hook = get_hook_question(db, topic_with_hooks.id, age_group="high")
        assert hook is not None
        assert hook.age_group == "high"

    def test_falls_back_to_mid_when_age_group_missing(
        self, db: Session, topic_with_mid_only
    ):
        """A topic with only a mid question still serves low/high children."""
        hook = get_hook_question(db, topic_with_mid_only.id, age_group="low")
        assert hook is not None
        assert hook.age_group == "mid"

        hook = get_hook_question(db, topic_with_mid_only.id, age_group="high")
        assert hook is not None
        assert hook.age_group == "mid"

    def test_returns_none_when_topic_has_no_hooks(self, db: Session):
        assert get_hook_question(db, 999999999, age_group="mid") is None

    def test_returns_none_for_topic_without_hooks(
        self, db: Session, topic_with_mid_only
    ):
        """Requesting mid on a topic that has no mid row (edge case) returns None."""
        db.query(TopicHookQuestion).filter(
            TopicHookQuestion.topic_id == topic_with_mid_only.id
        ).delete()
        db.flush()
        assert get_hook_question(db, topic_with_mid_only.id, age_group="mid") is None

    def test_zh_text_present(self, db: Session, topic_with_hooks):
        hook = get_hook_question(db, topic_with_hooks.id, age_group="mid")
        assert hook is not None
        assert hook.question_text_zh is not None
        assert "朋友" in hook.question_text_zh

    def test_pending_rows_are_not_served(self, db: Session, topic_with_hooks):
        """LLM-generated rows stay invisible until a human approves them."""
        db.query(TopicHookQuestion).filter(
            TopicHookQuestion.topic_id == topic_with_hooks.id
        ).update({TopicHookQuestion.review_status: "pending"})
        db.flush()
        assert get_hook_question(db, topic_with_hooks.id, age_group="mid") is None

    def test_pending_age_group_falls_back_to_approved_mid(
        self, db: Session, topic_with_hooks
    ):
        """An unapproved low row must not block the approved mid fallback."""
        db.query(TopicHookQuestion).filter(
            TopicHookQuestion.topic_id == topic_with_hooks.id,
            TopicHookQuestion.age_group == "low",
        ).update({TopicHookQuestion.review_status: "pending"})
        db.flush()

        hook = get_hook_question(db, topic_with_hooks.id, age_group="low")
        assert hook is not None
        assert hook.age_group == "mid"
        assert hook.review_status == "approved"
