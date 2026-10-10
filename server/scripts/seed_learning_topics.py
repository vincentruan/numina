"""Seed learning topics, dependencies, and clusters from taxonomy data.

Supports two sources:
    os-taxonomy (default) — packages/os_taxonomy JSON data
    beijing — os-taxonomy-beijing data via get_loader("beijing"), with
    dedup_mapping.json support for merging mt_/mtc_ overlap

Usage:
    cd server
    uv run python scripts/seed_learning_topics.py [--data-dir /path/to/os-taxonomy/data]
    uv run python scripts/seed_learning_topics.py --source beijing
"""

import argparse
import asyncio
import json
import os
import re
import subprocess
import sys
from collections import Counter
from dataclasses import asdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

DEFAULT_DATA_DIR = Path(os.environ.get("LEARNING_TAXONOMY_DIR", Path(__file__).parent.parent / "data" / "os-taxonomy"))

# Supported taxonomy source identifiers
SOURCE_OSTAX = "os-taxonomy"
SOURCE_BEIJING = "beijing"

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
    """Import topics from topics.json.

    UPSERT is keyed on the composite (topic_key, source_taxonomy) so that
    the same topic_key from different sources remains distinct rows.
    """
    from packages.db.models.learning.topic import LearningTopic

    with open(data_dir / "topics.json") as f:
        data = json.load(f)

    topics = data["topics"]
    created = 0
    for t in topics:
        topic_key = t["id"]  # mt_xxx format
        existing = (
            session.query(LearningTopic)
            .filter_by(topic_key=topic_key, source_taxonomy=SOURCE_OSTAX)
            .first()
        )
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
                source_taxonomy=SOURCE_OSTAX,
            )
            session.add(topic)
            created += 1

    session.flush()
    print(f"  Topics: {created} created, {len(topics) - created} updated")
    return len(topics)


def seed_dependencies(session, data_dir: Path) -> int:
    """Import dependencies from dependencies.json.

    topic_key -> id resolution is scoped to the os-taxonomy source so
    that beijing rows with the same topic_key are not accidentally used.
    """
    from packages.db.models.learning.topic import LearningDependency, LearningTopic

    with open(data_dir / "dependencies.json") as f:
        data = json.load(f)

    # Build topic_key -> id map (scoped to os-taxonomy source)
    key_map = {}
    for row in (
        session.query(LearningTopic.topic_key, LearningTopic.id)
        .filter(LearningTopic.source_taxonomy == SOURCE_OSTAX)
        .all()
    ):
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
                review_status=None,
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
                source_taxonomy=SOURCE_OSTAX,
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
                source_taxonomy=SOURCE_OSTAX,
            )
            session.add(cluster)
            created += 1

    session.flush()
    print(f"  Clusters: {created} created")
    return created


# ---------------------------------------------------------------------------
# Beijing source: loader-based seeding with dedup mapping
# ---------------------------------------------------------------------------


def load_dedup_mapping(loading_dir: Path) -> list[dict]:
    """Load dedup_mapping.json from the Beijing data root.

    Looks in <data_root>/dedup_mapping.json and <data_dir>/dedup_mapping.json.
    Returns [] when the file is absent.
    """
    for candidate in (loading_dir / "dedup_mapping.json", loading_dir.parent / "dedup_mapping.json"):
        if candidate.is_file():
            with open(candidate, encoding="utf-8") as f:
                return json.load(f)
    return []


def build_dedup_views(
    mapping: list[dict],
) -> tuple[dict[str, dict], dict[str, str]]:
    """Build pure-logic lookup structures from a dedup mapping.

    Returns:
        mtc_actions: mtc_topic_key -> mapping entry (dict with 'action', 'mt_topic_key')
        deprecated_to_merged: mtc_topic_key -> mt_topic_key for merge actions only
    """
    mtc_actions: dict[str, dict] = {}
    deprecated_to_merged: dict[str, str] = {}
    for entry in mapping:
        mtc_key = entry.get("mtc_topic_key")
        if not mtc_key:
            continue
        mtc_actions[mtc_key] = entry
        if entry.get("action") == "merge" and entry.get("mt_topic_key"):
            deprecated_to_merged[mtc_key] = entry["mt_topic_key"]
    return mtc_actions, deprecated_to_merged


def apply_dedup_to_topics(
    topics: list, mtc_actions: dict[str, dict]
) -> int:
    """Apply dedup actions to NormalizedTopic instances in place.

    For each mtc_ topic found in *topics*, apply the mapped action:
    - merge: mtc deprecated=True; mt_ topic gets concatenated description_zh,
      unioned curriculum_standards + evidence;
    - hide_mtc: mtc deprecated=True;
    - keep_both: no change.

    Returns the number of merge actions actually applied.
    """
    by_key = {t.topic_key: t for t in topics}
    merges_applied = 0
    for mtc_key, entry in mtc_actions.items():
        mtc = by_key.get(mtc_key)
        if mtc is None:
            continue
        action = entry.get("action")
        if action == "merge":
            mt_key = entry.get("mt_topic_key")
            mt = by_key.get(mt_key)
            mtc.deprecated = True
            if mt is None:
                continue
            merges_applied += 1
            # Concatenate description_zh
            mt_desc = (mt.description_zh or "").strip()
            mtc_desc = (mtc.description_zh or "").strip()
            combined = mt_desc
            if mtc_desc:
                combined = (combined + "\n\n" + mtc_desc) if combined else mtc_desc
            mt.description_zh = combined or None
            # Union curriculum_standards (order-preserving)
            mt.curriculum_standards = _union_list(mt.curriculum_standards, mtc.curriculum_standards)
            # Union evidence
            mt.evidence = _union_list(mt.evidence, mtc.evidence)
        elif action == "hide_mtc":
            mtc.deprecated = True
    return merges_applied


def _union_list(a: list, b: list) -> list:
    """Order-preserving union of two lists."""
    seen = set()
    result = []
    for item in list(a) + list(b):
        if item not in seen:
            seen.add(item)
            result.append(item)
    return result


def load_source_topics(source: str, data_dir: Path | None) -> list:
    """Load NormalizedTopic list for the given source.

    For 'os-taxonomy', reads packages/os_taxonomy/topics.json directly
    (preserving the legacy behavior, including *Zh fields). For 'beijing',
    uses the loader.
    """
    if source == SOURCE_BEIJING:
        # Import beijing loader module so it self-registers in the registry
        import packages.os_taxonomy.loaders.beijing  # noqa: F401
        from packages.os_taxonomy.loaders import get_loader
        loader = get_loader(SOURCE_BEIJING)
        if data_dir is not None:
            loader = type(loader)(data_dir=data_dir)
        return loader.load_topics()

    if source == SOURCE_OSTAX:
        # Read the same JSON file the legacy seed_topics path uses, but
        # through the loader so both code paths share one NormalizedTopic
        # shape. _Zh fields are picked up from the JSON.
        import packages.os_taxonomy.loaders.os_taxonomy  # noqa: F401
        from packages.os_taxonomy.loaders import get_loader
        loader = get_loader(SOURCE_OSTAX)
        topics = loader.load_topics()
        if data_dir is None:
            return topics
        # If a custom data dir was supplied, load topics.json from there.
        with open(data_dir / "topics.json", encoding="utf-8") as f:
            raw = json.load(f)["topics"]
        return [
            _topic_from_raw_os_taxonomy(r) for r in raw
        ]
    raise ValueError(f"Unknown source: {source!r}")


def _topic_from_raw_os_taxonomy(raw: dict):
    """Build a NormalizedTopic from a raw os-taxonomy topics.json record."""
    from packages.os_taxonomy.types import NormalizedTopic

    return NormalizedTopic(
        topic_key=raw["id"],
        source_taxonomy=SOURCE_OSTAX,
        topic_type=raw["type"],
        subject=raw["subject"],
        domain=raw.get("domain"),
        name=raw.get("name"),
        name_zh=raw.get("nameZh"),
        description=raw.get("description", ""),
        description_zh=raw.get("descriptionZh"),
        age_range_start=raw.get("ageRangeStart"),
        age_range_end=raw.get("ageRangeEnd"),
        centrality=raw.get("centrality"),
        evidence=raw.get("evidence", []),
        evidence_zh=raw.get("evidenceZh"),
        assessment_prompt=raw.get("assessmentPrompt"),
        assessment_prompt_zh=raw.get("assessmentPromptZh"),
        standards=raw.get("standards", []),
        curriculum_standards=raw.get("cnStandards", []),
        translation_status=raw.get("translationStatus"),
        deprecated=False,
        age_group=compute_age_group(raw.get("ageRangeStart")),
    )


def upsert_topic(session, t) -> bool:
    """UPSERT a single NormalizedTopic using the composite (topic_key, source_taxonomy) key.

    Returns True if a new row was created, False if an existing row was updated.
    Applies injection-pattern safety checks on text fields where sensible.
    """
    from packages.db.models.learning.topic import LearningTopic

    # Apply injection-pattern safety on Chinese-text fields
    if t.assessment_prompt_zh and has_injection_pattern(t.assessment_prompt_zh):
        t.assessment_prompt_zh = None

    existing = (
        session.query(LearningTopic)
        .filter_by(topic_key=t.topic_key, source_taxonomy=t.source_taxonomy)
        .first()
    )
    if existing:
        _apply_normalized_to_db(existing, t)
        return False
    row = LearningTopic(topic_key=t.topic_key, source_taxonomy=t.source_taxonomy)
    _apply_normalized_to_db(row, t)
    session.add(row)
    return True


def _apply_normalized_to_db(row, t) -> None:
    """Copy NormalizedTopic fields onto a LearningTopic instance."""
    # The loader returns subject as a slug (os-taxonomy: raw title, beijing: slug).
    # For os-taxonomy we normalize via SUBJECT_MAP; for beijing it's already a slug.
    if t.source_taxonomy == SOURCE_OSTAX:
        subject = normalize_subject(t.subject)
    else:
        subject = t.subject or normalize_subject("")
    row.topic_type = t.topic_type
    row.subject = subject
    row.domain = t.domain
    row.name = t.name
    row.name_zh = t.name_zh
    row.description = t.description or ""
    row.description_zh = t.description_zh
    row.age_range_start = t.age_range_start
    row.age_range_end = t.age_range_end
    row.centrality = t.centrality
    row.evidence_json = json.dumps(t.evidence or [])
    if t.evidence_zh is not None:
        row.evidence_zh_json = json.dumps(t.evidence_zh, ensure_ascii=False)
    row.assessment_prompt = t.assessment_prompt
    row.assessment_prompt_zh = t.assessment_prompt_zh
    row.standards_json = json.dumps(t.standards or [])
    row.curriculum_standards_json = json.dumps(
        [_curriculum_standard_to_json(cs) for cs in t.curriculum_standards or []],
        ensure_ascii=False,
    )
    row.age_group = compute_age_group(t.age_range_start)
    row.deprecated = t.deprecated


def _curriculum_standard_to_json(cs) -> object:
    """Serialize one curriculum standard for storage.

    The beijing loader resolves identifiers into ``CurriculumStandard``
    instances; the raw os-taxonomy path (``_topic_from_raw_os_taxonomy``)
    still yields bare identifiers, so both shapes are accepted here and
    normalized on read by ``TopicResponse``.
    """
    return cs if isinstance(cs, str) else asdict(cs)


def upsert_cluster(session, c) -> bool:
    """UPSERT a NormalizedCluster. Returns True if created, False if skipped."""
    from packages.db.models.learning.topic import LearningCluster

    subject = c.subject if c.source_taxonomy == SOURCE_BEIJING else normalize_subject(c.subject)
    existing = (
        session.query(LearningCluster)
        .filter_by(
            subject=subject,
            domain=c.domain,
            age_range_start=c.age_range_start,
            source_taxonomy=c.source_taxonomy,
        )
        .first()
    )
    if existing:
        existing.summary = c.summary or ""
        existing.summary_zh = c.summary_zh
        return False
    cluster = LearningCluster(
        subject=subject,
        domain=c.domain,
        age_range_start=c.age_range_start,
        age_group=c.age_group or compute_age_group(c.age_range_start),
        summary=c.summary or "",
        summary_zh=c.summary_zh,
        source_taxonomy=c.source_taxonomy,
    )
    session.add(cluster)
    return True


def seed_source_topics(
    session, source: str, data_dir: Path | None, dedup_mapping: list[dict] | None
) -> tuple[int, int, int]:
    """Seed topics for the given source. Returns (seeded, created, deprecated).

    For beijing, applies the dedup mapping before the UPSERT loop so merged
    topics are concatenated, mtc_ topics are marked deprecated, and
    dependencies that reference them will be rerouted.
    """
    if source == SOURCE_BEIJING:
        import packages.os_taxonomy.loaders.beijing  # noqa: F401
        from packages.os_taxonomy.loaders import get_loader
        loader = get_loader(SOURCE_BEIJING)
        if data_dir is not None:
            loader = type(loader)(data_dir=data_dir)
        topics = loader.load_topics()
    else:
        topics = _load_os_taxonomy_topics(data_dir)

    merges = 0
    deprecated = 0
    if source == SOURCE_BEIJING and dedup_mapping:
        mtc_actions, _ = build_dedup_views(dedup_mapping)
        merges = apply_dedup_to_topics(topics, mtc_actions)  # noqa: F841
        deprecated = sum(1 for t in topics if t.deprecated)

    created = 0
    for t in topics:
        if upsert_topic(session, t):
            created += 1
    session.flush()
    print(f"  Topics ({source}): {created} created, {len(topics) - created} updated")
    return len(topics), created, deprecated


def _load_os_taxonomy_topics(data_dir: Path | None):
    """Load os-taxonomy NormalizedTopics, honoring a custom data_dir if given."""
    if data_dir is None:
        import packages.os_taxonomy.loaders.os_taxonomy  # noqa: F401
        from packages.os_taxonomy.loaders import get_loader
        return get_loader(SOURCE_OSTAX).load_topics()
    with open(data_dir / "topics.json", encoding="utf-8") as f:
        raw = json.load(f)["topics"]
    return [_topic_from_raw_os_taxonomy(r) for r in raw]


def seed_source_dependencies(
    session,
    source: str,
    data_dir: Path | None,
    dedup_mapping: list[dict] | None,
) -> int:
    """Seed dependencies for the given source, rerouting any references to
    deprecated mtc_ topics through the merged mt_ counterpart.

    Skips NormalizedDependency rows whose review_status is 'rejected'.
    Returns the number of created rows.
    """
    from packages.db.models.learning.topic import LearningDependency, LearningTopic

    if source == SOURCE_BEIJING:
        import packages.os_taxonomy.loaders.beijing  # noqa: F401
        from packages.os_taxonomy.loaders import get_loader
        loader = get_loader(SOURCE_BEIJING)
        if data_dir is not None:
            loader = type(loader)(data_dir=data_dir)
        deps = loader.load_dependencies()
    else:
        import packages.os_taxonomy.loaders.os_taxonomy  # noqa: F401
        from packages.os_taxonomy.loaders import get_loader
        deps = get_loader(SOURCE_OSTAX).load_dependencies()
        if data_dir is not None:
            with open(data_dir / "dependencies.json", encoding="utf-8") as f:
                raw = json.load(f).get("dependencies", [])
            from packages.os_taxonomy.types import NormalizedDependency
            deps = [
                NormalizedDependency(
                    topic_key=r["topicId"],
                    prerequisite_key=r["prerequisiteId"],
                    strength=r["strength"],
                    reason=r.get("reason"),
                    review_status=r.get("reviewStatus"),
                )
                for r in raw
            ]

    # Composite key -> id map (topic_key, source_taxonomy)
    key_map: dict[tuple[str, str], int] = {}
    for topic_key, source_row, row_id in session.query(
        LearningTopic.topic_key, LearningTopic.source_taxonomy, LearningTopic.id
    ).all():
        key_map[(topic_key, source_row)] = row_id

    reroute: dict[str, str] = {}
    if source == SOURCE_BEIJING and dedup_mapping:
        _, reroute = build_dedup_views(dedup_mapping)

    created = 0
    skipped = 0
    for d in deps:
        if d.review_status == "rejected":
            skipped += 1
            continue
        topic_key = reroute.get(d.topic_key, d.topic_key)
        prereq_key = reroute.get(d.prerequisite_key, d.prerequisite_key)
        topic_id = key_map.get((topic_key, source))
        prereq_id = key_map.get((prereq_key, source))
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
                strength=d.strength,
                reason=d.reason,
                review_status=d.review_status,
            )
            session.add(dep)
            created += 1

    session.flush()
    print(f"  Dependencies ({source}): {created} created, {skipped} skipped")
    return created


def seed_source_clusters(
    session, source: str, data_dir: Path | None
) -> int:
    """Seed clusters for the given source via the loader."""
    if source == SOURCE_BEIJING:
        import packages.os_taxonomy.loaders.beijing  # noqa: F401
        from packages.os_taxonomy.loaders import get_loader
        loader = get_loader(SOURCE_BEIJING)
        if data_dir is not None:
            loader = type(loader)(data_dir=data_dir)
        clusters = loader.load_clusters()
    else:
        import packages.os_taxonomy.loaders.os_taxonomy  # noqa: F401
        from packages.os_taxonomy.loaders import get_loader
        clusters = get_loader(SOURCE_OSTAX).load_clusters()
        if data_dir is not None:
            with open(data_dir / "clusters.json", encoding="utf-8") as f:
                raw = json.load(f).get("clusters", [])
            from packages.os_taxonomy.types import NormalizedCluster
            clusters = [
                NormalizedCluster(
                    subject=r["subject"],
                    domain=r["domain"],
                    age_range_start=r.get("ageRangeStart"),
                    age_group=compute_age_group(r.get("ageRangeStart")),
                    summary=r.get("summary", ""),
                    summary_zh=r.get("summaryZh"),
                    source_taxonomy=SOURCE_OSTAX,
                )
                for r in raw
            ]

    created = 0
    for c in clusters:
        if upsert_cluster(session, c):
            created += 1
    session.flush()
    print(f"  Clusters ({source}): {created} created")
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


# ---------------------------------------------------------------------------
# MVP Topic Curation
# ---------------------------------------------------------------------------

MVP_SUBJECTS = {"mathematics", "science", "english"}
MVP_AGE_GROUP = "mid"
MVP_MIN_PER_SUBJECT = 20
MVP_MAX_PER_SUBJECT = 30
MVP_TOTAL_MIN = 60
MVP_TOTAL_MAX = 90


def select_mvp_topics(session) -> list[int]:
    """Select 60-90 MVP topics: top by centrality from 3 subjects, age_group=mid.

    Returns list of topic IDs in the MVP set.
    Ensures dependency completeness: if a selected topic has hard prereqs,
    those are included too (even if outside the subject/age_group filter).
    """
    from packages.db.models.learning.topic import LearningDependency, LearningTopic

    selected: dict[int, LearningTopic] = {}

    for subject in MVP_SUBJECTS:
        candidates = (
            session.query(LearningTopic)
            .filter(
                LearningTopic.subject == subject,
                LearningTopic.age_group == MVP_AGE_GROUP,
                LearningTopic.deprecated == False,  # noqa: E712
            )
            .order_by(LearningTopic.centrality.desc())
            .limit(MVP_MAX_PER_SUBJECT)
            .all()
        )
        for t in candidates:
            selected[t.id] = t

    # Ensure dependency completeness: add hard prereqs not yet selected
    added_prereqs = True
    while added_prereqs:
        added_prereqs = False
        for topic_id in list(selected.keys()):
            hard_deps = (
                session.query(LearningDependency)
                .filter_by(topic_id=topic_id, strength="hard")
                .all()
            )
            for dep in hard_deps:
                if dep.prerequisite_id not in selected:
                    prereq = session.query(LearningTopic).filter_by(id=dep.prerequisite_id).first()
                    if prereq:
                        selected[prereq.id] = prereq
                        added_prereqs = True

    return list(selected.keys())


def validate_mvp_curation(session, topic_ids: list[int]) -> list[str]:
    """Validate the MVP topic selection.

    Returns list of error messages (empty = all good).
    """
    from packages.db.models.learning.topic import LearningDependency, LearningTopic

    errors: list[str] = []

    topics = session.query(LearningTopic).filter(LearningTopic.id.in_(topic_ids)).all()
    if not topics:
        errors.append("No topics found in MVP set")
        return errors

    id_set = {t.id for t in topics}

    # Check total count
    total = len(topics)
    if total < MVP_TOTAL_MIN:
        errors.append(f"Too few MVP topics: {total} (min {MVP_TOTAL_MIN})")
    if total > MVP_TOTAL_MAX:
        errors.append(f"Too many MVP topics: {total} (max {MVP_TOTAL_MAX})")

    # Check per-subject counts
    subject_counts: Counter = Counter()
    for t in topics:
        subject_counts[t.subject] += 1

    for subject in MVP_SUBJECTS:
        count = subject_counts.get(subject, 0)
        if count < MVP_MIN_PER_SUBJECT:
            errors.append(f"Subject {subject}: only {count} topics (min {MVP_MIN_PER_SUBJECT})")

    # Check no orphans (all topics have at least one connection)
    topic_ids_with_deps = set()
    for dep in session.query(LearningDependency).all():
        if dep.topic_id in id_set:
            topic_ids_with_deps.add(dep.topic_id)
        if dep.prerequisite_id in id_set:
            topic_ids_with_deps.add(dep.prerequisite_id)

    orphans = id_set - topic_ids_with_deps
    if orphans:
        errors.append(f"{len(orphans)} orphan topics (no dependencies)")

    return errors


async def seed_topic_translations(
    session, batch_size: int = 50, force_retranslate: bool = False
):
    """Batch-translate topics using agent LLM infrastructure.

    When *force_retranslate* is False (default), only topics with NULL/empty
    ``name_zh`` are translated.  When True, all non-deprecated topics are
    re-translated — existing ``_zh`` fields are cleared first so the
    translation function overwrites them.
    """
    from apps.agent.core.config import get_ai_config
    from apps.agent.services.topic_translate import translate_topic
    from packages.db.models.learning.topic import LearningTopic

    query = session.query(LearningTopic).filter(
        LearningTopic.deprecated == False  # noqa: E712
    )

    if not force_retranslate:
        query = query.filter(
            (LearningTopic.name_zh.is_(None)) | (LearningTopic.name_zh == "")
        )

    untranslated = query.order_by(LearningTopic.centrality.desc().nullslast()).all()

    # Skip topics whose English name already contains Chinese chars
    untranslated = [t for t in untranslated if not has_chinese_chars(t.name or "")]

    if not untranslated:
        print("All topics already translated. Skipping.")
        return

    if force_retranslate:
        # Clear existing _zh fields so translate_topic overwrites them
        for topic in untranslated:
            topic.name_zh = None
            topic.description_zh = None
            topic.evidence_zh_json = None
            topic.assessment_prompt_zh = None
        session.flush()

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


async def seed_cluster_translations(session):
    """Translate cluster summaries to Chinese."""
    from apps.agent.core.config import get_ai_config
    from apps.agent.services.topic_translate import translate_topic
    from packages.db.models.learning.topic import LearningCluster

    ai_config = get_ai_config()

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
    parser = argparse.ArgumentParser(
        description="Seed learning OS data (os-taxonomy or beijing sources)"
    )
    parser.add_argument(
        "--source",
        choices=[SOURCE_OSTAX, SOURCE_BEIJING],
        default=SOURCE_OSTAX,
        help="Taxonomy source to seed from (default: os-taxonomy)",
    )
    parser.add_argument(
        "--data-dir", type=Path, default=None, help="Custom data directory (default per source)"
    )
    parser.add_argument(
        "--dedup-mapping",
        type=Path,
        default=None,
        help="Path to dedup_mapping.json (default: search Beijing data root)",
    )
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
    parser.add_argument(
        "--mvp-only",
        action="store_true",
        help="Select and validate MVP topic subset (60-90 topics, 3 subjects)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print MVP selection without modifying the database",
    )
    args = parser.parse_args()

    # Resolve the data dir based on source
    if args.source == SOURCE_BEIJING:
        beijing_dir = args.data_dir
        if beijing_dir is None:
            beijing_dir = Path(
                os.environ.get(
                    "BEIJING_TAXONOMY_DIR",
                    Path(__file__).parent.parent
                    / "data"
                    / "os-taxonomy-beijing"
                    / "data",
                )
            )
        if not beijing_dir.is_dir():
            print(f"Error: Beijing data directory {beijing_dir} does not exist")
            raise SystemExit(1)
    else:
        beijing_dir = None
        if args.data_dir is not None:
            ostax_dir = args.data_dir
            if not ostax_dir.is_dir():
                print(f"Error: os-taxonomy data directory {ostax_dir} does not exist")
                raise SystemExit(1)
        else:
            ostax_dir = DEFAULT_DATA_DIR

    # Load dedup mapping (Beijing only)
    dedup_mapping = None
    if args.source == SOURCE_BEIJING:
        if args.dedup_mapping is not None:
            if not args.dedup_mapping.is_file():
                print(f"Error: dedup mapping file {args.dedup_mapping} not found")
                raise SystemExit(1)
            with open(args.dedup_mapping, encoding="utf-8") as f:
                dedup_mapping = json.load(f)
        else:
            dedup_mapping = load_dedup_mapping(beijing_dir)

    version = get_taxonomy_version(
        beijing_dir if args.source == SOURCE_BEIJING else ostax_dir
    )
    print(f"{args.source} version: {version}")

    from apps.backend.app.database import SessionLocal

    session = SessionLocal()
    try:
        if args.source == SOURCE_BEIJING:
            print(f"Seeding {args.source} topics...")
            seeded, created, deprecated = seed_source_topics(
                session, args.source, beijing_dir, dedup_mapping
            )
            print(f"Seeding {args.source} dependencies...")
            deps_created = seed_source_dependencies(
                session, args.source, beijing_dir, dedup_mapping
            )
            print(f"Seeding {args.source} clusters...")
            clusters_created = seed_source_clusters(session, args.source, beijing_dir)
            session.commit()

            # Summary (U5 requirement)
            merges = 0
            if dedup_mapping:
                _, _ = build_dedup_views(dedup_mapping)
                merges = sum(
                    1 for m in dedup_mapping if m.get("action") == "merge"
                )
            print("\n=== Seed Summary ===")
            print(f"  Topics seeded          : {seeded}")
            print(f"  Topics deprecated      : {deprecated} (dedup hides + merges)")
            print(f"  Dependencies seeded    : {deps_created}")
            print(f"  Clusters seeded        : {clusters_created}")
            print(f"  Dedup merges applied   : {merges}")

        else:
            print(f"Seeding {args.source} topics...")
            seed_topics(session, ostax_dir)
            print(f"Seeding {args.source} dependencies...")
            seed_dependencies(session, ostax_dir)
            print(f"Seeding {args.source} clusters...")
            seed_clusters(session, ostax_dir)
            session.commit()

        if not args.skip_translation:
            asyncio.run(
                seed_topic_translations(
                    session, args.batch_size, args.force_retranslate
                )
            )
            asyncio.run(seed_cluster_translations(session))

        print("Done!")

        if not args.skip_validate:
            validate_quality(session)

        if args.mvp_only:
            print("\n=== MVP Topic Curation ===")
            mvp_ids = select_mvp_topics(session)
            errors = validate_mvp_curation(session, mvp_ids)

            # Per-subject breakdown
            from packages.db.models.learning.topic import LearningTopic
            mvp_topics = session.query(LearningTopic).filter(LearningTopic.id.in_(mvp_ids)).all()
            subject_counts: Counter = Counter()
            for t in mvp_topics:
                subject_counts[t.subject] += 1
            print(f"  Total MVP topics: {len(mvp_ids)}")
            for subj in sorted(subject_counts):
                print(f"    {subj}: {subject_counts[subj]}")

            if errors:
                print("\n  Validation ERRORS:")
                for err in errors:
                    print(f"    ❌ {err}")
            else:
                print("\n  ✅ MVP curation validation passed")

            if args.dry_run:
                # Export to JSON for review
                output_path = (
                    beijing_dir if args.source == SOURCE_BEIJING else ostax_dir
                )
                mvp_data = {
                    "topic_ids": sorted(mvp_ids),
                    "total": len(mvp_ids),
                    "subjects": dict(subject_counts),
                    "taxonomy_version": version,
                }
                with open(output_path / "mvp_topics.json", "w") as f:
                    json.dump(mvp_data, f, indent=2, ensure_ascii=False)
                print(f"\n  MVP topic list exported to {output_path / 'mvp_topics.json'}")
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()
