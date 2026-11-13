"""Life Skills question templates.

Covers the signature demo topic 'Buyers & Sellers' (mt_SbEaQnMQoD) so the
life_skills signature challenge can be reached.
"""

from packages.domain.question_templates.base import GeneratedQuestion
from packages.domain.question_templates.registry import register_template


@register_template("life_skills.buyers_sellers")
def _gen_buyers_sellers(params: dict) -> GeneratedQuestion:
    return GeneratedQuestion(
        template_id="life_skills.buyers_sellers",
        stem="You have $10 and want to buy an apple for $3 and a banana for $2. How much money do you have left?",
        stem_zh="你有 10 元，想买一个 3 元的苹果和一个 2 元的香蕉，还剩多少元？",
        answer={"answer": 5},
        question_type="calculation",
        difficulty=1,
        bloom_level="apply",
        topic_key="mt_SbEaQnMQoD",
        age_group="early",
        solution={"steps": ["Spend 3 + 2 = 5.", "10 - 5 = 5 left."]},
    )
