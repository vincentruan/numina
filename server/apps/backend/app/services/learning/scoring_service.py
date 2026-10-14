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

    if question_type == "multi_fill_blank":
        result = check_multi_fill_blank_partial(correct_answer, user_answer)
        return result["correct_count"] == result["total"]

    if question_type == "ai_graded":
        result = check_ai_graded(correct_answer, user_answer)
        return result["is_correct"]

    logger.warning("Unknown question_type for scoring: %s", question_type)
    return False


def check_multi_fill_blank_partial(
    correct_answer: dict,
    user_answer: dict,
) -> dict:
    """Score multi_fill_blank with per-blank detail.

    Returns {correct_count, total, per_blank: [bool, ...]}.
    """
    correct_blanks = correct_answer.get("blanks", [])
    user_blanks = user_answer.get("blanks", [])
    total = len(correct_blanks)
    per_blank = []

    for i in range(total):
        if i < len(user_blanks):
            c = str(correct_blanks[i]).strip()
            u = str(user_blanks[i]).strip()
            per_blank.append(c == u)
        else:
            per_blank.append(False)

    return {
        "correct_count": sum(per_blank),
        "total": total,
        "per_blank": per_blank,
    }


def check_ai_graded(
    correct_answer: dict,
    user_answer: dict,
    family_id: int | None = None,
    user_id: int | None = None,
    *,
    mock_confidence: float | None = None,
) -> dict:
    """AI-assisted grading with confidence.

    Returns {is_correct, result_level, confidence, explanation, low_confidence}.
    result_level: 'correct' | 'partial' | 'incorrect'.
    """
    confidence_threshold = 0.7

    if mock_confidence is not None:
        confidence = mock_confidence
        is_correct = confidence >= confidence_threshold
        result_level = "correct" if confidence >= 0.85 else ("partial" if confidence >= 0.5 else "incorrect")
        explanation = "Mock AI grading for testing"
    else:
        # Production path: synchronous HTTP call to agent's /grade endpoint.
        import httpx

        from packages.core.settings import settings
        try:
            response = httpx.post(
                f"{settings.AGENT_BASE_URL}/grade",
                json={
                    "rubric": correct_answer.get("rubric", ""),
                    "user_text": user_answer.get("text", ""),
                    "keywords": correct_answer.get("keywords", []),
                },
                headers={"X-Family-Id": str(family_id), "X-User-Id": str(user_id)},
                timeout=30.0,
            )
            data = response.json()
            confidence = data.get("confidence", 0.0)
            result_level = data.get("result_level", "correct" if confidence >= 0.85 else "partial" if confidence >= 0.5 else "incorrect")
            is_correct = confidence >= confidence_threshold
            explanation = data.get("explanation", "")
        except Exception:
            # Agent /grade endpoint is not yet deployed — ai_graded questions
            # will always score as incorrect until the endpoint exists.
            # Log at ERROR so ops can detect this gap in monitoring.
            logger.error(
                "ai_graded: agent /grade endpoint unavailable; "
                "ai_graded questions will fail closed until deployed"
            )
            confidence = 0.0
            result_level = "incorrect"
            is_correct = False
            explanation = "AI grading service unavailable"

    return {
        "is_correct": is_correct,
        "result_level": result_level,
        "confidence": confidence,
        "explanation": explanation,
        "low_confidence": confidence < confidence_threshold,
    }


def calculate_session_score(correct: int, total: int) -> float:
    """Calculate session score as ratio (0.0-1.0)."""
    if total == 0:
        return 0.0
    return correct / total
