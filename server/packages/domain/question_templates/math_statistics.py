"""Math statistics templates."""

import random

from packages.domain.question_templates.base import GeneratedQuestion
from packages.domain.question_templates.registry import register_template


@register_template("math.statistics.mean")
def _gen_mean(params: dict) -> GeneratedQuestion:
    count = random.randint(3, 5)
    numbers = [random.randint(1, 20) for _ in range(count)]
    total = sum(numbers)
    numbers[-1] = numbers[-1] + (count - total % count) % count
    mean = sum(numbers) // count
    num_str = "、".join(str(n) for n in numbers)
    return GeneratedQuestion(
        template_id="math.statistics.mean",
        stem=f"求以下数据的平均数：{num_str}",
        stem_zh=f"求平均数：{num_str}",
        answer={"answer": mean},
        question_type="calculation",
        difficulty=2,
        bloom_level="apply",
        topic_key="math.statistics.mean",
        age_group="low",
    )


@register_template("math.statistics.probability_basic")
def _gen_probability(params: dict) -> GeneratedQuestion:
    scenario = random.choice(["dice", "balls"])
    if scenario == "dice":
        target = random.randint(1, 6)
        question = f"掷一个骰子，掷出{target}的概率是多少？"
        answer_text = "1/6"
    else:
        question = "一个袋子中有3个红球和2个蓝球，随机摸一个球，摸到红球的概率是多少？"
        answer_text = "3/5"
    return GeneratedQuestion(
        template_id="math.statistics.probability_basic",
        stem=question,
        stem_zh=question,
        answer={"value": answer_text},
        question_type="fill_blank",
        difficulty=3,
        bloom_level="understand",
        topic_key="math.statistics.probability_basic",
        age_group="low",
    )
