"""Auto-grading service for practice answers."""
from packages.core.logging import get_logger

logger = get_logger(__name__)


def check_answer(
    question_type: str,
    correct_answer: dict,
    user_answer: dict,
) -> bool:
    """Check if user answer matches the correct answer.

    Returns False (not raises) for malformed input — graceful degradation.
    """
    if question_type == "calculation":
        return user_answer.get("answer") == correct_answer.get("answer")

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
        # Application questions need manual review; auto-check acceptable list
        acceptable = correct_answer.get("acceptable", [])
        return user_answer.get("answer") in acceptable

    logger.warning("Unknown question_type for scoring: %s", question_type)
    return False


def calculate_session_score(correct: int, total: int) -> float:
    """Calculate session score as ratio (0.0-1.0)."""
    if total == 0:
        return 0.0
    return correct / total
