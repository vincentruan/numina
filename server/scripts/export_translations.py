#!/usr/bin/env python3
"""Export learning topic/cluster translations from DB to JSON files.

Reads the original os-taxonomy JSON structure and merges Chinese translations
from the database, outputting complete JSON files with both English and Chinese fields.

Usage:
    cd server
    PYTHONPATH=. uv run python scripts/export_translations.py
    PYTHONPATH=. uv run python scripts/export_translations.py --data-dir /path/to/os-taxonomy/data
    PYTHONPATH=. uv run python scripts/export_translations.py --output-dir /path/to/output

Output:
    translations/topics.json    — full topics with *_zh fields merged
    translations/clusters.json  — full clusters with summary_zh merged
"""

import argparse
import json
import sys
from pathlib import Path

# Default paths
DEFAULT_TAXONOMY_DIR = Path(
    "/Volumes/LexarSSDNQ790/geek_space/learning/os-taxonomy/data"
)
DEFAULT_OUTPUT_DIR = Path(__file__).parent.parent / "packages" / "os_taxonomy"

# Subject normalization map — must match seed_learning_topics.py SUBJECT_MAP
SUBJECT_MAP = {
    "Mathematics": "mathematics",
    "Science": "science",
    "English": "english",
    "History": "history",
    "Personal & Social Development": "personal_social",
    "Life Skills": "life_skills",
    "Computing": "computing",
    "Learning to Learn": "learning_to_learn",
}


def normalize_subject(raw: str) -> str:
    """Normalize os-taxonomy subject title to DB slug (mirrors seed script)."""
    return SUBJECT_MAP.get(raw, raw.lower().replace(" & ", "_").replace(" ", "_"))


def export_topics(taxonomy_dir: Path, output_dir: Path) -> int:
    """Export topics with Chinese translations merged."""
    from apps.backend.app.database import SessionLocal
    from packages.db.models.learning.topic import LearningTopic

    # Read original topics.json
    topics_file = taxonomy_dir / "topics.json"
    if not topics_file.exists():
        print(f"Error: {topics_file} not found")
        return 1

    with open(topics_file, encoding="utf-8") as f:
        original = json.load(f)

    original_topics = original.get("topics", [])
    print(f"Read {len(original_topics)} topics from {topics_file}")

    # Query DB for translations, keyed by topic_key (= original id)
    db = SessionLocal()
    try:
        db_topics = (
            db.query(LearningTopic)
            .filter(LearningTopic.name_zh.isnot(None), LearningTopic.name_zh != "")
            .all()
        )
        translations = {t.topic_key: t for t in db_topics}
        print(f"Found {len(translations)} translated topics in DB")
    finally:
        db.close()

    # Merge translations into original structure
    merged_count = 0
    for topic in original_topics:
        topic_id = topic.get("id")
        if topic_id in translations:
            t = translations[topic_id]
            topic["nameZh"] = t.name_zh
            topic["descriptionZh"] = t.description_zh or ""
            topic["evidenceZh"] = t.evidence_zh or []
            topic["assessmentPromptZh"] = t.assessment_prompt_zh or ""
            merged_count += 1

    # Write output
    output_file = output_dir / "topics.json"
    output_data = {
        "version": original.get("version", "v1"),
        "topicCount": len(original_topics),
        "translatedCount": merged_count,
        "topics": original_topics,
    }

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)

    print(f"Exported {merged_count}/{len(original_topics)} topics to {output_file}")
    return 0


def export_clusters(taxonomy_dir: Path, output_dir: Path) -> int:
    """Export clusters with Chinese translations merged."""
    from apps.backend.app.database import SessionLocal
    from packages.db.models.learning.topic import LearningCluster

    # Read original clusters.json
    clusters_file = taxonomy_dir / "clusters.json"
    if not clusters_file.exists():
        print(f"Error: {clusters_file} not found")
        return 1

    with open(clusters_file, encoding="utf-8") as f:
        original = json.load(f)

    original_clusters = original.get("clusters", [])
    print(f"Read {len(original_clusters)} clusters from {clusters_file}")

    # Query DB for translations
    # Clusters don't have unique IDs — match by (subject, domain, age_range_start, summary)
    db = SessionLocal()
    try:
        db_clusters = (
            db.query(LearningCluster)
            .filter(LearningCluster.summary_zh.isnot(None), LearningCluster.summary_zh != "")
            .all()
        )
        print(f"Found {len(db_clusters)} translated clusters in DB")
    finally:
        db.close()

    # Build lookup: (subject, domain, age_range_start, summary) → summary_zh
    # Since multiple clusters can share (subject, domain, age_range_start),
    # we match by summary text as well
    translation_map = {}
    for c in db_clusters:
        key = (c.subject, c.domain, c.age_range_start, c.summary)
        translation_map[key] = c.summary_zh

    # Merge translations into original structure
    # JSON uses camelCase (ageRangeStart, string) — DB uses snake_case (age_range_start, int)
    # JSON subjects are title-case ("English") — DB subjects are slugs ("english")
    merged_count = 0
    for cluster in original_clusters:
        subject = normalize_subject(cluster.get("subject", ""))
        domain = cluster.get("domain", "")
        age_start = cluster.get("ageRangeStart")
        summary = cluster.get("summary", "")
        # Try matching with int conversion for ageRangeStart
        try:
            age_int = int(age_start) if age_start is not None else None
        except (ValueError, TypeError):
            age_int = None

        # Match by (subject, domain, age_range_start, summary)
        key = (subject, domain, age_int, summary)
        if key in translation_map:
            cluster["summaryZh"] = translation_map[key]
            merged_count += 1

    # Write output
    output_file = output_dir / "clusters.json"
    output_data = {
        "version": original.get("version", "v1"),
        "clusterCount": len(original_clusters),
        "translatedCount": merged_count,
        "clusters": original_clusters,
    }

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)

    print(f"Exported {merged_count}/{len(original_clusters)} clusters to {output_file}")
    return 0


def main():
    parser = argparse.ArgumentParser(
        description="Export learning translations from DB to JSON"
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=DEFAULT_TAXONOMY_DIR,
        help=f"Path to os-taxonomy data directory (default: {DEFAULT_TAXONOMY_DIR})",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help=f"Output directory for translated JSON (default: {DEFAULT_OUTPUT_DIR})",
    )
    args = parser.parse_args()

    if not args.data_dir.exists():
        print(f"Error: taxonomy data directory not found: {args.data_dir}")
        sys.exit(1)

    args.output_dir.mkdir(parents=True, exist_ok=True)

    print(f"Taxonomy data: {args.data_dir}")
    print(f"Output: {args.output_dir}")
    print()

    rc1 = export_topics(args.data_dir, args.output_dir)
    print()
    rc2 = export_clusters(args.data_dir, args.output_dir)

    if rc1 == 0 and rc2 == 0:
        print("\nExport complete!")
    else:
        print("\nExport completed with errors.")
        sys.exit(1)


if __name__ == "__main__":
    main()
