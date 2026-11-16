#!/usr/bin/env python3
"""Seed the misconception catalog for the fraction-addition pilot topic.

Usage:
    cd server
    uv run python scripts/seed_misconceptions.py

Writes 3 hand-authored misconceptions for fraction addition into
``misconceptions`` with ``review_status='approved'``, plus a linked diagnostic
question per misconception. Idempotent: deletes existing seeded rows for each
topic before re-inserting.
"""
import json
import sys
from pathlib import Path

# Ensure repo root is on sys.path for imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select  # noqa: E402

from packages.db.models.learning.misconception import Misconception  # noqa: E402
from packages.db.models.learning.question import Question  # noqa: E402
from packages.db.models.learning.topic import LearningTopic  # noqa: E402
from packages.db.session import SessionLocal  # noqa: E402

# Misconception data keyed by topic_key for portability across environments.
# Each misconception has:
#   - sequence: order within the topic's list
#   - error_pattern: how to detect it (match_type + expected_wrong/algorithm)
#   - category: concept_confusion | procedural_error | carelessness —
#     drives the Smart Tutor's feedback tone
#   - description / description_zh: child-facing feedback text (common-confusion framing)
#   - diagnostic_question: a regular Question offered after detection
#
# Content guidelines for descriptions:
#   - Target reading level age 10-12
#   - Max ~120 chars zh — fits the feedback card without scrolling
#   - Structure: name the confusion -> normalize it ("many students do this")
#     -> hint at the correct approach
#   - Tone: second person, encouraging, no blame language
SAMPLE_MISCONCEPTIONS: dict[str, list[dict]] = {
    "mt_9KmVWCuh5_": [  # Understanding fractions (age 10+)
        {
            "sequence": 0,
            "category": "concept_confusion",
            "error_pattern": {
                "match_type": "parametric",
                "algorithm": "fraction_add_numerators",
            },
            "description": (
                "Many students add numerators and denominators separately. "
                "Fractions need a common denominator before adding."
            ),
            "description_zh": (
                "很多同学会把分子和分母分别相加，这是一个常见的混淆。"
                "分数相加前需要先通分。"
            ),
            "diagnostic_question": {
                "question_type": "calculation",
                "stem": "What is 1/2 + 1/5?",
                "stem_zh": "1/2 + 1/5 等于多少？",
                "answer": {"answer": "7/10", "fractions": [[1, 2], [1, 5]]},
                "difficulty": 2,
                "bloom_level": "apply",
            },
        },
        {
            "sequence": 1,
            "category": "concept_confusion",
            "error_pattern": {
                "match_type": "parametric",
                "algorithm": "fraction_add_whole_numbers",
            },
            "description": (
                "It looks like you added the numerators as whole numbers. "
                "Fractions name parts of a whole — the denominators matter."
            ),
            "description_zh": (
                "看起来你把分子当作整数直接相加了。分数表示整体的一部分，"
                "分母很重要。"
            ),
            "diagnostic_question": {
                "question_type": "calculation",
                "stem": "What is 2/7 + 3/7?",
                "stem_zh": "2/7 + 3/7 等于多少？",
                "answer": {"answer": "5/7", "fractions": [[2, 7], [3, 7]]},
                "difficulty": 1,
                "bloom_level": "apply",
            },
        },
        {
            "sequence": 2,
            "category": "procedural_error",
            "error_pattern": {
                "match_type": "parametric",
                "algorithm": "fraction_add_product_denominator",
            },
            "description": (
                "The denominators here share a common factor. Instead of multiplying "
                "them, look for the smallest shared denominator first."
            ),
            "description_zh": (
                "这里的两个分母有公因数。不要直接相乘，"
                "先找最小的公共分母会让计算更简单。"
            ),
            "diagnostic_question": {
                "question_type": "calculation",
                "stem": "What is 1/4 + 1/6? (Hint: try 12 as the denominator)",
                "stem_zh": "1/4 + 1/6 等于多少？（提示：试试用 12 作分母）",
                "answer": {"answer": "5/12", "fractions": [[1, 4], [1, 6]]},
                "difficulty": 3,
                "bloom_level": "apply",
            },
        },
    ],
}


def seed_misconceptions() -> None:
    """Delete existing seeded misconceptions for pilot topics and re-insert."""
    db = SessionLocal()
    try:
        for topic_key, misconceptions in SAMPLE_MISCONCEPTIONS.items():
            topic = db.execute(
                select(LearningTopic).where(LearningTopic.topic_key == topic_key).limit(1)
            ).scalar_one_or_none()
            if topic is None:
                print(f"WARNING: topic_key '{topic_key}' not found, skipping")
                continue

            # Delete only misconceptions in the seeded sequence set so
            # hand-curated pending rows outside the seeded set are preserved.
            seeded_sequences = [m["sequence"] for m in misconceptions]
            db.query(Misconception).filter(
                Misconception.topic_id == topic.id,
                Misconception.age_group == "mid",
                Misconception.sequence.in_(seeded_sequences),
            ).delete(synchronize_session=False)

            for m_data in misconceptions:
                # Create or find the diagnostic question.
                diag_data = m_data["diagnostic_question"]
                existing_q = (
                    db.query(Question)
                    .filter(
                        Question.topic_id == topic.id,
                        Question.stem == diag_data["stem"],
                    )
                    .first()
                )
                if existing_q is not None:
                    diagnostic_question_id = existing_q.id
                else:
                    diag_q = Question(
                        topic_id=topic.id,
                        question_type=diag_data["question_type"],
                        stem=diag_data["stem"],
                        stem_zh=diag_data["stem_zh"],
                        answer_json=json.dumps(diag_data["answer"]),
                        difficulty=diag_data["difficulty"],
                        bloom_level=diag_data["bloom_level"],
                        source="seed",
                        age_group="mid",
                        review_status="approved",
                    )
                    db.add(diag_q)
                    db.flush()
                    diagnostic_question_id = diag_q.id

                row = Misconception(
                    topic_id=topic.id,
                    sequence=m_data["sequence"],
                    error_pattern_json=json.dumps(m_data["error_pattern"]),
                    description=m_data["description"],
                    description_zh=m_data["description_zh"],
                    age_group="mid",
                    diagnostic_question_id=diagnostic_question_id,
                    review_status="approved",
                    category=m_data["category"],
                )
                db.add(row)

            db.commit()
            print(
                f"Seeded {len(misconceptions)} misconceptions for topic "
                f"'{topic.name}' ({topic_key})"
            )

        print("\nDone. Total misconceptions:", db.query(Misconception).count())
    finally:
        db.close()


if __name__ == "__main__":
    seed_misconceptions()
