"""Fix NULL subject/age_group on Beijing-specific topics.

Uses upstream os-taxonomy topic data to fill missing fields by
matching domain + topic_key suffix.

Usage:
    cd server
    uv run python -m apps.backend.scripts.fix_beijing_topics [--dry-run]
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from packages.core.logging import get_logger
from packages.db.models.learning.topic import LearningTopic
from packages.db.session import SessionLocal

logger = get_logger(__name__)


def _build_upstream_index(db: Session) -> dict[str, LearningTopic]:
    """Build domain → upstream topic index for subject/age_group lookup."""
    topics = (
        db.query(LearningTopic)
        .filter(
            LearningTopic.source_taxonomy == "upstream",
            LearningTopic.deprecated == False,  # noqa: E712
        )
        .all()
    )
    # Index by domain (most Beijing topics can match by domain)
    index: dict[str, LearningTopic] = {}
    for t in topics:
        if t.domain and t.subject:
            index.setdefault(t.domain, t)
    return index


def fix_beijing_topics(db: Session, dry_run: bool = False) -> dict:
    """Fill NULL subject/age_group on Beijing topics from upstream data.

    Returns dict with fixed/skipped/total counts.
    """
    upstream_index = _build_upstream_index(db)

    beijing_topics = (
        db.query(LearningTopic)
        .filter(
            LearningTopic.source_taxonomy == "beijing",
            LearningTopic.deprecated == False,  # noqa: E712
        )
        .all()
    )

    fixed = 0
    skipped = 0
    no_match = 0

    for topic in beijing_topics:
        if topic.subject and topic.age_group:
            skipped += 1
            continue

        # Try to find matching upstream topic by domain
        upstream = upstream_index.get(topic.domain)
        if upstream is None:
            logger.warning(
                "No upstream match for Beijing topic domain=%s key=%s",
                topic.domain, topic.topic_key,
            )
            no_match += 1
            continue

        if not topic.subject:
            topic.subject = upstream.subject
        if not topic.age_group:
            topic.age_group = upstream.age_group
        fixed += 1

    if not dry_run:
        db.flush()

    logger.info(
        "Beijing topic fix: fixed=%d, skipped=%d, no_match=%d (dry_run=%s)",
        fixed, skipped, no_match, dry_run,
    )
    return {"fixed": fixed, "skipped": skipped, "no_match": no_match, "total": len(beijing_topics)}


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        result = fix_beijing_topics(db, dry_run=args.dry_run)
        print(f"Fix result: {result}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
