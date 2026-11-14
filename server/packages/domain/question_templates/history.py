"""History question templates.

Covers the signature demo topic 'Discovering Tutankhamun's Tomb' (mt_IR8kIjZn_V)
so the history signature challenge can be reached in the practice flow.
"""

from packages.domain.question_templates.base import GeneratedQuestion
from packages.domain.question_templates.registry import register_template


@register_template("history.tutankhamun")
def _gen_tutankhamun(params: dict) -> GeneratedQuestion:
    return GeneratedQuestion(
        template_id="history.tutankhamun",
        stem="Who found the tomb of Tutankhamun in 1922?",
        stem_zh="1922 年，谁发现了图坦卡蒙的墓？",
        answer={"answer": "Howard Carter"},
        question_type="multiple_choice",
        difficulty=2,
        bloom_level="remember",
        topic_key="mt_IR8kIjZn_V",
        age_group="mid",
        options=[
            {"key": "A", "text": "Howard Carter", "text_zh": "霍华德·卡特"},
            {"key": "B", "text": "Lord Carnarvon", "text_zh": "卡纳冯勋爵"},
            {"key": "C", "text": "Jean-François Champollion", "text_zh": "商博良"},
            {"key": "D", "text": "Mark Lehner", "text_zh": "莱纳"},
        ],
        solution={"steps": ["Howard Carter discovered the tomb in the Valley of the Kings in 1922."]},
    )
