#!/usr/bin/env python3
"""Translate os-taxonomy content and update packages/os_taxonomy/ JSON files.

Usage:
    cd server
    # Incremental — translate only new/changed items
    uv run python ../.claude/skills/learning-content-translate/scripts/translate-to-package.py

    # Force retranslate everything
    uv run python ../.claude/skills/learning-content-translate/scripts/translate-to-package.py --force

    # Retranslate specific topics
    uv run python ../.claude/skills/learning-content-translate/scripts/translate-to-package.py \
        --topic-ids mt_AzTrT5ySCx,mt_XbGfVhfiUz

    # Retranslate by subject
    uv run python ../.claude/skills/learning-content-translate/scripts/translate-to-package.py \
        --subject Computing

    # Custom concurrency
    uv run python ../.claude/skills/learning-content-translate/scripts/translate-to-package.py \
        --concurrency 10

What it does:
    1. Loads upstream English data from server/data/os-taxonomy/data/
    2. Loads current translated package from server/packages/os_taxonomy/
    3. Detects which items need translation (new/changed English, or forced)
    4. Translates in parallel via asyncio + translate_topic()
    5. Merges translations back into the package JSON files
    6. Writes updated JSON files atomically
"""

import argparse
import asyncio
import json
import logging
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

# Ensure server packages are importable
SERVER_ROOT = Path(__file__).resolve().parent.parent.parent.parent.parent / "server"
if str(SERVER_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVER_ROOT))

from apps.agent.services.topic_translate import translate_topic
from apps.agent.core.config import get_ai_config

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-5s %(message)s")
logger = logging.getLogger(__name__)

# Paths
UPSTREAM_DIR = SERVER_ROOT / "data" / "os-taxonomy" / "data"
PACKAGE_DIR = SERVER_ROOT / "packages" / "os_taxonomy"

# Translation fields per entity type
TOPIC_EN_FIELDS = ("name", "description", "evidence", "assessmentPrompt")
TOPIC_ZH_FIELDS = ("nameZh", "descriptionZh", "evidenceZh", "assessmentPromptZh")
CLUSTER_EN_FIELDS = ("summary",)
CLUSTER_ZH_FIELDS = ("summaryZh",)

# Retry config
MAX_RETRIES = 3
BACKOFF_BASE = 2.0  # seconds


def load_json(path: Path) -> dict:
    """Load a JSON file."""
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def write_json_atomic(path: Path, data: dict) -> None:
    """Write JSON atomically — write to temp then rename."""
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.rename(path)


def topic_needs_translation(
    upstream_topic: dict,
    current_topic: dict | None,
    force: bool = False,
) -> bool:
    """Check if a topic needs (re)translation."""
    if force:
        return True
    if current_topic is None:
        return True
    # Check if any English content field changed
    for field in TOPIC_EN_FIELDS:
        if upstream_topic.get(field) != current_topic.get(field):
            return True
    return False


def cluster_needs_translation(
    upstream_cluster: dict,
    current_cluster: dict | None,
    force: bool = False,
) -> bool:
    """Check if a cluster needs (re)translation."""
    if force:
        return True
    if current_cluster is None:
        return True
    for field in CLUSTER_EN_FIELDS:
        if upstream_cluster.get(field) != current_cluster.get(field):
            return True
    return False


def build_topic_for_translation(topic: dict) -> dict:
    """Shape an upstream topic dict for translate_topic()."""
    return {
        "name": topic.get("name", ""),
        "description": topic.get("description", ""),
        "evidence": topic.get("evidence", []),
        "assessment_prompt": topic.get("assessmentPrompt", ""),
    }


def build_cluster_for_translation(cluster: dict) -> dict:
    """Shape a cluster for translate_topic() (reuse topic translator)."""
    return {
        "name": f"{cluster['subject']} - {cluster['domain']}",
        "description": cluster.get("summary", ""),
        "evidence": [],
        "assessment_prompt": "",
    }


def apply_topic_translation(topic: dict, translation: dict) -> dict:
    """Merge translation result into a topic dict."""
    result = dict(topic)  # start with upstream EN fields
    result["nameZh"] = translation.get("name_zh", "")
    result["descriptionZh"] = translation.get("description_zh", "")
    result["evidenceZh"] = translation.get("evidence_zh", [])
    result["assessmentPromptZh"] = translation.get("assessment_prompt_zh", "")
    return result


def apply_cluster_translation(cluster: dict, translation: dict) -> dict:
    """Merge translation result into a cluster dict."""
    result = dict(cluster)
    result["summaryZh"] = translation.get("description_zh", "")
    return result


async def translate_with_retry(
    item: dict,
    ai_config: dict,
    label: str,
    semaphore: asyncio.Semaphore,
) -> dict | None:
    """Translate a single item with retry logic.

    Returns the translation dict, or None on failure.
    """
    async with semaphore:
        for attempt in range(MAX_RETRIES):
            try:
                result = await translate_topic(item, ai_config)
                return result
            except Exception as e:
                err_msg = str(e)
                is_transient = any(
                    kw in err_msg.lower()
                    for kw in ("timeout", "429", "rate", "503", "502", "500", "connection")
                )
                if is_transient and attempt < MAX_RETRIES - 1:
                    wait = BACKOFF_BASE ** attempt
                    logger.warning(
                        "Transient error translating %s (attempt %d/%d), "
                        "retrying in %.1fs: %s",
                        label, attempt + 1, MAX_RETRIES, wait, err_msg,
                    )
                    await asyncio.sleep(wait)
                else:
                    logger.error(
                        "Failed to translate %s after %d attempts: %s",
                        label, attempt + 1, err_msg,
                    )
                    return None
    return None


async def translate_topics_parallel(
    topics_to_translate: list[tuple[str, dict]],
    current_by_id: dict[str, dict],
    ai_config: dict,
    concurrency: int,
) -> dict[str, dict]:
    """Translate topics in parallel. Returns {topic_id: translation_dict}."""
    semaphore = asyncio.Semaphore(concurrency)
    results: dict[str, dict] = {}

    async def do_translate(topic_id: str, topic: dict) -> tuple[str, dict | None]:
        shaped = build_topic_for_translation(topic)
        label = f"topic:{topic_id} ({topic.get('name', '?')[:30]})"
        trans = await translate_with_retry(shaped, ai_config, label, semaphore)
        return topic_id, trans

    tasks = [do_translate(tid, t) for tid, t in topics_to_translate]
    total = len(tasks)
    completed = 0

    for coro in asyncio.as_completed(tasks):
        tid, trans = await coro
        completed += 1
        if trans:
            results[tid] = trans
            if completed % 50 == 0 or completed == total:
                logger.info(
                    "Progress: %d/%d topics translated (%d succeeded)",
                    completed, total, len(results),
                )
        else:
            logger.warning("Topic %s translation failed — will keep existing or leave empty", tid)

    return results


async def translate_clusters_parallel(
    clusters_to_translate: list[tuple[str, dict]],
    ai_config: dict,
    concurrency: int,
) -> dict[str, dict]:
    """Translate clusters in parallel. Returns {cluster_key: translation_dict}."""
    semaphore = asyncio.Semaphore(concurrency)
    results: dict[str, dict] = {}

    async def do_translate(key: str, cluster: dict) -> tuple[str, dict | None]:
        shaped = build_cluster_for_translation(cluster)
        label = f"cluster:{key} ({cluster.get('subject', '?')[:20]})"
        trans = await translate_with_retry(shaped, ai_config, label, semaphore)
        return key, trans

    tasks = [do_translate(key, c) for key, c in clusters_to_translate]
    total = len(tasks)
    completed = 0

    for coro in asyncio.as_completed(tasks):
        key, trans = await coro
        completed += 1
        if trans:
            results[key] = trans
        if completed % 20 == 0 or completed == total:
            logger.info("Progress: %d/%d clusters translated", completed, total)

    return results


def get_upstream_commit() -> str:
    """Get the current commit hash of the upstream repo."""
    import subprocess

    upstream_root = SERVER_ROOT / "data" / "os-taxonomy"
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=upstream_root,
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()
    except Exception:
        return "unknown"


def merge_and_write(
    upstream_topics: list[dict],
    upstream_clusters: list[dict],
    upstream_deps: list[dict],
    topic_translations: dict[str, dict],
    cluster_translations: dict[str, dict],
    current_topics_by_id: dict[str, dict],
    current_clusters_by_key: dict[str, dict],
    force: bool,
) -> None:
    """Merge translations into the package structure and write JSON files."""
    commit = get_upstream_commit()

    # --- Topics ---
    merged_topics = []
    translated_count = 0

    for ut in upstream_topics:
        tid = ut["id"]
        current = current_topics_by_id.get(tid)

        if tid in topic_translations:
            # Fresh translation
            merged = apply_topic_translation(ut, topic_translations[tid])
        elif current and not topic_needs_translation(ut, current, force):
            # Unchanged — keep existing translations
            merged = dict(current)
            # Update English fields from upstream (in case non-content fields changed)
            for field in TOPIC_EN_FIELDS:
                if field in ut:
                    merged[field] = ut[field]
            # Also update other upstream fields
            for field in ("type", "subject", "domain", "ageRangeStart", "ageRangeEnd",
                          "centrality", "standards"):
                if field in ut:
                    merged[field] = ut[field]
        elif current:
            # Needs translation but failed — keep old translations as fallback
            merged = apply_topic_translation(ut, {
                "name_zh": current.get("nameZh", ""),
                "description_zh": current.get("descriptionZh", ""),
                "evidence_zh": current.get("evidenceZh", []),
                "assessment_prompt_zh": current.get("assessmentPromptZh", ""),
            })
        else:
            # New topic, translation failed — EN only
            merged = dict(ut)
            merged.update({
                "nameZh": "",
                "descriptionZh": "",
                "evidenceZh": [],
                "assessmentPromptZh": "",
            })

        # Count as translated if all ZH fields present
        if merged.get("nameZh") and merged.get("descriptionZh"):
            translated_count += 1

        merged_topics.append(merged)

    topics_output = {
        "version": "v1",
        "topicCount": len(merged_topics),
        "translatedCount": translated_count,
        "lastSyncedAt": datetime.now(UTC).isoformat(),
        "upstreamCommit": commit,
        "topics": merged_topics,
    }

    # --- Clusters ---
    def cluster_key(c: dict) -> str:
        return f"{c['subject']}|{c['domain']}|{c.get('ageRangeStart', 0)}"

    merged_clusters = []
    cluster_translated = 0

    for uc in upstream_clusters:
        key = cluster_key(uc)
        current = current_clusters_by_key.get(key)

        if key in cluster_translations:
            merged = apply_cluster_translation(uc, cluster_translations[key])
        elif current and not cluster_needs_translation(uc, current, force):
            merged = dict(current)
            merged["summary"] = uc.get("summary", merged.get("summary", ""))
        elif current:
            merged = apply_cluster_translation(uc, {
                "description_zh": current.get("summaryZh", ""),
            })
        else:
            merged = dict(uc)
            merged["summaryZh"] = ""

        if merged.get("summaryZh"):
            cluster_translated += 1

        merged_clusters.append(merged)

    clusters_output = {
        "version": "v1",
        "clusterCount": len(merged_clusters),
        "translatedCount": cluster_translated,
        "lastSyncedAt": datetime.now(UTC).isoformat(),
        "upstreamCommit": commit,
        "clusters": merged_clusters,
    }

    # --- Dependencies ---
    deps_output = {
        "version": "v1",
        "note": "`topicId` depends on `prerequisiteId` (the prerequisite). Directed edges of a DAG.",
        "edgeCount": len(upstream_deps),
        "dependencies": upstream_deps,
    }

    # --- Write atomically ---
    PACKAGE_DIR.mkdir(parents=True, exist_ok=True)
    write_json_atomic(PACKAGE_DIR / "topics.json", topics_output)
    write_json_atomic(PACKAGE_DIR / "clusters.json", clusters_output)
    write_json_atomic(PACKAGE_DIR / "dependencies.json", deps_output)

    logger.info(
        "Wrote package: %d topics (%d translated), %d clusters (%d translated), %d dependencies",
        len(merged_topics), translated_count,
        len(merged_clusters), cluster_translated,
        len(upstream_deps),
    )


async def main() -> None:
    parser = argparse.ArgumentParser(
        description="Translate os-taxonomy content and update packages/os_taxonomy/"
    )
    parser.add_argument(
        "--force", action="store_true",
        help="Retranslate everything, ignoring existing translations",
    )
    parser.add_argument(
        "--topic-ids", type=str, default="",
        help="Comma-separated topic IDs to retranslate",
    )
    parser.add_argument(
        "--cluster-keys", type=str, default="",
        help="Comma-separated cluster keys to retranslate (subject|domain|ageRangeStart)",
    )
    parser.add_argument(
        "--subject", type=str, default="",
        help="Retranslate all topics in a subject (e.g., Computing, Mathematics)",
    )
    parser.add_argument(
        "--concurrency", type=int, default=5,
        help="Max parallel LLM calls (default: 5)",
    )
    args = parser.parse_args()

    # Load upstream data
    if not UPSTREAM_DIR.exists():
        logger.error(
            "Upstream data not found at %s. Run sync-taxonomy.py --init first.",
            UPSTREAM_DIR,
        )
        sys.exit(1)

    upstream_topics_raw = load_json(UPSTREAM_DIR / "topics.json")
    upstream_clusters_raw = load_json(UPSTREAM_DIR / "clusters.json")
    upstream_deps_raw = load_json(UPSTREAM_DIR / "dependencies.json")

    upstream_topics = upstream_topics_raw.get("topics", [])
    upstream_clusters = upstream_clusters_raw.get("clusters", [])
    upstream_deps = upstream_deps_raw.get("dependencies", [])

    logger.info(
        "Upstream: %d topics, %d clusters, %d dependencies",
        len(upstream_topics), len(upstream_clusters), len(upstream_deps),
    )

    # Load current package
    current_topics_raw = load_json(PACKAGE_DIR / "topics.json")
    current_clusters_raw = load_json(PACKAGE_DIR / "clusters.json")

    current_topics = current_topics_raw.get("topics", [])
    current_clusters = current_clusters_raw.get("clusters", [])

    current_topics_by_id = {t["id"]: t for t in current_topics}

    def cluster_key(c: dict) -> str:
        return f"{c['subject']}|{c['domain']}|{c.get('ageRangeStart', 0)}"

    current_clusters_by_key = {cluster_key(c): c for c in current_clusters}

    # Determine what needs translation
    topic_ids_override = set(args.topic_ids.split(",")) if args.topic_ids else set()
    cluster_keys_override = set(args.cluster_keys.split(",")) if args.cluster_keys else set()

    topics_to_translate: list[tuple[str, dict]] = []
    for ut in upstream_topics:
        tid = ut["id"]
        if args.force or tid in topic_ids_override:
            topics_to_translate.append((tid, ut))
        elif args.subject and ut.get("subject") != args.subject:
            continue
        elif topic_needs_translation(ut, current_topics_by_id.get(tid)):
            topics_to_translate.append((tid, ut))

    clusters_to_translate: list[tuple[str, dict]] = []
    for uc in upstream_clusters:
        key = cluster_key(uc)
        if args.force or key in cluster_keys_override:
            clusters_to_translate.append((key, uc))
        elif cluster_needs_translation(uc, current_clusters_by_key.get(key)):
            clusters_to_translate.append((key, uc))

    total_items = len(topics_to_translate) + len(clusters_to_translate)

    if total_items == 0:
        logger.info("Nothing to translate — package is up to date. Use --force to retranslate all.")
        return

    logger.info(
        "Translating %d items: %d topics + %d clusters (concurrency=%d)",
        total_items, len(topics_to_translate), len(clusters_to_translate), args.concurrency,
    )

    # Get AI config
    ai_config = get_ai_config()

    # Translate in parallel
    start = time.monotonic()

    topic_translations = {}
    cluster_translations = {}

    if topics_to_translate:
        logger.info("Translating %d topics...", len(topics_to_translate))
        topic_translations = await translate_topics_parallel(
            topics_to_translate, current_topics_by_id, ai_config, args.concurrency,
        )

    if clusters_to_translate:
        logger.info("Translating %d clusters...", len(clusters_to_translate))
        cluster_translations = await translate_clusters_parallel(
            clusters_to_translate, ai_config, args.concurrency,
        )

    elapsed = time.monotonic() - start
    logger.info(
        "Translation complete: %d/%d topics, %d/%d clusters in %.1fs",
        len(topic_translations), len(topics_to_translate),
        len(cluster_translations), len(clusters_to_translate),
        elapsed,
    )

    # Merge and write
    merge_and_write(
        upstream_topics, upstream_clusters, upstream_deps,
        topic_translations, cluster_translations,
        current_topics_by_id, current_clusters_by_key,
        force=args.force,
    )

    logger.info("Done. Package updated at %s", PACKAGE_DIR)


if __name__ == "__main__":
    asyncio.run(main())
