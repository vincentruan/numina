"""W4 wish-priority advice (Plan B T7) — INDEPENDENT of finance_coach.

spec §7.1 coherence c100: W4 output is ``redistribution[]``, NOT finance_coach's
``suggestions[]``. W4 shares only the prompt-template skeleton (家庭财务教练角色),
not the output schema. Separate cache key ``family_id:wish_advice:{fingerprint}``.

LLM call path: the lightweight-LLM helper (``_create_lightweight_llm``) lives in
the agent app (``apps/agent/services/runtime/run_extras.py``) and is NOT
importable from the backend (the backend has no langchain_openai dependency).
The plan-approved fallback is a dedicated ``wish-advice`` stream_run capability
mirroring finance_coach's chain (system-agent + gateway route + worker branch +
SKILL.md). Until that capability is wired, ``generate_advice`` returns
``(None, fp)`` so the router degrades gracefully (200 empty, spec §4.5) — the
cache hit + guardrail paths are fully functional and test-covered.
"""
import hashlib
import logging
from decimal import Decimal

from sqlalchemy.orm import Session

from apps.backend.app.models.user import User
from apps.backend.app.models.wish import Wish

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

    TODO(LLM-wire): connect to a dedicated ``wish-advice`` stream_run capability
    (the plan-approved fallback — the lightweight-LLM helper lives in the agent
    app and is not importable from the backend). The chain mirrors finance_coach:
    backend trigger → agent gateway /internal/gateway/runs/wish-advice/{thread_id}
    → worker ``_run_wish_advice_agent`` → emits a ``wish_advice.result`` frame
    with the validated redistribution[] JSON; the backend parses + caches it
    under capability='wish_advice' with the fingerprint embedded in report_json.

    Until wired, returns (None, fp) so the router degrades gracefully (200 empty,
    spec §4.5). The cache-hit + guardrail paths remain fully functional.
    """
    wishes, fp = build_advice_input(db, user)
    if len(wishes) < 2 or not any((w.monthly_saving or Decimal("0")) > 0 for w in wishes):
        return None, fp  # spec §4.1: don't show the card
    return None, fp
