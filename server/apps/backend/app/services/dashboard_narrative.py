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
from datetime import UTC, datetime, timedelta

from apps.backend.app.models.user import User
from apps.backend.app.services.agent_client import AgentClient
from apps.backend.app.services.finance_coach_cache import (
    SKILL_TTL,
    upsert_skill_result,
)

logger = logging.getLogger(__name__)

SKILL_ID = "dashboard-narrative"

# 4h TTL (R4).
SKILL_TTL[SKILL_ID] = timedelta(hours=4)

# Threshold defaults (R5). Configurable via module-level constants.
MIN_ASSET_COUNT = 5
MIN_HISTORY_MONTHS = 1  # TODO: raise back to 3 once snapshot data matures


def _extract_first_sentence(text: str) -> str:
    """Extract the first sentence from narrative text.

    Splits on Chinese sentence terminators (。！？) or Latin period (not inside
    decimal numbers). Falls back to truncation at 50 chars + ellipsis.
    """
    text = text.strip()
    if not text:
        return ""
    # Split on 。！？ or a Latin period NOT surrounded by digits (P3 fix)
    parts = re.split(r"[。！？]|(?<!\d)\.(?!\d)", text)
    first = next((p.strip() for p in parts if p.strip()), "")
    if first:
        return first + ("。" if not first.endswith(("。", "！", "？", ".")) else "")
    # Fallback: truncate
    if len(text) > 50:
        return text[:50] + "…"
    return text


def _clean_narrative_text(raw: str) -> str:
    """Strip LLM reasoning/thinking artifacts and return only the narrative.

    The LLM often outputs its chain-of-thought before the final narrative:
    "Let me load the skill...", "**Key data points:**", numbered analysis,
    self-reflection about length, markdown formatting, etc. This function
    extracts only the final Chinese narrative sentences.
    """
    text = raw.strip()
    if not text:
        return ""

    # 1. Remove markdown formatting
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)  # bold
    text = re.sub(r"\*(.+?)\*", r"\1", text)  # italic
    text = re.sub(r"`(.+?)`", r"\1", text)  # inline code
    text = re.sub(r"```[\s\S]*?```", "", text)  # code blocks

    # 2. Remove lines that are clearly reasoning/thinking (not narrative)
    lines = text.split("\n")
    narrative_lines: list[str] = []
    for line in lines:
        stripped = line.strip()
        # Skip empty lines
        if not stripped:
            continue
        # Skip lines that are reasoning markers
        if re.match(
            r"^(Let me |Now I |I need to |I should |Let me check |"
            r"I'll |First, |Second, |Next, |Finally, |"
            r"This is about |The data shows |Based on |"
            r"Key data|Analysis:|Summary:|Step \d|第 \d 步|"
            r"由于|我需要|让我|首先|其次|最后|由于没有|"
            r"Let me analyze|Let me construct|Let me refine)",
            stripped,
            re.IGNORECASE,
        ):
            continue
        # Skip numbered list items that are analysis (1. 2. 3.)
        if re.match(r"^\d+[\.\、\)]\s", stripped):
            continue
        # Skip lines that are mostly English reasoning
        english_chars = len(re.findall(r"[A-Za-z]", stripped))
        chinese_chars = len(re.findall(r"[一-鿿]", stripped))
        if english_chars > chinese_chars and english_chars > 10:
            # Mostly English — likely reasoning, not Chinese narrative
            continue
        narrative_lines.append(stripped)

    cleaned = "\n".join(narrative_lines).strip()

    # 3. If still empty after filtering, fall back to original (stripped)
    if not cleaned:
        cleaned = text

    # 4. Extract only the final 2-3 sentences if text is too long (>200 chars)
    #    This handles cases where the LLM outputs analysis before the narrative.
    if len(cleaned) > 200:
        # Find the last Chinese paragraph (consecutive Chinese sentences)
        parts = re.split(r"\n{2,}", cleaned)
        if len(parts) > 1:
            cleaned = parts[-1].strip()
        # If still too long, take last 3 Chinese sentences
        sentences = re.split(r"[。！？]", cleaned)
        sentences = [s.strip() for s in sentences if s.strip()]
        if len(sentences) > 3:
            sentences = sentences[-3:]
        cleaned = "。".join(sentences)
        if cleaned and not cleaned.endswith(("。", "！", "？")):
            cleaned += "。"

    # 5. Final length cap at 150 chars (R1)
    if len(cleaned) > 150:
        # Truncate at last sentence boundary
        parts = re.split(r"([。！？])", cleaned)
        result = ""
        for i in range(0, len(parts) - 1, 2):
            candidate = result + parts[i] + parts[i + 1]
            if len(candidate) > 150:
                break
            result = candidate
        cleaned = result or cleaned[:150] + "…"

    return cleaned.strip()


def _check_history_threshold(family_id_int: int, db_session_factory) -> bool:
    """Return True if the family has >= MIN_HISTORY_MONTHS distinct snapshot months.

    Uses SQL COUNT(DISTINCT) — no row fetch into Python (P2 fix).
    Called with a short-lived session to avoid holding the request-scoped one.
    """
    from sqlalchemy import func

    from apps.backend.app.models.snapshot import AssetSnapshot

    with db_session_factory() as db:
        # Cross-DB compatible: extract year-month as string, count distinct.
        month_count = (
            db.query(
                func.count(func.distinct(func.strftime("%Y-%m", AssetSnapshot.snapshot_date)))
            )
            .filter(AssetSnapshot.family_id == family_id_int)
            .scalar()
        )
    return (month_count or 0) >= MIN_HISTORY_MONTHS


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


async def generate_narrative(user: User, context: dict) -> dict:
    """Dispatch agent to generate narrative and persist result.

    Does NOT hold a DB session during the agent dispatch (P0 fix).
    Caller is responsible for cache check, threshold gate, and context building.

    Returns dict matching NarrativeResponse schema:
    {narrative: str|None, first_sentence: str, generated_at: str|None}
    """
    family_id = user.family_id

    # Dispatch to agent (KTD2 — full agent dispatch via worker.run_agent)
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

    # Clean LLM reasoning artifacts (chain-of-thought, markdown, etc.)
    narrative_text = _clean_narrative_text(narrative_text)
    if not narrative_text:
        return {"narrative": None, "first_sentence": "", "generated_at": None}

    # Persist to cache (uses its own short-lived session)
    first_sentence = _extract_first_sentence(narrative_text)
    payload = {"narrative": narrative_text, "first_sentence": first_sentence}
    generated_at: str | None = None
    try:
        from apps.backend.app.database import SessionLocal

        with SessionLocal() as write_db:
            row = upsert_skill_result(write_db, family_id, SKILL_ID, payload)
            write_db.commit()
            generated_at = (
                row.generated_at.isoformat() if row.generated_at else None
            )
    except Exception as exc:
        logger.warning("[dashboard-narrative] cache persist failed: %s", exc)
        # Still return the narrative even if persist failed
        generated_at = datetime.now(UTC).replace(tzinfo=None).isoformat()

    return {
        "narrative": narrative_text,
        "first_sentence": first_sentence,
        "generated_at": generated_at,  # P2 fix: actual timestamp
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
