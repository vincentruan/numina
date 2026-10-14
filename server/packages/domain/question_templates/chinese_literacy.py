"""Chinese literacy pilot templates."""
import random

from packages.domain.question_templates.base import GeneratedQuestion
from packages.domain.question_templates.registry import register_template


@register_template("chinese.literacy.radicals")
def _gen_radicals(params: dict) -> GeneratedQuestion:
    items = [
        ("河", "氵", ["氵", "木", "口", "日"]),
        ("树", "木", ["木", "氵", "土", "火"]),
        ("花", "艹", ["艹", "亻", "扌", "口"]),
    ]
    char, correct, opts = random.choice(items)
    options = [{"key": chr(65+i), "text": o, "text_zh": o} for i, o in enumerate(opts)]
    answer_key = chr(65 + opts.index(correct))
    return GeneratedQuestion(
        template_id="chinese.literacy.radicals",
        stem=f"汉字 '{char}' 的部首是什么？",
        stem_zh=f"'{char}' 的部首是？",
        answer={"key": answer_key},
        question_type="multiple_choice",
        difficulty=1,
        bloom_level="remember",
        topic_key="chinese.literacy.radicals",
        age_group="early",
        options=options,
    )


@register_template("chinese.literacy.stroke_count")
def _gen_stroke_count(params: dict) -> GeneratedQuestion:
    items = [("大", 3), ("人", 2), ("口", 3), ("手", 4), ("天", 4)]
    char, count = random.choice(items)
    return GeneratedQuestion(
        template_id="chinese.literacy.stroke_count",
        stem=f"汉字 '{char}' 有几画？",
        stem_zh=f"'{char}' 的笔画数",
        answer={"answer": count},
        question_type="calculation",
        difficulty=1,
        bloom_level="remember",
        topic_key="chinese.literacy.stroke_count",
        age_group="early",
    )
