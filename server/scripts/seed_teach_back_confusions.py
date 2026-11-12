#!/usr/bin/env python3
"""Seed preset confusion lists for the teach-back pilot topics.

Usage:
    cd server
    uv run python scripts/seed_teach_back_confusions.py

Writes 2-4 hand-authored confusions per pilot topic into ``topic_confusions``
with ``review_status='approved'``. Idempotent: deletes existing rows for each
topic before re-inserting.

Pilot topics (3 math, age_group='mid', chosen by centrality):
  - mt_9KmVWCuh5_  Understanding fractions (age 10+)
  - mt_ndGqFPWyen  Fractions of a whole
  - mt_FP-mjXaq3B  Equivalent fractions (age 8+)
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
            "expected_expression": "4/8 = 1/2",
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
            "expected_expression": "5/4 > 1",
        },
    ],
    "mt_FP-mjXaq3B": [  # Equivalent fractions (age 8+)
        {
            "sequence": 0,
            "confusion_text": "Are 1/2 and 2/4 really the same? They look different!",
            "confusion_text_zh": "1/2 和 2/4 真的相等吗？它们看起来不一样啊！",
            "rubric": "The child should explain that equivalent fractions represent the same amount, just divided differently. If you multiply or divide both the numerator and denominator by the same number, you get an equivalent fraction. 1/2 × 2/2 = 2/4. Or visually: half a pizza is the same as 2 quarters of a pizza.",
            "expected_expression": "1/2 = 2/4",
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
            "expected_expression": "1/2 + 1/3 = 3/6 + 2/6 = 5/6",
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

            # Delete existing confusions for this topic (idempotent)
            db.query(TopicConfusion).filter(
                TopicConfusion.topic_id == topic.id
            ).delete()

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
