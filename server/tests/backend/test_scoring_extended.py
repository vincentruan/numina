"""Tests for extended scoring types: multi_fill_blank and ai_graded."""
import pytest

from apps.backend.app.services.learning.scoring_service import (
    check_answer,
    check_ai_graded,
    check_multi_fill_blank_partial,
)


class TestMultiFillBlank:
    """multi_fill_blank: each blank scored independently."""

    def test_all_correct(self):
        correct = {"blanks": ["北京", "上海", "广州"]}
        user = {"blanks": ["北京", "上海", "广州"]}
        result = check_answer("multi_fill_blank", correct, user)
        assert result is True

    def test_partial_wrong(self):
        correct = {"blanks": ["北京", "上海", "广州"]}
        user = {"blanks": ["北京", "深圳", "广州"]}
        result = check_answer("multi_fill_blank", correct, user)
        assert result is False  # not all correct → overall False

    def test_whitespace_tolerance(self):
        correct = {"blanks": ["100", "km"]}
        user = {"blanks": [" 100 ", " km "]}
        result = check_answer("multi_fill_blank", correct, user)
        assert result is True

    def test_empty_blanks_counted(self):
        correct = {"blanks": ["a", "b"]}
        user = {"blanks": ["a", ""]}
        result = check_answer("multi_fill_blank", correct, user)
        assert result is False


class TestMultiFillBlankPartial:
    """Partial scoring for multi_fill_blank (returns per-blank results)."""

    def test_partial_score_returns_per_blank(self):
        correct = {"blanks": ["北京", "上海", "广州"]}
        user = {"blanks": ["北京", "深圳", "广州"]}
        result = check_multi_fill_blank_partial(correct, user)
        assert result["correct_count"] == 2
        assert result["total"] == 3
        assert result["per_blank"] == [True, False, True]


class TestAiGraded:
    """ai_graded: AI scoring with confidence."""

    def test_high_confidence_returns_correct(self):
        correct = {"rubric": "光合作用", "keywords": ["光", "二氧化碳", "氧"]}
        user = {"text": "植物通过光合作用将二氧化碳转化为氧气"}
        result = check_ai_graded(correct, user, mock_confidence=0.9)
        assert result["is_correct"] is True
        assert result["confidence"] == 0.9
        assert "explanation" in result

    def test_low_confidence_flagged(self):
        correct = {"rubric": "光合作用"}
        user = {"text": "一些关于植物的内容"}
        result = check_ai_graded(correct, user, mock_confidence=0.5)
        assert result["confidence"] == 0.5
        assert result["low_confidence"] is True

    def test_check_answer_returns_bool_for_ai_graded(self):
        correct = {"rubric": "test"}
        user = {"text": "answer"}
        result = check_answer("ai_graded", correct, user)
        assert isinstance(result, bool)
