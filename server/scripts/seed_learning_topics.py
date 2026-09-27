"""Seed learning topics, dependencies, and clusters from os-taxonomy data.

Usage:
    cd server
    uv run python scripts/seed_learning_topics.py [--data-dir /path/to/os-taxonomy/data]
"""

import argparse
import asyncio
import json
import os
import re
import subprocess
from collections import Counter
from pathlib import Path

DEFAULT_DATA_DIR = Path(os.environ.get("LEARNING_TAXONOMY_DIR", Path(__file__).parent.parent / "data" / "os-taxonomy"))

# os-taxonomy subject title -> DB subject slug
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


_INJECTION_PATTERNS = [
    re.compile(r"ignore\s+(all\s+)?previous\s+instructions", re.IGNORECASE),
    re.compile(r"忽略\s*(之前|所有)\s*(?:的\s*)?指令", re.IGNORECASE),
    re.compile(r"forget\s+(all\s+)?instructions", re.IGNORECASE),
    re.compile(r"system\s*:\s*", re.IGNORECASE),
    re.compile(r"<\|im_start\|>", re.IGNORECASE),
]

# Detect homoglyph attacks: Cyrillic/Greek chars that look like Latin
_HOMOGYPH_RANGES = [
    ("Ѐ", "ӿ"),  # Cyrillic
    ("Ͱ", "Ͽ"),  # Greek
]


def has_chinese_chars(text: str) -> bool:
    """Return True if text contains any CJK Unified Ideograph character."""
    return any("一" <= ch <= "鿿" for ch in text)


def has_injection_pattern(text: str) -> bool:
    """Return True if text contains prompt injection or homoglyph patterns."""
    # Check known injection patterns
    for pattern in _INJECTION_PATTERNS:
        if pattern.search(text):
            return True
    # Check for suspicious homoglyphs (Cyrillic/Greek mixed with Latin context)
    if len(text) > 10:
        homoglyph_count = sum(
            1
            for ch in text
            if any(start <= ch <= end for start, end in _HOMOGYPH_RANGES)
        )
        if homoglyph_count >= 3:
            return True
    return False


def compute_age_group(age_start: int | None) -> str:
    """Map age range start to age group bucket."""
    if age_start is None:
        return "mid"
    if age_start <= 7:
        return "low"
    if age_start <= 10:
        return "mid"
    return "high"


def normalize_subject(raw: str) -> str:
    """Normalize os-taxonomy subject title to DB slug."""
    return SUBJECT_MAP.get(raw, raw.lower().replace(" & ", "_").replace(" ", "_"))


def get_taxonomy_version(data_dir: Path) -> str:
    """Try to get os-taxonomy git commit hash for version tracking."""
    repo_dir = data_dir.parent
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            cwd=repo_dir,
            timeout=5,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except (subprocess.SubprocessError, OSError):
        pass
    return "unknown"


def seed_topics(session, data_dir: Path) -> int:
    """Import topics from topics.json."""
    from packages.db.models.learning.topic import LearningTopic

    with open(data_dir / "topics.json") as f:
        data = json.load(f)

    topics = data["topics"]
    created = 0
    for t in topics:
        topic_key = t["id"]  # mt_xxx format
        existing = session.query(LearningTopic).filter_by(topic_key=topic_key).first()
        if existing:
            existing.name = t.get("name")
            existing.description = t.get("description", "")
            existing.age_range_start = t.get("ageRangeStart")
            existing.age_range_end = t.get("ageRangeEnd")
            existing.centrality = t.get("centrality")
            existing.evidence_json = json.dumps(t.get("evidence", []))
            existing.standards_json = json.dumps(t.get("standards", []))
            existing.assessment_prompt = t.get("assessmentPrompt")
            existing.age_group = compute_age_group(t.get("ageRangeStart"))
        else:
            topic = LearningTopic(
                topic_key=topic_key,
                topic_type=t["type"],
                subject=normalize_subject(t["subject"]),
                domain=t.get("domain"),
                name=t.get("name"),
                description=t.get("description", ""),
                age_range_start=t.get("ageRangeStart"),
                age_range_end=t.get("ageRangeEnd"),
                centrality=t.get("centrality"),
                evidence_json=json.dumps(t.get("evidence", [])),
                standards_json=json.dumps(t.get("standards", [])),
                assessment_prompt=t.get("assessmentPrompt"),
                age_group=compute_age_group(t.get("ageRangeStart")),
            )
            session.add(topic)
            created += 1

    session.flush()
    print(f"  Topics: {created} created, {len(topics) - created} updated")
    return len(topics)


def seed_dependencies(session, data_dir: Path) -> int:
    """Import dependencies from dependencies.json."""
    from packages.db.models.learning.topic import LearningDependency, LearningTopic

    with open(data_dir / "dependencies.json") as f:
        data = json.load(f)

    # Build topic_key -> id map
    key_map = {}
    for row in session.query(LearningTopic.topic_key, LearningTopic.id).all():
        key_map[row[0]] = row[1]

    deps = data["dependencies"]
    created = 0
    skipped = 0
    for d in deps:
        topic_id = key_map.get(d["topicId"])
        prereq_id = key_map.get(d["prerequisiteId"])
        if topic_id is None or prereq_id is None:
            skipped += 1
            continue
        existing = (
            session.query(LearningDependency)
            .filter_by(topic_id=topic_id, prerequisite_id=prereq_id)
            .first()
        )
        if not existing:
            dep = LearningDependency(
                topic_id=topic_id,
                prerequisite_id=prereq_id,
                strength=d["strength"],
                reason=d.get("reason"),
            )
            session.add(dep)
            created += 1

    session.flush()
    print(f"  Dependencies: {created} created, {skipped} skipped (orphan edges)")
    return created


def seed_clusters(session, data_dir: Path) -> int:
    """Import clusters from clusters.json."""
    from packages.db.models.learning.topic import LearningCluster

    with open(data_dir / "clusters.json") as f:
        data = json.load(f)

    clusters = data["clusters"]
    created = 0
    for c in clusters:
        subject_slug = normalize_subject(c["subject"])
        existing = (
            session.query(LearningCluster)
            .filter_by(
                subject=subject_slug,
                domain=c["domain"],
                age_range_start=c.get("ageRangeStart"),
            )
            .first()
        )
        if not existing:
            cluster = LearningCluster(
                subject=subject_slug,
                domain=c["domain"],
                age_range_start=c.get("ageRangeStart"),
                age_group=compute_age_group(c.get("ageRangeStart")),
                summary=c.get("summary", ""),
            )
            session.add(cluster)
            created += 1

    session.flush()
    print(f"  Clusters: {created} created")
    return created


def validate_quality(session) -> None:
    """Run post-seed quality checks: orphan edges + per-subject stats + new validations."""
    from packages.db.models.learning.topic import (
        LearningCluster,
        LearningDependency,
        LearningTopic,
    )

    topic_count = session.query(LearningTopic).count()
    dep_count = session.query(LearningDependency).count()
    cluster_count = session.query(LearningCluster).count()

    print("\n=== Quality Validation ===")
    print(f"  Total topics: {topic_count}")
    print(f"  Total dependencies: {dep_count}")
    print(f"  Total clusters: {cluster_count}")

    # Orphan edge detection: deps referencing non-existent topic ids
    topic_ids = {row[0] for row in session.query(LearningTopic.id).all()}
    orphan_edges = 0
    for dep in session.query(LearningDependency).all():
        if dep.topic_id not in topic_ids or dep.prerequisite_id not in topic_ids:
            orphan_edges += 1
    print(f"  Orphan edges (FK violations): {orphan_edges}")

    # Per-subject topic counts
    subject_counts: Counter = Counter()
    for row in session.query(LearningTopic.subject, LearningTopic.id).all():
        subject_counts[row[0]] += 1
    print("\n  Topics per subject:")
    for subj, count in subject_counts.most_common():
        print(f"    {subj}: {count}")

    # --- New validations (OQ-6) ---
    from apps.backend.app.services.learning.validation import (
        validate_age_ranges,
        validate_badge_subjects,
    )

    # Badge subject validity check — badge dimensions must match LearningTopic.subject
    from packages.db.models.literacy_badge import LiteracyBadgeDefinition

    badge_subjects = set(
        r[0]
        for r in session.query(LiteracyBadgeDefinition.dimension).distinct().all()
    )
    subject_errors = validate_badge_subjects(badge_subjects, session)
    if subject_errors:
        for err in subject_errors:
            print(f"  BADGE SUBJECT ERROR: {err}")
        raise ValueError(f"Badge subject validation failed: {subject_errors}")
    print("  Badge subjects: OK")

    # Age range sanity
    age_errors = validate_age_ranges(session)
    if age_errors:
        for err in age_errors:
            print(f"  AGE RANGE ERROR: {err}")
        raise ValueError(f"Age range validation failed: {len(age_errors)} topics")
    print("  Age ranges: OK")

    print("\n  All quality validations passed.")


async def seed_topic_translations(session, data_dir: Path, batch_size: int = 50):
    """Batch-translate topics with empty *_zh fields using agent LLM infrastructure."""
    from apps.agent.core.config import get_ai_config

    from apps.agent.services.topic_translate import translate_topic
    from packages.db.models.learning.topic import LearningTopic

    # Query topics with missing Chinese translations, high-centrality first
    untranslated = (
        session.query(LearningTopic)
        .filter(
            (LearningTopic.name_zh.is_(None)) | (LearningTopic.name_zh == "")
        )
        .filter(LearningTopic.deprecated == False)  # noqa: E712
        .order_by(LearningTopic.centrality.desc().nullslast())
        .all()
    )

    # Skip topics whose English name already contains Chinese chars
    untranslated = [t for t in untranslated if not has_chinese_chars(t.name or "")]

    if not untranslated:
        print("All topics already translated. Skipping.")
        return

    print(f"Translating {len(untranslated)} topics (high-centrality first)...")

    ai_config = get_ai_config()
    total_translated = 0

    for batch_start in range(0, len(untranslated), batch_size):
        batch = untranslated[batch_start : batch_start + batch_size]
        for topic in batch:
            try:
                topic_dict = {
                    "name": topic.name,
                    "description": topic.description or "",
                    "evidence": topic.evidence or [],
                    "assessment_prompt": topic.assessment_prompt or "",
                }
                zh_fields = await translate_topic(topic_dict, ai_config)
            except Exception as e:
                print(f"  WARNING: Translation error for {topic.topic_key}: {e}")
                continue

            if zh_fields and zh_fields.get("name_zh"):
                # Validate assessment_prompt_zh
                prompt_zh = zh_fields.get("assessment_prompt_zh", "")
                if prompt_zh and (
                    len(prompt_zh) > 500 or has_injection_pattern(prompt_zh)
                ):
                    print(
                        f"  WARNING: Bad assessment_prompt_zh for {topic.topic_key}, keeping English"
                    )
                    zh_fields["assessment_prompt_zh"] = topic.assessment_prompt

                topic.name_zh = zh_fields.get("name_zh")
                topic.description_zh = zh_fields.get("description_zh")
                topic.evidence_zh_json = json.dumps(
                    zh_fields.get("evidence_zh", []), ensure_ascii=False
                )
                topic.assessment_prompt_zh = zh_fields.get("assessment_prompt_zh")
                total_translated += 1
            else:
                print(
                    f"  WARNING: Translation failed for {topic.topic_key}, keeping English"
                )

        session.commit()
        batch_num = batch_start // batch_size + 1
        total_batches = (len(untranslated) - 1) // batch_size + 1
        print(f"  Translated batch {batch_num}/{total_batches}")

    print(
        f"Translation complete: {total_translated}/{len(untranslated)} topics translated."
    )


async def seed_cluster_translations(session, ai_config):
    """Translate cluster summaries to Chinese."""
    from apps.agent.services.topic_translate import translate_topic
    from packages.db.models.learning.topic import LearningCluster

    clusters = (
        session.query(LearningCluster)
        .filter(
            (LearningCluster.summary_zh.is_(None)) | (LearningCluster.summary_zh == "")
        )
        .all()
    )

    if not clusters:
        print("All clusters already translated. Skipping.")
        return

    print(f"Translating {len(clusters)} cluster summaries...")
    translated = 0

    for cluster in clusters:
        try:
            # Reuse translate_topic with a dict shaped like a topic
            result = await translate_topic(
                {
                    "name": f"{cluster.subject} - {cluster.domain}",
                    "description": cluster.summary or "",
                    "evidence": [],
                    "assessment_prompt": "",
                },
                ai_config,
            )
            if result and result.get("description_zh"):
                cluster.summary_zh = result["description_zh"]
                translated += 1
        except Exception as e:
            print(
                f"  WARNING: Cluster translation error for {cluster.subject}/{cluster.domain}: {e}"
            )

    session.commit()
    print(f"Cluster translation complete: {translated}/{len(clusters)} translated.")


def main():
    parser = argparse.ArgumentParser(description="Seed learning OS data from os-taxonomy")
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument(
        "--skip-validate", action="store_true", help="Skip post-seed quality validation"
    )
    parser.add_argument(
        "--skip-translation",
        action="store_true",
        help="Skip the translation pass (for re-seed without re-translating)",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=50,
        help="Translation batch size (default: 50)",
    )
    parser.add_argument(
        "--force-retranslate",
        action="store_true",
        help="Force re-translate topics that already have _zh data",
    )
    args = parser.parse_args()

    if not args.data_dir.exists():
        print(f"Error: data directory {args.data_dir} does not exist")
        raise SystemExit(1)

    version = get_taxonomy_version(args.data_dir)
    print(f"os-taxonomy version: {version}")

    from apps.backend.app.database import SessionLocal

    session = SessionLocal()
    try:
        print("Seeding learning topics...")
        seed_topics(session, args.data_dir)
        print("Seeding dependencies...")
        seed_dependencies(session, args.data_dir)
        print("Seeding clusters...")
        seed_clusters(session, args.data_dir)
        session.commit()

        if not args.skip_translation:
            asyncio.run(seed_topic_translations(session, args.data_dir, args.batch_size))
            from apps.agent.core.config import get_ai_config

            asyncio.run(seed_cluster_translations(session, get_ai_config()))

        print("Done!")

        if not args.skip_validate:
            validate_quality(session)
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()
