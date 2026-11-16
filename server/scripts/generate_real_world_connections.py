"""Generate real-world connections for learning topics using LLM.

Generates 2-3 real-world scenarios per topic showing how the knowledge
is used in everyday life. Results are persisted to the DB.

Usage:
    cd server
    # Requires env vars: AI_PROVIDER, AI_API_KEY, AI_MODEL (or use --provider/--api-key/--model)
    uv run python scripts/generate_real_world_connections.py [--batch-size 20] [--dry-run]
    uv run python scripts/generate_real_world_connections.py --topic-ids 123,456,789
    uv run python scripts/generate_real_world_connections.py --quarterly-refresh  # 10% sample
    uv run python scripts/generate_real_world_connections.py --export-json /tmp/rwc.json
"""

import argparse
import asyncio
import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from packages.core.logging import get_logger

logger = get_logger(__name__)

SYSTEM_PROMPT = """You are an educational content creator who helps children understand \
how school knowledge connects to real life. For each topic, generate 2-3 vivid, \
age-appropriate real-world scenarios that show why this knowledge matters.

Rules:
- Use concrete, relatable examples (food, games, shopping, sports, nature, family)
- Match the age group: "low" = ages 5-8, "mid" = ages 9-12, "high" = ages 13+
- Each scenario should have a short context (where/when) and explanation (how the knowledge applies)
- Be culturally diverse and inclusive
- Avoid abstract or adult-only scenarios (e.g., taxes, mortgages for young kids)
- Language: Generate in {language}

Output JSON format:
[
  {{
    "context": "Short scenario title (e.g., 'Baking a cake')",
    "explanation": "How this knowledge is used in this scenario (1-2 sentences)",
    "icon": "optional lucide icon name (e.g., 'chef-hat', 'shopping-cart', 'music')"
  }}
]"""

USER_PROMPT = """Topic: {name}
Subject: {subject}
Domain: {domain}
Age group: {age_group}
Description: {description}

Generate 2-3 real-world connections for this topic. Output only the JSON array."""


def _parse_llm_json(raw: str) -> list | dict | None:
    """Parse LLM JSON output, stripping markdown fences if present."""
    text = raw.strip()
    # Strip markdown code fences
    if text.startswith("```"):
        first_nl = text.index("\n") if "\n" in text else 3
        text = text[first_nl + 1:]
    if text.endswith("```"):
        text = text[:-3].strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def _get_llm(provider: str, api_key: str, model: str, base_url: str | None = None):
    from apps.agent.core.llm import get_llm_client

    return get_llm_client(
        provider=provider,
        api_key=api_key,
        model_id=model,
        base_url=base_url,
        timeout=60.0,
    )


async def generate_connections_for_topic(
    llm,
    topic_dict: dict,
    language: str = "English",
) -> list[dict] | None:
    """Generate real-world connections for a single topic via LLM."""
    system = SYSTEM_PROMPT.format(language=language)
    user = USER_PROMPT.format(
        name=topic_dict.get("name", ""),
        subject=topic_dict.get("subject", ""),
        domain=topic_dict.get("domain", ""),
        age_group=topic_dict.get("age_group", "mid"),
        description=(topic_dict.get("description", "") or "")[:300],
    )

    try:
        raw = await llm.complete_json(user, max_tokens=500, system=system)
        parsed = _parse_llm_json(raw)
        if isinstance(parsed, list) and len(parsed) > 0:
            return parsed[:3]
    except Exception:
        logger.exception("LLM generation failed for topic %s", topic_dict.get("id"))
    return None


async def generate_zh_connections(llm, en_connections: list[dict]) -> list[dict] | None:
    """Translate English real-world connections to Chinese."""
    system = (
        "You are a translator. Translate each real-world scenario to natural, "
        "child-friendly Chinese. Keep the JSON structure. Output only the JSON array."
    )
    user = json.dumps(en_connections, ensure_ascii=False)

    try:
        raw = await llm.complete_json(user, max_tokens=500, system=system)
        parsed = _parse_llm_json(raw)
        if isinstance(parsed, list) and len(parsed) > 0:
            return parsed
    except Exception:
        logger.exception("Translation failed")
    return None


async def process_batch(
    llm,
    topics: list[dict],
    language: str,
) -> list[dict]:
    """Process a batch of topics, generating connections for each."""
    results = []
    for topic in topics:
        logger.info("Generating for topic %s: %s", topic["id"], topic.get("name", ""))
        connections = await generate_connections_for_topic(llm, topic, language)
        if connections:
            zh_connections = None
            if language == "English":
                zh_connections = await generate_zh_connections(llm, connections)

            result = {
                "id": topic["id"],
                "real_world_connections": connections,
                "real_world_connections_zh": zh_connections,
            }
            results.append(result)
            logger.info("  -> %d connections generated", len(connections))
        else:
            logger.warning("  -> Failed to generate for topic %s", topic["id"])
    return results


def save_to_db(results: list[dict], dry_run: bool = False) -> None:
    """Persist generated connections to the database."""
    if dry_run:
        logger.info("[DRY RUN] Would save %d results", len(results))
        return

    from packages.db.models.learning.topic import LearningTopic
    from packages.db.session import SessionLocal

    db = SessionLocal()
    try:
        for result in results:
            topic = db.query(LearningTopic).filter(LearningTopic.id == result["id"]).first()
            if topic:
                topic.real_world_connections_json = json.dumps(
                    result["real_world_connections"], ensure_ascii=False
                )
                if result.get("real_world_connections_zh"):
                    topic.real_world_connections_zh_json = json.dumps(
                        result["real_world_connections_zh"], ensure_ascii=False
                    )
        db.commit()
        logger.info("Saved %d results to database", len(results))
    except Exception:
        db.rollback()
        logger.exception("Failed to save results")
    finally:
        db.close()


async def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate real-world connections for learning topics"
    )
    parser.add_argument("--batch-size", type=int, default=20, help="Topics per batch")
    parser.add_argument("--dry-run", action="store_true", help="Generate but don't save")
    parser.add_argument("--topic-ids", type=str, help="Comma-separated topic IDs")
    parser.add_argument(
        "--quarterly-refresh",
        action="store_true",
        help="Refresh 10%% of topics (random sample)",
    )
    parser.add_argument("--language", type=str, default="English", help="Generation language")
    parser.add_argument("--export-json", type=str, help="Export to JSON file instead of DB")
    parser.add_argument("--provider", type=str, help="LLM provider (or AI_PROVIDER env)")
    parser.add_argument("--api-key", type=str, help="LLM API key (or AI_API_KEY env)")
    parser.add_argument("--model", type=str, help="LLM model (or AI_MODEL env)")
    parser.add_argument("--base-url", type=str, help="LLM base URL (or AI_BASE_URL env)")
    args = parser.parse_args()

    import os

    provider = args.provider or os.environ.get("AI_PROVIDER", "openai_compatible")
    api_key = args.api_key or os.environ.get("AI_API_KEY", "")
    model = args.model or os.environ.get("AI_MODEL", "")
    base_url = args.base_url or os.environ.get("AI_BASE_URL")

    if not api_key or not model:
        logger.error("Set --api-key/--model or AI_API_KEY/AI_MODEL env vars")
        sys.exit(1)

    llm = _get_llm(provider, api_key, model, base_url)

    from packages.db.models.learning.topic import LearningTopic
    from packages.db.session import SessionLocal

    db = SessionLocal()
    try:
        query = db.query(LearningTopic).filter(LearningTopic.deprecated == False)  # noqa: E712

        if args.topic_ids:
            ids = [int(x.strip()) for x in args.topic_ids.split(",") if x.strip()]
            query = query.filter(LearningTopic.id.in_(ids))
        elif args.quarterly_refresh:
            query = query.filter(LearningTopic.real_world_connections_json.isnot(None))
            all_ids = [r.id for r in query.all()]
            sample_size = max(1, len(all_ids) // 10)
            sampled_ids = random.sample(all_ids, sample_size)
            query = query.filter(LearningTopic.id.in_(sampled_ids))
        else:
            query = query.filter(LearningTopic.real_world_connections_json.is_(None))

        topics = query.limit(args.batch_size).all()

        if not topics:
            logger.info("No topics to process")
            return

        logger.info("Processing %d topics...", len(topics))

        topic_dicts = [
            {
                "id": t.id,
                "name": t.name or "",
                "subject": t.subject,
                "domain": t.domain or "",
                "age_group": t.age_group,
                "description": t.description or "",
            }
            for t in topics
        ]

        results = await process_batch(llm, topic_dicts, args.language)

        if args.export_json:
            with open(args.export_json, "w", encoding="utf-8") as f:
                json.dump(results, f, ensure_ascii=False, indent=2)
            logger.info("Exported %d results to %s", len(results), args.export_json)
        else:
            save_to_db(results, args.dry_run)

    finally:
        db.close()


if __name__ == "__main__":
    asyncio.run(main())
