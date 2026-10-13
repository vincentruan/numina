"""Auto-grading service for practice answers."""
import math

from packages.core.logging import get_logger

logger = get_logger(__name__)

_FLOAT_TOLERANCE = 1e-6


def _float_eq(a: float, b: float, *, rel_tol: float = 1e-4, abs_tol: float = _FLOAT_TOLERANCE) -> bool:
    """Compare floats with tolerance (handles 0.1+0.2 style imprecision)."""
    return math.isclose(a, b, rel_tol=rel_tol, abs_tol=abs_tol)


def check_answer(
    question_type: str,
    correct_answer: dict,
    user_answer: dict,
) -> bool:
    """Check if user answer matches the correct answer.

    Returns False (not raises) for malformed input — graceful degradation.
    """
    if question_type == "calculation":
        correct_val = correct_answer.get("answer")
        user_val = user_answer.get("answer")
        if isinstance(correct_val, (int, float)) and isinstance(user_val, (int, float)):
            return _float_eq(float(correct_val), float(user_val))
        return user_val == correct_val

    if question_type == "fill_blank":
        correct_val = correct_answer.get("value")
        user_val = user_answer.get("value")
        if isinstance(correct_val, str) and isinstance(user_val, str):
            return correct_val.strip() == user_val.strip()
        return user_val == correct_val

    if question_type == "multiple_choice":
        return user_answer.get("key") == correct_answer.get("key")

    if question_type == "true_false":
        return user_answer.get("value") == correct_answer.get("value")

    if question_type == "application":
        # Accept both "answer" and "value" keys for frontend compatibility
        user_val = user_answer.get("answer") or user_answer.get("value")
        acceptable = correct_answer.get("acceptable", [])
        return user_val in acceptable

    logger.warning("Unknown question_type for scoring: %s", question_type)
    return False


def calculate_session_score(correct: int, total: int) -> float:
    """Calculate session score as ratio (0.0-1.0)."""
    if total == 0:
        return 0.0
    return correct / total
