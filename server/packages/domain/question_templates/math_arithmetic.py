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
        topic_key="mt_glPPG-kTQY",
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
        topic_key="mt_SrrsLiJkr3",
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
        topic_key="mt_HhuSDxwDNM",
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
        topic_key="mt_DyGBW3ZHh3",
        age_group="mid",
        parameters={"dividend": dividend, "divisor": divisor, "quotient": quotient},
    )


@register_template("math.arithmetic.addition_3digit")
def _gen_addition_3digit(params: dict) -> GeneratedQuestion:
    lo = params.get("min", 100)
    hi = params.get("max", 999)
    a = random.randint(lo, hi)
    b = random.randint(lo, hi)
    return GeneratedQuestion(
        template_id="math.arithmetic.addition_3digit",
        stem=f"Calculate: {a} + {b} = ?",
        stem_zh=f"计算：{a} + {b} = ?",
        answer={"answer": a + b},
        solution={"steps": [f"{a} + {b} = {a + b}"]},
        question_type="calculation",
        difficulty=2,
        bloom_level="apply",
        topic_key="mt_mpS-JK_p_m",
        age_group="mid",
        parameters={"a": a, "b": b},
    )


@register_template("math.arithmetic.subtraction_3digit")
def _gen_subtraction_3digit(params: dict) -> GeneratedQuestion:
    lo = params.get("min", 100)
    hi = params.get("max", 999)
    a = random.randint(lo, hi)
    b = random.randint(lo, min(a, hi))  # Ensure non-negative result
    return GeneratedQuestion(
        template_id="math.arithmetic.subtraction_3digit",
        stem=f"Calculate: {a} - {b} = ?",
        stem_zh=f"计算：{a} - {b} = ?",
        answer={"answer": a - b},
        solution={"steps": [f"{a} - {b} = {a - b}"]},
        question_type="calculation",
        difficulty=2,
        bloom_level="apply",
        topic_key="mt_mpS-JK_p_m",
        age_group="mid",
        parameters={"a": a, "b": b},
    )


@register_template("math.arithmetic.multiplication_estimate")
def _gen_multiplication_estimate(params: dict) -> GeneratedQuestion:
    """Estimate product by rounding to nearest 10 (四舍五入)."""
    a = random.randint(11, 99)
    b = random.randint(11, 99)
    # Use floor-based rounding: 四舍五入 (half-up)
    a_round = int(a / 10 + 0.5) * 10
    b_round = int(b / 10 + 0.5) * 10
    return GeneratedQuestion(
        template_id="math.arithmetic.multiplication_estimate",
        stem=f"估算：{a} × {b} ≈ ?（将两个数四舍五入到最近的整十数再相乘）",
        stem_zh=f"估算：{a} × {b} ≈ ?（将两个数四舍五入到最近的整十数再相乘）",
        answer={"answer": a_round * b_round},
        solution={"steps": [f"{a} ≈ {a_round}，{b} ≈ {b_round}", f"{a_round} × {b_round} = {a_round * b_round}"]},
        question_type="calculation",
        difficulty=2,
        bloom_level="apply",
        topic_key="mt_QaYfeVL-0C",
        age_group="mid",
        parameters={"a": a, "b": b},
    )


@register_template("math.arithmetic.division_with_remainder")
def _gen_division_with_remainder(params: dict) -> GeneratedQuestion:
    """Division that produces a quotient and remainder."""
    divisor = random.randint(3, 12)
    quotient = random.randint(5, 30)
    remainder = random.randint(1, divisor - 1)  # 1 <= remainder < divisor
    dividend = divisor * quotient + remainder
    return GeneratedQuestion(
        template_id="math.arithmetic.division_with_remainder",
        stem=f"计算：{dividend} ÷ {divisor} = ?……?",
        stem_zh=f"计算：{dividend} ÷ {divisor} = ?……?（写出商和余数）",
        answer={"value": f"{quotient}……{remainder}"},
        solution={"steps": [f"{dividend} ÷ {divisor}", f"= {quotient}……{remainder}", f"验证：{divisor} × {quotient} + {remainder} = {dividend}"]},
        question_type="fill_blank",
        difficulty=3,
        bloom_level="apply",
        topic_key="mt_p-nbe0w_lf",
        age_group="mid",
        parameters={"dividend": dividend, "divisor": divisor},
    )


@register_template("math.arithmetic.mixed_operations")
def _gen_mixed_operations(params: dict) -> GeneratedQuestion:
    """Mixed operations with order-of-operations rules."""
    op = random.choice(["add_then_multiply", "multiply_then_add", "subtract_then_divide"])
    if op == "add_then_multiply":
        a = random.randint(5, 30)
        b = random.randint(5, 30)
        c = random.randint(2, 9)
        result = (a + b) * c
        stem = f"计算：({a} + {b}) × {c} = ?"
    elif op == "multiply_then_add":
        a = random.randint(2, 12)
        b = random.randint(2, 12)
        c = random.randint(10, 100)
        result = a * b + c
        stem = f"计算：{a} × {b} + {c} = ?"
    else:  # subtract_then_divide
        c = random.randint(2, 8)
        quotient = random.randint(3, 15)
        b = random.randint(5, 30)
        a = c * quotient + b  # Ensure (a-b) is divisible by c
        result = quotient
        stem = f"计算：({a} - {b}) ÷ {c} = ?"
    return GeneratedQuestion(
        template_id="math.arithmetic.mixed_operations",
        stem=stem,
        stem_zh=stem,
        answer={"answer": result},
        solution={"steps": [stem.replace("计算：", "").replace(" = ?", ""), f"= {result}"]},
        question_type="calculation",
        difficulty=3,
        bloom_level="apply",
        topic_key="mt_AR-K72OIIO",
        age_group="mid",
        parameters={"a": a, "b": b, "c": c, "op": op},
    )
