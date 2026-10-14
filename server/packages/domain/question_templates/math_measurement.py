"""Math measurement templates."""
import random

from packages.domain.question_templates.base import GeneratedQuestion
from packages.domain.question_templates.registry import register_template


@register_template("math.measurement.unit_conversion")
def _gen_unit_conversion(params: dict) -> GeneratedQuestion:
    conversions = [
        (random.randint(1, 20), "米", "厘米", 100),
        (random.randint(1, 10), "千克", "克", 1000),
        (random.randint(1, 60), "分钟", "秒", 60),
        (random.randint(1, 5), "千米", "米", 1000),
    ]
    val, from_u, to_u, factor = random.choice(conversions)
    answer = val * factor
    return GeneratedQuestion(
        template_id="math.measurement.unit_conversion",
        stem=f"{val}{from_u} = ?{to_u}",
        stem_zh=f"{val}{from_u} = ?{to_u}",
        answer={"answer": answer}, question_type="calculation",
        difficulty=2, bloom_level="apply",
        topic_key="math.measurement.unit_conversion", age_group="low",
    )


@register_template("math.measurement.perimeter_rectangle")
def _gen_perimeter(params: dict) -> GeneratedQuestion:
    l = random.randint(3, 20)
    w = random.randint(2, 15)
    answer = 2 * (l + w)
    return GeneratedQuestion(
        template_id="math.measurement.perimeter_rectangle",
        stem=f"一个长方形，长{l}厘米，宽{w}厘米，周长是多少厘米？",
        stem_zh=f"长方形长{l}cm，宽{w}cm，求周长。",
        answer={"answer": answer}, question_type="calculation",
        difficulty=2, bloom_level="apply",
        topic_key="math.measurement.perimeter_rectangle", age_group="low",
        solution={"steps": [f"周长 = 2×(长+宽) = 2×({l}+{w}) = {answer}"]},
    )


@register_template("math.measurement.area_rectangle")
def _gen_area(params: dict) -> GeneratedQuestion:
    l = random.randint(3, 15)
    w = random.randint(2, 12)
    answer = l * w
    return GeneratedQuestion(
        template_id="math.measurement.area_rectangle",
        stem=f"一个长方形，长{l}厘米，宽{w}厘米，面积是多少平方厘米？",
        stem_zh=f"长方形长{l}cm，宽{w}cm，求面积。",
        answer={"answer": answer}, question_type="calculation",
        difficulty=2, bloom_level="apply",
        topic_key="math.measurement.area_rectangle", age_group="low",
    )
