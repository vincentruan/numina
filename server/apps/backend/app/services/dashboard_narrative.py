"""Dashboard narrative service (仪表盘叙事卡片).

Generates a 2-3 sentence natural-language narrative explaining the family's
current financial picture. Uses the same skill-scoped cache pattern as
finance_coach_cache.py (latest_by_skill / is_cache_fresh / upsert_skill_result).

4h TTL; CRUD invalidation via invalidate_skill() at asset/liability/wish write
sites (mirrors finance_coach invalidation). Threshold gate: asset_count >= 5
AND snapshot history >= 3 months. Silent degradation on agent failure.
"""
import json
import logging
import re
import uuid
from datetime import timedelta

from sqlalchemy.orm import Session

from apps.backend.app.models.user import User
from apps.backend.app.services.agent_client import AgentClient
from apps.backend.app.services.dashboard import get_insights, get_overview
from apps.backend.app.services.finance_coach_cache import (
    SKILL_TTL,
    is_cache_fresh,
    latest_by_skill,
    upsert_skill_result,
)

logger = logging.getLogger(__name__)

SKILL_ID = "dashboard-narrative"

# 4h TTL (R4).
SKILL_TTL[SKILL_ID] = timedelta(hours=4)

# Threshold defaults (R5). Configurable via module-level constants.
MIN_ASSET_COUNT = 5
MIN_HISTORY_MONTHS = 3


def _extract_first_sentence(text: str) -> str:
    """Extract the first sentence from narrative text.

    Splits on Chinese sentence terminators (。！？) or Latin period.
    Falls back to truncation at 50 chars + ellipsis.
    """
    text = text.strip()
    if not text:
        return ""
    parts = re.split(r"[。！？.]", text)
    first = next((p.strip() for p in parts if p.strip()), "")
    if first:
        return first + ("。" if not first.endswith(("。", "！", "？", ".")) else "")
    # Fallback: truncate
    if len(text) > 50:
        return text[:50] + "…"
    return text


def _check_threshold(db: Session, user: User) -> bool:
    """Return True if the family has enough data for a meaningful narrative (R5).

    asset_count >= MIN_ASSET_COUNT AND snapshot history >= MIN_HISTORY_MONTHS.
    """
    overview = get_overview(db, user)
    if overview.asset_count < MIN_ASSET_COUNT:
        return False

    # Check snapshot history: need >= MIN_HISTORY_MONTHS distinct months.
    from apps.backend.app.models.snapshot import AssetSnapshot

    family_id_int = int(user.family_id)
    snapshot_months = (
        db.query(AssetSnapshot.valued_at)
        .filter(AssetSnapshot.family_id == family_id_int)
        .order_by(AssetSnapshot.valued_at.desc())
        .limit(100)
        .all()
    )
    if len(snapshot_months) < MIN_HISTORY_MONTHS:
        return False
    # Check distinct months
    from datetime import datetime

    months = set()
    for (ts,) in snapshot_months:
        if isinstance(ts, datetime):
            months.add((ts.year, ts.month))
        elif ts is not None:
            try:
                dt = datetime.fromisoformat(str(ts))
                months.add((dt.year, dt.month))
            except (ValueError, TypeError):
                pass
    return len(months) >= MIN_HISTORY_MONTHS


def _build_narrative_context(overview, insights) -> dict:
    """Build structured context dict from overview + insights for the LLM prompt.

    Currency-annotated amounts (e.g., "net_worth: 523000 CNY") so the LLM
    generates correct currency references (KTD5).
    """
    currency = getattr(overview, "currency", "CNY")
    liability_ratio = (
        (overview.total_liabilities / overview.total_assets * 100)
        if overview.total_assets > 0
        else 0.0
    )

    ctx: dict = {
        "currency": currency,
        "net_worth": f"{overview.net_worth:.0f} {currency}",
        "total_assets": f"{overview.total_assets:.0f} {currency}",
        "total_liabilities": f"{overview.total_liabilities:.0f} {currency}",
        "asset_count": overview.asset_count,
        "month_over_month_change": overview.month_over_month_change,
        "month_over_month_change_amount": overview.month_over_month_change_amount,
        "liability_ratio": f"{liability_ratio:.1f}%",
        "total_daily_cost": f"{overview.total_daily_cost:.0f} {currency}",
    }

    # Add insights signals if available
    if insights:
        try:
            smart = getattr(insights, "smart_discovery", None)
            if smart and getattr(smart, "items", None):
                ctx["smart_discoveries"] = [
                    {"type": getattr(i, "type", ""), "message": getattr(i, "message", "")}
                    for i in smart.items[:5]
                ]
        except Exception:
            pass
        try:
            inv = getattr(insights, "investment_returns", None)
            if inv:
                ctx["investment_returns"] = {
                    "annualized_rate": getattr(inv, "annualized_rate", None),
                    "asset_count": getattr(inv, "asset_count", 0),
                }
        except Exception:
            pass

    return ctx


async def generate_narrative(db: Session, user: User, force: bool = False) -> dict:
    """Generate or retrieve cached narrative for the family.

    Returns dict matching NarrativeResponse schema:
    {narrative: str|None, first_sentence: str, generated_at: str|None}
    """
    family_id = user.family_id

    # 1. Check cache (R4)
    if not force:
        cached = latest_by_skill(db, family_id, SKILL_ID)
        if is_cache_fresh(cached, SKILL_ID) and cached is not None:
            report = cached.report_json or {}
            narrative = report.get("narrative", "")
            return {
                "narrative": narrative or None,
                "first_sentence": report.get("first_sentence", _extract_first_sentence(narrative)),
                "generated_at": cached.generated_at.isoformat() if cached.generated_at else None,
            }

    # 2. Threshold check (R5)
    if not _check_threshold(db, user):
        return {"narrative": None, "first_sentence": "", "generated_at": None}

    # 3. Build context from existing endpoints (R3 — no new aggregation pipeline)
    try:
        overview = get_overview(db, user)
        insights = get_insights(db, user)
    except Exception as exc:
        logger.warning("[dashboard-narrative] context build failed: %s", exc)
        return {"narrative": None, "first_sentence": "", "generated_at": None}

    context = _build_narrative_context(overview, insights)

    # 4. Dispatch to agent (KTD2 — full agent dispatch via worker.run_agent)
    try:
        narrative_text = await _dispatch_narrative_agent(
            family_id=str(family_id),
            user_id=str(user.id),
            context=context,
        )
    except Exception as exc:
        logger.warning("[dashboard-narrative] agent dispatch failed: %s", type(exc).__name__)
        # Graceful degradation (R2/F3): return empty, not 500
        return {"narrative": None, "first_sentence": "", "generated_at": None}

    if not narrative_text:
        return {"narrative": None, "first_sentence": "", "generated_at": None}

    # 5. Persist to cache
    first_sentence = _extract_first_sentence(narrative_text)
    payload = {"narrative": narrative_text, "first_sentence": first_sentence}
    try:
        from apps.backend.app.database import SessionLocal

        with SessionLocal() as write_db:
            upsert_skill_result(write_db, family_id, SKILL_ID, payload)
            write_db.commit()
    except Exception as exc:
        logger.warning("[dashboard-narrative] cache persist failed: %s", exc)

    return {
        "narrative": narrative_text,
        "first_sentence": first_sentence,
        "generated_at": None,  # caller can re-read from DB if needed
    }


async def _dispatch_narrative_agent(
    *, family_id: str, user_id: str, context: dict
) -> str | None:
    """Call the agent's dashboard-narrative gateway endpoint and parse the result.

    Mirrors _stream_finance_coach_sse but collects and returns the narrative text
    instead of streaming to the client.
    """
    agent_client = AgentClient(family_id, user_id, timeout=120.0)
    agent_url = f"/internal/gateway/runs/dashboard-narrative/{_make_thread_id(family_id)}"

    async with agent_client.stream(
        "POST",
        agent_url,
        json={
            "family_id": family_id,
            "user_id": user_id,
            "input": {
                "messages": [
                    {"role": "user", "content": json.dumps(context, ensure_ascii=False)}
                ]
            },
        },
    ) as resp:
        if resp.status_code != 200:
            body = await resp.aread()
            logger.warning(
                "[dashboard-narrative] agent non-200: status=%s body=%s",
                resp.status_code,
                body[:200],
            )
            return None

        collected = b""
        async for line in resp.aiter_lines():
            collected += (line + "\n").encode()

    # Parse the dashboard_narrative.result custom event
    text = collected.decode("utf-8", errors="replace")
    for block in text.split("\n\n"):
        if "dashboard_narrative.result" not in block:
            continue
        for line in block.split("\n"):
            if line.startswith("data: "):
                try:
                    data = json.loads(line[len("data: "):])
                    if data.get("type") == "dashboard_narrative.result":
                        return data.get("payload", {}).get("narrative")
                except json.JSONDecodeError:
                    continue
    return None


def _make_thread_id(family_id: str) -> str:
    """Generate a unique thread_id for the narrative agent run."""
    return f"dashboard-narrative-{family_id}-{uuid.uuid4().hex[:8]}"
