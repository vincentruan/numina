"""Math estimation templates."""
import random

from packages.domain.question_templates.base import GeneratedQuestion
from packages.domain.question_templates.registry import register_template


@register_template("math.estimation.rounding")
def _gen_rounding(params: dict) -> GeneratedQuestion:
    number = random.randint(10, 9999)
    place = random.choice([("十", 10), ("百", 100), ("千", 1000)])
    rounded = round(number / place[1]) * place[1]
    return GeneratedQuestion(
        template_id="math.estimation.rounding",
        stem=f"将 {number} 四舍五入到{place[0]}位约是多少？",
        stem_zh=f"将 {number} 四舍五入到{place[0]}位约是多少？",
        answer={"answer": rounded}, question_type="calculation",
        difficulty=2, bloom_level="apply",
        topic_key="math.estimation.rounding", age_group="lower",
    )


@register_template("math.estimation.approximate_calc")
def _gen_approx_calc(params: dict) -> GeneratedQuestion:
    a = random.randint(10, 99)
    b = random.randint(10, 99)
    approx = round(a, -1) + round(b, -1)
    return GeneratedQuestion(
        template_id="math.estimation.approximate_calc",
        stem=f"估算：{a} + {b} 大约等于多少？（先四舍五入到十位再计算）",
        stem_zh=f"估算：{a} + {b} 大约等于多少？",
        answer={"answer": approx}, question_type="calculation",
        difficulty=2, bloom_level="understand",
        topic_key="math.estimation.approximate_calc", age_group="lower",
    )
