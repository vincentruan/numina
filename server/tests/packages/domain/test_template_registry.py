"""Tests for question template registry."""
import pytest

from packages.domain.question_templates.base import GeneratedQuestion
from packages.domain.question_templates.registry import (
    TEMPLATE_REGISTRY,
    generate_question,
    list_templates,
    register_template,
)


@pytest.fixture(autouse=True)
def clean_registry():
    """Clear registry for isolated tests, restore after."""
    saved = dict(TEMPLATE_REGISTRY)
    TEMPLATE_REGISTRY.clear()
    yield
    TEMPLATE_REGISTRY.clear()
    TEMPLATE_REGISTRY.update(saved)


def test_register_and_generate():
    @register_template("math.test.add")
    def gen(params: dict) -> GeneratedQuestion:
        a, b = params["a"], params["b"]
        return GeneratedQuestion(
            template_id="math.test.add",
            stem=f"{a} + {b} = ?",
            stem_zh=f"计算：{a} + {b} = ?",
            answer={"answer": a + b},
            question_type="calculation",
            difficulty=1,
            bloom_level="apply",
            topic_key="mt_test",
            age_group="mid",
            parameters={"a": a, "b": b},
        )

    result = generate_question("math.test.add", {"a": 3, "b": 4})
    assert result.stem_zh == "计算：3 + 4 = ?"
    assert result.answer == {"answer": 7}


def test_list_templates_by_subject():
    @register_template("math.test.a")
    def a(params: dict) -> GeneratedQuestion:
        return GeneratedQuestion(
            "t", "s", {"answer": 1}, "calculation", 1, "apply", "mt", "mid"
        )

    @register_template("math.test.b")
    def b(params: dict) -> GeneratedQuestion:
        return GeneratedQuestion(
            "t", "s", {"answer": 1}, "calculation", 1, "apply", "mt", "mid"
        )

    @register_template("chinese.test.c")
    def c(params: dict) -> GeneratedQuestion:
        return GeneratedQuestion(
            "t", "s", {"answer": 1}, "fill_blank", 1, "remember", "mt", "mid"
        )

    math = list_templates(subject="math")
    assert len(math) == 2
    assert "math.test.a" in math
    assert "math.test.b" in math

    chinese = list_templates(subject="chinese")
    assert len(chinese) == 1


def test_generate_unknown_template_raises():
    with pytest.raises(ValueError, match="Unknown template"):
        generate_question("nonexistent.template", {})
