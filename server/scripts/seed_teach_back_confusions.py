#!/usr/bin/env python3
"""Seed preset confusion lists for teach-back topics.

Usage:
    cd server
    uv run python scripts/seed_teach_back_confusions.py

Writes 2-3 hand-authored confusions per topic into ``topic_confusions``
with ``review_status='approved'``. Idempotent: deletes existing rows for each
topic before re-inserting.

Topics (6 math, age_group='mid', chosen by centrality):
  Pilot (3 fractions):
  - mt_9KmVWCuh5_  Understanding fractions (age 10+)
  - mt_ndGqFPWyen  Fractions of a whole
  - mt_FP-mjXaq3B  Equivalent fractions (age 8+)
  Expansion (decimals, percentages, fraction multiplication):
  - mt_Fl7b8q9pI1  Decimal place value (age 8-10)
  - mt_ZM9mhHsyYZ  Understanding Percentages (age 9-11)
  - mt_TgHxujL81r  Multiplying fractions (age 9-11)
"""

import sys
from pathlib import Path

# Ensure repo root is on sys.path for imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select  # noqa: E402

from packages.db.models.learning.confusion import TopicConfusion  # noqa: E402
from packages.db.models.learning.topic import LearningTopic  # noqa: E402
from packages.db.session import SessionLocal  # noqa: E402

# Confusion data keyed by topic_key for portability across environments.
# Each confusion has:
#   - confusion_text: what the AI student "doesn't understand" (English)
#   - confusion_text_zh: Chinese translation
#   - rubric: instructions for LLM to judge if the child's explanation hits
#   - expected_expression: math expression for SymPy comparison (nullable)
SAMPLE_CONFUSIONS: dict[str, list[dict]] = {
    "mt_9KmVWCuh5_": [  # Understanding fractions (age 10+)
        {
            "sequence": 0,
            "confusion_text": "Why can't I just add the denominators when adding fractions? Like, 1/4 + 2/4 = 3/8?",
            "confusion_text_zh": "为什么分数相加时不能直接把分母加起来？比如 1/4 + 2/4 = 3/8？",
            "rubric": "The child should explain that the denominator tells us how many equal parts the whole is divided into. When adding, we're combining parts of the SAME whole, so the denominator stays the same. Only the numerators (how many parts we have) get added.",
            "expected_expression": "1/4 + 2/4 = 3/4",
        },
        {
            "sequence": 1,
            "confusion_text": "Is 2/3 bigger than 3/4? I think 2/3 is bigger because 2 is close to 3.",
            "confusion_text_zh": "2/3 比 3/4 大吗？我觉得 2/3 更大，因为 2 很接近 3。",
            "rubric": "The child should explain that you can't compare fractions just by looking at how close numerator and denominator are. You need a common denominator (like 12) or convert to decimals. 2/3 = 8/12 and 3/4 = 9/12, so 3/4 is bigger.",
            "expected_expression": None,
        },
        {
            "sequence": 2,
            "confusion_text": "What does it mean to 'simplify' a fraction? Can't I just leave 4/8 as it is?",
            "confusion_text_zh": "'化简'分数是什么意思？我不能直接把 4/8 留在那吗？",
            "rubric": "The child should explain that simplifying means finding an equivalent fraction with the smallest possible numbers. You divide both numerator and denominator by their greatest common factor. 4/8 = 1/2 because both 4 and 8 are divisible by 4.",
            "expected_expression": "1/2",
        },
    ],
    "mt_ndGqFPWyen": [  # Fractions of a whole
        {
            "sequence": 0,
            "confusion_text": "If I have a pizza cut into 6 slices and I eat 2 slices, is that 2/6 or 2/4 of the pizza?",
            "confusion_text_zh": "如果一个披萨切成 6 块，我吃了 2 块，那是 2/6 还是 2/4？",
            "rubric": "The child should explain that the denominator is the TOTAL number of equal parts (6 slices total), and the numerator is how many parts you're talking about (2 slices eaten). So it's 2/6, not 2/4. The denominator doesn't change based on what you do — it's fixed by how the whole was divided.",
            "expected_expression": "2/6",
        },
        {
            "sequence": 1,
            "confusion_text": "Can a fraction be bigger than 1? Like 5/4?",
            "confusion_text_zh": "分数能大于 1 吗？比如 5/4？",
            "rubric": "The child should explain that yes, fractions can be bigger than 1 — these are called improper fractions. 5/4 means you have 5 parts when each whole is divided into 4 parts. It's more than one whole. 5/4 = 1 and 1/4.",
            "expected_expression": None,
        },
    ],
    "mt_FP-mjXaq3B": [  # Equivalent fractions (age 8+)
        {
            "sequence": 0,
            "confusion_text": "Are 1/2 and 2/4 really the same? They look different!",
            "confusion_text_zh": "1/2 和 2/4 真的相等吗？它们看起来不一样啊！",
            "rubric": "The child should explain that equivalent fractions represent the same amount, just divided differently. If you multiply or divide both the numerator and denominator by the same number, you get an equivalent fraction. 1/2 × 2/2 = 2/4. Or visually: half a pizza is the same as 2 quarters of a pizza.",
            "expected_expression": "2/4",
        },
        {
            "sequence": 1,
            "confusion_text": "How do I know if two fractions are equivalent without drawing pictures?",
            "confusion_text_zh": "不画图的话，我怎么知道两个分数是否相等？",
            "rubric": "The child should explain the cross-multiplication test: a/b = c/d if and only if a×d = b×c. For example, 2/3 and 4/6: 2×6 = 12 and 3×4 = 12, so they're equivalent. Or simplify both to lowest terms and compare.",
            "expected_expression": None,
        },
        {
            "sequence": 2,
            "confusion_text": "Why do we need equivalent fractions? Can't I just work with the fractions as they are?",
            "confusion_text_zh": "我们为什么需要等值分数？我不能直接用原来的分数吗？",
            "rubric": "The child should explain that equivalent fractions are essential for adding/subtracting fractions with different denominators. You need to convert them to have a common denominator first. For example, 1/2 + 1/3 requires converting to 3/6 + 2/6.",
            "expected_expression": "1/2 + 1/3 = 5/6",
        },
    ],
    # --- Expansion topics (issue #234) ---
    "mt_Fl7b8q9pI1": [  # Decimal place value (age 8-10)
        {
            "sequence": 0,
            "confusion_text": "Is 0.5 bigger than 0.25 because 5 is bigger than 25?",
            "confusion_text_zh": "0.5 比 0.25 大吗？因为 5 比 25 大？",
            "rubric": "The child should explain that decimal place value matters. 0.5 means 5 tenths (5/10), while 0.25 means 2 tenths and 5 hundredths (25/100). Since 5/10 = 50/100, we can see that 0.5 = 0.50 which is bigger than 0.25. You can't just compare the digits after the decimal point as whole numbers.",
            "expected_expression": "0.5",
        },
        {
            "sequence": 1,
            "confusion_text": "What does the 3 in 1.32 actually mean?",
            "confusion_text_zh": "1.32 里的 3 到底表示什么？",
            "rubric": "The child should explain place value: in 1.32, the 1 is ones, the 3 is in the tenths place (meaning 3/10 or 0.3), and the 2 is in the hundredths place (meaning 2/100 or 0.02). So 1.32 = 1 + 3/10 + 2/100.",
            "expected_expression": None,
        },
        {
            "sequence": 2,
            "confusion_text": "Are 0.5 and 0.50 different numbers? One looks shorter.",
            "confusion_text_zh": "0.5 和 0.50 是不同的数吗？一个看起来更短。",
            "rubric": "The child should explain that trailing zeros after the decimal point don't change the value. 0.5 = 5/10 and 0.50 = 50/100 = 5/10. They are exactly the same number, just written differently. This is like how 1/2 and 2/4 are equivalent fractions.",
            "expected_expression": "0.50",
        },
    ],
    "mt_ZM9mhHsyYZ": [  # Understanding Percentages (age 9-11)
        {
            "sequence": 0,
            "confusion_text": "Is 50% the same as the number 50?",
            "confusion_text_zh": "50% 和数字 50 是一样的吗？",
            "rubric": "The child should explain that percent means 'per hundred'. 50% means 50 out of 100, which equals 50/100 = 1/2 = 0.5. It is NOT the same as the whole number 50. Percent is a ratio or fraction, not a standalone number.",
            "expected_expression": "50/100",
        },
        {
            "sequence": 1,
            "confusion_text": "If I scored 80% on a test, does that mean I got 80 questions right?",
            "confusion_text_zh": "如果我考试得了 80 分，是不是意味着我做对了 80 道题？",
            "rubric": "The child should explain that percent is relative to the total. 80% means 80 out of every 100. If the test had 50 questions, 80% means 80/100 × 50 = 40 questions right. You need to know the total to find the actual number.",
            "expected_expression": None,
        },
        {
            "sequence": 2,
            "confusion_text": "Can a percentage be more than 100%? Like 150%?",
            "confusion_text_zh": "百分比能超过 100% 吗？比如 150%？",
            "rubric": "The child should explain that yes, percentages can exceed 100%. 100% means the whole amount, so 150% means 150/100 = 1.5 times the whole. For example, if you had 10 cookies and got 5 more, you now have 150% of your original amount.",
            "expected_expression": "150/100",
        },
    ],
    "mt_TgHxujL81r": [  # Multiplying fractions (age 9-11)
        {
            "sequence": 0,
            "confusion_text": "Why do we just multiply straight across when multiplying fractions? Like 1/2 × 1/3 = 1/6?",
            "confusion_text_zh": "为什么分数乘法直接分子乘分子、分母乘分母？比如 1/2 × 1/3 = 1/6？",
            "rubric": "The child should explain that multiplying fractions means finding a part of a part. 1/2 × 1/3 means 'half of one-third'. If you take 1/3 and split it in half, you get 1/6. The rule (a/b × c/d = ac/bd) works because you're scaling both the parts and the whole.",
            "expected_expression": "1/6",
        },
        {
            "sequence": 1,
            "confusion_text": "Is multiplying fractions the same as adding them? Like, is 1/2 × 1/3 the same as 1/2 + 1/3?",
            "confusion_text_zh": "分数乘法和分数加法一样吗？比如 1/2 × 1/3 和 1/2 + 1/3 一样吗？",
            "rubric": "The child should explain that multiplication and addition are different operations. 1/2 × 1/3 = 1/6 (finding a part of a part), while 1/2 + 1/3 = 3/6 + 2/6 = 5/6 (combining amounts). Multiplication of fractions usually makes the result smaller; addition makes it bigger.",
            "expected_expression": "1/2 + 1/3 = 5/6",
        },
        {
            "sequence": 2,
            "confusion_text": "Does multiplying fractions always give a smaller answer?",
            "confusion_text_zh": "分数乘法的結果总是更小吗？",
            "rubric": "The child should explain that multiplying proper fractions (less than 1) always gives a smaller result — you're taking a part of a part. But multiplying by an improper fraction (greater than 1) can give a bigger result. For example, 2/3 × 3/2 = 1, and 2/3 × 5/4 = 10/12 which is bigger than 2/3.",
            # The rubric's worked example, not the starting fraction: a child writing
            # "2/3 × 5/4 = 10/12" extracts the full equation and grades against 10/12.
            "expected_expression": "10/12",
        },
    ],
}


def seed_confusions() -> None:
    """Delete existing approved confusions for pilot topics and re-insert."""
    db = SessionLocal()
    try:
        for topic_key, confusions in SAMPLE_CONFUSIONS.items():
            # Resolve topic_id from topic_key (may have duplicate rows per locale — take first)
            topic = db.execute(
                select(LearningTopic).where(LearningTopic.topic_key == topic_key).limit(1)
            ).scalar_one_or_none()
            if topic is None:
                print(f"WARNING: topic_key '{topic_key}' not found, skipping")
                continue

            # Delete only confusions in the seeded sequence set so hand-curated
            # pending/rejected rows outside the seeded set are preserved (#15 review fix).
            seeded_sequences = [c["sequence"] for c in confusions]
            db.query(TopicConfusion).filter(
                TopicConfusion.topic_id == topic.id,
                TopicConfusion.age_group == "mid",
                TopicConfusion.sequence.in_(seeded_sequences),
            ).delete(synchronize_session=False)

            # Insert new confusions with review_status='approved'
            for c in confusions:
                row = TopicConfusion(
                    topic_id=topic.id,
                    sequence=c["sequence"],
                    confusion_text=c["confusion_text"],
                    confusion_text_zh=c.get("confusion_text_zh"),
                    age_group="mid",
                    rubric=c["rubric"],
                    expected_expression=c.get("expected_expression"),
                    review_status="approved",
                )
                db.add(row)

            db.commit()
            print(f"Seeded {len(confusions)} confusions for topic '{topic.name}' ({topic_key})")

        print("\nDone. Total confusions seeded:", db.query(TopicConfusion).count())
    finally:
        db.close()


if __name__ == "__main__":
    seed_confusions()
