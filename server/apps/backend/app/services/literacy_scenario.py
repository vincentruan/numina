"""U2: Weekly scenario generation service for the literacy badge system.

Generates a personalized weekly scenario for a child by selecting an appropriate
template (based on age group + growth dimensions + recent history) and enriching
it via a lightweight LLM call through AgentClient. Falls back to a generic
scenario if no template is available or the LLM call fails.

Idempotent: at most one ``LiteracyScenario`` per (child_id, week_start).
"""
from __future__ import annotations

import json
import logging
from datetime import date, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from packages.db.models.literacy_badge import LiteracyBadge, LiteracyBadgeDefinition
from packages.db.models.literacy_scenario import (
    LiteracyScenario,
    LiteracyScenarioTemplate,
)
from packages.db.models.user import User

logger = logging.getLogger(__name__)

ALL_DIMENSIONS = ["earning", "choosing", "waiting", "caring"]

# Fallback content used when no template is available or the LLM call fails.
_FALLBACK_CONTENT: dict[str, Any] = {
    "story": "这周我们一起来想一个小问题：如果你有一块钱，你会怎么用它呢？"
    "可以存起来、花掉、分享给别人，或者想一个办法让它变多。"
    "想一想，然后告诉爸爸妈妈你的想法吧！",
    "choices": [
        {"text": "我会把钱存起来，等需要的时候再用。", "feedback": "储蓄是一种很棒的习惯！"},
        {"text": "我会买一点喜欢的东西。", "feedback": "合理的消费也是一种选择。"},
        {"text": "我会分享给需要帮助的人。", "feedback": "分享让快乐变得更多。"},
        {"text": "我会想办法让它变多。", "feedback": "思考如何让钱增值是很棒的投资思维！"},
    ],
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _sunday_of(d: date) -> date:
    """Return the Sunday that starts the week containing ``d``.

    Python's ``date.weekday()`` returns Mon=0..Sun=6, so days since Sunday is
    ``(weekday + 1) % 7``. For Sunday itself that yields 0.
    """
    days_since_sunday = (d.weekday() + 1) % 7
    return d - timedelta(days=days_since_sunday)


def _get_age_group(birthday: date | None, *, reference: date | None = None) -> str:
    """Map a child's birthday to an age group.

    Returns ``"low"`` (5-7), ``"mid"`` (8-10), or ``"high"`` (11+).
    Returns ``"mid"`` when the birthday is unknown — a reasonable default that
    matches the middle of the target age range.
    """
    if birthday is None:
        return "mid"
    ref = reference or date.today()
    age = ref.year - birthday.year
    if (ref.month, ref.day) < (birthday.month, birthday.day):
        age -= 1
    if age <= 7:
        return "low"
    if age <= 10:
        return "mid"
    return "high"


def _select_template(
    db: Session,
    child_id: int,
    age_group: str,
    *,
    growth_dimensions: list[str] | None = None,
    lookback_weeks: int = 4,
    reference: date | None = None,
) -> LiteracyScenarioTemplate | None:
    """Pick an active template for the child, excluding recently-used ones.

    Preference order:
    1. A template whose dimension is in ``growth_dimensions`` (badge the child
       has not yet earned) — promotes growth where it's needed most.
    2. Any active template for the age group that hasn't been used recently.
    """
    ref = reference or date.today()
    cutoff = ref - timedelta(weeks=lookback_weeks)

    used_template_ids = {
        row[0]
        for row in db.execute(
            select(LiteracyScenario.template_id).where(
                LiteracyScenario.child_id == child_id,
                LiteracyScenario.week_start >= cutoff,
            )
        ).all()
    }

    candidates = (
        db.execute(
            select(LiteracyScenarioTemplate).where(
                LiteracyScenarioTemplate.age_group == age_group,
                LiteracyScenarioTemplate.is_active.is_(True),
                ~LiteracyScenarioTemplate.id.in_(used_template_ids) if used_template_ids else True,  # type: ignore[arg-type]
            )
        )
        .scalars()
        .all()
    )

    if not candidates:
        return None

    if growth_dimensions:
        growth_set = set(growth_dimensions)
        for c in candidates:
            if c.dimension in growth_set:
                return c

    return candidates[0]


def _growth_dimensions(db: Session, child_id: int) -> list[str]:
    """Return dimensions where the child has NOT yet earned any badge."""
    earned_rows = (
        db.execute(
            select(LiteracyBadgeDefinition.dimension)
            .join(LiteracyBadge, LiteracyBadge.definition_id == LiteracyBadgeDefinition.id)
            .where(
                LiteracyBadge.child_id == child_id,
                LiteracyBadge.superseded_at.is_(None),
            )
        )
        .scalars()
        .all()
    )
    earned = set(earned_rows)
    return [d for d in ALL_DIMENSIONS if d not in earned]


# ---------------------------------------------------------------------------
# LLM enrichment
# ---------------------------------------------------------------------------

async def _enrich_with_llm(
    family_id: int,
    child_id: int,
    template: LiteracyScenarioTemplate,
) -> dict[str, Any] | None:
    """Ask the lightweight LLM to personalize the template for the child.

    Returns a dict with ``story`` and ``choices`` on success, or ``None`` if the
    LLM is unavailable / returns invalid data — callers should fall back.
    """
    try:
        from apps.backend.app.services.agent_client import (
            AgentClient,  # deferred import
        )
    except Exception:  # pragma: no cover - import-time failure
        logger.exception("literacy_scenario: failed to import AgentClient")
        return None

    prompt = (
        "你正在为一位小朋友设计一个财商启蒙小场景。请根据下面的故事模板，"
        "输出一个更生动、更适合这个年龄段孩子的故事，并给出 2-4 个选择项和每个选择的反馈。\n\n"
        f"模板故事：\n{template.story_template}\n\n"
        f"模板选择项（参考，可改写）：\n{template.choices_json}\n\n"
        "请用 JSON 输出，格式：{\"story\": \"...\", \"choices\": [{\"text\": \"...\", \"feedback\": \"...\"}]}。"
        "只输出 JSON，不要附加解释。"
    )

    body = {"prompt": prompt, "max_tokens": 512, "temperature": 0.7}
    client = AgentClient(family_id=family_id, user_id=child_id, timeout=45.0)

    try:
        resp = await client.post("/suggest/asset", json=body)
        resp.raise_for_status()
        payload = resp.json()
    except Exception:
        logger.warning("literacy_scenario: LLM call failed, falling back", exc_info=True)
        return None

    data = payload.get("data") or payload
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except (json.JSONDecodeError, TypeError):
            logger.warning("literacy_scenario: LLM returned non-JSON string")
            return None

    if not isinstance(data, dict):
        return None

    story = data.get("story")
    choices = data.get("choices")
    if not story or not isinstance(choices, list) or not choices:
        return None

    return {"story": str(story), "choices": choices}


def _build_fallback_content() -> dict[str, Any]:
    """Return a deep copy of the fallback content so callers can mutate safely."""
    return {
        "story": _FALLBACK_CONTENT["story"],
        "choices": [dict(c) for c in _FALLBACK_CONTENT["choices"]],
    }


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

async def generate_weekly_scenario(
    db: Session,
    child: User,
    *,
    reference: date | None = None,
) -> LiteracyScenario:
    """Generate (or return the existing) weekly scenario for ``child``.

    Idempotent: if a ``LiteracyScenario`` already exists for this child's
    current week, it is returned unchanged.
    """
    ref = reference or date.today()
    week_start = _sunday_of(ref)

    # Idempotency: return existing scenario for this week.
    existing = db.execute(
        select(LiteracyScenario).where(
            LiteracyScenario.child_id == child.id,
            LiteracyScenario.week_start == week_start,
        )
    ).scalar_one_or_none()
    if existing is not None:
        return existing

    age_group = _get_age_group(child.birthday, reference=ref)
    growth_dims = _growth_dimensions(db, child.id)
    template = _select_template(
        db,
        child.id,
        age_group,
        growth_dimensions=growth_dims,
        reference=ref,
    )

    if template is None:
        # No eligible template → generic fallback.
        content = _build_fallback_content()
        scenario = LiteracyScenario(
            child_id=child.id,
            week_start=week_start,
            template_id=None,
            content_json=json.dumps(content, ensure_ascii=False),
        )
        db.add(scenario)
        db.commit()
        db.refresh(scenario)
        return scenario

    # Attempt LLM enrichment; fall back to the raw template on any failure.
    enriched = await _enrich_with_llm(child.family_id, child.id, template)
    if enriched is None:
        # Use the template's story_template + choices_json verbatim.
        try:
            choices = json.loads(template.choices_json)
        except (json.JSONDecodeError, TypeError):
            choices = []
        content = {"story": template.story_template, "choices": choices}
    else:
        content = enriched

    scenario = LiteracyScenario(
        child_id=child.id,
        week_start=week_start,
        template_id=template.id,
        content_json=json.dumps(content, ensure_ascii=False),
    )
    db.add(scenario)
    db.commit()
    db.refresh(scenario)
    return scenario
