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
# Number operand: either a fraction (1/2) or a whole number (4).
_NUM_OPERAND = r"(?:\d+\s*/\s*\d+|\d+)"
# Fraction multiplication — at least one operand must be a fraction.
# Matches 1/2 × 1/3 = 1/6, 1/2 × 4 = 2, 4 × 1/2 = 2.
_FRACTION_MULTIPLY_PATTERN = re.compile(
    rf"({_NUM_OPERAND})\s*[*×xX]\s*({_NUM_OPERAND})\s*=\s*({_NUM_OPERAND})"
)
# Whole-number multiplication: 3 × 2 = 6. Must come AFTER the fraction-multiply
# pattern or its bare-digit groups shadow fraction operands ("1/2 × 4" would
# match as "2 × 4", a false equation).
_MULTIPLY_PATTERN = re.compile(r"(\d+)\s*[*×xX]\s*(\d+)\s*=\s*(\d+)")
# Decimal numbers: 0.25, 3.14, 1.5
_DECIMAL_PATTERN = re.compile(r"(\d+\.\d+)")
# Decimal arithmetic: "1.5 + 0.3 = 1.8", "0.5+0.3=0.8". Must be tried before
# _DECIMAL_EQUATION_PATTERN, which would otherwise match only the tail
# ("0.3 = 1.8") and grade a correct statement as a false equation.
_DECIMAL_ARITHMETIC_PATTERN = re.compile(
    r"(\d+\.\d+)\s*([+\-])\s*(\d+\.\d+)\s*=\s*(\d+\.\d+)"
)
# Percent values: 25%, 50%, 12.5%
_PERCENT_PATTERN = re.compile(r"(\d+(?:\.\d+)?)\s*%")
# Decimal/percent equations: "0.5 = 0.05", "50% = 5", "50% = 1/2". Captured so
# the grader's require_true check can reject a false numeric claim — a bare-value
# extraction would discard the equation and let "0.5 = 0.05" pass against expected
# 0.5. Fractions are allowed on either side so a percent-to-fraction claim survives.
_DECIMAL_EQUATION_PATTERN = re.compile(
    r"(\d+(?:\.\d+)?%?(?:\s*/\s*\d+)?)\s*=\s*(\d+(?:\.\d+)?%?(?:\s*/\s*\d+)?)"
)
_WHOLE_NUMBER_PATTERN = re.compile(r"\b(\d+)\b")


def _is_fraction_operand(text: str) -> bool:
    """Return True if the operand text is a fraction (contains '/')."""
    return "/" in text


def _percent_to_fraction(operand: str) -> str:
    """Rewrite ``"25%"`` as ``"25/100"`` so SymPy can compare it numerically."""
    if operand.endswith("%"):
        return f"{operand[:-1]}/100"
    return operand


def _select_decimal(child_text: str, expected: str | None) -> str | None:
    """Pick the decimal the child is asserting, not one they are only quoting.

    A refutation of a misconception normally names the wrong value before the
    right one ("It's not 0.2, it's 0.5"). A leftmost-match would extract the
    quoted misconception, grade a correct explanation as a miss, and let the
    deterministic override downgrade the turn. When the caller knows the
    expected answer, prefer a decimal that matches it; otherwise keep the
    leftmost match.
    """
    matches = list(_DECIMAL_PATTERN.finditer(child_text))
    if not matches:
        return None
    if expected:
        for match in matches:
            if grade_expression(expected, match.group(1)) is True:
                return match.group(1).strip()
    return matches[0].group(1).strip()


def extract_expression(child_text: str, expected: str | None = None) -> str | None:
    """Extract the most relevant math expression from a child's free-text explanation.

    Priority: fraction arithmetic > fraction multiply > whole multiply >
    decimal arithmetic > decimal/percent equation > percent > decimal >
    bare fraction > bare number.
    Returns the extracted expression string, or None if nothing found.
    Percent values are converted to fraction form (e.g., "25%" → "25/100").

    ``expected`` is the confusion's ``expected_expression`` when the caller knows
    it. It disambiguates rebuttal-shaped text, where the child quotes the wrong
    value before correcting it.
    """
    if not child_text or not child_text.strip():
        return None

    # Try fraction arithmetic pattern first (e.g., "1/4 + 2/4 = 3/4")
    m = _ARITHMETIC_PATTERN.search(child_text)
    if m:
        return m.group(0).strip()

    # Try fraction multiplication (e.g., "1/2 × 1/3 = 1/6" or "1/2 × 4 = 2").
    # Checked before whole-number multiply so fraction operands are not shadowed.
    m = _FRACTION_MULTIPLY_PATTERN.search(child_text)
    if m and (_is_fraction_operand(m.group(1)) or _is_fraction_operand(m.group(2))):
        return m.group(0).strip()

    # Try whole number multiply (e.g., "3 × 2 = 6")
    m = _MULTIPLY_PATTERN.search(child_text)
    if m:
        return m.group(0).strip()

    # Try decimal arithmetic before the decimal-equation pattern, which would
    # otherwise capture only the tail of "1.5 + 0.3 = 1.8" as "0.3 = 1.8".
    m = _DECIMAL_ARITHMETIC_PATTERN.search(child_text)
    if m:
        return m.group(0).strip()

    # Try decimal/percent equations (e.g., "0.5 = 0.05", "50% = 5") so a false
    # numeric claim reaches the grader's require_true check instead of being
    # reduced to a bare value that would grade True. At least one side must carry
    # a decimal point or percent sign, or ordinary integer prose ("3 = 5") would
    # be captured as a false equation and downgrade a valid explanation.
    m = _DECIMAL_EQUATION_PATTERN.search(child_text)
    if m and ("." in m.group(1) + m.group(2) or "%" in m.group(1) + m.group(2)):
        lhs = _percent_to_fraction(m.group(1))
        rhs = _percent_to_fraction(m.group(2))
        return f"{lhs} = {rhs}"

    # Try percent before decimal so "12.5%" is read as a percentage, not the
    # bare decimal 12.5. Converted to fraction form for SymPy ("12.5%" → "12.5/100").
    m = _PERCENT_PATTERN.search(child_text)
    if m:
        return f"{m.group(1)}/100"

    # Try decimal (e.g., "0.25" or "3.14")
    selected = _select_decimal(child_text, expected)
    if selected is not None:
        return selected

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

    Decimal literals are parsed as exact ``Rational`` values (``rational=True``).
    SymPy's default ``Float`` makes "0.1 + 0.2 = 0.3" fail the ``simplify(...) ==
    0`` check by ~5.6e-17, which would downgrade a correct statement to a miss.
    """
    try:
        import sympy

        normalized = (
            expr.strip()
            .replace("^", "**")
            .replace("×", "*")
            .replace("x", "*")
            .replace("X", "*")
        )
        parsed = sympy.sympify(normalized, strict=False, rational=True)
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
