"""Regression tests: suspended review_status excluded from all question selection paths."""
import pytest

from packages.db.models.learning.question import Question
from packages.db.models.learning.topic import LearningTopic


@pytest.fixture
def suspended_question(db_session):
    t = LearningTopic(topic_key="math.suspend.test", subject="mathematics",
                     domain="number", name="Suspend Test", age_group="lower",
                     deprecated=False, topic_type="knowledge")
    db_session.add(t)
    db_session.flush()
    q = Question(
        topic_id=t.id, question_type="calculation",
        stem="1+1=?", answer_json='{"answer": 2}',
        difficulty=1, source="template", review_status="suspended",
        age_group="lower",
    )
    db_session.add(q)
    db_session.flush()
    return t, q


class TestSuspendedExcludedFromSelection:
    """Suspended questions never appear in question selection or coverage."""

    def test_adaptive_service_excludes_suspended(self, db_session, suspended_question):
        from apps.backend.app.services.learning.adaptive_service import select_questions

        t, q = suspended_question
        selected = select_questions(
            db_session, topic_id=t.id, mastery_level="learning",
            count=10, exclude_question_ids=[], exclude_recent_days=0,
            child_id=1,
        )
        assert not any(x.id == q.id for x in selected)

    def test_coverage_service_excludes_suspended(self, db_session, suspended_question):
        from apps.backend.app.services.learning.coverage_service import compute_topic_coverage

        t, _ = suspended_question
        result = compute_topic_coverage(db_session, t.id)
        assert result["existence"] == 0.0

    def test_question_router_excludes_suspended(self, db_session, suspended_question):
        from apps.backend.app.services.learning.question_router import route

        t, _ = suspended_question
        result = route(db_session, t.id)
        # Suspended question doesn't count toward existing coverage →
        # recommended_count stays at max
        assert result.recommended_count == 5


class TestQuestionServiceReviewPaths:
    """question_service review paths handle suspended."""

    def test_question_service_review_supports_suspend(self, db_session, suspended_question):
        from apps.backend.app.services.learning.question_service import review_question

        t, _ = suspended_question
        # Create a pending question, then suspend it via review_question
        q = Question(
            topic_id=t.id, question_type="calculation",
            stem="2+2=?", answer_json='{"answer": 4}',
            difficulty=1, source="template", review_status="pending",
            age_group="lower",
        )
        db_session.add(q)
        db_session.flush()

        result = review_question(db_session, q.id, "suspended")
        assert result.review_status == "suspended"
