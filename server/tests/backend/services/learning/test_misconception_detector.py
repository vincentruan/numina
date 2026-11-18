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


# --- text_match tests ---


class TestTextMatching:
    def test_exact_normalized_match_returns_misconception(self, db, topic, question):
        """Text answer '分子' matches text_match pattern with expected_wrong '分子'."""
        m = _create_misconception(
            db, topic,
            error_pattern_json=json.dumps({
                "match_type": "text_match",
                "expected_wrong": "分子",
                "normalize": True,
            }),
        )
        result = detect_misconception(db, topic.id, {"answer": "分子"}, question)
        assert result is not None
        assert result.id == m.id

    def test_trailing_whitespace_matches_after_normalization(self, db, topic, question):
        """Text answer '分子 ' (trailing space) matches '分子' after normalization."""
        m = _create_misconception(
            db, topic,
            error_pattern_json=json.dumps({
                "match_type": "text_match",
                "expected_wrong": "分子",
                "normalize": True,
            }),
        )
        result = detect_misconception(db, topic.id, {"answer": "分子 "}, question)
        assert result is not None
        assert result.id == m.id

    def test_case_insensitive_match(self, db, topic, question):
        """Text answer 'FRACTION' matches 'fraction' when normalize=true."""
        m = _create_misconception(
            db, topic,
            error_pattern_json=json.dumps({
                "match_type": "text_match",
                "expected_wrong": "fraction",
                "normalize": True,
            }),
        )
        result = detect_misconception(db, topic.id, {"answer": "FRACTION"}, question)
        assert result is not None
        assert result.id == m.id

    def test_normalize_false_requires_exact_match(self, db, topic, question):
        """With normalize=false, case difference means no match."""
        _create_misconception(
            db, topic,
            error_pattern_json=json.dumps({
                "match_type": "text_match",
                "expected_wrong": "fraction",
                "normalize": False,
            }),
        )
        result = detect_misconception(db, topic.id, {"answer": "Fraction"}, question)
        assert result is None

    def test_non_matching_text_returns_none(self, db, topic, question):
        """Unrelated text answer does not match."""
        _create_misconception(
            db, topic,
            error_pattern_json=json.dumps({
                "match_type": "text_match",
                "expected_wrong": "分子",
                "normalize": True,
            }),
        )
        result = detect_misconception(db, topic.id, {"answer": "分母"}, question)
        assert result is None

    def test_chinese_text_bypasses_safe_math_re(self, db, topic, question):
        """Chinese text answer is handled by text_match without _SAFE_MATH_RE blocking it."""
        m = _create_misconception(
            db, topic,
            error_pattern_json=json.dumps({
                "match_type": "text_match",
                "expected_wrong": "光合作用",
                "normalize": True,
            }),
        )
        result = detect_misconception(db, topic.id, {"answer": "光合作用"}, question)
        assert result is not None
        assert result.id == m.id

    def test_list_based_expected_wrong_matches_any_candidate(self, db, topic, question):
        """expected_wrong as a list matches if user answer equals any candidate."""
        m = _create_misconception(
            db, topic,
            error_pattern_json=json.dumps({
                "match_type": "text_match",
                "expected_wrong": ["denominator", "分母"],
                "normalize": True,
            }),
        )
        # English form matches
        result_en = detect_misconception(db, topic.id, {"answer": "denominator"}, question)
        assert result_en is not None
        assert result_en.id == m.id
        # Chinese form matches the same misconception
        result_zh = detect_misconception(db, topic.id, {"answer": "分母"}, question)
        assert result_zh is not None
        assert result_zh.id == m.id
        # Unrelated text does not match
        result_miss = detect_misconception(db, topic.id, {"answer": "numerator"}, question)
        assert result_miss is None

    def test_empty_expected_wrong_list_returns_none(self, db, topic, question):
        """An empty expected_wrong list matches nothing."""
        _create_misconception(
            db, topic,
            error_pattern_json=json.dumps({
                "match_type": "text_match",
                "expected_wrong": [],
                "normalize": True,
            }),
        )
        result = detect_misconception(db, topic.id, {"answer": "anything"}, question)
        assert result is None


# --- option_select tests ---


class TestOptionSelectMatching:
    def test_wrong_option_in_list_returns_misconception(self, db, topic, question):
        """Selecting option 'B' when wrong_options=['B', 'C'] triggers detection."""
        m = _create_misconception(
            db, topic,
            error_pattern_json=json.dumps({
                "match_type": "option_select",
                "wrong_options": ["B", "C"],
            }),
        )
        result = detect_misconception(db, topic.id, {"answer": "B"}, question)
        assert result is not None
        assert result.id == m.id

    def test_correct_option_not_in_list_returns_none(self, db, topic, question):
        """Selecting option 'A' when wrong_options=['B', 'C'] does not trigger."""
        _create_misconception(
            db, topic,
            error_pattern_json=json.dumps({
                "match_type": "option_select",
                "wrong_options": ["B", "C"],
            }),
        )
        result = detect_misconception(db, topic.id, {"answer": "A"}, question)
        assert result is None

    def test_empty_wrong_options_returns_none(self, db, topic, question):
        """Empty wrong_options list means no match."""
        _create_misconception(
            db, topic,
            error_pattern_json=json.dumps({
                "match_type": "option_select",
                "wrong_options": [],
            }),
        )
        result = detect_misconception(db, topic.id, {"answer": "B"}, question)
        assert result is None

    def test_option_select_bypasses_safe_math_re(self, db, topic, question):
        """Option key 'B' is handled by option_select without _SAFE_MATH_RE gate."""
        m = _create_misconception(
            db, topic,
            error_pattern_json=json.dumps({
                "match_type": "option_select",
                "wrong_options": ["B"],
            }),
        )
        result = detect_misconception(db, topic.id, {"answer": "B"}, question)
        assert result is not None
        assert result.id == m.id


# --- Answer-extraction prelude: the payload shapes production actually sends ---
#
# The practice API forwards the child app's raw payload (see
# PracticeAnswerInput.vue emit shapes and scoring_service.check_answer). For
# multiple_choice that is {"key": ...} — not {"answer": ...} — so these tests
# exercise the prelude probe that recovers the option key, which the
# TestOptionSelectMatching cases above never reach.


class TestAnswerExtractionPrelude:
    def _option_misconception(self, db, topic):
        return _create_misconception(
            db, topic,
            error_pattern_json=json.dumps({
                "match_type": "option_select",
                "wrong_options": ["B", "C"],
            }),
            description="Adds numerators and denominators",
        )

    def test_option_key_payload_matches(self, db, topic, question):
        """{"key": "B"} — the shape the child app emits — reaches option_select."""
        m = self._option_misconception(db, topic)
        result = detect_misconception(db, topic.id, {"key": "B"}, question)
        assert result is not None
        assert result.id == m.id

    def test_option_key_payload_not_in_wrong_options_returns_none(self, db, topic, question):
        """A correct option key passes through the prelude but matches nothing."""
        self._option_misconception(db, topic)
        result = detect_misconception(db, topic.id, {"key": "A"}, question)
        assert result is None

    def test_none_option_key_returns_none(self, db, topic, question):
        """{"key": None} with no answer/value is treated as missing."""
        self._option_misconception(db, topic)
        result = detect_misconception(db, topic.id, {"key": None}, question)
        assert result is None

    def test_answer_payload_still_matches(self, db, topic, question):
        """Regression: the pre-existing {"answer": ...} shape keeps working."""
        m = self._option_misconception(db, topic)
        result = detect_misconception(db, topic.id, {"answer": "B"}, question)
        assert result is not None
        assert result.id == m.id

    def test_answer_probe_wins_over_key(self, db, topic, question):
        """When both are present, "answer" is read first — probe order is preserved."""
        symbolic = _create_misconception(
            db, topic,
            sequence=0,
            error_pattern_json=json.dumps({"match_type": "symbolic", "expected_wrong": "2/7"}),
            description="Symbolic match on the answer probe",
        )
        option = _create_misconception(
            db, topic,
            sequence=1,
            error_pattern_json=json.dumps({
                "match_type": "option_select",
                "wrong_options": ["B"],
            }),
            description="Option match on the key probe",
        )
        result = detect_misconception(db, topic.id, {"answer": "2/7", "key": "B"}, question)
        assert result is not None
        # "answer" is probed first, so the symbolic pattern is what fires.
        assert result.id == symbolic.id
        assert result.id != option.id

    def test_value_probe_wins_over_key(self, db, topic, question):
        """"value" outranks "key": a fill_blank payload carrying both uses value."""
        text = _create_misconception(
            db, topic,
            sequence=0,
            error_pattern_json=json.dumps({
                "match_type": "text_match",
                "expected_wrong": "denominator",
                "normalize": True,
            }),
            description="Text match on the value probe",
        )
        _create_misconception(
            db, topic,
            sequence=1,
            error_pattern_json=json.dumps({
                "match_type": "option_select",
                "wrong_options": ["B"],
            }),
            description="Option match on the key probe",
        )
        result = detect_misconception(
            db, topic.id, {"value": "denominator", "key": "B"}, question
        )
        assert result is not None
        assert result.id == text.id

    def test_injected_option_key_never_reaches_sympy(self, db, topic, question):
        """A code-injection-shaped key is rejected by _SAFE_MATH_RE before sympy."""
        _create_misconception(
            db, topic,
            error_pattern_json=json.dumps({"match_type": "symbolic", "expected_wrong": "2/7"}),
        )
        result = detect_misconception(
            db, topic.id, {"key": "__import__('os').system('rm -rf /')"}, question
        )
        assert result is None


# --- Integration tests: detect_and_record_misconception with non-calc types ---


class TestServiceNonCalcIntegration:
    """Tests that detect_and_record_misconception works for non-calculation question types."""

    def test_fill_blank_question_detected(self, db, topic):
        """fill_blank question with text_match misconception is detected via the service."""
        from apps.backend.app.services.learning.misconception_service import (
            detect_and_record_misconception,
        )
        from packages.db.models.learning.question import Question

        q = Question(
            topic_id=topic.id,
            question_type="fill_blank",
            stem="The top part of a fraction is called the ___",
            answer_json=json.dumps({"value": "numerator"}),
            difficulty=1,
            bloom_level="remember",
            source="test",
            age_group="mid",
            review_status="approved",
        )
        db.add(q)
        db.flush()

        _create_misconception(
            db, topic,
            error_pattern_json=json.dumps({
                "match_type": "text_match",
                "expected_wrong": "denominator",
                "normalize": True,
            }),
            description="Confuses numerator and denominator",
        )

        # The child app emits {"value": ...} for fill_blank.
        result = detect_and_record_misconception(
            db,
            child_id=1,
            topic_id=topic.id,
            question_id=q.id,
            user_answer={"value": "denominator"},
        )
        assert result is not None
        misconception_id, feedback = result
        assert misconception_id is not None
        assert feedback.description is not None

    def test_multiple_choice_question_detected(self, db, topic):
        """multiple_choice question with option_select misconception is detected via the service."""
        from apps.backend.app.services.learning.misconception_service import (
            detect_and_record_misconception,
        )
        from packages.db.models.learning.question import Question

        q = Question(
            topic_id=topic.id,
            question_type="multiple_choice",
            stem="What is 1/3 + 1/4?",
            options_json=json.dumps([
                {"key": "A", "text": "2/7"},
                {"key": "B", "text": "7/12"},
                {"key": "C", "text": "4/7"},
            ]),
            answer_json=json.dumps({"key": "B"}),
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
                "match_type": "option_select",
                "wrong_options": ["A", "C"],
            }),
            description="Incorrect fraction addition",
        )

        # The child app emits {"key": ...} for multiple_choice.
        result = detect_and_record_misconception(
            db,
            child_id=1,
            topic_id=topic.id,
            question_id=q.id,
            user_answer={"key": "A"},
        )
        assert result is not None
        misconception_id, feedback = result
        assert misconception_id is not None
        assert feedback.description is not None

    def test_unknown_question_type_returns_none(self, db, topic):
        """Unknown question_type runs detection but returns None when no match."""
        from apps.backend.app.services.learning.misconception_service import (
            detect_and_record_misconception,
        )
        from packages.db.models.learning.question import Question

        q = Question(
            topic_id=topic.id,
            question_type="matching",
            stem="Match the fractions",
            answer_json=json.dumps({"answer": "pairs"}),
            difficulty=1,
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
                "match_type": "text_match",
                "expected_wrong": "wrong_match",
                "normalize": True,
            }),
        )

        result = detect_and_record_misconception(
            db,
            child_id=1,
            topic_id=topic.id,
            question_id=q.id,
            user_answer={"answer": "some_other_match"},
        )
        assert result is None

