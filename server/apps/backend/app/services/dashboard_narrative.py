"""Dashboard narrative service (仪表盘叙事卡片).

Generates a 2-3 sentence natural-language narrative explaining the family's
current financial picture. Uses the same skill-scoped cache pattern as
finance_coach_cache.py (latest_by_skill / is_cache_fresh / upsert_skill_result).

4h TTL; CRUD invalidation via invalidate_skill() at asset/liability/wish write
sites (mirrors finance_coach invalidation). Threshold gate: asset_count >= 5
AND snapshot history >= 3 months. Silent degradation on agent failure.

Supports SSE streaming: ``stream_narrative_sse()`` proxies the agent's SSE
events (reasoning_delta, messages, custom, end) to the frontend and persists
the result to cache after the stream completes.
"""
import json
import logging
import re
import uuid
from collections.abc import AsyncGenerator
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
    """Strip LLM reasoning artifacts and return only the clean narrative.

    Delegates to _separate_narrative_and_thinking and returns the narrative.
    Kept for backward compatibility.
    """
    narrative, _ = _separate_narrative_and_thinking(raw)
    return narrative


def _separate_narrative_and_thinking(raw: str) -> tuple[str, str]:
    """Separate LLM output into (clean_narrative, thinking_process).

    Strategy: strip markdown, find the last 2-3 Chinese sentences as narrative,
    everything before that point is thinking. Preserves all content —
    no paragraph-boundary dependency.
    """
    text = raw.strip()
    if not text:
        return "", ""

    # 1. Strip markdown formatting (preserve content)
    cleaned = re.sub(r"\*\*(.+?)\*\*", r"\1", text)  # bold
    cleaned = re.sub(r"\*(.+?)\*", r"\1", cleaned)  # italic
    cleaned = re.sub(r"`(.+?)`", r"\1", cleaned)  # inline code
    cleaned = re.sub(r"```[\s\S]*?```", "", cleaned)  # code blocks
    # Normalize bullet markers but keep content
    cleaned = re.sub(r"^[\-\*]\s+", "• ", cleaned, flags=re.MULTILINE)
    # Normalize whitespace but preserve paragraph breaks
    cleaned = re.sub(r"[ \t]+", " ", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    cleaned = cleaned.strip()

    if not cleaned:
        return "", ""

    # 2. Split into sentences on Chinese terminators AND Latin periods
    #    (Latin period not surrounded by digits, to avoid splitting decimals).
    #    Use finditer instead of re.split to avoid None-group interleaving.
    all_sentences: list[str] = []
    prev = 0
    for m in re.finditer(r"[。！？]|(?<!\d)\.(?!\d)", cleaned):
        seg = cleaned[prev : m.end()].strip()
        if seg:
            all_sentences.append(seg)
        prev = m.end()
    trailing = cleaned[prev:].strip()
    if trailing:
        all_sentences.append(trailing)

    # Filter to Chinese-dominant sentences (≥5 Chinese chars)
    chinese_sentences: list[tuple[int, str]] = []
    for idx, s in enumerate(all_sentences):
        cn = len(re.findall(r"[一-鿿]", s))
        en = len(re.findall(r"[A-Za-z]", s))
        if cn > en and cn >= 5:
            chinese_sentences.append((idx, s))

    # 3. Narrative = last 2-3 Chinese sentences (capped at 150 chars)
    if len(chinese_sentences) >= 2:
        take = min(3, len(chinese_sentences))
        narrative_sentences = [s for _, s in chinese_sentences[-take:]]
        narrative = "".join(narrative_sentences)
        # Cap at 150 chars — drop earliest sentence if too long
        while len(narrative) > 150 and len(narrative_sentences) > 1:
            narrative_sentences.pop(0)
            narrative = "".join(narrative_sentences)
        if len(narrative) > 150:
            narrative = narrative[:150] + "…"

        # 4. Thinking = everything before the narrative's first sentence
        narrative_first_idx = chinese_sentences[-take][0]
        thinking_parts = [all_sentences[i] for i in range(narrative_first_idx)]
        thinking = "".join(thinking_parts).strip()
    elif len(chinese_sentences) == 1:
        # Single Chinese sentence at the end — it's the narrative, rest is thinking
        _, narrative = chinese_sentences[0]
        narrative_first_idx = chinese_sentences[0][0]
        thinking_parts = [all_sentences[i] for i in range(narrative_first_idx)]
        thinking = "".join(thinking_parts).strip()
    else:
        # No Chinese-dominant sentences — entire text is narrative
        narrative = cleaned
        thinking = ""

    return narrative, thinking


def _check_history_threshold(family_id_int: int, db_session_factory, min_months: int | None = None) -> bool:
    """Return True if the family has >= min_months distinct snapshot months.

    Uses SQL COUNT(DISTINCT) — no row fetch into Python (P2 fix).
    Called with a short-lived session to avoid holding the request-scoped one.
    min_months defaults to MIN_HISTORY_MONTHS if not provided.
    """
    from sqlalchemy import func

    from apps.backend.app.models.snapshot import AssetSnapshot

    threshold = min_months if min_months is not None else MIN_HISTORY_MONTHS

    with db_session_factory() as db:
        # Cross-DB compatible: extract year-month as string, count distinct.
        month_count = (
            db.query(
                func.count(func.distinct(
                    func.extract("year", AssetSnapshot.snapshot_date) * 12
                    + func.extract("month", AssetSnapshot.snapshot_date)
                ))
            )
            .filter(AssetSnapshot.family_id == family_id_int)
            .scalar()
        )
    return (month_count or 0) >= threshold


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
    {narrative: str|None, first_sentence: str, thinking: str, generated_at: str|None}
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
        return {"narrative": None, "first_sentence": "", "thinking": "", "generated_at": None}

    if not narrative_text:
        return {"narrative": None, "first_sentence": "", "thinking": "", "generated_at": None}

    # Separate narrative from thinking/reasoning
    narrative_text, thinking_text = _separate_narrative_and_thinking(narrative_text)
    if not narrative_text:
        return {"narrative": None, "first_sentence": "", "thinking": "", "generated_at": None}

    # Persist to cache (uses its own short-lived session)
    first_sentence = _extract_first_sentence(narrative_text)
    payload = {
        "narrative": narrative_text,
        "first_sentence": first_sentence,
        "thinking": thinking_text,
    }
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
        "thinking": thinking_text,
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


async def stream_narrative_sse(
    *, family_id: str, user_id: str, context: dict
) -> AsyncGenerator[bytes, None]:
    """Proxy the agent's dashboard-narrative SSE stream to the frontend.

    Mirrors ``_stream_finance_coach_sse``: calls the agent gateway, forwards
    raw SSE lines, and persists the result to cache after the stream ends.

    The agent emits:
    - ``custom`` events with ``type: "reasoning_delta"`` (thinking chunks)
    - ``messages`` events with ``type: "ai"`` (narrative text chunks)
    - ``custom`` event with ``type: "dashboard_narrative.result"`` (final result)
    - ``end`` event (stream complete)
    """
    agent_client = AgentClient(family_id, user_id, timeout=120.0)
    thread_id = _make_thread_id(family_id)
    agent_url = f"/internal/gateway/runs/dashboard-narrative/{thread_id}"

    try:
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
                    "[dashboard-narrative] agent stream non-200: status=%s body=%s",
                    resp.status_code,
                    body[:200],
                )
                err = json.dumps(
                    {"message": "叙事生成服务异常", "name": "AgentError"}
                ).encode()
                yield f"event: error\ndata: {err.decode()}\n\n".encode()
                return

            collected = b""
            async for line in resp.aiter_lines():
                yield (line + "\n").encode()
                collected += (line + "\n").encode()

            # Persist the result to cache after stream ends
            _persist_narrative_result(family_id, collected)
    except Exception as exc:
        logger.warning(
            "[dashboard-narrative] agent stream failed err=%s", type(exc).__name__
        )
        err = json.dumps(
            {"message": "叙事生成服务中断", "name": type(exc).__name__}
        ).encode()
        yield f"event: error\ndata: {err.decode()}\n\n".encode()


def _persist_narrative_result(family_id: str, collected_sse: bytes) -> None:
    """Extract the dashboard_narrative.result payload and cache it.

    Called after a successful stream. Opens a short-lived session to write
    the result row. Silently no-ops if the result frame is missing.
    """
    try:
        text = collected_sse.decode("utf-8", errors="replace")
        payload = None
        for block in text.split("\n\n"):
            if "dashboard_narrative.result" not in block:
                continue
            for line in block.split("\n"):
                if line.startswith("data: "):
                    try:
                        data = json.loads(line[len("data: "):])
                        if data.get("type") == "dashboard_narrative.result":
                            payload = data.get("payload")
                    except json.JSONDecodeError:
                        continue
        if payload is None:
            logger.info(
                "[dashboard-narrative] no result frame in stream — not caching"
            )
            return

        narrative_text = payload.get("narrative", "")
        thinking_text = payload.get("thinking", "")
        if not narrative_text:
            return

        first_sentence = _extract_first_sentence(narrative_text)
        full_payload = {
            "narrative": narrative_text,
            "first_sentence": first_sentence,
            "thinking": thinking_text,
        }

        from apps.backend.app.database import SessionLocal

        with SessionLocal() as db:
            upsert_skill_result(db, family_id, SKILL_ID, full_payload)
            db.commit()
    except Exception as exc:
        logger.warning("[dashboard-narrative] persist result failed err=%s", exc)
