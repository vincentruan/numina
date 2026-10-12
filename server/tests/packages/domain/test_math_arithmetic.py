"""Tests for math arithmetic question templates."""
from packages.domain.question_templates.registry import (
    generate_question,
    list_templates,
)


def test_addition_2digit_generates_valid_question():
    q = generate_question("math.arithmetic.addition_2digit", {})
    assert q.question_type == "calculation"
    assert q.difficulty == 1
    assert q.bloom_level == "apply"
    assert q.age_group == "mid"
    assert "answer" in q.answer
    assert isinstance(q.answer["answer"], int)
    assert q.answer["answer"] >= 20  # min 10+10
    assert q.answer["answer"] <= 198  # max 99+99


def test_subtraction_2digit_generates_valid_question():
    q = generate_question("math.arithmetic.subtraction_2digit", {})
    assert q.question_type == "calculation"
    assert "answer" in q.answer
    assert q.answer["answer"] >= 0  # no negative results


def test_multiplication_table():
    q = generate_question("math.arithmetic.multiplication_table", {})
    assert q.question_type == "calculation"
    assert "answer" in q.answer
    a, b = q.parameters["a"], q.parameters["b"]
    assert 1 <= a <= 9
    assert 1 <= b <= 9
    assert q.answer["answer"] == a * b


def test_division_basic():
    q = generate_question("math.arithmetic.division_basic", {})
    assert q.question_type == "calculation"
    assert "answer" in q.answer
    assert isinstance(q.answer["answer"], int)


def test_all_templates_registered():
    templates = list_templates(subject="math")
    assert len(templates) >= 4
    assert "math.arithmetic.addition_2digit" in templates
    assert "math.arithmetic.subtraction_2digit" in templates
    assert "math.arithmetic.multiplication_table" in templates
    assert "math.arithmetic.division_basic" in templates


def test_templates_have_stem_zh():
    q = generate_question("math.arithmetic.addition_2digit", {})
    assert q.stem_zh is not None
    assert "计算" in q.stem_zh or "+" in q.stem_zh
