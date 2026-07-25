"""W4 wish-priority advice endpoint (Plan B T7). Independent AI call + cache.

POST /api/v1/ai/wish-advice/generate?force=false
Cache key: family_id:wish_advice:{fingerprint}, TTL 8h, wish-change invalidated.
Output schema (NOT finance_coach's suggestions[]): {primary_wish_id, reason,
suggested_monthly, redistribution: [{wish_id, suggested_amount, note}]}.
"""
import logging

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from apps.backend.app.auth.ai_deps import require_ai_enabled, require_owner
from apps.backend.app.auth.deps import require_adult
from apps.backend.app.database import get_db
from apps.backend.app.models.user import User
from apps.backend.app.routers._ai_events_helper import check_circuit_blocked
from apps.backend.app.services import wish_advice
from apps.backend.app.services.finance_coach_cache import (
    is_cache_fresh,
    latest_by_skill,
    upsert_skill_result,
)

router = APIRouter(prefix="/ai/wish-advice", tags=["ai-wish-advice"])
logger = logging.getLogger(__name__)


@router.post("/generate")
async def generate_wish_advice(
    force: bool = False,
    current_user: User = Depends(require_adult),
    _ai: None = Depends(require_ai_enabled),
    _owner: None = Depends(require_owner),
    db: Session = Depends(get_db),
):
    blocked = check_circuit_blocked(current_user.family_id, "wish_advice", db)
    if blocked is not None:
        return blocked

    _wishes, fingerprint = wish_advice.build_advice_input(db, current_user)

    if not force:
        # The wish_advice cache is keyed by fingerprint; we store under a single
        # skill_id='wish_advice' row and compare fingerprints in the payload
        # (pragmatic adaptation — keeps the skill_id column's cardinality
        # bounded; see commit message for the spec §4.4 key-shape rationale).
        cached = latest_by_skill(db, current_user.family_id, "wish_advice")
        if (
            is_cache_fresh(cached, "wish_advice")
            and cached
            and cached.report_json.get("fingerprint") == fingerprint
        ):
            return JSONResponse(
                status_code=200,
                content={
                    "status": "cached",
                    "generated_at": cached.generated_at.isoformat() if cached.generated_at else None,
                    "report": cached.report_json.get("advice"),
                },
            )

    advice, fp = await wish_advice.generate_advice(db, current_user)
    if advice is None:
        # No usable advice (guardrail fail / AI down / <2 wishes / LLM not wired)
        # → silent (spec §4.5).
        return JSONResponse(status_code=200, content={"status": "empty", "report": None})

    upsert_skill_result(
        db, current_user.family_id, "wish_advice", {"fingerprint": fp, "advice": advice}
    )
    db.commit()
    return JSONResponse(status_code=200, content={"status": "fresh", "report": advice})
