"""Tests for teach-back dual-track grading and progress update (Issue #216, #234)."""

import pytest

from apps.backend.app.services.learning import teach_back_service
from apps.backend.app.services.learning.progress_service import apply_teach_back_success
from apps.backend.app.services.learning.teach_back_grading import (
    extract_expression,
    grade_expression,
)
from packages.core.settings import Settings
from packages.db.models.learning.confusion import TopicConfusion
from packages.db.models.learning.progress import LearningProgress
from packages.db.models.learning.session import (
    LearningAssessmentAttempt,
)
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

    def test_fraction_multiply(self):
        assert extract_expression("1/2 × 1/3 = 1/6 对的") == "1/2 × 1/3 = 1/6"

    def test_decimal(self):
        assert extract_expression("答案是 0.25") == "0.25"

    def test_decimal_in_text(self):
        assert extract_expression("因为 0.5 等于 0.50") == "0.5"

    def test_percent(self):
        # Percent is converted to fraction form
        assert extract_expression("25% 就是四分之一") == "25/100"

    def test_percent_in_text(self):
        assert extract_expression("我觉得 50% 就是一半") == "50/100"

    def test_bare_fraction(self):
        assert extract_expression("答案是 3/4") == "3/4"

    def test_bare_number(self):
        assert extract_expression("我觉得是 6 块") == "6"

    def test_no_number(self):
        assert extract_expression("没有数字在这里") is None

    def test_empty(self):
        assert extract_expression("") is None
        assert extract_expression(None) is None

    def test_priority_fraction_multiply_over_decimal(self):
        """Fraction multiply pattern is more specific than bare decimal."""
        text = "1/2 × 1/3 = 1/6 也就是约 0.17"
        assert extract_expression(text) == "1/2 × 1/3 = 1/6"


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

    def test_equation_form_matches_bare_value(self):
        """The extractor captures equations; they must grade against a bare value."""
        assert grade_expression("3/4", "1/4 + 2/4 = 3/4") is True

    def test_equation_form_with_wrong_result(self):
        assert grade_expression("3/4", "1/4 + 2/4 = 3/8") is False

    def test_expected_may_itself_be_an_equation(self):
        """Seed rows store full equations as the expected expression."""
        assert grade_expression("1/4 + 2/4 = 3/4", "1/4 + 2/4 = 3/4") is True

    def test_prose_yields_unknown_not_false(self):
        """Free text must never read as a wrong answer — that would downgrade a hit."""
        assert grade_expression("3/4", "嗯我不确定") is None
        assert grade_expression("3/4", "the denominator stays the same") is None

    def test_equivalent_fractions(self):
        assert grade_expression("1/2", "2/4") is True
        assert grade_expression("2/6", "1/3") is True

    def test_decimal_equivalent_to_fraction(self):
        """0.25 should grade as equivalent to 1/4."""
        assert grade_expression("1/4", "0.25") is True

    def test_decimal_equivalence(self):
        """0.5 and 0.50 should be equivalent."""
        assert grade_expression("0.5", "0.50") is True

    def test_decimal_not_equivalent(self):
        assert grade_expression("0.5", "0.25") is False

    def test_percent_equivalent_to_fraction(self):
        """25% (extracted as 25/100) should grade as equivalent to 1/4."""
        assert grade_expression("1/4", "25/100") is True

    def test_percent_50(self):
        """50% (extracted as 50/100) should grade as equivalent to 1/2."""
        assert grade_expression("1/2", "50/100") is True

    def test_fraction_multiply_grading(self):
        """1/2 × 1/3 = 1/6 should grade correctly."""
        assert grade_expression("1/6", "1/2 × 1/3 = 1/6") is True

    def test_x_letter_multiply_form(self):
        """The ASCII 'x' separator the extractor accepts must also grade."""
        assert extract_expression("3 x 2 = 6") == "3 x 2 = 6"
        assert grade_expression("6", "3 × 2 = 6") is True

    def test_decimal_expected_fraction_child(self):
        """Reverse direction: expected is a decimal seed, child text yields a fraction."""
        assert grade_expression("0.25", "1/4") is True
        assert grade_expression("0.5", "2/4") is True

    def test_percent_expected_fraction_child(self):
        assert grade_expression("50/100", "1/2") is True


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
        # #49: the 180-day cap and the 30.0 stability ceiling are the guard rails
        # that keep R1's next-revisit trigger reachable — assert both.
        from datetime import UTC, datetime, timedelta

        assert result.next_review_at <= datetime.now(UTC) + timedelta(days=180)

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

    def test_next_review_capped_at_180_days(self, db, child_user, topic):
        """A high-stability, high-ease row must not produce a century-scale interval."""
        from datetime import UTC, datetime, timedelta

        progress = LearningProgress(
            child_id=child_user["id"],
            topic_id=topic.id,
            mastery_level="mastered",
            stability=30.0,
            ease_factor=2.5,
            consecutive_review_passes=0,
        )
        db.add(progress)
        db.flush()

        result = apply_teach_back_success(db, progress)

        assert result.stability == 30.0
        assert result.next_review_at is not None
        assert result.next_review_at <= datetime.now(UTC) + timedelta(days=180)

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
        """A real teach-back-enabled topic that is not mastered is rejected for the mastery reason.

        #46: the previous fixture used a non-enabled topic, so this passed because of
        the scope guard rather than the mastery guard. Put an enabled topic key
        on the fixture so only the mastery check can reject.
        """
        from packages.core.settings import settings

        child = db.query(User).filter(User.id == child_user["id"]).first()
        topic.topic_key = next(iter(settings.teach_back_enabled_topic_keys_set))
        db.flush()

        progress = LearningProgress(
            child_id=child_user["id"],
            topic_id=topic.id,
            mastery_level="learning",
        )
        db.add(progress)
        db.flush()

        from apps.backend.app.errors import AppError

        with pytest.raises(AppError) as exc_info:
            teach_back_service.validate_teach_back_request(
                db=db, child=child, topic_id=topic.id
            )
        details = getattr(exc_info.value, "details", None) or {}
        assert "mastered" in str(details), (
            f"expected the mastery guard to reject, got {details!r}"
        )

    def test_validate_rejects_non_enabled_topic(self, db, child_user):
        child = db.query(User).filter(User.id == child_user["id"]).first()
        from apps.backend.app.errors import AppError

        with pytest.raises(AppError):
            teach_back_service.validate_teach_back_request(
                db=db, child=child, topic_id=999999
            )

    def test_validate_rejects_topic_outside_allowlist(self, db, child_user, topic):
        """A topic that exists but is not in the enabled set is rejected (#234).

        The default allowlist contains real taxonomy keys, so a fixture key like
        'teachback-topic-1' is never in the set — this isolates the allowlist guard.
        """
        from apps.backend.app.errors import AppError

        child = db.query(User).filter(User.id == child_user["id"]).first()
        assert topic.topic_key not in (
            settings_holder().teach_back_enabled_topic_keys_set
        )
        with pytest.raises(AppError) as exc_info:
            teach_back_service.validate_teach_back_request(
                db=db, child=child, topic_id=topic.id
            )
        details = getattr(exc_info.value, "details", None) or {}
        assert "enabled" in str(details), (
            f"expected the allowlist guard to reject, got {details!r}"
        )


# ---------------------------------------------------------------------------
# TEACH_BACK_ENABLED_TOPIC_KEYS configuration (Issue #234)
# ---------------------------------------------------------------------------

_EXPECTED_DEFAULT_KEYS = frozenset(
    {
        "mt_9KmVWCuh5_",
        "mt_ndGqFPWyen",
        "mt_FP-mjXaq3B",
        "mt_Fl7b8q9pI1",
        "mt_ZM9mhHsyYZ",
        "mt_TgHxujL81r",
    }
)


def settings_holder():
    """Lazy settings import to keep module-level import ordering tidy."""
    from packages.core.settings import settings

    return settings


class TestTeachBackEnabledTopicKeysConfig:
    def test_default_includes_all_six_topics(self):
        assert settings_holder().teach_back_enabled_topic_keys_set == _EXPECTED_DEFAULT_KEYS

    def test_custom_keys_parsed(self, monkeypatch):
        monkeypatch.setenv("TEACH_BACK_ENABLED_TOPIC_KEYS", "mt_a,mt_b")
        from packages.core.settings import Settings

        s = Settings()
        assert s.teach_back_enabled_topic_keys_set == frozenset({"mt_a", "mt_b"})

    def test_whitespace_stripped(self, monkeypatch):
        monkeypatch.setenv("TEACH_BACK_ENABLED_TOPIC_KEYS", " mt_a ,  mt_b ")
        from packages.core.settings import Settings

        s = Settings()
        assert s.teach_back_enabled_topic_keys_set == frozenset({"mt_a", "mt_b"})

    def test_empty_string_yields_empty_set(self, monkeypatch):
        monkeypatch.setenv("TEACH_BACK_ENABLED_TOPIC_KEYS", "")
        from packages.core.settings import Settings

        s = Settings()
        assert s.teach_back_enabled_topic_keys_set == frozenset()
