"""Backfill content_hash on existing questions.

Usage:
    cd server
    uv run python -m apps.backend.scripts.backfill_content_hash
"""
from __future__ import annotations

import json

from sqlalchemy.orm import Session

from packages.core.logging import get_logger
from packages.db.models.learning.question import Question
from packages.db.session import SessionLocal
from apps.backend.app.services.learning.question_seeder import _compute_content_hash

logger = get_logger(__name__)


def backfill(db: Session, batch_size: int = 100) -> dict:
    """Fill content_hash for questions that don't have one.

    Returns dict with backfilled/skipped counts.
    Fixed-offset loop: the content_hash IS NULL filter shrinks as rows
    are flushed, so we re-query from offset 0 until a batch returns empty.
    """
    backfilled = 0
    skipped = (
        db.query(Question)
        .filter(Question.content_hash.isnot(None))
        .count()
    )

    while True:
        questions = (
            db.query(Question)
            .filter(Question.content_hash.is_(None))
            .limit(batch_size)
            .offset(0)
            .all()
        )
        if not questions:
            break

        for q in questions:
            answer = json.loads(q.answer_json)
            q.content_hash = _compute_content_hash(q.stem, answer)
            backfilled += 1

        db.flush()

    logger.info("content_hash backfill: backfilled=%d, skipped=%d", backfilled, skipped)
    return {"backfilled": backfilled, "skipped": skipped}


def main() -> None:
    db = SessionLocal()
    try:
        result = backfill(db)
        print(f"Backfill complete: {result}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
