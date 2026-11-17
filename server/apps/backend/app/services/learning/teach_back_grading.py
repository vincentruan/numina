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
_MULTIPLY_PATTERN = re.compile(r"(\d+)\s*[*×xX]\s*(\d+)\s*=\s*(\d+)")
# Fraction multiplication: 1/2 × 1/3 = 1/6
_FRACTION_MULTIPLY_PATTERN = re.compile(
    r"(\d+\s*/\s*\d+)\s*[*×xX]\s*(\d+\s*/\s*\d+)\s*=\s*(\d+\s*/\s*\d+)"
)
# Decimal numbers: 0.25, 3.14, 1.5
_DECIMAL_PATTERN = re.compile(r"(\d+\.\d+)")
# Percent values: 25%, 50%
_PERCENT_PATTERN = re.compile(r"(\d+)\s*%")
_WHOLE_NUMBER_PATTERN = re.compile(r"\b(\d+)\b")


def extract_expression(child_text: str) -> str | None:
    """Extract the most relevant math expression from a child's free-text explanation.

    Priority: fraction arithmetic > whole multiply > fraction multiply >
    decimal > percent > bare fraction > bare number.
    Returns the extracted expression string, or None if nothing found.
    Percent values are converted to fraction form (e.g., "25%" → "25/100").
    """
    if not child_text or not child_text.strip():
        return None

    # Try fraction arithmetic pattern first (e.g., "1/4 + 2/4 = 3/4")
    m = _ARITHMETIC_PATTERN.search(child_text)
    if m:
        return m.group(0).strip()

    # Try whole number multiply (e.g., "3 × 2 = 6")
    m = _MULTIPLY_PATTERN.search(child_text)
    if m:
        return m.group(0).strip()

    # Try fraction multiplication (e.g., "1/2 × 1/3 = 1/6")
    m = _FRACTION_MULTIPLY_PATTERN.search(child_text)
    if m:
        return m.group(0).strip()

    # Try decimal (e.g., "0.25" or "3.14")
    m = _DECIMAL_PATTERN.search(child_text)
    if m:
        return m.group(1).strip()

    # Try percent — convert to fraction form for SymPy (e.g., "25%" → "25/100")
    m = _PERCENT_PATTERN.search(child_text)
    if m:
        return f"{m.group(1)}/100"

    # Try bare fraction (e.g., "3/4" or "2/6")
    m = _FRACTION_PATTERN.search(child_text)
    if m:
        return f"{m.group(1)}/{m.group(2)}"

    # Try bare number
    m = _WHOLE_NUMBER_PATTERN.search(child_text)
    if m:
        return m.group(1)

    return None


def _sympy_parse(expr: str):
    """Parse ``expr`` as a numeric SymPy expression, or return ``None``.

    Free text sympifies into a bare Symbol, which would compare unequal to any
    number and read as a wrong answer. Only numeric results are accepted here,
    so prose yields ``None`` (undetermined) rather than a spurious ``False``.
    """
    try:
        import sympy

        normalized = expr.strip().replace("^", "**").replace("×", "*").replace("x", "*")
        parsed = sympy.sympify(normalized, strict=False)
    except Exception:
        return None
    if not isinstance(parsed, sympy.Expr) or parsed.free_symbols:
        return None
    return parsed


def _clean_side(side: str) -> str:
    """Strip stray characters left over when splitting an equation on ``=``."""
    return side.strip().strip("=:：").strip()


def _resolve_value(expr: str, *, require_true: bool):
    """Resolve ``expr`` to the numeric value it denotes.

    Handles both a bare expression (``"3/4"``) and an equation
    (``"1/4 + 2/4 = 3/4"``). Returns ``(value, equation_holds)`` or ``None``
    when the text cannot be read as math.

    ``require_true`` makes a false equation unresolvable (used for the child's
    claims, which must be both true and correct); the expected expression's own
    equation form is a statement of the answer, so it resolves regardless.
    """
    import sympy

    if "=" not in expr:
        parsed = _sympy_parse(expr)
        return None if parsed is None else (parsed, True)

    lhs_text, _, rhs_text = expr.partition("=")
    lhs = _sympy_parse(_clean_side(lhs_text))
    rhs = _sympy_parse(_clean_side(rhs_text))
    if lhs is None or rhs is None:
        return None
    try:
        holds = sympy.simplify(lhs - rhs) == 0
    except Exception:
        return None
    if require_true and not holds:
        return (rhs, False)
    return (rhs, holds)


def grade_expression(expected: str | None, child_expr: str | None) -> bool | None:
    """Compare expected and child expressions using SymPy equivalence.

    The child's expression may be a bare value (``"3/4"``) or a full equation
    the extractor captured (``"1/4 + 2/4 = 3/4"``). An equation is graded on two
    things: that it is arithmetically true, and that its result matches
    ``expected``. Anything SymPy cannot read as numeric math yields ``None``
    (undetermined) — never ``False`` — so an unreadable form cannot downgrade a
    correct explanation.

    Returns:
        True — child expression is equivalent to expected
        False — child expression is verifiably wrong
        None — cannot determine (no expected, no child expr, SymPy unavailable,
               or a side could not be read as numeric math)
    """
    if not expected or not child_expr:
        return None

    if not _check_sympy_available():
        return None

    expected_resolved = _resolve_value(expected, require_true=False)
    if expected_resolved is None:
        return None
    expected_value = expected_resolved[0]

    child_resolved = _resolve_value(child_expr, require_true=True)
    if child_resolved is None:
        return None
    child_value, equation_holds = child_resolved

    if not equation_holds:
        return False

    import sympy

    try:
        return bool(sympy.simplify(child_value - expected_value) == 0)
    except Exception:
        return None
