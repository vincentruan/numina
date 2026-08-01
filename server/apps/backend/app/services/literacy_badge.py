"""Literacy Badge Evaluation Service (U3).

Evaluates whether a child should unlock a new literacy badge after a scenario
choice or chore approval. Uses a lightweight LLM call to judge whether the
child's recent behavioral signals demonstrate understanding at the next tier.

The 4 dimensions: earning / choosing / waiting / caring.
Each dimension has 3 badge levels. After every trigger event, we re-evaluate
whether the child is ready for the next level in each relevant dimension.

Failure-safe: any error (DB, LLM, network) is caught and logged. The primary
chore-approval / scenario-completion flow must never break because of a badge
evaluation failure.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import desc, func
from sqlalchemy.orm import Session

from packages.db.models.literacy_badge import LiteracyBadge, LiteracyBadgeDefinition
from packages.db.models.literacy_scenario import LiteracyScenario

logger = logging.getLogger(__name__)

# Dimensions and which triggers evaluate them.
ALL_DIMENSIONS = ("earning", "choosing", "waiting", "caring")
_CHORE_ONLY_DIMENSIONS = ("earning",)
MAX_LEVEL = 3


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


async def evaluate_badge_unlocks(
    db: Session,
    child: Any,
    trigger: str,
    scenario: LiteracyScenario | None = None,
) -> list[LiteracyBadge]:
    """Evaluate whether a child should unlock new badges after an event.

    Args:
        db: SQLAlchemy session.
        child: User model instance (must have `.id` and `.family_id`).
        trigger: One of ``"scenario_completed"`` or ``"chore_approved"``.
        scenario: Optional latest LiteracyScenario (for scenario trigger).

    Returns:
        List of newly unlocked ``LiteracyBadge`` records (may be empty).
    """
    try:
        return await _evaluate_impl(db, child, trigger, scenario)
    except Exception:
        logger.exception(
            "Badge evaluation failed for child %s (trigger=%s) — ignoring",
            getattr(child, "id", "?"),
            trigger,
        )
        return []


# ---------------------------------------------------------------------------
# Internal implementation
# ---------------------------------------------------------------------------


async def _evaluate_impl(
    db: Session,
    child: Any,
    trigger: str,
    scenario: LiteracyScenario | None,
) -> list[LiteracyBadge]:
    dimensions = _CHORE_ONLY_DIMENSIONS if trigger == "chore_approved" else ALL_DIMENSIONS

    async def _eval_one(dimension: str) -> LiteracyBadge | None:
        try:
            return await _evaluate_dimension(db, child, dimension, trigger, scenario)
        except Exception:
            logger.exception(
                "Badge evaluation failed for child %s dimension %s — skipping",
                child.id,
                dimension,
            )
            return None

    try:
        results = await asyncio.wait_for(
            asyncio.gather(*[_eval_one(d) for d in dimensions]),
            timeout=30.0,
        )
    except TimeoutError:
        logger.warning("Badge evaluation timed out for child %s", child.id)
        return []

    return [b for b in results if b is not None]


async def _evaluate_dimension(
    db: Session,
    child: Any,
    dimension: str,
    trigger: str,
    scenario: LiteracyScenario | None,
) -> LiteracyBadge | None:
    current_row = _get_current_badge(db, child.id, dimension)
    current = current_row[0] if current_row else None
    current_def = current_row[1] if current_row else None
    current_level = current_def.level if current_def else 0
    if current_level >= MAX_LEVEL:
        return None

    next_def = _get_next_definition(db, current_level, dimension)
    if next_def is None:
        return None

    # Idempotency: if the child already holds this definition, skip.
    existing = (
        db.query(LiteracyBadge)
        .filter(
            LiteracyBadge.child_id == child.id,
            LiteracyBadge.definition_id == next_def.id,
        )
        .first()
    )
    if existing is not None:
        return None

    context = _build_evaluation_context(db, child.id, dimension, trigger, scenario)
    passed = await _evaluate_with_llm(
        family_id=child.family_id,
        child_id=child.id,
        dimension=dimension,
        next_def=next_def,
        context=context,
    )
    if not passed:
        return None

    # Supersede the previous badge in the same dimension (if any).
    now = datetime.now(tz=UTC)
    if current is not None:
        current.superseded_at = now

    source = "scenario" if trigger == "scenario_completed" else "passive"
    new_badge = LiteracyBadge(
        child_id=child.id,
        definition_id=next_def.id,
        earned_at=now,
        superseded_at=None,
        source=source,
    )
    db.add(new_badge)
    db.flush()  # populate new_badge.id for the coin transaction ref_id

    try:
        _credit_badge_coins(db, child, new_badge, next_def)
    except Exception:
        logger.exception(
            "Coin crediting failed for badge %s (child %s) — continuing",
            new_badge.id,
            child.id,
        )

    return new_badge


# ---------------------------------------------------------------------------
# Helpers — DB lookups
# ---------------------------------------------------------------------------


def _get_current_badge(
    db: Session, child_id: int, dimension: str
) -> tuple[LiteracyBadge, LiteracyBadgeDefinition] | None:
    """Return ``(badge, definition)`` for the highest non-superseded badge in
    ``dimension``, or ``None`` if the child holds no active badge there."""
    row = (
        db.query(LiteracyBadge, LiteracyBadgeDefinition)
        .join(
            LiteracyBadgeDefinition,
            LiteracyBadge.definition_id == LiteracyBadgeDefinition.id,
        )
        .filter(
            LiteracyBadge.child_id == child_id,
            LiteracyBadgeDefinition.dimension == dimension,
            LiteracyBadge.superseded_at.is_(None),
        )
        .order_by(desc(LiteracyBadgeDefinition.level))
        .first()
    )
    if row is None:
        return None
    return row[0], row[1]


def _get_next_definition(
    db: Session, current_level: int, dimension: str
) -> LiteracyBadgeDefinition | None:
    """Return the definition for ``dimension`` at ``current_level + 1``."""
    next_level = current_level + 1
    if next_level > MAX_LEVEL:
        return None
    return (
        db.query(LiteracyBadgeDefinition)
        .filter(
            LiteracyBadgeDefinition.dimension == dimension,
            LiteracyBadgeDefinition.level == next_level,
        )
        .first()
    )


# ---------------------------------------------------------------------------
# Helpers — evaluation context
# ---------------------------------------------------------------------------


def _build_evaluation_context(
    db: Session,
    child_id: int,
    dimension: str,
    trigger: str,
    scenario: LiteracyScenario | None,
) -> dict:
    """Aggregate behavioral signals from the last 14 days for the LLM judge."""
    cutoff = datetime.now(tz=UTC) - timedelta(days=14)
    context: dict[str, Any] = {"window_days": 14, "dimension": dimension}

    if dimension == "earning":
        # Count approved chores in window (best proxy we have without a chore model import).
        try:
            from apps.backend.app.models.chore import ChoreInstance

            approved_count = (
                db.query(func.count(ChoreInstance.id))
                .filter(
                    ChoreInstance.child_user_id == child_id,
                    ChoreInstance.status == "approved",
                    ChoreInstance.approved_at >= cutoff,
                )
                .scalar()
                or 0
            )
            context["approved_chores_14d"] = int(approved_count)
        except Exception:
            context["approved_chores_14d"] = 0

    elif dimension == "choosing":
        # Scenarios completed in window (each reflects a choice).
        scenario_count = (
            db.query(func.count(LiteracyScenario.id))
            .filter(
                LiteracyScenario.child_id == child_id,
                LiteracyScenario.completed_at >= cutoff,
            )
            .scalar()
            or 0
        )
        context["scenarios_completed_14d"] = int(scenario_count)

    elif dimension == "waiting":
        # Wish savings progress — count wishes with non-zero saved_amount.
        try:
            from apps.backend.app.models.child_wish import ChildWish

            # ChildWish has no saved_amount column — count all wishes instead.
            saving_count = (
                db.query(func.count(ChildWish.id))
                .filter(
                    ChildWish.child_user_id == child_id,
                )
                .scalar()
                or 0
            )
            context["wishes_saving"] = int(saving_count)
        except Exception:
            context["wishes_saving"] = 0

    elif dimension == "caring":
        # Gift transactions sent = proxy for caring/sharing.
        try:
            from apps.backend.app.models.coin_transaction import CoinTransaction

            gift_count = (
                db.query(func.count(CoinTransaction.id))
                .filter(
                    CoinTransaction.child_user_id == child_id,
                    CoinTransaction.transaction_type == "gift_sent",
                    CoinTransaction.created_at >= cutoff,
                )
                .scalar()
                or 0
            )
            context["gifts_sent_14d"] = int(gift_count)
        except Exception:
            context["gifts_sent_14d"] = 0

    # Attach scenario choice if this evaluation was triggered by scenario completion.
    if trigger == "scenario_completed" and scenario is not None:
        with contextlib.suppress(Exception):
            context["latest_scenario"] = {
                "dimension": _scenario_dimension(db, scenario),
                "choice_index": scenario.choice_index,
                "feedback": scenario.feedback_json,
            }

    return context


def _scenario_dimension(db: Session, scenario: LiteracyScenario) -> str | None:
    """Best-effort lookup of the scenario's dimension via its template."""
    try:
        from packages.db.models.literacy_scenario import LiteracyScenarioTemplate

        if scenario.template_id is None:
            return None

        template = (
            db.query(LiteracyScenarioTemplate.dimension)
            .filter(LiteracyScenarioTemplate.id == scenario.template_id)
            .scalar()
        )
        return str(template) if template is not None else None
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Helpers — LLM judge
# ---------------------------------------------------------------------------


async def _evaluate_with_llm(
    *,
    family_id: int,
    child_id: int,
    dimension: str,
    next_def: LiteracyBadgeDefinition,
    context: dict,
) -> bool:
    """Ask the lightweight LLM whether the child has demonstrated the next tier.

    Returns ``False`` on any error (fail-closed: don't unlock on LLM failure).
    """
    try:
        from apps.backend.app.services.agent_client import AgentClient
    except Exception:
        logger.warning("AgentClient unavailable — skipping badge evaluation")
        return False

    prompt = (
        "你是一位儿童财商素养评估专家。请根据以下行为信号，判断该孩子是否已达到"
        f"【{dimension}】维度第 {next_def.level} 级徽章「{next_def.name}」的标准。\n\n"
        f"徽章标准摘要：{next_def.criteria_summary}\n\n"
        f"行为信号（最近 14 天）：{json.dumps(context, ensure_ascii=False)}\n\n"
        "请仅返回 JSON：{\"unlock\": true 或 false, \"reason\": \"一句话理由\"}。"
    )

    try:
        client = AgentClient(family_id=family_id, user_id=child_id, timeout=45.0)
        resp = await client.post(
            "/suggest/asset",
            json={
                "prompt": prompt,
                "max_tokens": 200,
                "temperature": 0.2,
            },
        )
        if resp.status_code != 200:
            logger.warning(
                "Badge LLM eval returned %s for child %s dim %s",
                resp.status_code,
                child_id,
                dimension,
            )
            return False

        data = resp.json()
        text = _extract_text(data)
        return _parse_unlock(text)
    except Exception:
        logger.exception(
            "Badge LLM eval failed for child %s dim %s — failing closed",
            child_id,
            dimension,
        )
        return False


def _extract_text(data: Any) -> str:
    """Best-effort extraction of text content from various agent response shapes."""
    if isinstance(data, str):
        return data
    if isinstance(data, dict):
        for key in ("content", "text", "suggestion", "result", "message"):
            if key in data and isinstance(data[key], str):
                return str(data[key])
        if "data" in data:
            return _extract_text(data["data"])
    return json.dumps(data, ensure_ascii=False)


def _parse_unlock(text: str) -> bool:
    """Parse the LLM response for ``{"unlock": true}``. Fail-closed on parse error."""
    if not text:
        return False
    # Try to find JSON substring.
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return False
    try:
        obj = json.loads(text[start : end + 1])
    except Exception:
        return False
    return bool(obj.get("unlock")) is True


# ---------------------------------------------------------------------------
# Helpers — coin crediting
# ---------------------------------------------------------------------------


def _credit_badge_coins(
    db: Session,
    child: Any,
    badge: LiteracyBadge,
    definition: LiteracyBadgeDefinition,
) -> None:
    """Credit bonus coins if the family opted in via ``ChildEconomyConfig``."""
    try:
        from apps.backend.app.models.child_economy_config import ChildEconomyConfig
        from apps.backend.app.models.coin_transaction import CoinTransaction
    except Exception:
        return

    config = (
        db.query(ChildEconomyConfig)
        .filter(ChildEconomyConfig.family_id == child.family_id)
        .first()
    )
    if config is None or not config.literacy_badge_coin_enabled:
        return

    amount = int(config.literacy_badge_coin_amount or 0)
    if amount <= 0:
        return

    tx = CoinTransaction(
        family_id=child.family_id,
        child_user_id=child.id,
        amount=amount,
        transaction_type="badge_earn",
        ref_id=badge.id,
        narrative=f"解锁素养徽章: {definition.name}",
        narrative_emoji="🏅",
    )
    db.add(tx)
