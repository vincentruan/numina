"""Teach-back grading — deterministic half of the dual-track validation.

Expression extraction from free text + SymPy equivalence check.
The conceptual-reasoning half is judged in-skill by the LLM (see SKILL.md).
"""

import re

_SYMBOLIC_EQ_AVAILABLE: bool | None = None


def _check_sympy_available() -> bool:
    """Lazy check for SymPy availability (mirrors symbolic_equivalence.py)."""
    global _SYMBOLIC_EQ_AVAILABLE
    if _SYMBOLIC_EQ_AVAILABLE is None:
        try:
            import sympy  # noqa: F401
            _SYMBOLIC_EQ_AVAILABLE = True
        except ImportError:
            _SYMBOLIC_EQ_AVAILABLE = False
    return _SYMBOLIC_EQ_AVAILABLE


# Regex patterns for extracting math expressions from free text.
# Order matters: more specific patterns first.
_FRACTION_PATTERN = re.compile(
    r"(\d+)\s*/\s*(\d+)"  # 1/4, 2/3, etc.
)
_ARITHMETIC_PATTERN = re.compile(
    r"(\d+\s*/\s*\d+)\s*([+\-])\s*(\d+\s*/\s*\d+)\s*=\s*(\d+\s*/\s*\d+)"
)
_MULTIPLY_PATTERN = re.compile(
    r"(\d+)\s*[*×xX]\s*(\d+)\s*=\s*(\d+)"
)
_WHOLE_NUMBER_PATTERN = re.compile(
    r"\b(\d+)\b"
)


def extract_expression(child_text: str) -> str | None:
    """Extract the most relevant math expression from a child's free-text explanation.

    Priority: arithmetic with fractions > multiply > bare fraction > bare number.
    Returns the extracted expression string, or None if nothing found.
    """
    if not child_text or not child_text.strip():
        return None

    # Try arithmetic pattern first (e.g., "1/4 + 2/4 = 3/4")
    m = _ARITHMETIC_PATTERN.search(child_text)
    if m:
        return m.group(0).strip()

    # Try multiply pattern (e.g., "3 × 2 = 6")
    m = _MULTIPLY_PATTERN.search(child_text)
    if m:
        return m.group(0).strip()

    # Try bare fraction (e.g., "3/4" or "2/6")
    m = _FRACTION_PATTERN.search(child_text)
    if m:
        return f"{m.group(1)}/{m.group(2)}"

    # Try bare number
    m = _WHOLE_NUMBER_PATTERN.search(child_text)
    if m:
        return m.group(1)

    return None


def grade_expression(expected: str | None, child_expr: str | None) -> bool | None:
    """Compare expected and child expressions using SymPy equivalence.

    Returns:
        True — expressions are equivalent
        False — expressions are not equivalent
        None — cannot determine (no expected, no child expr, or SymPy unavailable)
    """
    if not expected or not child_expr:
        return None

    if not _check_sympy_available():
        return None

    from apps.backend.app.services.learning.symbolic_equivalence import (
        numeric_or_symbolic_eq,
    )

    try:
        result = numeric_or_symbolic_eq(expected, child_expr)
        return result
    except Exception:
        return None
