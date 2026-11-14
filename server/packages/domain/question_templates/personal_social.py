"""Personal & Social Development question templates.

Covers the signature demo topic 'Expressing Feelings with Words' (mt_kvrvpQris4)
so the personal_social signature challenge can be reached.
"""

from packages.domain.question_templates.base import GeneratedQuestion
from packages.domain.question_templates.registry import register_template


@register_template("personal_social.expressing_feelings")
def _gen_expressing_feelings(params: dict) -> GeneratedQuestion:
    return GeneratedQuestion(
        template_id="personal_social.expressing_feelings",
        stem="Which sentence shows a child using words to express a feeling?",
        stem_zh="哪句话是孩子在用语言表达自己的感受？",
        answer={"answer": "I feel sad because my friend left."},
        question_type="multiple_choice",
        difficulty=1,
        bloom_level="apply",
        topic_key="mt_kvrvpQris4",
        age_group="low",
        options=[
            {"key": "A", "text": "I feel sad because my friend left.", "text_zh": "朋友走了，我觉得难过。"},
            {"key": "B", "text": "Go away!", "text_zh": "走开！"},
            {"key": "C", "text": "I am fine.", "text_zh": "我很好。"},
            {"key": "D", "text": "Whatever.", "text_zh": "随便。"},
        ],
        solution={"steps": ["Naming a feeling with words (sad, happy, angry) is expressing it."] },
    )
