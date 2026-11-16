"""Seed sample hook questions for development / testing.

Usage:
    cd server
    uv run python scripts/seed_hook_questions.py

Creates a small set of hook questions across age groups for a handful of
well-known topics so the feature can be exercised before the full 1590-topic
LLM-assisted generation run.  Production data is meant to be LLM-generated and
human-reviewed; this script only seeds exemplars for the topics named in
issue #200.

Each topic gets up to three age-layered variants:

* ``low``  — ages 5-7  (concrete, sensory, playful)
* ``mid``  — ages 8-10 (concrete reasoning, a small step of inference)
* ``high`` — ages 11+  (abstract framing, "why does this work")
"""

import sys
from pathlib import Path

# Ensure the workspace root is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from packages.db.models.learning.hook import TopicHookQuestion
from packages.db.models.learning.topic import LearningTopic
from packages.db.session import SessionLocal

# Sample hook questions — keyed by topic_key for portability across environments.
SAMPLE_HOOKS: dict[str, list[dict]] = {
    # "Adding Fractions (Same Denominator)" — ages 8-9
    "mt_CBHwluE6Lp": [
        {
            "question_text": "Why can't you just add pieces from a cake cut into 3 and a cake cut into 4?",
            "question_text_zh": "为什么切成 3 块的蛋糕和切成 4 块的蛋糕，不能直接把块数加起来？",
            "age_group": "low",
            "difficulty": "easy",
        },
        {
            "question_text": "If you eat 2/5 of a chocolate bar and your friend eats 1/5, how much is gone?",
            "question_text_zh": "你吃了巧克力的 2/5，朋友吃了 1/5，一共吃了多少？",
            "age_group": "mid",
            "difficulty": "easy",
        },
        {
            "question_text": "Why does adding fractions with the same denominator work by only adding the top numbers?",
            "question_text_zh": "为什么分母相同时，分数相加只需要把分子加起来？",
            "age_group": "high",
            "difficulty": "medium",
        },
    ],
    # "Understanding Area" — ages 8-9
    "mt_6xNmQLzuqm": [
        {
            "question_text": "How big is your room? What if you measured it by lying down on the floor?",
            "question_text_zh": "你的房间有多大？如果用你身体躺下来量呢，要躺几次？",
            "age_group": "low",
            "difficulty": "easy",
        },
        {
            "question_text": "Why does multiplying length by width tell you how many squares fit inside a rectangle?",
            "question_text_zh": "为什么长乘宽就能算出长方形里能放下多少个正方形？",
            "age_group": "mid",
            "difficulty": "medium",
        },
        {
            "question_text": "Two shapes can have the same perimeter but different areas — how is that possible?",
            "question_text_zh": "两个形状的周长一样，面积却可以不同，这是怎么回事？",
            "age_group": "high",
            "difficulty": "hard",
        },
    ],
    # "Prime numbers" — ages 9-10
    "mt_y1XCVsIelg": [
        {
            "question_text": "Is there a number you simply cannot split into two equal piles?",
            "question_text_zh": "有没有一个数，怎么也拆不成两堆一样多的？",
            "age_group": "low",
            "difficulty": "easy",
        },
        {
            "question_text": "Which numbers can only be made by multiplying 1 by themselves?",
            "question_text_zh": "哪些数只能用它自己乘以 1 得到？",
            "age_group": "mid",
            "difficulty": "medium",
        },
        {
            "question_text": "Why are primes called the 'building blocks' of all whole numbers?",
            "question_text_zh": "为什么质数被称为所有整数的「积木」？",
            "age_group": "high",
            "difficulty": "medium",
        },
    ],
}


def seed() -> None:
    db = SessionLocal()
    try:
        created = 0
        skipped = 0
        for topic_key, hooks in SAMPLE_HOOKS.items():
            topic = (
                db.query(LearningTopic)
                .filter(LearningTopic.topic_key == topic_key)
                .first()
            )
            if not topic:
                print(f"  ! topic_key={topic_key} not found — skipping")
                skipped += len(hooks)
                continue

            for hook in hooks:
                existing = (
                    db.query(TopicHookQuestion)
                    .filter(
                        TopicHookQuestion.topic_id == topic.id,
                        TopicHookQuestion.age_group == hook["age_group"],
                    )
                    .first()
                )
                if existing:
                    print(f"  - {topic_key}/{hook['age_group']} already exists")
                    continue
                # These exemplars are hand-authored, so they ship as approved.
                db.add(
                    TopicHookQuestion(
                        topic_id=topic.id, review_status="approved", **hook
                    )
                )
                created += 1
                print(f"  + {topic_key}/{hook['age_group']}")

        db.commit()
        print(f"\nDone — {created} created, {skipped} skipped (missing topic).")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
