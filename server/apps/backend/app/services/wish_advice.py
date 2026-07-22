"""W4 wish-priority advice (Plan B T7) — INDEPENDENT of finance_coach.

spec §7.1 coherence c100: W4 output is ``redistribution[]``, NOT finance_coach's
``suggestions[]``. W4 shares only the prompt-template skeleton (家庭财务教练角色),
not the output schema. Separate cache key ``family_id:wish_advice:{fingerprint}``.

LLM call path: W4 runs as a dedicated ``wish-advice`` stream_run capability that
mirrors finance_coach's chain (system-agent + gateway route + worker branch +
SKILL.md). The backend ``generate_advice`` calls the agent gateway via
``AgentClient.stream`` (X-Agent-Token service-to-service auth), consumes the SSE
stream, and extracts the terminal ``wish_advice.result`` frame — the same
frame-parsing pattern finance_coach uses in ``ai_finance_coach._persist_*``.
Unlike finance_coach (which streams SSE to the frontend D2 card), W4's
``generate_advice`` consumes the stream internally and returns the parsed advice
dict so the router can cache + return it as JSON (W4's card reads JSON, not a
live stream).
"""
import hashlib
import json
import logging
import uuid
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from apps.backend.app.models.user import User
from apps.backend.app.models.wish import Wish
from apps.backend.app.services.agent_client import AgentClient

logger = logging.getLogger(__name__)


def wish_fingerprint(wishes: list[Wish]) -> str:
    """Stable hash of the pending wishes' savings-relevant fields.

    The cache key is keyed by this fingerprint so a wish change (new/deleted/
    monthly_saving/target_date/expected_price edit) produces a new fingerprint
    → cache miss → regenerate. (spec §4.4: 心愿变更失效.)
    """
    parts = []
    for w in sorted(wishes, key=lambda x: x.id):
        parts.append(
            f"{w.id}:{w.expected_price}:{w.saved_amount}:{w.monthly_saving}:{w.target_date}:{w.priority}"
        )
    raw = "|".join(parts)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def build_advice_input(db: Session, user: User) -> tuple[list[Wish], str]:
    """Return (pending wishes, fingerprint). Only wishes with a savings plan
    or a target_date are relevant (spec §4.1: ≥2 pending, ≥1 monthly_saving)."""
    wishes = (
        db.query(Wish)
        .filter(Wish.family_id == user.family_id, Wish.status == "pending")
        .order_by(Wish.created_at)
        .all()
    )
    return wishes, wish_fingerprint(wishes)


def validate_advice(payload: dict | None) -> dict | None:
    """Advice baseline gate (spec §7.1): schema-validate + suggested_amount >= 0.

    Returns the payload if valid, else None (caller drops silently + logs).
    Required: primary_wish_id (str), reason (str), suggested_monthly (>=0),
    redistribution (list of {wish_id, suggested_amount >=0, note}).
    """
    if not payload or not isinstance(payload, dict):
        return None
    for k in ("primary_wish_id", "reason", "suggested_monthly", "redistribution"):
        if k not in payload:
            return None
    try:
        sm = Decimal(str(payload["suggested_monthly"]))
    except Exception:
        return None
    if sm < 0:
        return None
    redist = payload["redistribution"]
    if not isinstance(redist, list):
        return None
    for item in redist:
        if not isinstance(item, dict) or "wish_id" not in item or "suggested_amount" not in item:
            return None
        try:
            if Decimal(str(item["suggested_amount"])) < 0:
                return None
        except Exception:
            return None
    return payload


async def generate_advice(db: Session, user: User) -> tuple[dict | None, str]:
    """Run the W4 AI call + validate. Returns (validated_payload, fingerprint).

    Calls the agent gateway ``/internal/gateway/runs/wish-advice/{thread_id}``
    via ``AgentClient.stream`` (X-Agent-Token service-to-service auth). The
    worker (``_run_wish_advice_agent``) drives the single-run advice agent and
    emits exactly one ``wish_advice.result`` custom event with the parsed
    redistribution[] JSON. This function consumes the SSE stream to its terminal
    frame, extracts the payload, and schema-validates it (``validate_advice``).
    On any failure (no provider / parse error / guardrail fail / stream error)
    returns (None, fp) so the router degrades gracefully (200 empty, spec §4.5).
    """
    wishes, fp = build_advice_input(db, user)
    if len(wishes) < 2 or not any((w.monthly_saving or Decimal("0")) > 0 for w in wishes):
        return None, fp  # spec §4.1: don't show the card

    # Build the PII-minimized snapshot injected as the run's user message.
    # wish name IS prompt-required here (the user names wishes and the AI reasons
    # about them by name) — unlike finance_coach's id+category minimization.
    snapshot: dict[str, Any] = {
        "type": "wish_advice",
        "wishes": [
            {
                "id": str(w.id),
                "name": w.name,
                "expected_price": float(w.expected_price or 0),
                "saved_amount": float(w.saved_amount or 0),
                "monthly_saving": float(w.monthly_saving or 0),
                "target_date": str(w.target_date) if w.target_date else None,
                "priority": w.priority,
            }
            for w in wishes
        ],
    }

    thread_id = f"wish-advice-{user.family_id}-{uuid.uuid4().hex[:8]}"
    agent_url = f"/internal/gateway/runs/wish-advice/{thread_id}"
    agent_client = AgentClient(user.family_id, user.id, timeout=300.0)

    try:
        async with agent_client.stream(
            "POST",
            agent_url,
            json={
                "family_id": str(user.family_id),
                "user_id": str(user.id),
                # Inject the snapshot as the run's user message so the worker
                # (_extract_wish_advice_input) picks it up.
                "input": {"messages": [{"role": "user", "content": json.dumps(snapshot, ensure_ascii=False)}]},
            },
        ) as resp:
            if resp.status_code != 200:
                body = await resp.aread()
                logger.warning(
                    "[wish-advice] agent stream non-200: status=%s body=%s",
                    resp.status_code, body[:200],
                )
                return None, fp
            advice = await _extract_wish_advice_result(resp)
        return validate_advice(advice), fp
    except Exception as exc:
        logger.warning("[wish-advice] generate failed err=%s", type(exc).__name__)
        return None, fp


async def _extract_wish_advice_result(resp: Any) -> dict | None:
    """Consume the agent SSE stream and pull out the wish_advice.result payload.

    Mirrors ``ai_finance_coach._persist_finance_coach_result``'s frame parsing:
    SSE frames look like ``event: custom\\ndata: {"type":"wish_advice.result",
    "payload":{...}}\\n\\n``. Returns the payload dict, or None if no result
    frame was emitted (advice baseline: wrong/absent output is dropped, not
    displayed — spec §7.1).
    """
    text = ""
    try:
        async for chunk in resp.aiter_text():
            text += chunk
    except Exception as exc:
        logger.warning("[wish-advice] stream read failed err=%s", type(exc).__name__)
        return None

    for block in text.split("\n\n"):
        if "wish_advice.result" not in block:
            continue
        for line in block.split("\n"):
            if line.startswith("data: "):
                try:
                    data = json.loads(line[len("data: "):])
                    if data.get("type") == "wish_advice.result":
                        payload = data.get("payload")
                        if isinstance(payload, dict):
                            return payload
                except json.JSONDecodeError:
                    continue
    return None
