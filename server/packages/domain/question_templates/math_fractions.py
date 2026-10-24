"""Math fraction question templates — elementary school level."""

import random

from packages.domain.question_templates.base import GeneratedQuestion
from packages.domain.question_templates.registry import register_template


@register_template("math.fractions.comparison")
def _gen_fraction_comparison(params: dict) -> GeneratedQuestion:
    """Compare two fractions using cross-multiplication."""
    a_den = random.randint(2, 12)
    b_den = random.randint(2, 12)
    a_num = random.randint(1, a_den * 2)
    b_num = random.randint(1, b_den * 2)
    # Cross-multiply to determine comparison
    lhs = a_num * b_den
    rhs = b_num * a_den
    if lhs > rhs:
        symbol = ">"
    elif lhs < rhs:
        symbol = "<"
    else:
        symbol = "="
    return GeneratedQuestion(
        template_id="math.fractions.comparison",
        stem=f"比较大小：{a_num}/{a_den} ○ {b_num}/{b_den}，○里填 >、< 或 = ?",
        stem_zh=f"比较大小：{a_num}/{a_den} ○ {b_num}/{b_den}，○里填 >、< 或 = ?",
        answer={"value": symbol},
        solution={
            "steps": [
                f"交叉相乘：{a_num}×{b_den}={lhs}，{b_num}×{a_den}={rhs}",
                f"{lhs} {'>' if lhs > rhs else '<' if lhs < rhs else '='} {rhs}",
            ]
        },
        question_type="fill_blank",
        difficulty=2,
        bloom_level="understand",
        topic_key="mt_IfEgu0X449",
        age_group="mid",
        parameters={"a_num": a_num, "a_den": a_den, "b_num": b_num, "b_den": b_den},
    )


@register_template("math.fractions.addition_same_denominator")
def _gen_fraction_addition(params: dict) -> GeneratedQuestion:
    """Add two fractions with the same denominator."""
    den = random.randint(2, 12)
    a_num = random.randint(1, den - 1)
    b_num = random.randint(1, den - a_num)  # Ensure sum <= den for simplicity
    result_num = a_num + b_num
    return GeneratedQuestion(
        template_id="math.fractions.addition_same_denominator",
        stem=f"计算：{a_num}/{den} + {b_num}/{den} = ?/{den}",
        stem_zh=f"计算：{a_num}/{den} + {b_num}/{den} = ?/{den}",
        answer={"answer": result_num},
        solution={
            "steps": [
                "同分母分数相加，分母不变，分子相加",
                f"{a_num} + {b_num} = {result_num}，结果为 {result_num}/{den}",
            ]
        },
        question_type="calculation",
        difficulty=2,
        bloom_level="apply",
        topic_key="mt_CBHwluE6Lp",
        age_group="mid",
        parameters={"a_num": a_num, "b_num": b_num, "den": den},
    )


@register_template("math.fractions.subtraction_same_denominator")
def _gen_fraction_subtraction(params: dict) -> GeneratedQuestion:
    """Subtract two fractions with the same denominator."""
    den = random.randint(2, 12)
    a_num = random.randint(2, den)
    b_num = random.randint(1, a_num - 1)  # Ensure positive result
    result_num = a_num - b_num
    return GeneratedQuestion(
        template_id="math.fractions.subtraction_same_denominator",
        stem=f"计算：{a_num}/{den} - {b_num}/{den} = ?/{den}",
        stem_zh=f"计算：{a_num}/{den} - {b_num}/{den} = ?/{den}",
        answer={"answer": result_num},
        solution={
            "steps": [
                "同分母分数相减，分母不变，分子相减",
                f"{a_num} - {b_num} = {result_num}，结果为 {result_num}/{den}",
            ]
        },
        question_type="calculation",
        difficulty=2,
        bloom_level="apply",
        topic_key="mt_CBHwluE6Lp",
        age_group="mid",
        parameters={"a_num": a_num, "b_num": b_num, "den": den},
    )


@register_template("math.fractions.to_decimal")
def _gen_fraction_to_decimal(params: dict) -> GeneratedQuestion:
    """Convert a simple fraction to decimal."""
    # Use denominators that produce clean decimals: 2, 4, 5, 8, 10, 20, 25, 50
    clean_denoms = [2, 4, 5, 8, 10, 20, 25, 50]
    den = random.choice(clean_denoms)
    num = random.randint(1, den - 1)
    decimal_val = round(num / den, 4)
    return GeneratedQuestion(
        template_id="math.fractions.to_decimal",
        stem=f"将分数 {num}/{den} 转换为小数",
        stem_zh=f"将分数 {num}/{den} 转换为小数",
        answer={"answer": decimal_val},
        solution={"steps": [f"{num} ÷ {den} = {decimal_val}"]},
        question_type="calculation",
        difficulty=2,
        bloom_level="apply",
        topic_key="mt_TqDq6jyOmL",
        age_group="mid",
        parameters={"numerator": num, "denominator": den},
    )


@register_template("math.fractions.simple_reduction")
def _gen_fraction_reduction(params: dict) -> GeneratedQuestion:
    """Reduce a fraction to its simplest form."""
    from math import gcd

    # Generate a fraction that can be reduced
    reduced_num = random.randint(1, 10)
    reduced_den = random.randint(reduced_num + 1, 20)
    # Make sure they're coprime in reduced form
    while gcd(reduced_num, reduced_den) != 1:
        reduced_num = random.randint(1, 10)
        reduced_den = random.randint(reduced_num + 1, 20)
    # Multiply by a common factor
    factor = random.randint(2, 5)
    num = reduced_num * factor
    den = reduced_den * factor
    return GeneratedQuestion(
        template_id="math.fractions.simple_reduction",
        stem=f"将分数 {num}/{den} 化简为最简分数",
        stem_zh=f"将分数 {num}/{den} 化简为最简分数",
        answer={"value": f"{reduced_num}/{reduced_den}"},
        solution={
            "steps": [
                f"求最大公因数：gcd({num}, {den}) = {factor}",
                f"{num}÷{factor} = {reduced_num}，{den}÷{factor} = {reduced_den}",
            ]
        },
        question_type="fill_blank",
        difficulty=3,
        bloom_level="apply",
        topic_key="mt_b7T-CjOYUR",
        age_group="mid",
        parameters={"numerator": num, "denominator": den},
    )
