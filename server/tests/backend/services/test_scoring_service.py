"""Tests for scoring service — auto-grading answers."""
from apps.backend.app.services.learning.scoring_service import (
    calculate_session_score,
    check_answer,
)


def test_check_calculation_correct():
    assert check_answer("calculation", {"answer": 95}, {"answer": 95}) is True


def test_check_calculation_wrong():
    assert check_answer("calculation", {"answer": 95}, {"answer": 96}) is False


def test_check_multiple_choice_correct():
    assert check_answer("multiple_choice", {"key": "B"}, {"key": "B"}) is True


def test_check_multiple_choice_wrong():
    assert check_answer("multiple_choice", {"key": "B"}, {"key": "A"}) is False


def test_check_true_false():
    assert check_answer("true_false", {"value": True}, {"value": True}) is True
    assert check_answer("true_false", {"value": True}, {"value": False}) is False


def test_check_fill_blank():
    assert check_answer("fill_blank", {"value": "分数"}, {"value": "分数"}) is True
    assert check_answer("fill_blank", {"value": "分数"}, {"value": "小数"}) is False


def test_check_answer_missing_key():
    """User answer missing required key returns False, not error."""
    assert check_answer("calculation", {"answer": 95}, {}) is False


def test_calculate_session_score():
    assert calculate_session_score(correct=4, total=5) == 0.8


def test_calculate_session_score_zero_total():
    assert calculate_session_score(correct=0, total=0) == 0.0
