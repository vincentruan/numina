#!/usr/bin/env python3
"""Spot-check translation quality for high-centrality topics.

Run from the server/ directory:
    cd server
    uv run python ../.claude/skills/learning-content-translate/scripts/qa-check-translations.py

Shows 30 high-centrality translated topics for manual quality review.
"""
import sys
from pathlib import Path

# Ensure we can import from the server packages
server_root = Path(__file__).resolve().parent.parent.parent.parent.parent / "server"
if str(server_root) not in sys.path:
    sys.path.insert(0, str(server_root))

from packages.db.session import SessionLocal
from packages.db.models.learning.topic import LearningTopic


def check_quality(limit: int = 30, min_centrality: float = 0.5) -> None:
    """Print high-centrality translated topics for manual review."""
    db = SessionLocal()

    try:
        topics = db.query(LearningTopic).filter(
            LearningTopic.name_zh.isnot(None),
            LearningTopic.centrality > min_centrality,
        ).order_by(LearningTopic.centrality.desc()).limit(limit).all()

        print(f"{'Subject':15s} | {'English':40s} | {'Chinese'}")
        print("-" * 100)
        for t in topics:
            print(f"{t.subject:15s} | {t.name:40s} | {t.name_zh}")

        # Coverage stats
        total = db.query(LearningTopic).filter(LearningTopic.deprecated == False).count()
        translated = db.query(LearningTopic).filter(
            LearningTopic.name_zh.isnot(None),
            LearningTopic.deprecated == False,
        ).count()
        high_value_untranslated = db.query(LearningTopic).filter(
            LearningTopic.name_zh.is_(None),
            LearningTopic.deprecated == False,
            LearningTopic.centrality > 0.3,
        ).count()

        print(f"\nCoverage: {translated}/{total} topics translated")
        print(f"High-value (centrality>0.3) untranslated: {high_value_untranslated}")
    finally:
        db.close()


if __name__ == "__main__":
    check_quality()
