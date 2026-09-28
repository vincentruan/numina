#!/usr/bin/env python3
"""Export all learning translations to a JSON fixture file.

Run from the server/ directory:
    cd server
    uv run python ../.claude/skills/learning-content-translate/scripts/export-translations.py

Output: server/data/learning_translations.json
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


def export_translations(output_path: Path | None = None) -> Path:
    """Export all *_zh translations to a JSON fixture.

    Matches by stable keys (topic_key, subject+domain) — never by Snowflake ID.
    """
    db = SessionLocal()

    try:
        # Export topic translations
        topics = db.query(LearningTopic).filter(
            LearningTopic.name_zh.isnot(None),
            LearningTopic.deprecated == False,
        ).all()

        topic_data = []
        for t in topics:
            topic_data.append({
                "topic_key": t.topic_key,
                "name_zh": t.name_zh,
                "description_zh": t.description_zh,
                "evidence_zh": t.evidence_zh or [],
                "assessment_prompt_zh": t.assessment_prompt_zh,
            })

        # Export cluster translations
        clusters = db.query(LearningCluster).filter(
            LearningCluster.summary_zh.isnot(None),
        ).all()

        cluster_data = []
        for c in clusters:
            cluster_data.append({
                "subject": c.subject,
                "domain": c.domain,
                "summary_zh": c.summary_zh,
            })

        output = {
            "version": 1,
            "topics": topic_data,
            "clusters": cluster_data,
        }

        out_path = output_path or Path("data/learning_translations.json")
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(output, ensure_ascii=False, indent=2))

        print(f"Exported {len(topic_data)} topics, {len(cluster_data)} clusters → {out_path}")
        return out_path
    finally:
        db.close()


if __name__ == "__main__":
    export_translations()
