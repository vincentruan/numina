"""Life science pilot templates."""
import random

from packages.domain.question_templates.base import GeneratedQuestion
from packages.domain.question_templates.registry import register_template


@register_template("science.life.plant_parts")
def _gen_plant_parts(params: dict) -> GeneratedQuestion:
    items = [
        ("从土壤中吸收水分和养料的是？", "根", ["根", "茎", "叶", "花"]),
        ("进行光合作用的主要器官是？", "叶", ["叶", "根", "茎", "果实"]),
        ("运输水分和养料的是？", "茎", ["茎", "根", "叶", "花"]),
    ]
    question, correct, opts = random.choice(items)
    options = [{"key": chr(65+i), "text": o, "text_zh": o} for i, o in enumerate(opts)]
    answer_key = chr(65 + opts.index(correct))
    return GeneratedQuestion(
        template_id="science.life.plant_parts",
        stem=question,
        stem_zh=question,
        answer={"key": answer_key},
        question_type="multiple_choice",
        difficulty=1,
        bloom_level="remember",
        topic_key="science.life.plant_parts",
        age_group="lower",
        options=options,
    )


@register_template("science.life.animal_types")
def _gen_animal_types(params: dict) -> GeneratedQuestion:
    items = [
        ("鲸鱼属于哪类动物？", "哺乳动物", ["哺乳动物", "鱼类", "鸟类", "爬行动物"]),
        ("蝴蝶属于哪类动物？", "昆虫", ["昆虫", "鸟类", "鱼类", "哺乳动物"]),
        ("金鱼属于哪类动物？", "鱼类", ["鱼类", "哺乳动物", "两栖动物", "昆虫"]),
    ]
    question, correct, opts = random.choice(items)
    options = [{"key": chr(65+i), "text": o, "text_zh": o} for i, o in enumerate(opts)]
    answer_key = chr(65 + opts.index(correct))
    return GeneratedQuestion(
        template_id="science.life.animal_types",
        stem=question,
        stem_zh=question,
        answer={"key": answer_key},
        question_type="multiple_choice",
        difficulty=1,
        bloom_level="remember",
        topic_key="science.life.animal_types",
        age_group="lower",
        options=options,
    )
