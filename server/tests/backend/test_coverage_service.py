"""Tests for minimal coverage service (P7a-min)."""
import pytest

from packages.db.models.learning.question import Question
from packages.db.models.learning.topic import LearningTopic, LearningDependency
from apps.backend.app.services.learning.coverage_service import (
    compute_topic_coverage,
    compute_subject_coverage,
    get_gap_report,
    get_prerequisite_value,
)


@pytest.fixture
def math_topics(db_session):
    """Create a small set of math topics with dependencies."""
    t1 = LearningTopic(topic_key="math.add", subject="mathematics", domain="number",
                       name="Addition", age_group="lower", deprecated=False,
                       topic_type="knowledge")
    t2 = LearningTopic(topic_key="math.mul", subject="mathematics", domain="number",
                       name="Multiplication", age_group="lower", deprecated=False,
                       topic_type="knowledge")
    t3 = LearningTopic(topic_key="math.div", subject="mathematics", domain="number",
                       name="Division", age_group="lower", deprecated=False,
                       topic_type="knowledge")
    db_session.add_all([t1, t2, t3])
    db_session.flush()
    # t2 depends on t1, t3 depends on t2
    db_session.add_all([
        LearningDependency(topic_id=t2.id, prerequisite_id=t1.id, strength="required"),
        LearningDependency(topic_id=t3.id, prerequisite_id=t2.id, strength="required"),
    ])
    db_session.flush()
    return [t1, t2, t3]


class TestPrerequisiteValue:
    """Prerequisite value = normalized dependent count."""

    def test_topic_with_no_dependents_returns_zero(self, db_session, math_topics):
        t3 = math_topics[2]  # Division — nothing depends on it
        value = get_prerequisite_value(db_session, t3.id)
        assert value == 0.0

    def test_topic_with_dependents_returns_positive(self, db_session, math_topics):
        t1 = math_topics[0]  # Addition — Multiplication depends on it
        value = get_prerequisite_value(db_session, t1.id)
        assert value > 0.0

    def test_value_is_normalized_to_zero_one(self, db_session, math_topics):
        t1 = math_topics[0]
        value = get_prerequisite_value(db_session, t1.id)
        assert 0.0 <= value <= 1.0


class TestTopicCoverage:
    """Coverage score = binary existence in P7a-min."""

    def test_topic_without_questions_has_zero_existence(self, db_session, math_topics):
        result = compute_topic_coverage(db_session, math_topics[0].id)
        assert result["existence"] == 0.0
        assert result["coverage_score"] == 0.0

    def test_topic_with_approved_question_has_full_existence(self, db_session, math_topics):
        t1 = math_topics[0]
        db_session.add(Question(
            topic_id=t1.id, question_type="calculation",
            stem="1+1=?", answer_json='{"answer": 2}',
            difficulty=1, source="template", review_status="approved",
            age_group="lower",
        ))
        db_session.flush()

        result = compute_topic_coverage(db_session, t1.id)
        assert result["existence"] == 1.0

    def test_rejected_questions_dont_count(self, db_session, math_topics):
        t1 = math_topics[0]
        db_session.add(Question(
            topic_id=t1.id, question_type="calculation",
            stem="1+1=?", answer_json='{"answer": 2}',
            difficulty=1, source="template", review_status="rejected",
            age_group="lower",
        ))
        db_session.flush()

        result = compute_topic_coverage(db_session, t1.id)
        assert result["existence"] == 0.0

    def test_suspended_questions_dont_count(self, db_session, math_topics):
        t1 = math_topics[0]
        db_session.add(Question(
            topic_id=t1.id, question_type="calculation",
            stem="1+1=?", answer_json='{"answer": 2}',
            difficulty=1, source="template", review_status="suspended",
            age_group="lower",
        ))
        db_session.flush()

        result = compute_topic_coverage(db_session, t1.id)
        assert result["existence"] == 0.0


class TestSubjectCoverage:
    """Subject-level aggregation."""

    def test_subject_coverage_aggregation(self, db_session, math_topics):
        t1 = math_topics[0]
        db_session.add(Question(
            topic_id=t1.id, question_type="calculation",
            stem="1+1=?", answer_json='{"answer": 2}',
            difficulty=1, source="template", review_status="approved",
            age_group="lower",
        ))
        db_session.flush()

        result = compute_subject_coverage(db_session, "mathematics")
        assert result["total_topics"] == 3
        assert result["covered_topics"] == 1
        assert 0.0 < result["coverage_rate"] < 1.0


class TestGapReport:
    """Gap report lists topics below threshold, sorted by prerequisite value."""

    def test_gap_report_returns_topics_below_threshold(self, db_session, math_topics):
        report = get_gap_report(db_session, subject="mathematics", threshold=0.5)
        # All 3 topics have no questions → all below threshold
        assert len(report) == 3

    def test_gap_report_sorted_by_prerequisite_value(self, db_session, math_topics):
        report = get_gap_report(db_session, subject="mathematics", threshold=0.5)
        # First item should have highest prerequisite value
        values = [item["prerequisite_value"] for item in report]
        assert values == sorted(values, reverse=True)
