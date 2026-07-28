"""U5: Weekly literacy report generation service.

Aggregates passive signals (chores, coins, scenario choices, badges) for a child
over a given week, asks the LLM for a narrative, and persists a
``LiteracyWeeklyReport`` record.

Idempotent: at most one report per (child_id, week_start).
"""
from __future__ import annotations

import json
import logging
from datetime import date, datetime, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from packages.db.models.literacy_badge import LiteracyBadge, LiteracyBadgeDefinition
from packages.db.models.literacy_report import LiteracyWeeklyReport
from packages.db.models.literacy_scenario import LiteracyScenario
from packages.db.models.user import User

logger = logging.getLogger(__name__)


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
    """Map a child's birthday to an age group: low (5-7), mid (8-10), high (11+)."""
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


# ---------------------------------------------------------------------------
# Signal aggregation
# ---------------------------------------------------------------------------


def _aggregate_signals(db: Session, child_id: int, week_start: date) -> dict[str, Any]:
    """Aggregate passive signals for the child during [week_start, week_start+7).

    Returns a dict with chore, coin, scenario, and badge data.
    """
    week_end = week_start + timedelta(days=7)
    ws_dt = datetime.combine(week_start, datetime.min.time())
    we_dt = datetime.combine(week_end, datetime.min.time())

    # -- Chore completion rate --
    from apps.backend.app.models.chore import ChoreInstance

    total_chores = (
        db.execute(
            select(func.count(ChoreInstance.id)).where(
                ChoreInstance.child_user_id == child_id,
                ChoreInstance.created_at >= ws_dt,
                ChoreInstance.created_at < we_dt,
            )
        ).scalar()
    ) or 0

    approved_chores = (
        db.execute(
            select(func.count(ChoreInstance.id)).where(
                ChoreInstance.child_user_id == child_id,
                ChoreInstance.status == "approved",
                ChoreInstance.created_at >= ws_dt,
                ChoreInstance.created_at < we_dt,
            )
        ).scalar()
    ) or 0

    chore_completion_rate = (
        round(approved_chores / total_chores, 2) if total_chores > 0 else 0.0
    )

    # -- Coin earn/spend --
    from apps.backend.app.models.coin_transaction import CoinTransaction

    coin_earned = (
        db.execute(
            select(func.coalesce(func.sum(CoinTransaction.amount), 0)).where(
                CoinTransaction.child_user_id == child_id,
                CoinTransaction.amount > 0,
                CoinTransaction.created_at >= ws_dt,
                CoinTransaction.created_at < we_dt,
            )
        ).scalar()
    ) or 0

    coin_spent = abs(
        (
            db.execute(
                select(func.coalesce(func.sum(CoinTransaction.amount), 0)).where(
                    CoinTransaction.child_user_id == child_id,
                    CoinTransaction.amount < 0,
                    CoinTransaction.created_at >= ws_dt,
                    CoinTransaction.created_at < we_dt,
                )
            ).scalar()
        )
        or 0
    )

    # -- Scenario completion --
    scenario_completed = (
        db.execute(
            select(func.count(LiteracyScenario.id)).where(
                LiteracyScenario.child_id == child_id,
                LiteracyScenario.week_start == week_start,
                LiteracyScenario.completed_at.is_not(None),
            )
        ).scalar()
    ) or 0

    # -- Badge changes (badges earned this week) --
    badges_earned = (
        db.execute(
            select(LiteracyBadgeDefinition.name, LiteracyBadgeDefinition.dimension)
            .join(
                LiteracyBadge,
                LiteracyBadge.definition_id == LiteracyBadgeDefinition.id,
            )
            .where(
                LiteracyBadge.child_id == child_id,
                LiteracyBadge.earned_at >= ws_dt,
                LiteracyBadge.earned_at < we_dt,
            )
        ).all()
    )

    return {
        "chores_total": total_chores,
        "chores_approved": approved_chores,
        "chore_completion_rate": chore_completion_rate,
        "coin_earned": int(coin_earned),
        "coin_spent": int(coin_spent),
        "scenario_completed": scenario_completed > 0,
        "badges_earned": [
            {"name": name, "dimension": dim} for name, dim in badges_earned
        ],
    }


# ---------------------------------------------------------------------------
# LLM narrative generation
# ---------------------------------------------------------------------------


async def _build_report_narrative(
    family_id: int,
    child_id: int,
    signals: dict[str, Any],
    age_group: str,
) -> str:
    """Call AgentClient to generate an AI narrative from the aggregated signals.

    Returns the narrative text, or a fallback string on any error.
    """
    fallback = _build_fallback_narrative(signals)

    try:
        from apps.backend.app.services.agent_client import AgentClient
    except Exception:
        logger.warning("literacy_report: AgentClient import failed, using fallback")
        return fallback

    age_label = {"low": "5-7岁", "mid": "8-10岁", "high": "11岁以上"}.get(
        age_group, "8-10岁"
    )

    prompt = (
        "你是一位温暖的家庭财商教练。请根据以下数据，为家长撰写一段简短的"
        "（3-5句话）周报告，描述孩子这一周在财商启蒙方面的表现和成长。\n\n"
        f"孩子年龄段：{age_label}\n"
        f"本周家务完成情况：{signals['chores_approved']}/{signals['chores_total']}"
        f"（完成率 {signals['chore_completion_rate'] * 100:.0f}%）\n"
        f"本周获得星星币：{signals['coin_earned']} 枚\n"
        f"本周花费星星币：{signals['coin_spent']} 枚\n"
        f"本周是否完成启蒙场景：{'是' if signals['scenario_completed'] else '否'}\n"
        f"本周获得徽章：{', '.join(b['name'] for b in signals['badges_earned']) or '无'}\n\n"
        "请用中文输出，语气温和鼓励，只输出叙述正文，不要标题或附加解释。"
    )

    body = {"prompt": prompt, "max_tokens": 256, "temperature": 0.7}
    client = AgentClient(family_id=family_id, user_id=child_id, timeout=45.0)

    try:
        resp = await client.post("/suggest/asset", json=body)
        resp.raise_for_status()
        payload = resp.json()
    except Exception:
        logger.warning("literacy_report: LLM call failed, using fallback", exc_info=True)
        return fallback

    data = payload.get("data") or payload
    if isinstance(data, dict):
        narrative = data.get("text") or data.get("content") or ""
    elif isinstance(data, str):
        narrative = data
    else:
        return fallback

    narrative = str(narrative).strip()
    return narrative if narrative else fallback


def _build_fallback_narrative(signals: dict[str, Any]) -> str:
    """Generate a minimal narrative without LLM, based purely on signal counts."""
    parts: list[str] = []

    if signals["chores_total"] > 0:
        pct = signals["chore_completion_rate"] * 100
        parts.append(
            f"本周完成了 {signals['chores_approved']}/{signals['chores_total']} 项家务"
            f"（{pct:.0f}%）。"
        )
    else:
        parts.append("本周暂无家务记录。")

    if signals["coin_earned"] > 0:
        parts.append(f"赚取了 {signals['coin_earned']} 枚星星币。")
    if signals["coin_spent"] > 0:
        parts.append(f"花费了 {signals['coin_spent']} 枚星星币。")

    if signals["scenario_completed"]:
        parts.append("完成了本周的财商启蒙场景。")
    else:
        parts.append("还未完成本周的启蒙场景，下周加油哦！")

    if signals["badges_earned"]:
        names = ", ".join(b["name"] for b in signals["badges_earned"])
        parts.append(f"获得了新徽章：{names}！")

    return "".join(parts)


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


async def generate_weekly_report(
    db: Session,
    child: User,
    week_start: date,
) -> LiteracyWeeklyReport:
    """Generate (or return the existing) weekly literacy report for ``child``.

    Idempotent: if a report already exists for this child + week, it is returned
    unchanged.
    """
    # Idempotency check
    existing = db.execute(
        select(LiteracyWeeklyReport).where(
            LiteracyWeeklyReport.child_id == child.id,
            LiteracyWeeklyReport.week_start == week_start,
        )
    ).scalar_one_or_none()
    if existing is not None:
        return existing

    # Aggregate signals
    signals = _aggregate_signals(db, child.id, week_start)
    age_group = _get_age_group(child.birthday, reference=week_start)

    # Build narrative (LLM with fallback)
    narrative = await _build_report_narrative(
        child.family_id, child.id, signals, age_group
    )

    # Build structured report JSON
    report_data = {
        "age_group": age_group,
        "signals": signals,
        "week_start": week_start.isoformat(),
    }
    report_json = json.dumps(report_data, ensure_ascii=False)

    report = LiteracyWeeklyReport(
        child_id=child.id,
        week_start=week_start,
        report_json=report_json,
        narrative=narrative,
    )
    db.add(report)
    db.commit()
    db.refresh(report)
    return report
