"""Misconception detection service — matches wrong answers to known error patterns.

Runs after a wrong answer is scored. Loads the topic's approved misconceptions,
compares the child's wrong answer against each entry's error_pattern, and returns
the first match (or None).

Supports three match types:
- "symbolic": exact symbolic comparison (e.g., "2/7" == "2/7")
- "numeric": tolerance-based float comparison
- "parametric": dynamic computation from question content (e.g., "add numerators
  and denominators" computes expected_wrong from the specific fractions in the question)
"""

import re

from sqlalchemy.orm import Session

from packages.core.logging import get_logger
from packages.db.models.learning.misconception import Misconception
from packages.db.models.learning.question import Question

logger = get_logger(__name__)

# Safe math expression pattern: digits, fractions, basic operators, parens, whitespace.
# Rejects anything that could be a code injection attempt.
_SAFE_MATH_RE = re.compile(r'^[0-9+\-*/().\s^a-zA-Z]+$')


def detect_misconception(
    db: Session,
    topic_id: int,
    wrong_answer: dict,
    question: Question,
    age_group: str = "mid",
) -> Misconception | None:
    """Detect if a wrong answer matches a known misconception for the topic.

    Args:
        db: Database session.
        topic_id: The topic being practiced.
        wrong_answer: The child's wrong answer dict (e.g., {"answer": "2/7"}).
        question: The Question object (provides correct_answer for parametric matching).
        age_group: Age group filter (only misconceptions for this group are checked).

    Returns:
        The first matching Misconception, or None if no match.
    """
    misconceptions = (
        db.query(Misconception)
        .filter(
            Misconception.topic_id == topic_id,
            Misconception.age_group == age_group,
            Misconception.review_status == "approved",
        )
        .order_by(Misconception.sequence)
        .all()
    )

    if not misconceptions:
        return None

    # Extract the user's answer value from the dict.
    # Use explicit None check to handle falsy values like 0 correctly.
    user_val = wrong_answer.get("answer")
    if user_val is None:
        user_val = wrong_answer.get("value")
    if user_val is None:
        return None

    user_str = str(user_val).strip()

    # Reject inputs that don't look like math expressions — prevents passing
    # code injection payloads to sympy.sympify downstream.
    if not _SAFE_MATH_RE.match(user_str):
        logger.debug("Rejecting non-math answer for misconception detection: %s", user_str[:50])
        return None

    for m in misconceptions:
        try:
            pattern = _parse_pattern(m)
        except _PatternParseError:
            continue

        match_type = pattern.get("match_type")

        if match_type == "symbolic":
            if _match_symbolic(user_str, pattern):
                logger.debug(
                    "Misconception detected (symbolic): misconception_id=%s, topic_id=%s",
                    m.id,
                    topic_id,
                )
                return m

        elif match_type == "numeric":
            if _match_numeric(user_str, pattern):
                logger.debug(
                    "Misconception detected (numeric): misconception_id=%s, topic_id=%s",
                    m.id,
                    topic_id,
                )
                return m

        elif match_type == "parametric" and _match_parametric(user_str, pattern, question):
            logger.debug(
                "Misconception detected (parametric): misconception_id=%s, topic_id=%s",
                m.id,
                topic_id,
            )
            return m

    return None


class _PatternParseError(Exception):
    """Raised when error_pattern_json is malformed or missing required fields."""


def _parse_pattern(m: Misconception) -> dict:
    """Parse and validate the error_pattern_json field."""
    raw = m.error_pattern
    if not raw or not isinstance(raw, dict):
        raise _PatternParseError(f"Invalid error_pattern for misconception {m.id}")
    if "match_type" not in raw:
        raise _PatternParseError(f"Missing match_type for misconception {m.id}")
    return raw


def _match_symbolic(user_str: str, pattern: dict) -> bool:
    """Match using symbolic equivalence (SymPy-based)."""
    from apps.backend.app.services.learning.symbolic_equivalence import symbolic_eq

    expected = pattern.get("expected_wrong")
    if expected is None:
        return False

    expected_str = str(expected).strip()
    result = symbolic_eq(user_str, expected_str)
    return result is True


def _match_numeric(user_str: str, pattern: dict) -> bool:
    """Match using tolerance-based numeric comparison."""
    from apps.backend.app.services.learning.symbolic_equivalence import (
        numeric_or_symbolic_eq,
    )

    expected = pattern.get("expected_wrong")
    if expected is None:
        return False

    tolerance = pattern.get("tolerance", 0.01)

    try:
        user_float = float(user_str)
        expected_float = float(expected)
    except (ValueError, TypeError):
        return False

    return numeric_or_symbolic_eq(
        expected_float,
        user_float,
        float_rel_tol=tolerance,
        float_abs_tol=tolerance,
    )


def _match_parametric(user_str: str, pattern: dict, question: Question) -> bool:
    """Match using dynamic computation from question content.

    The algorithm named in the pattern computes what the expected wrong answer
    would be given the question's specific values, then compares with the user's answer.
    """
    algorithm = pattern.get("algorithm")
    if not algorithm:
        return False

    # Dispatch to the appropriate algorithm handler.
    handler = _PARAMETRIC_HANDLERS.get(algorithm)
    if handler is None:
        logger.warning("Unknown parametric algorithm: %s", algorithm)
        return False

    return handler(user_str, question)


# --- Parametric algorithm handlers ---


def _algo_fraction_add_numerators(user_str: str, question: Question) -> bool:
    """Detect 'add numerators and denominators' misconception.

    For a/b + c/d, the wrong answer is (a+c)/(b+d).
    Extracts the two fractions from the question's correct_answer and computes
    what the 'naive addition' result would be.
    """
    fractions = _extract_fractions_from_question(question)
    if not fractions or len(fractions) < 2:
        return False

    a, b = fractions[0]
    c, d = fractions[1]

    # The misconception: (a+c)/(b+d)
    wrong_num = a + c
    wrong_den = b + d
    expected_wrong = f"{wrong_num}/{wrong_den}"

    from apps.backend.app.services.learning.symbolic_equivalence import symbolic_eq

    result = symbolic_eq(user_str, expected_wrong)
    return result is True


def _algo_fraction_add_product_denominator(user_str: str, question: Question) -> bool:
    """Detect 'wrong common denominator (product instead of LCM)' misconception.

    For a/b + c/d, the child uses b*d as denominator instead of lcm(b,d).
    The wrong computation: (a*d + c*b) / (b*d).
    """
    fractions = _extract_fractions_from_question(question)
    if not fractions or len(fractions) < 2:
        return False

    a, b = fractions[0]
    c, d = fractions[1]

    # Wrong: product of denominators instead of LCM
    wrong_num = a * d + c * b
    wrong_den = b * d
    expected_wrong = f"{wrong_num}/{wrong_den}"

    from apps.backend.app.services.learning.symbolic_equivalence import symbolic_eq

    result = symbolic_eq(user_str, expected_wrong)
    # Only match if this is NOT also the correct answer (LCM might equal product
    # when b and d are coprime — in that case, the product IS the correct denominator).
    if result is True:
        import math
        lcm = (b * d) // math.gcd(b, d)
        if lcm == wrong_den:
            # Product equals LCM — this is actually the correct answer, not a misconception.
            return False

    return result is True


def _algo_fraction_add_whole_numbers(user_str: str, question: Question) -> bool:
    """Detect 'whole number addition' misconception.

    For a/b + c/d, the child treats as whole numbers: (a+c) (ignoring denominators),
    or adds as (a+c)/(1) — i.e., just adds the numerators.
    """
    fractions = _extract_fractions_from_question(question)
    if not fractions or len(fractions) < 2:
        return False

    a, _b = fractions[0]
    c, _d = fractions[1]

    # Wrong: just adds numerators, result is a whole number
    wrong_val = str(a + c)

    from apps.backend.app.services.learning.symbolic_equivalence import symbolic_eq

    result = symbolic_eq(user_str, wrong_val)
    return result is True


def _extract_fractions_from_question(question: Question) -> list[tuple[int, int]] | None:
    """Extract fraction operands from a question's correct_answer.

    Expects the answer dict to contain fraction operands in one of these formats:
    - {"fractions": [[num, den], [num, den]]}
    - {"answer": "a/b + c/d", "operands": [[a, b], [c, d]]}
    - Parameters stored in the question's parameters field.

    Returns list of (numerator, denominator) tuples, or None if extraction fails.
    """
    answer = question.answer
    if not answer or not isinstance(answer, dict):
        return None

    # Try explicit fractions list
    fractions = answer.get("fractions")
    if fractions and isinstance(fractions, list) and len(fractions) >= 2:
        result = []
        for f in fractions[:2]:
            if isinstance(f, (list, tuple)) and len(f) >= 2:
                try:
                    result.append((int(f[0]), int(f[1])))
                except (ValueError, TypeError):
                    return None
        if len(result) == 2:
            return result

    # Try operands list
    operands = answer.get("operands")
    if operands and isinstance(operands, list) and len(operands) >= 2:
        result = []
        for o in operands[:2]:
            if isinstance(o, (list, tuple)) and len(o) >= 2:
                try:
                    result.append((int(o[0]), int(o[1])))
                except (ValueError, TypeError):
                    return None
        if len(result) == 2:
            return result

    # Try parsing from question parameters
    params = question.parameters
    if params and isinstance(params, dict):
        fractions = params.get("fractions") or params.get("operands")
        if fractions and isinstance(fractions, list) and len(fractions) >= 2:
            result = []
            for f in fractions[:2]:
                if isinstance(f, (list, tuple)) and len(f) >= 2:
                    try:
                        result.append((int(f[0]), int(f[1])))
                    except (ValueError, TypeError):
                        return None
            if len(result) == 2:
                return result

    return None


# Registry of parametric algorithm handlers.
_PARAMETRIC_HANDLERS = {
    "fraction_add_numerators": _algo_fraction_add_numerators,
    "fraction_add_product_denominator": _algo_fraction_add_product_denominator,
    "fraction_add_whole_numbers": _algo_fraction_add_whole_numbers,
}
