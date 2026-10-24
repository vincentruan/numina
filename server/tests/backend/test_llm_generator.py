"""Tests for LLM question generator with 3-layer validation."""

import pytest

from apps.backend.app.services.learning.llm_generator import (
    _build_generation_prompt,
    classify_risk,
    validate_layer1_format,
    validate_layer3_ai_cross,
)
from packages.db.models.learning.topic import LearningTopic
from packages.domain.question_templates.base import GeneratedQuestion


@pytest.fixture
def math_topic(db_session):
    t = LearningTopic(
        topic_key="math.fraction.addition", subject="mathematics",
        domain="number", name="Fraction Addition", age_group="lower",
        description="Add fractions with like denominators", deprecated=False,
        topic_type="knowledge",
    )
    db_session.add(t)
    db_session.flush()
    return t


class TestLayer1FormatValidation:
    """Layer 1: structural format checks."""

    def test_valid_question_passes(self, math_topic):
        gq = GeneratedQuestion(
            template_id="llm.gen", stem="1/4 + 2/4 = ?",
            answer={"answer": "3/4"}, question_type="calculation",
            difficulty=2, bloom_level="apply", topic_key="math.fraction.addition",
            age_group="lower", stem_zh="1/4 + 2/4 = ?",
        )
        errors = validate_layer1_format(gq, math_topic)
        assert errors == []

    def test_empty_stem_fails(self, math_topic):
        gq = GeneratedQuestion(
            template_id="llm.gen", stem="",
            answer={"answer": "3/4"}, question_type="calculation",
            difficulty=2, bloom_level="apply", topic_key="math.fraction.addition",
            age_group="lower",
        )
        errors = validate_layer1_format(gq, math_topic)
        assert len(errors) > 0

    def test_wrong_topic_key_fails(self, math_topic):
        gq = GeneratedQuestion(
            template_id="llm.gen", stem="Some question about math",
            answer={"answer": "42"}, question_type="calculation",
            difficulty=2, bloom_level="apply", topic_key="wrong.key",
            age_group="lower",
        )
        errors = validate_layer1_format(gq, math_topic)
        assert any("topic_key" in e for e in errors)


class TestLayer3AiCrossValidation:
    """Layer 3: AI cross-validation (mocked)."""

    def test_high_agreement_passes(self, math_topic):
        result = validate_layer3_ai_cross(gq=None, topic=math_topic, llm_client=None,
                                          mock_verdict="match")
        assert result["passed"] is True

    def test_mismatch_fails(self, math_topic):
        result = validate_layer3_ai_cross(gq=None, topic=math_topic, llm_client=None,
                                          mock_verdict="mismatch")
        assert result["passed"] is False

    def test_content_safety_filter_applied(self, math_topic):
        from apps.backend.app.services.learning.content_safety_filter import (
            filter_tutor_output,
        )
        unsafe = "Some violent content"
        result = filter_tutor_output(unsafe, child_id=0)
        assert hasattr(result, "safe")
        assert isinstance(result.safe, bool)


class TestRiskClassification:
    """Risk classification based on validation results and question type."""

    def test_objective_low_risk_when_all_pass(self):
        validation = {"layer1": [], "layer2": {"passed": True}, "layer3": {"passed": True}}
        gq = GeneratedQuestion(
            template_id="llm.gen", stem="test", answer={"answer": 42},
            question_type="calculation", difficulty=2, bloom_level="apply",
            topic_key="math.test", age_group="lower",
        )
        risk = classify_risk(gq, validation)
        assert risk == "low"

    def test_analyze_bloom_is_medium_risk(self):
        validation = {"layer1": [], "layer2": {"passed": True}, "layer3": {"passed": True}}
        gq = GeneratedQuestion(
            template_id="llm.gen", stem="What pattern?", answer={"answer": "42"},
            question_type="application", difficulty=3, bloom_level="analyze",
            topic_key="math.test", age_group="lower",
        )
        risk = classify_risk(gq, validation)
        assert risk == "medium"

    def test_layer2_failure_is_high_risk(self):
        validation = {"layer1": [], "layer2": {"passed": False}, "layer3": {"passed": True}}
        gq = GeneratedQuestion(
            template_id="llm.gen", stem="test", answer={"answer": 42},
            question_type="calculation", difficulty=2, bloom_level="apply",
            topic_key="math.test", age_group="lower",
        )
        risk = classify_risk(gq, validation)
        assert risk == "high"


class TestPromptConstruction:
    """Prompt must include topic info and enforce topic_key in output."""

    def test_prompt_includes_topic_name(self, math_topic):
        prompt = _build_generation_prompt(math_topic)
        assert "Fraction Addition" in prompt

    def test_prompt_includes_topic_key_constraint(self, math_topic):
        prompt = _build_generation_prompt(math_topic)
        assert "math.fraction.addition" in prompt
        assert "must" in prompt.lower() or "必须" in prompt
