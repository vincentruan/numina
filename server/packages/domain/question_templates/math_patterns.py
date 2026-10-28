"""Math patterns template."""

import random

from packages.domain.question_templates.base import GeneratedQuestion
from packages.domain.question_templates.registry import register_template


@register_template("math.patterns.number_sequence")
def _gen_number_sequence(params: dict) -> GeneratedQuestion:
    """Generate a number sequence where the student finds the next term."""
    pattern_type = random.choice(["arithmetic", "geometric_simple"])
    if pattern_type == "arithmetic":
        start = random.randint(1, 10)
        diff = random.randint(2, 7)
        seq = [start + i * diff for i in range(5)]
        answer = start + 5 * diff
        rule = f"等差数列，公差为{diff}"
    else:
        base = random.randint(2, 3)
        seq = [base ** (i + 1) for i in range(5)]
        answer = base**6
        rule = f"每次乘以{base}"
    seq_str = "、".join(str(n) for n in seq[:4])
    return GeneratedQuestion(
        template_id="math.patterns.number_sequence",
        stem=f"找规律，填下一个数：{seq_str}、?",
        stem_zh=f"找规律：{seq_str}、?",
        answer={"answer": answer},
        question_type="calculation",
        difficulty=3,
        bloom_level="analyze",
        topic_key="mt_WXW0hjNhph",
        age_group="low",
        solution={"steps": [f"规律：{rule}", f"下一个数 = {answer}"]},
    )
