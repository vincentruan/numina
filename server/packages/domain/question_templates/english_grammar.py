"""English grammar pilot templates."""

import random

from packages.domain.question_templates.base import GeneratedQuestion
from packages.domain.question_templates.registry import register_template


@register_template("english.grammar.be_verbs")
def _gen_be_verbs(params: dict) -> GeneratedQuestion:
    sentences = [
        ("I ___ a student.", "am"),
        ("She ___ a teacher.", "is"),
        ("They ___ happy.", "are"),
        ("He ___ my friend.", "is"),
        ("We ___ in the classroom.", "are"),
    ]
    sentence, answer = random.choice(sentences)
    return GeneratedQuestion(
        template_id="english.grammar.be_verbs",
        stem=f"Fill in the blank: {sentence}",
        stem_zh=f"填空：{sentence}",
        answer={"value": answer},
        question_type="fill_blank",
        difficulty=1,
        bloom_level="apply",
        topic_key="english.grammar.be_verbs",
        age_group="low",
    )
