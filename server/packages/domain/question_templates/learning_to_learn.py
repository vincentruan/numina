"""Learning to Learn question templates.

Covers the signature demo topic 'Asking for Help' (mt_mvXufozy2s) so the
learning_to_learn signature challenge can be reached.
"""

from packages.domain.question_templates.base import GeneratedQuestion
from packages.domain.question_templates.registry import register_template


@register_template("learning_to_learn.asking_for_help")
def _gen_asking_for_help(params: dict) -> GeneratedQuestion:
    return GeneratedQuestion(
        template_id="learning_to_learn.asking_for_help",
        stem="You do not understand your homework. What is the best first step?",
        stem_zh="作业看不懂，第一步该怎么做？",
        answer={"answer": "Read the question slowly and underline the part you do not understand."},
        question_type="multiple_choice",
        difficulty=1,
        bloom_level="apply",
        topic_key="mt_mvXufozy2s",
        age_group="low",
        options=[
            {"key": "A", "text": "Read the question slowly and underline the part you do not understand.", "text_zh": "慢慢读题，把你看不懂的地方画出来。"},
            {"key": "B", "text": "Skip it and never ask.", "text_zh": "跳过，永远不问。"},
            {"key": "C", "text": "Copy a classmate's work without asking.", "text_zh": "不问就抄同学的。"},
            {"key": "D", "text": "Guess the answer and move on.", "text_zh": "猜一个答案然后继续。"},
        ],
        solution={"steps": ["Pinpointing what you do not understand is the first step to asking a useful question."]},
    )
