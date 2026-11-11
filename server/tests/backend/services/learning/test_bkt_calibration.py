"""Tests for per-skill BKT parameter calibration."""

import pytest
from sqlalchemy.orm import Session

from apps.backend.app.services.learning.bkt_calibration import (
    DEFAULT_P_G,
    DEFAULT_P_L0,
    DEFAULT_P_S,
    DEFAULT_P_T,
    MIN_FIT_ATTEMPTS,
    batch_fit_parameters,
    clear_cache,
    fit_bkt_parameters,
    get_bkt_parameters,
    get_fit_stats,
)
from packages.db.models.learning.practice import PracticeAttempt, PracticeSession
from packages.db.models.learning.question import Question
from packages.db.models.learning.topic import LearningTopic


def _make_topic(db: Session, *, key: str) -> LearningTopic:
    topic = LearningTopic(
        topic_key=key,
        topic_type="CONCEPTUAL",
        subject="mathematics",
        domain="Test",
        name=f"Topic {key}",
        description="Test topic",
        age_group="mid",
        centrality=50.0,
        evidence_json="[]",
        standards_json="[]",
        curriculum_standards_json="[]",
    )
    db.add(topic)
    db.flush()
    return topic


def _make_question(db: Session, *, topic_id: int) -> Question:
    question = Question(
        topic_id=topic_id,
        question_type="multiple_choice",
        stem="Test question",
        answer_json='{"answer": 5}',
        difficulty=2,
        bloom_level="apply",
        source="template",
        age_group="6-8",
        review_status="approved",
    )
    db.add(question)
    db.flush()
    return question


def _make_session(db: Session, *, child_id: int, topic_id: int) -> PracticeSession:
    session = PracticeSession(
        child_id=child_id,
        topic_id=topic_id,
        session_mode="practice",
        question_ids_json="[]",
    )
    db.add(session)
    db.flush()
    return session


def _make_attempt(
    db: Session,
    *,
    child_id: int,
    question_id: int,
    topic_id: int,
    session_id: int,
    is_correct: bool,
) -> PracticeAttempt:
    attempt = PracticeAttempt(
        session_id=session_id,
        child_id=child_id,
        question_id=question_id,
        topic_id=topic_id,
        user_answer_json='{"answer": 5}',
        is_correct=is_correct,
        time_spent_seconds=30,
        attempt_number=1,
        is_retry=False,
    )
    db.add(attempt)
    return attempt


@pytest.fixture
def topic_with_data(db: Session):
    """Create a topic with enough attempts for fitting."""
    topic = _make_topic(db, key="bkt_test_topic")
    child_id = 12345
    session = _make_session(db, child_id=child_id, topic_id=topic.id)

    # Create MIN_FIT_ATTEMPTS questions with 70% accuracy attempts
    # (unique constraint requires one attempt per session+question pair)
    questions = [_make_question(db, topic_id=topic.id) for _ in range(MIN_FIT_ATTEMPTS)]
    for i, q in enumerate(questions):
        _make_attempt(
            db,
            child_id=child_id,
            question_id=q.id,
            topic_id=topic.id,
            session_id=session.id,
            is_correct=(i % 10 < 7),  # 70% correct
        )
    db.commit()
    return topic


@pytest.fixture
def topic_without_data(db: Session):
    """Create a topic with insufficient attempts."""
    topic = _make_topic(db, key="bkt_no_data_topic")
    child_id = 12345
    session = _make_session(db, child_id=child_id, topic_id=topic.id)

    # Only 5 attempts (below MIN_FIT_ATTEMPTS)
    questions = [_make_question(db, topic_id=topic.id) for _ in range(5)]
    for i, q in enumerate(questions):
        _make_attempt(
            db,
            child_id=child_id,
            question_id=q.id,
            topic_id=topic.id,
            session_id=session.id,
            is_correct=(i % 2 == 0),
        )
    db.commit()
    return topic


class TestBKTParameterFitting:
    """Test fit_bkt_parameters function."""

    def test_insufficient_data_returns_defaults(self, db: Session, topic_without_data):
        """Topics with < MIN_FIT_ATTEMPTS get default parameters."""
        params = fit_bkt_parameters(db, topic_without_data.id)

        assert params.topic_id == topic_without_data.id
        assert params.is_fitted is False
        assert params.p_l0 == DEFAULT_P_L0
        assert params.p_t == DEFAULT_P_T
        assert params.p_g == DEFAULT_P_G
        assert params.p_s == DEFAULT_P_S
        assert params.sample_size == 5

    def test_sufficient_data_fits_parameters(self, db: Session, topic_with_data):
        """Topics with >= MIN_FIT_ATTEMPTS get fitted parameters."""
        clear_cache()
        params = fit_bkt_parameters(db, topic_with_data.id)

        assert params.topic_id == topic_with_data.id
        assert params.is_fitted is True
        assert params.sample_size == MIN_FIT_ATTEMPTS
        # Parameters should be within valid bounds
        assert 0.01 <= params.p_l0 <= 0.5
        assert 0.01 <= params.p_t <= 0.8
        assert 0.0 <= params.p_g <= 0.5
        assert 0.0 <= params.p_s <= 0.4

    def test_high_accuracy_topic_has_higher_p_l0(self, db: Session):
        """Easy topics (high accuracy) should have higher P(L0)."""
        topic = _make_topic(db, key="easy_topic")
        session = _make_session(db, child_id=999, topic_id=topic.id)

        # Create multiple questions and 90% accuracy attempts
        questions = [_make_question(db, topic_id=topic.id) for _ in range(MIN_FIT_ATTEMPTS)]
        for i, q in enumerate(questions):
            _make_attempt(
                db,
                child_id=999,
                question_id=q.id,
                topic_id=topic.id,
                session_id=session.id,
                is_correct=(i % 10 < 9),  # 90% correct
            )
        db.commit()
        clear_cache()

        params = fit_bkt_parameters(db, topic.id)
        assert params.is_fitted
        assert params.p_l0 > DEFAULT_P_L0  # Higher initial knowledge

    def test_low_accuracy_topic_has_lower_p_l0(self, db: Session):
        """Hard topics (low accuracy) should have lower P(L0) than the default."""
        topic = _make_topic(db, key="hard_topic")
        session = _make_session(db, child_id=888, topic_id=topic.id)

        # Create multiple questions and 10% accuracy attempts
        questions = [_make_question(db, topic_id=topic.id) for _ in range(MIN_FIT_ATTEMPTS)]
        for i, q in enumerate(questions):
            _make_attempt(
                db,
                child_id=888,
                question_id=q.id,
                topic_id=topic.id,
                session_id=session.id,
                is_correct=(i == 0),  # 1/20 = 5% correct
            )
        db.commit()
        clear_cache()

        params = fit_bkt_parameters(db, topic.id)
        assert params.is_fitted
        # accuracy 0.05 -> p_l0 = 0.05 + 0.35*0.05 = 0.0675 < default 0.1
        assert params.p_l0 < DEFAULT_P_L0  # Lower initial knowledge


class TestGetBKTParameters:
    """Test get_bkt_parameters with caching."""

    def test_caches_fitted_parameters(self, db: Session, topic_with_data):
        """Parameters are cached after first call."""
        clear_cache()

        params1 = get_bkt_parameters(db, topic_with_data.id)
        params2 = get_bkt_parameters(db, topic_with_data.id)

        assert params1 is params2  # Same object (cached)

    def test_clear_cache_works(self, db: Session, topic_with_data):
        """clear_cache() removes cached parameters."""
        clear_cache()
        get_bkt_parameters(db, topic_with_data.id)

        clear_cache()
        params = get_bkt_parameters(db, topic_with_data.id)

        assert params.is_fitted  # Re-fitted from data


class TestBatchFitParameters:
    """Test batch_fit_parameters function."""

    def test_batch_fit_multiple_topics(self, db: Session):
        """Batch fit processes multiple topics."""
        topic1 = _make_topic(db, key="batch_topic_1")
        topic2 = _make_topic(db, key="batch_topic_2")
        s1 = _make_session(db, child_id=111, topic_id=topic1.id)
        s2 = _make_session(db, child_id=111, topic_id=topic2.id)

        # Create multiple questions per topic (unique constraint on session+question)
        qs1 = [_make_question(db, topic_id=topic1.id) for _ in range(MIN_FIT_ATTEMPTS)]
        qs2 = [_make_question(db, topic_id=topic2.id) for _ in range(MIN_FIT_ATTEMPTS)]

        for q in qs1:
            _make_attempt(db, child_id=111, question_id=q.id, topic_id=topic1.id, session_id=s1.id, is_correct=True)
        for q in qs2:
            _make_attempt(db, child_id=111, question_id=q.id, topic_id=topic2.id, session_id=s2.id, is_correct=False)
        db.commit()
        clear_cache()

        results = batch_fit_parameters(db, [topic1.id, topic2.id])

        assert len(results) == 2
        assert results[topic1.id].is_fitted
        assert results[topic2.id].is_fitted


class TestGetFitStats:
    """Test get_fit_stats function."""

    def test_stats_reflect_fitting_coverage(self, db: Session, topic_with_data, topic_without_data):
        """Stats correctly report fitted vs unfitted topics."""
        stats = get_fit_stats(db)

        assert stats["total_topics_with_data"] >= 2
        assert stats["min_fit_attempts"] == MIN_FIT_ATTEMPTS
        # At least topic_with_data should be fittable
        assert stats["fitted_topics"] >= 1
