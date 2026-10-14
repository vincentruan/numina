#!/usr/bin/env python3
"""CLI entry point for question seeding from templates.

Usage:
    cd server && uv run python -m apps.backend.scripts.seed_questions
    cd server && uv run python -m apps.backend.scripts.seed_questions --count 10
    cd server && uv run python -m apps.backend.scripts.seed_questions --topic math.arithmetic
    cd server && uv run python -m apps.backend.scripts.seed_questions --dry-run
"""

import argparse
import sys

# Ensure template modules are imported so @register_template fires
import packages.domain.question_templates.math_arithmetic  # noqa: F401
from apps.backend.app.services.learning.question_seeder import (
    seed_questions_from_templates,
)
from packages.core.logging import get_logger
from packages.db.session import SessionLocal

logger = get_logger(__name__)


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed questions from templates")
    parser.add_argument(
        "--count",
        type=int,
        default=10,
        help="Number of variants per template (default: 10)",
    )
    parser.add_argument(
        "--topic",
        type=str,
        default=None,
        help="Filter templates by substring (e.g. 'math.arithmetic.addition')",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Generate but don't persist questions",
    )
    args = parser.parse_args()

    db = SessionLocal()
    try:
        result = seed_questions_from_templates(
            db,
            count_per_template=args.count,
            topic_filter=args.topic,
            dry_run=args.dry_run,
        )
        if args.dry_run:
            db.rollback()
        else:
            db.commit()

        print("Seed complete:")
        print(f"  Generated:        {result.generated}")
        print(f"  Skipped (dup):    {result.skipped_duplicate}")
        print(f"  Skipped (topic):  {result.skipped_no_topic}")
        print(f"  Failed:           {result.failed}")
        return 0 if result.failed == 0 else 1
    except Exception:
        logger.exception("Seed failed")
        db.rollback()
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
