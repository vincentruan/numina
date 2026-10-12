"""Math arithmetic question templates — elementary school level."""
import random

from packages.domain.question_templates.base import GeneratedQuestion
from packages.domain.question_templates.registry import register_template


@register_template("math.arithmetic.addition_2digit")
def _gen_addition_2digit(params: dict) -> GeneratedQuestion:
    lo = params.get("min", 10)
    hi = params.get("max", 99)
    a = random.randint(lo, hi)
    b = random.randint(lo, hi)
    return GeneratedQuestion(
        template_id="math.arithmetic.addition_2digit",
        stem=f"Calculate: {a} + {b} = ?",
        stem_zh=f"计算：{a} + {b} = ?",
        answer={"answer": a + b},
        solution={"steps": [f"{a} + {b} = {a + b}"]},
        question_type="calculation",
        difficulty=1,
        bloom_level="apply",
        topic_key="mt_arithmetic_addition",
        age_group="mid",
        parameters={"a": a, "b": b},
    )


@register_template("math.arithmetic.subtraction_2digit")
def _gen_subtraction_2digit(params: dict) -> GeneratedQuestion:
    lo = params.get("min", 10)
    hi = params.get("max", 99)
    a = random.randint(lo, hi)
    b = random.randint(lo, min(a, hi))  # Ensure non-negative result
    return GeneratedQuestion(
        template_id="math.arithmetic.subtraction_2digit",
        stem=f"Calculate: {a} - {b} = ?",
        stem_zh=f"计算：{a} - {b} = ?",
        answer={"answer": a - b},
        solution={"steps": [f"{a} - {b} = {a - b}"]},
        question_type="calculation",
        difficulty=1,
        bloom_level="apply",
        topic_key="mt_arithmetic_subtraction",
        age_group="mid",
        parameters={"a": a, "b": b},
    )


@register_template("math.arithmetic.multiplication_table")
def _gen_multiplication_table(params: dict) -> GeneratedQuestion:
    a = random.randint(1, 9)
    b = random.randint(1, 9)
    return GeneratedQuestion(
        template_id="math.arithmetic.multiplication_table",
        stem=f"Calculate: {a} × {b} = ?",
        stem_zh=f"计算：{a} × {b} = ?",
        answer={"answer": a * b},
        solution={"steps": [f"{a} × {b} = {a * b}"]},
        question_type="calculation",
        difficulty=1,
        bloom_level="apply",
        topic_key="mt_arithmetic_multiplication",
        age_group="mid",
        parameters={"a": a, "b": b},
    )


@register_template("math.arithmetic.division_basic")
def _gen_division_basic(params: dict) -> GeneratedQuestion:
    # Generate division that yields integer result
    divisor = random.randint(2, 9)
    quotient = random.randint(2, 12)
    dividend = divisor * quotient
    return GeneratedQuestion(
        template_id="math.arithmetic.division_basic",
        stem=f"Calculate: {dividend} ÷ {divisor} = ?",
        stem_zh=f"计算：{dividend} ÷ {divisor} = ?",
        answer={"answer": quotient},
        solution={"steps": [f"{dividend} ÷ {divisor} = {quotient}"]},
        question_type="calculation",
        difficulty=1,
        bloom_level="apply",
        topic_key="mt_arithmetic_division",
        age_group="mid",
        parameters={"dividend": dividend, "divisor": divisor, "quotient": quotient},
    )
