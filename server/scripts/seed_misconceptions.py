#!/usr/bin/env python3
"""Seed the misconception catalog for the fraction-addition pilot topic.

Usage:
    cd server
    uv run python scripts/seed_misconceptions.py

Writes hand-authored misconceptions into ``misconceptions`` with
``review_status='approved'``, plus a linked diagnostic question per
misconception: three calculation (parametric), two fill_blank (text_match) and
two multiple_choice (option_select). Idempotent: misconceptions are upserted by
(topic_id, age_group, sequence) and diagnostic questions by stem.

Diagnostic question payloads must match the grading contract in
``apps/backend/app/services/learning/scoring_service.py`` — ``{"value": ...}``
for fill_blank and ``{"key": ...}`` for multiple_choice. Seeded rows using any
other shape grade as wrong for every child.
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
        # --- fill_blank misconceptions (sequence 3-4) ---
        # expected_wrong lists both languages: the stems are bilingual, so the
        # child may answer in either. See scoring_service: fill_blank reads "value".
        {
            "sequence": 3,
            "category": "concept_confusion",
            "error_pattern": {
                "match_type": "text_match",
                "expected_wrong": ["denominator", "分母"],
                "normalize": True,
            },
            "description": (
                "You mixed up numerator and denominator. The numerator is the top "
                "number (how many parts), the denominator is the bottom (how many "
                "equal parts the whole is split into)."
            ),
            "description_zh": (
                "你把分子和分母搞混了。分子是上面的数（表示几份），"
                "分母是下面的数（表示平均分成几份）。"
            ),
            "diagnostic_question": {
                "question_type": "fill_blank",
                "stem": "In the fraction 3/4, the number 3 is called the ___",
                "stem_zh": "在分数 3/4 中，上面的 3 叫做___",
                "answer": {"value": "numerator"},
                "difficulty": 1,
                "bloom_level": "remember",
            },
        },
        {
            "sequence": 4,
            "category": "concept_confusion",
            "error_pattern": {
                "match_type": "text_match",
                "expected_wrong": ["numerator", "分子"],
                "normalize": True,
            },
            "description": (
                "You mixed up numerator and denominator. The denominator is the "
                "bottom number — it tells you how many equal parts the whole is "
                "divided into."
            ),
            "description_zh": (
                "你把分子和分母搞混了。分母是下面的数，"
                "表示把一个整体平均分成多少份。"
            ),
            "diagnostic_question": {
                "question_type": "fill_blank",
                "stem": "In the fraction 2/5, the number 5 is called the ___",
                "stem_zh": "在分数 2/5 中，下面的 5 叫做___",
                "answer": {"value": "denominator"},
                "difficulty": 1,
                "bloom_level": "remember",
            },
        },
        # --- multiple_choice misconceptions (sequence 5-6) ---
        # wrong_options are option keys on the linked diagnostic question below.
        # See scoring_service: multiple_choice reads "key".
        {
            "sequence": 5,
            "category": "concept_confusion",
            "error_pattern": {
                "match_type": "option_select",
                "wrong_options": ["A"],
            },
            "description": (
                "It looks like you added the numerators and denominators directly. "
                "Remember: find a common denominator first, then add only the "
                "numerators."
            ),
            "description_zh": (
                "看起来你直接把分子和分母相加了。记住：先通分，"
                "然后只加分子。"
            ),
            "diagnostic_question": {
                "question_type": "multiple_choice",
                "stem": "What is 1/3 + 1/6?",
                "stem_zh": "1/3 + 1/6 等于多少？",
                "options": [
                    {"key": "A", "text": "2/9"},
                    {"key": "B", "text": "1/2"},
                    {"key": "C", "text": "2/6"},
                    {"key": "D", "text": "1/9"},
                ],
                "answer": {"key": "B"},
                "difficulty": 2,
                "bloom_level": "apply",
            },
        },
        {
            "sequence": 6,
            "category": "procedural_error",
            "error_pattern": {
                "match_type": "option_select",
                "wrong_options": ["B"],
            },
            "description": (
                "You used the product of the denominators instead of the lowest "
                "common denominator. The answer may look right but isn't simplified."
            ),
            "description_zh": (
                "你用了分母的乘积而不是最小公分母。答案看起来对，"
                "但没有化简。"
            ),
            "diagnostic_question": {
                "question_type": "multiple_choice",
                "stem": "What is 1/4 + 1/6?",
                "stem_zh": "1/4 + 1/6 等于多少？",
                "options": [
                    {"key": "A", "text": "2/10"},
                    {"key": "B", "text": "10/24"},
                    {"key": "C", "text": "5/12"},
                    {"key": "D", "text": "1/3"},
                ],
                "answer": {"key": "C"},
                "difficulty": 3,
                "bloom_level": "apply",
            },
        },
    ],
}


def _sync_diagnostic_question(q: Question, diag_data: dict) -> None:
    """Write the seed data's gradable fields onto a diagnostic question row.

    Used both on insert and when the row already exists. Re-runs of the seed
    script must overwrite ``answer_json``/``options_json`` too — otherwise a
    corrected seed row never reaches an already-seeded question and the child
    keeps grading against the stale payload.

    ``source`` is deliberately not overwritten on an existing row: the seed
    only owns rows it created, and the stem-dedup lookup could otherwise
    re-label an unrelated question as seed-owned.
    """
    q.question_type = diag_data["question_type"]
    q.stem = diag_data["stem"]
    q.stem_zh = diag_data["stem_zh"]
    q.answer_json = json.dumps(diag_data["answer"])
    # options_json is required for multiple_choice: without it the child sees a
    # question with no choices. Other types carry no options.
    options = diag_data.get("options")
    q.options_json = json.dumps(options) if options is not None else None
    q.difficulty = diag_data["difficulty"]
    q.bloom_level = diag_data["bloom_level"]
    q.age_group = "mid"
    q.review_status = "approved"


def seed_misconceptions() -> None:
    """Upsert hand-authored misconceptions for pilot topics.

    For each (topic_id, age_group, sequence) tuple: UPDATE fields if the row
    already exists, INSERT otherwise. Diagnostic questions are deduplicated
    by stem as before.
    """
    db = SessionLocal()
    try:
        for topic_key, misconceptions in SAMPLE_MISCONCEPTIONS.items():
            topic = db.execute(
                select(LearningTopic).where(LearningTopic.topic_key == topic_key).limit(1)
            ).scalar_one_or_none()
            if topic is None:
                print(f"WARNING: topic_key '{topic_key}' not found, skipping")
                continue

            for m_data in misconceptions:
                # Create or find the diagnostic question (dedup by stem).
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
                    _sync_diagnostic_question(existing_q, diag_data)
                    diagnostic_question_id = existing_q.id
                else:
                    diag_q = Question(
                        topic_id=topic.id, stem=diag_data["stem"], source="seed"
                    )
                    _sync_diagnostic_question(diag_q, diag_data)
                    db.add(diag_q)
                    db.flush()
                    diagnostic_question_id = diag_q.id

                # Upsert misconception by (topic_id, age_group, sequence).
                existing = (
                    db.query(Misconception)
                    .filter(
                        Misconception.topic_id == topic.id,
                        Misconception.age_group == "mid",
                        Misconception.sequence == m_data["sequence"],
                    )
                    .first()
                )
                if existing is not None:
                    existing.error_pattern_json = json.dumps(m_data["error_pattern"])
                    existing.description = m_data["description"]
                    existing.description_zh = m_data["description_zh"]
                    existing.diagnostic_question_id = diagnostic_question_id
                    existing.review_status = "approved"
                    existing.category = m_data["category"]
                else:
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
