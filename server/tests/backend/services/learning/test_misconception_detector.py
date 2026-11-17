"""Tests for the misconception detection service."""

import json

import pytest

from apps.backend.app.services.learning.misconception_detector import (
    detect_misconception,
    _extract_fractions_from_question,
    _algo_fraction_add_numerators,
    _algo_fraction_add_product_denominator,
)
from packages.db.models.learning.misconception import Misconception


# The `db` fixture is provided by tests/backend/conftest.py (in-memory SQLite with tables).


@pytest.fixture
def topic(db):
    """Create a test topic."""
    from packages.db.models.learning.topic import LearningTopic

    t = LearningTopic(
        topic_key="test_fraction_add",
        topic_type="concept",
        subject="math",
        name="Fraction Addition",
        name_zh="分数加法",
        description="Test topic for fraction addition",
        age_group="mid",
        source_taxonomy="test",
    )
    db.add(t)
    db.flush()
    return t


@pytest.fixture
def question(db, topic):
    """Create a test fraction addition question (1/3 + 1/4)."""
    from packages.db.models.learning.question import Question

    q = Question(
        topic_id=topic.id,
        question_type="calculation",
        stem="What is 1/3 + 1/4?",
        stem_zh="1/3 + 1/4 等于多少？",
        answer_json=json.dumps({
            "answer": "7/12",
            "fractions": [[1, 3], [1, 4]],
        }),
        difficulty=2,
        bloom_level="apply",
        source="test",
        age_group="mid",
        review_status="approved",
    )
    db.add(q)
    db.flush()
    return q


def _create_misconception(db, topic, **kwargs) -> Misconception:
    """Helper to create an approved misconception."""
    defaults = {
        "topic_id": topic.id,
        "sequence": 0,
        "error_pattern_json": json.dumps({"match_type": "symbolic", "expected_wrong": "2/7"}),
        "description": "Adding numerators and denominators",
        "description_zh": "分子分母分别相加",
        "age_group": "mid",
        "review_status": "approved",
    }
    defaults.update(kwargs)
    m = Misconception(**defaults)
    db.add(m)
    db.flush()
    return m


# --- Happy path ---


class TestSymbolicMatching:
    def test_exact_match_returns_misconception(self, db, topic, question):
        """Wrong answer '2/7' matches symbolic pattern with expected_wrong '2/7'."""
        m = _create_misconception(
            db, topic,
            error_pattern_json=json.dumps({"match_type": "symbolic", "expected_wrong": "2/7"}),
        )
        result = detect_misconception(db, topic.id, {"answer": "2/7"}, question)
        assert result is not None
        assert result.id == m.id

    def test_no_match_returns_none(self, db, topic, question):
        """Wrong answer '5/12' does not match any pattern."""
        _create_misconception(
            db, topic,
            error_pattern_json=json.dumps({"match_type": "symbolic", "expected_wrong": "2/7"}),
        )
        result = detect_misconception(db, topic.id, {"answer": "5/12"}, question)
        assert result is None

    def test_correct_answer_not_detected(self, db, topic, question):
        """Correct answer '7/12' is not a misconception (detection only runs on wrong answers)."""
        _create_misconception(
            db, topic,
            error_pattern_json=json.dumps({"match_type": "symbolic", "expected_wrong": "2/7"}),
        )
        result = detect_misconception(db, topic.id, {"answer": "7/12"}, question)
        assert result is None


class TestNumericMatching:
    def test_within_tolerance_matches(self, db, topic, question):
        """Numeric answer within tolerance matches."""
        m = _create_misconception(
            db, topic,
            error_pattern_json=json.dumps({
                "match_type": "numeric",
                "expected_wrong": 0.286,
                "tolerance": 0.01,
            }),
        )
        result = detect_misconception(db, topic.id, {"answer": "0.285"}, question)
        assert result is not None
        assert result.id == m.id

    def test_outside_tolerance_no_match(self, db, topic, question):
        """Numeric answer outside tolerance does not match."""
        _create_misconception(
            db, topic,
            error_pattern_json=json.dumps({
                "match_type": "numeric",
                "expected_wrong": 0.286,
                "tolerance": 0.01,
            }),
        )
        result = detect_misconception(db, topic.id, {"answer": "0.5"}, question)
        assert result is None


class TestParametricMatching:
    def test_fraction_add_numerators_detected(self, db, topic, question):
        """For 1/3 + 1/4, wrong answer '2/7' matches 'add numerators and denominators'."""
        m = _create_misconception(
            db, topic,
            sequence=0,
            error_pattern_json=json.dumps({
                "match_type": "parametric",
                "algorithm": "fraction_add_numerators",
            }),
            description="Adding numerators and denominators",
        )
        # 1/3 + 1/4: naive addition gives (1+1)/(3+4) = 2/7
        result = detect_misconception(db, topic.id, {"answer": "2/7"}, question)
        assert result is not None
        assert result.id == m.id

    def test_fraction_add_numerators_no_match_for_correct(self, db, topic, question):
        """Correct answer 7/12 does not trigger the parametric misconception."""
        _create_misconception(
            db, topic,
            error_pattern_json=json.dumps({
                "match_type": "parametric",
                "algorithm": "fraction_add_numerators",
            }),
        )
        result = detect_misconception(db, topic.id, {"answer": "7/12"}, question)
        assert result is None

    def test_fraction_add_whole_numbers_detected(self, db, topic, question):
        """For 1/3 + 1/4, wrong answer '2' matches 'whole number addition'."""
        m = _create_misconception(
            db, topic,
            error_pattern_json=json.dumps({
                "match_type": "parametric",
                "algorithm": "fraction_add_whole_numbers",
            }),
            description="Whole number addition",
        )
        # 1/3 + 1/4: whole number addition gives 1+1 = 2
        result = detect_misconception(db, topic.id, {"answer": "2"}, question)
        assert result is not None
        assert result.id == m.id


# --- Edge cases ---


class TestEdgeCases:
    def test_no_approved_misconceptions(self, db, topic, question):
        """No misconceptions exist for the topic."""
        result = detect_misconception(db, topic.id, {"answer": "2/7"}, question)
        assert result is None

    def test_pending_misconception_not_matched(self, db, topic, question):
        """Misconception with review_status='pending' is not matched."""
        _create_misconception(
            db, topic,
            review_status="pending",
            error_pattern_json=json.dumps({"match_type": "symbolic", "expected_wrong": "2/7"}),
        )
        result = detect_misconception(db, topic.id, {"answer": "2/7"}, question)
        assert result is None

    def test_age_group_filter_excludes(self, db, topic, question):
        """Misconception with different age_group is not matched."""
        _create_misconception(
            db, topic,
            age_group="early",
            error_pattern_json=json.dumps({"match_type": "symbolic", "expected_wrong": "2/7"}),
        )
        result = detect_misconception(db, topic.id, {"answer": "2/7"}, question, age_group="mid")
        assert result is None

    def test_malformed_error_pattern_skipped(self, db, topic, question):
        """Malformed error_pattern_json is skipped without crashing."""
        _create_misconception(
            db, topic,
            sequence=0,
            error_pattern_json=json.dumps({"bad": "data"}),  # missing match_type
        )
        # Should not crash, returns None
        result = detect_misconception(db, topic.id, {"answer": "2/7"}, question)
        assert result is None

    def test_empty_wrong_answer_dict(self, db, topic, question):
        """Empty answer dict returns None without crashing."""
        _create_misconception(
            db, topic,
            error_pattern_json=json.dumps({"match_type": "symbolic", "expected_wrong": "2/7"}),
        )
        result = detect_misconception(db, topic.id, {}, question)
        assert result is None

    def test_unknown_parametric_algorithm_skipped(self, db, topic, question):
        """Unknown algorithm name is skipped with a warning."""
        _create_misconception(
            db, topic,
            error_pattern_json=json.dumps({
                "match_type": "parametric",
                "algorithm": "nonexistent_algorithm",
            }),
        )
        result = detect_misconception(db, topic.id, {"answer": "2/7"}, question)
        assert result is None

    def test_first_match_returned(self, db, topic, question):
        """When multiple misconceptions match, the first (by sequence) is returned."""
        m1 = _create_misconception(
            db, topic,
            sequence=0,
            error_pattern_json=json.dumps({"match_type": "symbolic", "expected_wrong": "2/7"}),
            description="First match",
        )
        _create_misconception(
            db, topic,
            sequence=1,
            error_pattern_json=json.dumps({"match_type": "symbolic", "expected_wrong": "2/7"}),
            description="Second match",
        )
        result = detect_misconception(db, topic.id, {"answer": "2/7"}, question)
        assert result is not None
        assert result.id == m1.id


class TestFractionExtraction:
    def test_extracts_from_answer_fractions(self, question):
        """Extracts fractions from answer['fractions'] field."""
        result = _extract_fractions_from_question(question)
        assert result == [(1, 3), (1, 4)]

    def test_returns_none_for_missing_data(self, db, topic):
        """Returns None when no fraction data is available."""
        from packages.db.models.learning.question import Question

        q = Question(
            topic_id=topic.id,
            question_type="calculation",
            stem="What is 2+3?",
            answer_json=json.dumps({"answer": "5"}),
            difficulty=1,
            bloom_level="apply",
            source="test",
            age_group="mid",
            review_status="approved",
        )
        db.add(q)
        db.flush()
        result = _extract_fractions_from_question(q)
        assert result is None


class TestFractionAddProductDenominator:
    """Tests for the 'product of denominators instead of LCM' misconception."""

    def test_happy_path_product_denominator_detected(self, db, topic):
        """For 1/4 + 1/6, wrong answer '10/24' matches the product-denominator pattern.

        Product denominator: (1*6 + 1*4) / (4*6) = 10/24.
        LCM(4, 6) = 12, so 10/24 is NOT the correct answer (correct is 5/12).
        """
        from packages.db.models.learning.question import Question

        q = Question(
            topic_id=topic.id,
            question_type="calculation",
            stem="What is 1/4 + 1/6?",
            answer_json=json.dumps({
                "answer": "5/12",
                "fractions": [[1, 4], [1, 6]],
            }),
            difficulty=3,
            bloom_level="apply",
            source="test",
            age_group="mid",
            review_status="approved",
        )
        db.add(q)
        db.flush()
        m = _create_misconception(
            db, topic,
            error_pattern_json=json.dumps({
                "match_type": "parametric",
                "algorithm": "fraction_add_product_denominator",
            }),
            description="Product denominator instead of LCM",
        )
        result = detect_misconception(db, topic.id, {"answer": "10/24"}, q)
        assert result is not None
        assert result.id == m.id

    def test_coprime_denominators_product_equals_lcm_not_detected(self, db, topic):
        """For 1/3 + 1/4, correct answer '7/12' must NOT trigger the misconception.

        Product of denominators: 3*4 = 12. LCM(3, 4) = 12 (coprime).
        Since product equals LCM, this is the correct denominator, not a mistake.
        """
        from packages.db.models.learning.question import Question

        q = Question(
            topic_id=topic.id,
            question_type="calculation",
            stem="What is 1/3 + 1/4?",
            answer_json=json.dumps({
                "answer": "7/12",
                "fractions": [[1, 3], [1, 4]],
            }),
            difficulty=2,
            bloom_level="apply",
            source="test",
            age_group="mid",
            review_status="approved",
        )
        db.add(q)
        db.flush()
        _create_misconception(
            db, topic,
            error_pattern_json=json.dumps({
                "match_type": "parametric",
                "algorithm": "fraction_add_product_denominator",
            }),
            description="Product denominator instead of LCM",
        )
        # Correct answer should not be flagged
        result = detect_misconception(db, topic.id, {"answer": "7/12"}, q)
        assert result is None

    def test_coprime_denominators_unrelated_wrong_answer_not_detected(self, db, topic):
        """For 1/2 + 1/3, unrelated wrong answer '3/5' must NOT trigger.

        Product of denominators: 2*3 = 6. LCM(2, 3) = 6 (coprime).
        Expected wrong by product rule: (1*3 + 1*2) / (2*3) = 5/6 — which is
        also the correct answer. So even entering '5/6' should not trigger.
        An unrelated wrong answer like '3/5' must not trigger either.
        """
        from packages.db.models.learning.question import Question

        q = Question(
            topic_id=topic.id,
            question_type="calculation",
            stem="What is 1/2 + 1/3?",
            answer_json=json.dumps({
                "answer": "5/6",
                "fractions": [[1, 2], [1, 3]],
            }),
            difficulty=2,
            bloom_level="apply",
            source="test",
            age_group="mid",
            review_status="approved",
        )
        db.add(q)
        db.flush()
        _create_misconception(
            db, topic,
            error_pattern_json=json.dumps({
                "match_type": "parametric",
                "algorithm": "fraction_add_product_denominator",
            }),
            description="Product denominator instead of LCM",
        )
        # Even the correct answer must not trigger when product == LCM
        result_correct = detect_misconception(db, topic.id, {"answer": "5/6"}, q)
        assert result_correct is None
        # Unrelated wrong answer also must not trigger
        result_wrong = detect_misconception(db, topic.id, {"answer": "3/5"}, q)
        assert result_wrong is None
