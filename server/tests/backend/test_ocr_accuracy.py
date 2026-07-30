"""Tests for OCR accuracy calculator service."""
from apps.backend.app.services.ocr_accuracy import (
    calculate_ocr_accuracy,
    levenshtein_ratio,
)


def test_levenshtein_ratio_exact_match():
    """Exact match should return 1.0."""
    assert levenshtein_ratio("这是一个测试文本~", "这是一个测试文本~") == 1.0


def test_levenshtein_ratio_partial_match():
    """Partial match should return appropriate ratio."""
    # 8 of 9 chars match: "这是一个测试文本" vs "这是一个测试文本~"
    ratio = levenshtein_ratio("这是一个测试文本", "这是一个测试文本~")
    assert 0.8 <= ratio <= 0.95


def test_levenshtein_ratio_no_match():
    """Completely different strings should return low ratio."""
    ratio = levenshtein_ratio("abc", "xyz")
    assert ratio == 0.0


def test_levenshtein_ratio_empty_strings():
    """Empty strings should return 1.0 (both empty = match)."""
    assert levenshtein_ratio("", "") == 1.0


def test_calculate_ocr_accuracy_exact():
    """Exact match should return 100."""
    assert calculate_ocr_accuracy("这是一个测试文本~", "这是一个测试文本~") == 100


def test_calculate_ocr_accuracy_threshold():
    """80% match should return 80."""
    # Create a string with 80% match
    result = calculate_ocr_accuracy("这是一个测试文本~", "这是一个测试文本")
    assert 80 <= result <= 95  # Roughly 8/9 chars match
