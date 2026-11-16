"""Tests for empirical difficulty calculator."""

import pytest
from sqlalchemy.orm import Session

from apps.backend.app.services.learning.difficulty_calculator import (
    DIFFICULTY_MAX,
    DIFFICULTY_MIN,
    MIN_SAMPLE_SIZE,
    DifficultySignals,
    batch_update_empirical_difficulty,
    calculate_empirical_difficulty,
    get_difficulty_stats,
    signals_to_difficulty,
)
from packages.db.models.learning.practice import PracticeAttempt
from packages.db.models.learning.question import Question
from packages.db.models.learning.topic import LearningTopic


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_topic(db: Session, *, key: str, **kw) -> LearningTopic:
    """Create a learning topic with required fields."""
    topic = LearningTopic(
        topic_key=key,
        topic_type=kw.get("topic_type", "CONCEPTUAL"),
        subject=kw.get("subject", "mathematics"),
        domain=kw.get("domain", "Test"),
        name=kw.get("name", f"Topic {key}"),
        name_zh=kw.get("name_zh"),
        description="Test topic",
        age_group=kw.get("age_group", "mid"),
        centrality=kw.get("centrality", 50.0),
        evidence_json="[]",
        standards_json="[]",
        curriculum_standards_json=kw.get("curriculum_standards_json", "[]"),
    )
    db.add(topic)
    db.flush()
    return topic


def _make_question(db: Session, *, topic_id: int, difficulty: int = 2) -> Question:
    """Create a sample question."""
    question = Question(
        topic_id=topic_id,
        question_type="multiple_choice",
        stem="What is 2 + 3?",
        answer_json='{"answer": 5}',
        difficulty=difficulty,
        bloom_level="apply",
        source="template",
        age_group="6-8",
        review_status="approved",
    )
    db.add(question)
    db.flush()
    return question


def _make_attempt(
    db: Session,
    *,
    question_id: int,
    topic_id: int,
    child_id: int,
    is_correct: bool,
    time_spent_seconds: int = 30,
    is_retry: bool = False,
    session_id: int | None = None,
) -> PracticeAttempt:
    """Create a practice attempt."""
    # Use child_id as session_id base to ensure uniqueness per attempt
    if session_id is None:
        session_id = child_id * 1000 + question_id % 1000
    attempt = PracticeAttempt(
        session_id=session_id,
        question_id=question_id,
        child_id=child_id,
        topic_id=topic_id,
        user_answer_json='{"answer": 5}',
        is_correct=is_correct,
        time_spent_seconds=time_spent_seconds,
        attempt_number=1,
        is_retry=is_retry,
    )
    db.add(attempt)
    return attempt


@pytest.fixture
def topic(db: Session) -> LearningTopic:
    return _make_topic(db, key="test.difficulty.topic")


@pytest.fixture
def question(db: Session, topic: LearningTopic) -> Question:
    return _make_question(db, topic_id=topic.id)


# ---------------------------------------------------------------------------
# Tests: signals_to_difficulty (pure function, no DB)
# ---------------------------------------------------------------------------


class TestSignalsToDifficulty:
    """Test the signals_to_difficulty conversion function."""

    def test_perfect_accuracy_easy(self):
        """All correct, fast, no retries → easy (close to 1)."""
        signals = DifficultySignals(
            attempt_count=20,
            accuracy=1.0,  # 100% correct
            median_time_seconds=15,  # Fast
            retry_rate=0.0,
        )
        result = signals_to_difficulty(signals)
        assert result == DIFFICULTY_MIN  # Easiest

    def test_zero_accuracy_hard(self):
        """All wrong, slow, many retries → hard (close to 5)."""
        signals = DifficultySignals(
            attempt_count=20,
            accuracy=0.0,  # 0% correct
            median_time_seconds=60,  # Slow
            retry_rate=1.0,  # All retries
        )
        result = signals_to_difficulty(signals)
        assert result == DIFFICULTY_MAX  # Hardest

    def test_medium_difficulty(self):
        """50% accuracy, medium time → medium difficulty."""
        signals = DifficultySignals(
            attempt_count=20,
            accuracy=0.5,
            median_time_seconds=30,  # Baseline
            retry_rate=0.5,
        )
        result = signals_to_difficulty(signals)
        # Should be around 3.0 (middle of 1-5 scale)
        assert 2.5 <= result <= 3.5

    def test_accuracy_dominates(self):
        """Accuracy has highest weight (50%)."""
        easy_accuracy = DifficultySignals(
            attempt_count=20, accuracy=0.9, median_time_seconds=30, retry_rate=0.5
        )
        hard_accuracy = DifficultySignals(
            attempt_count=20, accuracy=0.1, median_time_seconds=30, retry_rate=0.5
        )
        easy_result = signals_to_difficulty(easy_accuracy)
        hard_result = signals_to_difficulty(hard_accuracy)
        # Hard should be significantly higher
        assert hard_result - easy_result > 1.5

    def test_no_time_data_neutral(self):
        """No time data → neutral time factor."""
        signals = DifficultySignals(
            attempt_count=20,
            accuracy=0.5,
            median_time_seconds=None,
            retry_rate=0.5,
        )
        result = signals_to_difficulty(signals)
        # Should still compute, using neutral time factor
        assert DIFFICULTY_MIN <= result <= DIFFICULTY_MAX


# ---------------------------------------------------------------------------
# Tests: calculate_empirical_difficulty (needs DB)
# ---------------------------------------------------------------------------


class TestCalculateEmpiricalDifficulty:
    """Test calculate_empirical_difficulty with database."""

    def test_insufficient_data_returns_none(
        self, db: Session, topic: LearningTopic, question: Question
    ):
        """Fewer than MIN_SAMPLE_SIZE attempts → None."""
        for i in range(5):
            _make_attempt(
                db,
                question_id=question.id,
                topic_id=topic.id,
                child_id=100 + i,
                is_correct=(i % 2 == 0),
            )
        db.flush()

        result = calculate_empirical_difficulty(db, question.id)
        assert result is None

    def test_sufficient_data_returns_value(
        self, db: Session, topic: LearningTopic, question: Question
    ):
        """≥MIN_SAMPLE_SIZE attempts → float value."""
        for i in range(MIN_SAMPLE_SIZE):
            _make_attempt(
                db,
                question_id=question.id,
                topic_id=topic.id,
                child_id=100 + i,
                is_correct=True,
                time_spent_seconds=20,
            )
        db.flush()

        result = calculate_empirical_difficulty(db, question.id)
        assert result is not None
        assert DIFFICULTY_MIN <= result <= DIFFICULTY_MAX

    def test_all_correct_easy(
        self, db: Session, topic: LearningTopic, question: Question
    ):
        """All correct answers → low difficulty."""
        for i in range(MIN_SAMPLE_SIZE):
            _make_attempt(
                db,
                question_id=question.id,
                topic_id=topic.id,
                child_id=100 + i,
                is_correct=True,
                time_spent_seconds=15,  # Fast
            )
        db.flush()

        result = calculate_empirical_difficulty(db, question.id)
        assert result is not None
        assert result < 2.0  # Should be easy

    def test_all_wrong_hard(
        self, db: Session, topic: LearningTopic, question: Question
    ):
        """All wrong answers → high difficulty."""
        for i in range(MIN_SAMPLE_SIZE):
            _make_attempt(
                db,
                question_id=question.id,
                topic_id=topic.id,
                child_id=100 + i,
                is_correct=False,
                time_spent_seconds=60,  # Slow
                is_retry=True,
            )
        db.flush()

        result = calculate_empirical_difficulty(db, question.id)
        assert result is not None
        assert result > 4.0  # Should be hard


# ---------------------------------------------------------------------------
# Tests: batch_update_empirical_difficulty
# ---------------------------------------------------------------------------


class TestBatchUpdateEmpiricalDifficulty:
    """Test batch_update_empirical_difficulty."""

    def test_updates_eligible_questions(
        self, db: Session, topic: LearningTopic, question: Question
    ):
        """Questions with ≥MIN_SAMPLE_SIZE attempts get empirical_difficulty set."""
        for i in range(MIN_SAMPLE_SIZE):
            _make_attempt(
                db,
                question_id=question.id,
                topic_id=topic.id,
                child_id=100 + i,
                is_correct=True,
            )
        db.flush()

        # Initially no empirical difficulty
        assert question.empirical_difficulty is None

        result = batch_update_empirical_difficulty(db)

        # Should have updated
        assert result["updated"] >= 1

        # Refresh and check
        db.refresh(question)
        assert question.empirical_difficulty is not None

    def test_skips_ineligible_questions(
        self, db: Session, topic: LearningTopic, question: Question
    ):
        """Questions with <MIN_SAMPLE_SIZE attempts are skipped."""
        for i in range(5):
            _make_attempt(
                db,
                question_id=question.id,
                topic_id=topic.id,
                child_id=100 + i,
                is_correct=True,
            )
        db.flush()

        result = batch_update_empirical_difficulty(db)

        # Should have skipped
        db.refresh(question)
        assert question.empirical_difficulty is None


# ---------------------------------------------------------------------------
# Tests: get_difficulty_stats
# ---------------------------------------------------------------------------


class TestGetDifficultyStats:
    """Test get_difficulty_stats."""

    def test_stats_with_data(self, db: Session, topic: LearningTopic, question: Question):
        """Stats reflect questions with and without empirical difficulty."""
        # Set empirical difficulty on the sample question
        question.empirical_difficulty = 3.5
        db.flush()

        stats = get_difficulty_stats(db)
        assert stats["total_questions"] >= 1
        assert stats["with_empirical"] >= 1
        assert stats["coverage_pct"] > 0
        assert stats["avg_empirical"] == 3.5
