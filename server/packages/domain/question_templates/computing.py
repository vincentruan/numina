"""Computing question templates.

Covers the signature demo topic 'AI in Daily Life' (mt_AzTrT5ySCx) so the
computing signature challenge can be reached.
"""

from packages.domain.question_templates.base import GeneratedQuestion
from packages.domain.question_templates.registry import register_template


@register_template("computing.ai_daily_life")
def _gen_ai_daily_life(params: dict) -> GeneratedQuestion:
    return GeneratedQuestion(
        template_id="computing.ai_daily_life",
        stem="Which of these is a daily-life example of AI?",
        stem_zh="以下哪一个是日常生活中用到人工智能的例子？",
        answer={"answer": "A phone that suggests the next word you will type."},
        question_type="multiple_choice",
        difficulty=2,
        bloom_level="apply",
        topic_key="mt_AzTrT5ySCx",
        age_group="mid",
        options=[
            {"key": "A", "text": "A phone that suggests the next word you will type.", "text_zh": "手机根据你已打的字建议下一个词。"},
            {"key": "B", "text": "A clock that rings at 7 a.m.", "text_zh": "早上 7 点响的闹钟。"},
            {"key": "C", "text": "A lamp that turns on with a switch.", "text_zh": "用开关打开的灯。"},
            {"key": "D", "text": "A kettle that boils water.", "text_zh": "烧开水的壶。"},
        ],
        solution={"steps": ["Word prediction uses a trained language model — that is AI."]},
    )
