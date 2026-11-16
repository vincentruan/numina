"""LLM-assisted hook question generation for the full topic set.

Generates a Socratic curiosity hook question per topic / age group using the
configured LLM, then writes them to ``topic_hook_questions`` for human review.

This is an offline batch job — it is not called at request time. Run it once
per taxonomy refresh:

    cd server
    uv run python scripts/generate_hook_questions.py --dry-run          # preview
    uv run python scripts/generate_hook_questions.py --limit 5          # smoke test
    uv run python scripts/generate_hook_questions.py                    # full run
    uv run python scripts/generate_hook_questions.py --review-pending   # list unreviewed

Design notes
------------
* One LLM call per (topic, age_group) — about 1500 topics × up to 3 groups.
  The script skips topics that already have a row, so it is safe to re-run and
  will resume after an interruption.
* Generated text is marked ``difficulty`` but there is no automatic review
  gate: a human must approve the output before it ships. The
  ``--review-pending`` flag prints everything not yet approved (see
  ``review_status`` below).
* Failures are collected per topic and do not abort the run.

Human review workflow
---------------------
Generated rows land with ``review_status = "pending"``. To approve, flip the
column to ``"approved"`` for the rows you accept (a SQL UPDATE, an admin
screen, or a small script). The child-facing endpoint serves every row, so an
unreviewed row is visible as soon as it is written — run generation against a
staging database if the review must gate publication.

Environment
-----------
Reads the same AI config the agent uses: ``AI_PROVIDER``, ``AI_MODEL_ID``,
``AI_API_KEY``, ``AI_BASE_URL`` (``scripts`` run outside a request context, so
per-family config lookup does not apply — this is a global knowledge-graph
asset, identical for all families).
"""

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from packages.core.logging import get_logger

logger = get_logger(__name__)

#: Age band → prompt guidance. Mirrors LearningTopic.age_group / the
#: low/mid/high bands used by packages.domain.literacy.service._get_age_group.
AGE_BANDS: dict[str, str] = {
    "low": (
        "ages 5-7. Use concrete, sensory, playful language. Reference things a "
        "child that age touches daily (toys, food, their own body, pets). One "
        "short sentence, no more than 20 words. No jargon."
    ),
    "mid": (
        "ages 8-10. Concrete situation first, then one small step of inference. "
        "May reference school, games, or sharing. One or two sentences, no more "
        "than 30 words. Plain words only."
    ),
    "high": (
        "ages 11-14. Frame an abstract 'why does this work / what if it didn't' "
        "question. May use the topic's own vocabulary, but must not state the "
        "answer or define the concept. One or two sentences, no more than 35 words."
    ),
}

SYSTEM_PROMPT = (
    "You write Socratic 'hook' questions that make a child want to explore a "
    "learning topic before it is explained. A hook is NOT a definition, NOT a "
    "learning objective, and NOT a quiz question with a right answer the child "
    "is expected to already know. It is a question a curious child would "
    "genuinely want answered.\n\n"
    "Rules:\n"
    "- Never state the answer or define the topic.\n"
    "- Ask about something concrete the child can picture.\n"
    "- Sound like a person talking to a child, not a textbook.\n"
    "- Use the child's language; avoid assessment vocabulary "
    "('explain', 'identify', 'demonstrate', 'students will').\n"
    "- Output JSON only."
)


def _build_prompt(
    *,
    name: str,
    description: str,
    subject: str,
    domain: str | None,
    age_group: str,
) -> str:
    band = AGE_BANDS[age_group]
    return (
        f"Learning topic: {name}\n"
        f"Subject: {subject}\n"
        f"Domain: {domain or '(none)'}\n"
        f"Topic description (context only — do NOT restate or define it):\n"
        f"{description[:800]}\n\n"
        f"Write one hook question for a child {band}\n\n"
        f"Return JSON with exactly these keys:\n"
        f'  "question_text"    — the hook question in English\n'
        f'  "question_text_zh" — the same question in Simplified Chinese, '
        f"natural for a child (not a literal translation)\n"
        f'  "difficulty"       — one of "easy" | "medium" | "hard"\n'
    )


async def _generate_one(
    client,
    *,
    name: str,
    description: str,
    subject: str,
    domain: str | None,
    age_group: str,
) -> dict | None:
    """Generate one hook question; returns None on LLM/validation failure."""
    import json
    import re

    prompt = _build_prompt(
        name=name,
        description=description,
        subject=subject,
        domain=domain,
        age_group=age_group,
    )
    try:
        raw = await client.complete_json(
            prompt=prompt, max_tokens=600, system=SYSTEM_PROMPT
        )
        # Some providers wrap JSON in a markdown fence despite response_format.
        raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw.strip())
        data = json.loads(raw)
    except Exception as exc:  # noqa: BLE001 — one failure must not abort the batch
        logger.warning("hook generation failed (%s/%s): %s", name, age_group, exc)
        return None

    question = (data.get("question_text") or "").strip()
    if not question:
        logger.warning("hook generation returned empty question (%s/%s)", name, age_group)
        return None

    difficulty = (data.get("difficulty") or "medium").strip().lower()
    if difficulty not in ("easy", "medium", "hard"):
        difficulty = "medium"

    question_zh = (data.get("question_text_zh") or "").strip() or None

    return {
        "question_text": question,
        "question_text_zh": question_zh,
        "difficulty": difficulty,
    }


async def run(
    *,
    dry_run: bool = False,
    limit: int | None = None,
    age_groups: list[str] | None = None,
    only_missing: bool = True,
) -> None:
    from apps.agent.core.llm import LLMClient
    from apps.backend.app.config import settings
    from packages.db.models.learning.hook import TopicHookQuestion
    from packages.db.models.learning.topic import LearningTopic
    from packages.db.session import SessionLocal

    api_key = getattr(settings, "ai_api_key", None)
    if not api_key:
        print("AI_API_KEY is not configured — cannot generate hook questions.")
        return

    client = LLMClient(
        provider=(getattr(settings, "ai_provider", None) or "openai").lower(),
        api_key=api_key,
        model_id=getattr(settings, "ai_model_id", None) or "gpt-4o-mini",
        base_url=getattr(settings, "ai_base_url", None),
        timeout=90.0,
    )
    bands = age_groups or list(AGE_BANDS)

    db = SessionLocal()
    try:
        q = db.query(LearningTopic).filter(LearningTopic.deprecated.is_(False))
        topics = q.all()
        if limit:
            topics = topics[:limit]

        existing: set[tuple[int, str]] = set()
        if only_missing:
            existing = {
                (row.topic_id, row.age_group)
                for row in db.query(
                    TopicHookQuestion.topic_id, TopicHookQuestion.age_group
                ).all()
            }

        todo = [
            (topic, band)
            for topic in topics
            for band in bands
            if (topic.id, band) not in existing
        ]
        print(
            f"{len(topics)} topics, {len(bands)} age bands → "
            f"{len(todo)} generation(s) to run"
            + (" (dry run — nothing written)" if dry_run else "")
        )
        if dry_run:
            for topic, band in todo[:20]:
                print(f"  would generate: {topic.name} / {band}")
            return

        created = 0
        failed = 0
        for idx, (topic, band) in enumerate(todo, start=1):
            result = await _generate_one(
                client,
                name=topic.name or topic.topic_key,
                description=topic.description or "",
                subject=topic.subject,
                domain=topic.domain,
                age_group=band,
            )
            if result is None:
                failed += 1
                continue
            db.add(TopicHookQuestion(topic_id=topic.id, age_group=band, **result))
            created += 1
            if idx % 25 == 0:
                db.commit()
                print(f"  ... {idx}/{len(todo)} (created={created}, failed={failed})")

        db.commit()
        print(f"\nDone — created={created}, failed={failed}, total={len(todo)}")
    finally:
        db.close()


def review_pending() -> None:
    """Print generated rows awaiting human review."""
    from packages.db.models.learning.hook import TopicHookQuestion
    from packages.db.models.learning.topic import LearningTopic
    from packages.db.session import SessionLocal

    db = SessionLocal()
    try:
        rows = (
            db.query(TopicHookQuestion, LearningTopic.name)
            .join(LearningTopic, LearningTopic.id == TopicHookQuestion.topic_id)
            .order_by(LearningTopic.subject, LearningTopic.name)
            .all()
        )
        print(f"{len(rows)} hook question(s):\n")
        for hook, topic_name in rows:
            zh = f"\n      zh: {hook.question_text_zh}" if hook.question_text_zh else ""
            print(f"  [{hook.age_group:4}] {topic_name}")
            print(f"      en: {hook.question_text}{zh}")
    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="preview, write nothing")
    parser.add_argument("--limit", type=int, default=None, help="cap topic count")
    parser.add_argument(
        "--age-group",
        action="append",
        choices=list(AGE_BANDS),
        help="restrict to one or more age groups (repeatable)",
    )
    parser.add_argument(
        "--review-pending",
        action="store_true",
        help="list generated hook questions for human review, then exit",
    )
    args = parser.parse_args()

    if args.review_pending:
        review_pending()
        return

    asyncio.run(
        run(dry_run=args.dry_run, limit=args.limit, age_groups=args.age_group)
    )


if __name__ == "__main__":
    main()
