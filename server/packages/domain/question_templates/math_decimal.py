"""Math decimal operation templates."""
import random

from packages.domain.question_templates.base import GeneratedQuestion
from packages.domain.question_templates.registry import register_template


@register_template("math.decimal.addition")
def _gen_decimal_addition(params: dict) -> GeneratedQuestion:
    a = round(random.uniform(0.1, 9.9), 1)
    b = round(random.uniform(0.1, 9.9), 1)
    answer = round(a + b, 1)
    return GeneratedQuestion(
        template_id="math.decimal.addition",
        stem=f"计算：{a} + {b} = ?",
        stem_zh=f"计算：{a} + {b} = ?",
        answer={"answer": answer},
        question_type="calculation",
        difficulty=2,
        bloom_level="apply",
        topic_key="math.decimal.addition",
        age_group="low",
        solution={"steps": [f"{a} + {b} = {answer}"]},
    )


@register_template("math.decimal.subtraction")
def _gen_decimal_subtraction(params: dict) -> GeneratedQuestion:
    a = round(random.uniform(1.0, 9.9), 1)
    b = round(random.uniform(0.1, a), 1)
    answer = round(a - b, 1)
    return GeneratedQuestion(
        template_id="math.decimal.subtraction",
        stem=f"计算：{a} - {b} = ?",
        stem_zh=f"计算：{a} - {b} = ?",
        answer={"answer": answer},
        question_type="calculation",
        difficulty=2,
        bloom_level="apply",
        topic_key="math.decimal.subtraction",
        age_group="low",
    )


@register_template("math.decimal.multiplication")
def _gen_decimal_multiplication(params: dict) -> GeneratedQuestion:
    a = round(random.uniform(0.1, 5.0), 1)
    b = random.randint(2, 9)
    answer = round(a * b, 1)
    return GeneratedQuestion(
        template_id="math.decimal.multiplication",
        stem=f"计算：{a} × {b} = ?",
        stem_zh=f"计算：{a} × {b} = ?",
        answer={"answer": answer},
        question_type="calculation",
        difficulty=3,
        bloom_level="apply",
        topic_key="math.decimal.multiplication",
        age_group="low",
    )
