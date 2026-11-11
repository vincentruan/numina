"""Tests for SymPy-based symbolic equivalence checker."""

import pytest

from apps.backend.app.services.learning.symbolic_equivalence import (
    clear_cache,
    numeric_or_symbolic_eq,
    symbolic_eq,
)


@pytest.fixture(autouse=True)
def _clear_sympy_cache():
    """Clear expression cache between tests."""
    clear_cache()
    yield
    clear_cache()


class TestSymbolicEquivalence:
    """Test symbolic_eq function for expression equivalence."""

    def test_algebraic_equivalence_expand(self):
        """3*(x+2) ≡ 3*x+6"""
        assert symbolic_eq("3*(x+2)", "3*x+6") is True

    def test_algebraic_equivalence_factor(self):
        """x^2 - 1 ≡ (x-1)*(x+1)"""
        assert symbolic_eq("x^2 - 1", "(x-1)*(x+1)") is True

    def test_algebraic_equivalence_simplify(self):
        """(x^2 - 1)/(x - 1) ≡ x + 1 (for x != 1)"""
        assert symbolic_eq("(x^2 - 1)/(x - 1)", "x + 1") is True

    def test_different_expressions(self):
        """x + 1 ≠ x + 2"""
        assert symbolic_eq("x + 1", "x + 2") is False

    def test_numeric_equivalence(self):
        """2 + 3 ≡ 5"""
        assert symbolic_eq("2 + 3", "5") is True

    def test_fraction_equivalence(self):
        """1/2 ≡ 2/4"""
        assert symbolic_eq("1/2", "2/4") is True

    def test_power_equivalence(self):
        """x^2 * x^3 ≡ x^5"""
        assert symbolic_eq("x^2 * x^3", "x^5") is True

    def test_invalid_expression_returns_none(self):
        """Invalid expression returns None (cannot determine)."""
        assert symbolic_eq("not a valid expression $$$", "x + 1") is None

    def test_whitespace_handling(self):
        """Whitespace should not affect equivalence."""
        assert symbolic_eq("  x  +  1  ", "x+1") is True


class TestNumericOrSymbolicEq:
    """Test numeric_or_symbolic_eq - the main scoring entry point."""

    def test_numeric_int_equal(self):
        """Integer equality."""
        assert numeric_or_symbolic_eq(5, 5) is True
        assert numeric_or_symbolic_eq(5, 6) is False

    def test_numeric_float_equal(self):
        """Float equality with tolerance."""
        assert numeric_or_symbolic_eq(0.1 + 0.2, 0.3) is True
        assert numeric_or_symbolic_eq(1.0, 1.00001) is True
        assert numeric_or_symbolic_eq(1.0, 2.0) is False

    def test_bool_strict_comparison(self):
        """Bool comparison uses Python's native equality (True == 1 in Python)."""
        assert numeric_or_symbolic_eq(True, True) is True
        assert numeric_or_symbolic_eq(True, False) is False
        # Note: In Python, True == 1 is True (bool is int subclass)
        # This matches the original _float_eq behavior
        assert numeric_or_symbolic_eq(True, 1) is True

    def test_string_expression_equivalence(self):
        """String expressions use symbolic equivalence."""
        assert numeric_or_symbolic_eq("3*(x+2)", "3*x+6") is True
        assert numeric_or_symbolic_eq("x+1", "x+2") is False

    def test_string_fallback_to_strip_compare(self):
        """Non-math strings fall back to strip comparison."""
        assert numeric_or_symbolic_eq("hello", "hello") is True
        assert numeric_or_symbolic_eq("hello", " hello ") is True
        assert numeric_or_symbolic_eq("hello", "world") is False

    def test_mixed_types_exact_equality(self):
        """Mixed types use exact equality."""
        assert numeric_or_symbolic_eq("5", 5) is False
        assert numeric_or_symbolic_eq([1, 2], [1, 2]) is True
        assert numeric_or_symbolic_eq({"a": 1}, {"a": 1}) is True


class TestScoringServiceIntegration:
    """Test that scoring_service uses symbolic equivalence."""

    def test_calculation_with_expression(self):
        """Calculation questions accept equivalent expressions."""
        from apps.backend.app.services.learning.scoring_service import check_answer

        # User writes expanded form, correct is factored
        assert check_answer(
            "calculation",
            {"answer": "3*(x+2)"},
            {"answer": "3*x+6"},
        ) is True

    def test_calculation_with_numeric(self):
        """Calculation questions still work with numeric answers."""
        from apps.backend.app.services.learning.scoring_service import check_answer

        assert check_answer(
            "calculation",
            {"answer": 5},
            {"answer": 5},
        ) is True

        assert check_answer(
            "calculation",
            {"answer": 0.3},
            {"answer": 0.1 + 0.2},
        ) is True

    def test_calculation_wrong_answer(self):
        """Wrong answers return False."""
        from apps.backend.app.services.learning.scoring_service import check_answer

        assert check_answer(
            "calculation",
            {"answer": "x+1"},
            {"answer": "x+2"},
        ) is False
