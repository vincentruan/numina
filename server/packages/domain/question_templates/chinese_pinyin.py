"""Chinese pinyin pilot templates."""
import random

from packages.domain.question_templates.base import GeneratedQuestion
from packages.domain.question_templates.registry import register_template


@register_template("chinese.pinyin.initials")
def _gen_pinyin_initials(params: dict) -> GeneratedQuestion:
    questions = [
        ("b", "玻", ["b", "p", "d", "q"]),
        ("p", "坡", ["b", "p", "d", "q"]),
        ("m", "摸", ["m", "n", "l", "f"]),
        ("f", "佛", ["f", "h", "b", "p"]),
    ]
    correct_key, char, options_chars = random.choice(questions)
    options = [
        {"key": "A", "text": options_chars[0], "text_zh": options_chars[0]},
        {"key": "B", "text": options_chars[1], "text_zh": options_chars[1]},
        {"key": "C", "text": options_chars[2], "text_zh": options_chars[2]},
        {"key": "D", "text": options_chars[3], "text_zh": options_chars[3]},
    ]
    correct_idx = options_chars.index(correct_key)
    answer_key = ["A", "B", "C", "D"][correct_idx]
    return GeneratedQuestion(
        template_id="chinese.pinyin.initials",
        stem=f"声母 '{correct_key}' 对应的汉字是？",
        stem_zh=f"声母 '{correct_key}' 对应的汉字是？",
        answer={"key": answer_key},
        question_type="multiple_choice",
        difficulty=1,
        bloom_level="remember",
        topic_key="chinese.pinyin.initials",
        age_group="early",
        options=options,
    )


@register_template("chinese.pinyin.finals")
def _gen_pinyin_finals(params: dict) -> GeneratedQuestion:
    questions = [
        ("ā", "第一声"), ("á", "第二声"), ("ǎ", "第三声"), ("à", "第四声"),
    ]
    tone_char, tone_name = random.choice(questions)
    tone_options = ["第一声", "第二声", "第三声", "第四声"]
    options = [{"key": chr(65+i), "text": t, "text_zh": t} for i, t in enumerate(tone_options)]
    correct_idx = tone_options.index(tone_name)
    answer_key = chr(65 + correct_idx)
    return GeneratedQuestion(
        template_id="chinese.pinyin.finals",
        stem=f"'{tone_char}' 是第几声？",
        stem_zh=f"'{tone_char}' 是第几声？",
        answer={"key": answer_key},
        question_type="multiple_choice",
        difficulty=1,
        bloom_level="remember",
        topic_key="chinese.pinyin.finals",
        age_group="early",
        options=options,
    )


@register_template("chinese.pinyin.spelling")
def _gen_pinyin_spelling(params: dict) -> GeneratedQuestion:
    chars = [("大", "dà"), ("天", "tiān"), ("水", "shuǐ")]
    char, pinyin = random.choice(chars)
    return GeneratedQuestion(
        template_id="chinese.pinyin.spelling",
        stem=f"汉字 '{char}' 的拼音是？",
        stem_zh=f"汉字 '{char}' 的拼音是？",
        answer={"value": pinyin},
        question_type="fill_blank",
        difficulty=1,
        bloom_level="remember",
        topic_key="chinese.pinyin.spelling",
        age_group="early",
    )
