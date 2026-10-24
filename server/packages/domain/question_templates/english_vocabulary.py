"""English vocabulary pilot templates."""

import random

from packages.domain.question_templates.base import GeneratedQuestion
from packages.domain.question_templates.registry import register_template


@register_template("english.vocabulary.animals")
def _gen_animals(params: dict) -> GeneratedQuestion:
    items = [
        ("dog", "狗", ["dog", "cat", "bird", "fish"]),
        ("cat", "猫", ["cat", "dog", "rabbit", "duck"]),
        ("bird", "鸟", ["bird", "fish", "cat", "dog"]),
    ]
    word, meaning, opts = random.choice(items)
    options = [{"key": chr(65 + i), "text": o} for i, o in enumerate(opts)]
    answer_key = chr(65 + opts.index(word))
    return GeneratedQuestion(
        template_id="english.vocabulary.animals",
        stem=f"Which word means '{meaning}'?",
        stem_zh=f"哪个单词的意思是 '{meaning}'？",
        answer={"key": answer_key},
        question_type="multiple_choice",
        difficulty=1,
        bloom_level="remember",
        topic_key="english.vocabulary.animals",
        age_group="low",
        options=options,
    )


@register_template("english.vocabulary.colors")
def _gen_colors(params: dict) -> GeneratedQuestion:
    items = [
        ("red", "红色", ["red", "blue", "green", "yellow"]),
        ("blue", "蓝色", ["blue", "red", "white", "black"]),
        ("green", "绿色", ["green", "red", "blue", "orange"]),
    ]
    word, meaning, opts = random.choice(items)
    options = [{"key": chr(65 + i), "text": o} for i, o in enumerate(opts)]
    answer_key = chr(65 + opts.index(word))
    return GeneratedQuestion(
        template_id="english.vocabulary.colors",
        stem=f"Which word means '{meaning}'?",
        stem_zh=f"哪个单词的意思是 '{meaning}'？",
        answer={"key": answer_key},
        question_type="multiple_choice",
        difficulty=1,
        bloom_level="remember",
        topic_key="english.vocabulary.colors",
        age_group="low",
        options=options,
    )
