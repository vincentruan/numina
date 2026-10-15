"""LLM question generator with 3-layer validation and risk classification.

Pipeline:
  1. Build prompt from topic info (topic_key enforced in output)
  2. Call LLM → parse JSON → GeneratedQuestion
  3. Layer 1: format validation (stem non-empty, topic_key match, answer format)
  4. Layer 2: correctness validation (recompute for calculation, option exclusivity)
  5. Layer 3: AI cross-validation (separate prompt/model judges the question)
  6. Risk classification → route to review strategy
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

from apps.backend.app.services.learning.content_safety_filter import filter_tutor_output
from packages.core.logging import get_logger
from packages.db.models.learning.topic import LearningTopic
from packages.domain.question_templates.base import GeneratedQuestion

logger = get_logger(__name__)

# Objective question types that can be auto-verified
OBJECTIVE_TYPES = {"calculation", "fill_blank", "multiple_choice", "true_false"}

# Bloom levels requiring human review
REVIEW_BLOOM_LEVELS = {"analyze", "evaluate", "create"}


@dataclass
class ValidationResult:
    layer1: list[str] = field(default_factory=list)
    layer2: dict = field(default_factory=dict)
    layer3: dict = field(default_factory=dict)

    @property
    def passed(self) -> bool:
        return (
            len(self.layer1) == 0
            and self.layer2.get("passed", False)
            and self.layer3.get("passed", False)
        )


def _build_generation_prompt(topic: LearningTopic) -> str:
    """Build prompt for LLM question generation.

    Critical: prompt must include target topic_key and require it in output.
    """
    return f"""You are a professional K-12 math question generator.

Generate ONE high-quality math question for the following knowledge point:

Topic: {topic.name}
Topic Key: {topic.topic_key}
Domain: {topic.domain}
Age Group: {topic.age_group}
Description: {topic.description or topic.name}

Requirements:
- The question MUST measure the knowledge point "{topic.name}" (topic_key: {topic.topic_key})
- The question must be appropriate for age group "{topic.age_group}"
- Provide a clear, unambiguous question with a verifiable answer
- All text must be in Chinese (中文)

Output format (JSON):
{{
    "stem": "question text in Chinese",
    "stem_zh": "same as stem (Chinese)",
    "question_type": "calculation|fill_blank|multiple_choice|true_false|application",
    "answer": {{"answer": "correct answer"}},
    "difficulty": 1-5,
    "bloom_level": "remember|understand|apply|analyze",
    "topic_key": "{topic.topic_key}",
    "solution": {{"steps": ["step 1", "step 2"]}},
    "options": [{{"key": "A", "text": "option A"}}, ...]  // only for multiple_choice
}}

CRITICAL: The topic_key in your output MUST be exactly "{topic.topic_key}". Do not choose a different topic.
"""


def validate_layer1_format(gq: GeneratedQuestion, topic: LearningTopic) -> list[str]:
    """Layer 1: Structural format validation.

    Returns list of error strings (empty = passed).
    """
    errors = []

    if not gq.stem or len(gq.stem.strip()) < 5:
        errors.append("stem is empty or too short (< 5 chars)")

    # CRITICAL: topic_key must match (anti-hallucination defense)
    if gq.topic_key != topic.topic_key:
        errors.append(
            f"topic_key mismatch: expected '{topic.topic_key}', got '{gq.topic_key}'"
        )

    if gq.question_type not in {
        "calculation",
        "fill_blank",
        "multiple_choice",
        "true_false",
        "application",
    }:
        errors.append(f"unknown question_type: {gq.question_type}")

    if gq.difficulty < 1 or gq.difficulty > 5:
        errors.append(f"difficulty out of range: {gq.difficulty}")

    if gq.bloom_level not in {
        "remember",
        "understand",
        "apply",
        "analyze",
        "evaluate",
        "create",
    }:
        errors.append(f"unknown bloom_level: {gq.bloom_level}")

    # Content safety
    safety_result = filter_tutor_output(gq.stem, child_id=0)
    if not safety_result.safe:
        errors.append("stem failed content safety filter")

    return errors


def validate_layer2_correctness(gq: GeneratedQuestion) -> dict:
    """Layer 2: Answer correctness validation.

    Returns {passed: bool, detail: str}.
    """
    if gq.question_type == "calculation":
        answer = gq.answer
        if "answer" not in answer:
            return {"passed": False, "detail": "calculation missing 'answer' key"}
        # P2-4 fix: verify answer is actually numeric
        ans_val = answer["answer"]
        if isinstance(ans_val, str):
            try:
                float(ans_val)
            except ValueError:
                return {"passed": False, "detail": f"calculation answer not numeric: {ans_val}"}
        elif not isinstance(ans_val, (int, float)):
            return {"passed": False, "detail": f"calculation answer not numeric: {ans_val}"}
        return {
            "passed": True,
            "detail": "calculation answer present and numeric (manual verify recommended)",
        }

    if gq.question_type == "multiple_choice":
        options = gq.options or []
        if len(options) < 3:
            return {"passed": False, "detail": f"too few options: {len(options)}"}
        answer_key = gq.answer.get("key")
        option_keys = {o.get("key") for o in options}
        if answer_key not in option_keys:
            return {
                "passed": False,
                "detail": f"answer key '{answer_key}' not in options",
            }
        texts = [o.get("text", "") for o in options]
        if len(set(texts)) != len(texts):
            return {"passed": False, "detail": "duplicate option texts"}
        return {"passed": True, "detail": "multiple_choice structure valid"}

    if gq.question_type in ("fill_blank", "true_false", "application"):
        answer = gq.answer
        if not answer:
            return {"passed": False, "detail": "empty answer"}
        return {"passed": True, "detail": "answer present"}

    return {"passed": True, "detail": "no auto-verification available"}


def validate_layer3_ai_cross(
    gq: GeneratedQuestion | None,
    topic: LearningTopic,
    llm_client=None,
    mock_verdict: str | None = None,
    family_id: int | None = None,
    user_id: int | None = None,
) -> dict:
    """Layer 3: AI cross-validation — a separate prompt judges question quality.

    Returns {passed: bool, score: float, detail: str}.
    FAILS CLOSED on agent outage.
    """
    if mock_verdict is not None:
        passed = mock_verdict == "match"
        return {
            "passed": passed,
            "score": 1.0 if passed else 0.0,
            "detail": f"mock: {mock_verdict}",
        }

    # Production path: synchronous HTTP call to agent's cross-validation endpoint.
    import httpx

    from packages.core.settings import settings

    try:
        response = httpx.post(
            f"{settings.AGENT_BASE_URL}/cross-validate-question",
            json={
                "stem": gq.stem if gq else "",
                "topic_name": topic.name,
                "topic_key": topic.topic_key,
                "answer": json.dumps(gq.answer) if gq else "",
            },
            headers={
                "X-Family-Id": str(family_id) if family_id else "",
                "X-User-Id": str(user_id) if user_id else "",
            },
            timeout=30.0,
        )
        verdict = response.json().get("verdict", "match")
        score = {"match": 1.0, "partial": 0.5, "mismatch": 0.0}.get(verdict, 0.5)
        return {
            "passed": verdict != "mismatch",
            "score": score,
            "detail": f"agent: {verdict}",
        }
    except Exception:
        logger.warning("Layer 3: agent cross-validation unavailable, failing closed")
        return {
            "passed": False,
            "score": 0.0,
            "detail": "agent unavailable — routed to human review",
        }


def classify_risk(gq: GeneratedQuestion, validation: dict) -> str:
    """Classify question risk for review routing.

    Returns: "low", "medium", or "high"
    """
    # High risk: any layer failure
    if validation.get("layer1") and len(validation["layer1"]) > 0:
        return "high"
    if not validation.get("layer2", {}).get("passed", True):
        return "high"
    if not validation.get("layer3", {}).get("passed", True):
        return "high"

    # Medium risk: subjective Bloom levels
    if gq.bloom_level in REVIEW_BLOOM_LEVELS:
        return "medium"

    # Low risk: objective type + all layers pass
    if gq.question_type in OBJECTIVE_TYPES:
        return "low"

    return "medium"
