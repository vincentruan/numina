"""Tests for teach-back dual-track grading and progress update (Issue #216)."""

import pytest

from apps.backend.app.services.learning.teach_back_grading import (
    extract_expression,
    grade_expression,
)
from apps.backend.app.services.learning import teach_back_service
from apps.backend.app.services.learning.progress_service import apply_teach_back_success
from packages.db.models.learning.confusion import TopicConfusion
from packages.db.models.learning.progress import LearningProgress
from packages.db.models.learning.session import LearningAssessmentAttempt, LearningSession
from packages.db.models.learning.topic import LearningTopic
from packages.db.models.user import User


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def child_user(db, client, auth_headers):
    """Create a child via API."""
    from datetime import date

    resp = client.post(
        "/api/v1/family/children",
        headers=auth_headers,
        json={
            "username": "teachback_child",
            "password": "ChildPass1",
            "display_name": "Teach Back Kid",
            "avatar_color": "#FF5733",
            "pin": ["\U0001f431", "\U0001f31f", "\U0001f388", "\U0001f436"],
        },
    )
    assert resp.status_code == 201, f"child creation failed: {resp.text}"
    child_id = int(resp.json()["data"]["id"])
    child = db.query(User).filter(User.id == child_id).first()
    child.birthday = date(2017, 1, 1)
    db.flush()

    parent = db.query(User).filter(User.username == "testuser").first()
    return {"id": child_id, "parent_id": parent.id, "family_id": parent.family_id}


@pytest.fixture
def topic(db):
    """Create a test topic."""
    t = LearningTopic(
        topic_key="teachback-topic-1",
        topic_type="CONCEPTUAL",
        subject="mathematics",
        domain="Test",
        name="Teach Back Topic",
        name_zh="教学主题",
        description="Test topic for teach-back",
        age_group="mid",
        source_taxonomy="beijing",
        centrality=50.0,
        evidence_json="[]",
        standards_json="[]",
        curriculum_standards_json="[]",
    )
    db.add(t)
    db.flush()
    return t


# ---------------------------------------------------------------------------
# Expression extraction
# ---------------------------------------------------------------------------


class TestExtractExpression:
    def test_fraction_arithmetic(self):
        text = "因为 1/4 + 2/4 = 3/4，分母不用变"
        assert extract_expression(text) == "1/4 + 2/4 = 3/4"

    def test_multiply(self):
        assert extract_expression("3 × 2 = 6 块") == "3 × 2 = 6"

    def test_bare_fraction(self):
        assert extract_expression("答案是 3/4") == "3/4"

    def test_bare_number(self):
        assert extract_expression("我觉得是 6 块") == "6"

    def test_no_number(self):
        assert extract_expression("没有数字在这里") is None

    def test_empty(self):
        assert extract_expression("") is None
        assert extract_expression(None) is None


# ---------------------------------------------------------------------------
# SymPy grading
# ---------------------------------------------------------------------------


class TestGradeExpression:
    def test_equivalent(self):
        assert grade_expression("3/4", "3/4") is True

    def test_not_equivalent(self):
        assert grade_expression("3/4", "3/8") is False

    def test_algebraically_equivalent(self):
        # numeric_or_symbolic_eq handles algebraic equivalence via SymPy
        assert grade_expression("1/4+2/4", "3/4") is True

    def test_no_expected(self):
        assert grade_expression(None, "3/4") is None

    def test_no_child(self):
        assert grade_expression("3/4", None) is None


# ---------------------------------------------------------------------------
# Progress update
# ---------------------------------------------------------------------------


class TestApplyTeachBackSuccess:
    def test_success_updates_progress(self, db, child_user, topic):
        progress = LearningProgress(
            child_id=child_user["id"],
            topic_id=topic.id,
            mastery_level="mastered",
            stability=2.0,
            ease_factor=2.5,
            consecutive_review_passes=0,
        )
        db.add(progress)
        db.flush()

        result = apply_teach_back_success(db, progress)

        assert result.completed_via == "teaching"
        assert result.stability == pytest.approx(3.0)  # 2.0 * 1.5
        assert result.consecutive_review_passes == 1
        assert result.next_review_at is not None

        # History record created
        attempt = (
            db.query(LearningAssessmentAttempt)
            .filter(
                LearningAssessmentAttempt.child_id == child_user["id"],
                LearningAssessmentAttempt.assessment_type == "teach_back",
            )
            .first()
        )
        assert attempt is not None
        assert attempt.passed is True

    def test_stability_capped_at_30(self, db, child_user, topic):
        progress = LearningProgress(
            child_id=child_user["id"],
            topic_id=topic.id,
            mastery_level="mastered",
            stability=25.0,
            ease_factor=2.5,
            consecutive_review_passes=0,
        )
        db.add(progress)
        db.flush()

        result = apply_teach_back_success(db, progress)
        assert result.stability == 30.0  # capped

    def test_completed_via_teaching_validated(self, db, child_user, topic):
        progress = LearningProgress(
            child_id=child_user["id"],
            topic_id=topic.id,
            mastery_level="mastered",
            stability=1.0,
        )
        db.add(progress)
        db.flush()

        result = apply_teach_back_success(db, progress)
        assert result.completed_via == "teaching"


# ---------------------------------------------------------------------------
# Teach-back service
# ---------------------------------------------------------------------------


class TestTeachBackService:
    def test_get_approved_confusions(self, db, topic):
        # Create 3 confusions: 2 approved, 1 pending
        approved = [
            TopicConfusion(
                topic_id=topic.id,
                sequence=0,
                confusion_text="confusion 0",
                rubric="rubric 0",
                review_status="approved",
            ),
            TopicConfusion(
                topic_id=topic.id,
                sequence=1,
                confusion_text="confusion 1",
                rubric="rubric 1",
                review_status="approved",
            ),
        ]
        pending = TopicConfusion(
            topic_id=topic.id,
            sequence=2,
            confusion_text="confusion 2 (pending)",
            rubric="rubric 2",
            review_status="pending",
        )
        db.add_all(approved + [pending])
        db.flush()

        result = teach_back_service.get_approved_confusions(db, topic.id)
        assert len(result) == 2
        assert all(c.review_status == "approved" for c in result)
        assert result[0].sequence == 0
        assert result[1].sequence == 1

    def test_create_teach_back_session(self, db, child_user, topic):
        child = db.query(User).filter(User.id == child_user["id"]).first()
        session = teach_back_service.create_teach_back_session(db, child, topic)
        assert session.session_type == "teach_back"
        assert session.thread_id == str(session.id)
        assert session.topic_id == topic.id

    def test_validate_rejects_non_mastered(self, db, child_user, topic):
        child = db.query(User).filter(User.id == child_user["id"]).first()
        # Topic not mastered
        progress = LearningProgress(
            child_id=child_user["id"],
            topic_id=topic.id,
            mastery_level="learning",
        )
        db.add(progress)
        db.flush()

        from apps.backend.app.errors import AppError

        with pytest.raises(AppError):
            teach_back_service.validate_teach_back_request(
                db=db, child=child, topic_id=topic.id
            )

    def test_validate_rejects_non_pilot_topic(self, db, child_user):
        child = db.query(User).filter(User.id == child_user["id"]).first()
        from apps.backend.app.errors import AppError

        with pytest.raises(AppError):
            teach_back_service.validate_teach_back_request(
                db=db, child=child, topic_id=999999
            )
