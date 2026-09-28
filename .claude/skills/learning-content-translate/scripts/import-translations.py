#!/usr/bin/env python3
"""Import learning translations from a JSON fixture file.

Run from the server/ directory:
    cd server
    uv run python ../.claude/skills/learning-content-translate/scripts/import-translations.py

Idempotent — skips records that already have translations.
Matching: topics by topic_key, clusters by (subject, domain). Never by Snowflake ID.
"""
import json
import sys
from pathlib import Path

# Ensure we can import from the server packages
server_root = Path(__file__).resolve().parent.parent.parent.parent.parent / "server"
if str(server_root) not in sys.path:
    sys.path.insert(0, str(server_root))

from packages.db.session import SessionLocal
from packages.db.models.learning.topic import LearningTopic, LearningCluster


def import_translations(fixture_path: Path | None = None) -> tuple[int, int]:
    """Import translations from JSON fixture into the database.

    Returns (imported_topics, imported_clusters) counts.
    """
    path = fixture_path or Path("data/learning_translations.json")
    if not path.exists():
        print(f"No translation fixture found at {path}. Run export first.")
        return 0, 0

    data = json.loads(path.read_text())
    db = SessionLocal()

    try:
        # Import topic translations
        imported_topics = 0
        for entry in data.get("topics", []):
            topic = db.query(LearningTopic).filter(
                LearningTopic.topic_key == entry["topic_key"]
            ).first()
            if not topic:
                continue
            # Skip if already translated (idempotent)
            if topic.name_zh:
                continue
            topic.name_zh = entry.get("name_zh")
            topic.description_zh = entry.get("description_zh")
            topic.evidence_zh_json = json.dumps(
                entry.get("evidence_zh", []), ensure_ascii=False
            )
            topic.assessment_prompt_zh = entry.get("assessment_prompt_zh")
            imported_topics += 1

        # Import cluster translations
        imported_clusters = 0
        for entry in data.get("clusters", []):
            cluster = db.query(LearningCluster).filter(
                LearningCluster.subject == entry["subject"],
                LearningCluster.domain == entry["domain"],
            ).first()
            if not cluster or cluster.summary_zh:
                continue
            cluster.summary_zh = entry.get("summary_zh")
            imported_clusters += 1

        db.commit()
        print(f"Imported {imported_topics} topics, {imported_clusters} clusters")
        return imported_topics, imported_clusters
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    import_translations()
