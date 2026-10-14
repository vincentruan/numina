"""Matter science pilot templates."""
import random

from packages.domain.question_templates.base import GeneratedQuestion
from packages.domain.question_templates.registry import register_template


@register_template("science.matter.states_of_matter")
def _gen_states_of_matter(params: dict) -> GeneratedQuestion:
    items = [
        ("水在常温下是什么状态？", "液态", ["固态", "液态", "气态"]),
        ("冰是什么状态的水？", "固态", ["固态", "液态", "气态"]),
        ("水蒸气是什么状态？", "气态", ["固态", "液态", "气态"]),
        ("铁在常温下是什么状态？", "固态", ["固态", "液态", "气态"]),
    ]
    question, correct, opts = random.choice(items)
    options = [{"key": chr(65+i), "text": o, "text_zh": o} for i, o in enumerate(opts)]
    answer_key = chr(65 + opts.index(correct))
    return GeneratedQuestion(
        template_id="science.matter.states_of_matter",
        stem=question,
        stem_zh=question,
        answer={"key": answer_key},
        question_type="multiple_choice",
        difficulty=1,
        bloom_level="remember",
        topic_key="science.matter.states_of_matter",
        age_group="low",
        options=options,
    )
