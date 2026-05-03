"""AI 处置建议端点。"""

import logging
from datetime import datetime

import httpx
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth.ai_deps import require_ai_enabled
from app.auth.deps import require_adult
from app.config import settings
from app.database import get_db
from app.errors import AppError, ErrorCode
from app.models.ai_disposal_suggestion import AIDisposalSuggestion
from app.models.user import User

router = APIRouter(prefix="/ai/disposal-suggestions", tags=["ai-disposal"])
logger = logging.getLogger(__name__)


@router.get("")
def get_disposal_suggestions(
    current_user: User = Depends(require_adult),
    db: Session = Depends(get_db),
):
    suggestions = (
        db.query(AIDisposalSuggestion)
        .filter(
            AIDisposalSuggestion.family_id == current_user.family_id,
            AIDisposalSuggestion.is_dismissed == False,
        )
        .order_by(AIDisposalSuggestion.inefficiency_score.desc())
        .all()
    )
    return [
        {
            "id": str(s.id),
            "asset_id": s.asset_id,
            "asset_name": s.asset_name,
            "category_name": s.category_name,
            "inefficiency_score": s.inefficiency_score,
            "suggested_channel": s.suggested_channel,
            "estimated_resale_range": s.estimated_resale_range,
            "suggestion": s.suggestion,
            "daily_cost": s.daily_cost,
            "created_at": s.created_at.isoformat(),
        }
        for s in suggestions
    ]


@router.post("/refresh")
async def refresh_disposal_suggestions(
    current_user: User = Depends(require_adult),
    _ai: None = Depends(require_ai_enabled),
    db: Session = Depends(get_db),
):
    """触发 agent 扫描并刷新处置建议。"""
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                f"{settings.AGENT_BASE_URL}/disposal/scan",
                headers={
                    "X-Family-Id": str(current_user.family_id),
                    "X-Agent-Token": settings.AGENT_INTERNAL_TOKEN,
                },
            )
            resp.raise_for_status()
            data = resp.json()
    except Exception as e:
        logger.error(f"调用 agent disposal 失败: {e}")
        raise AppError(ErrorCode.AI_SERVICE_UNAVAILABLE)

    # Clear old undismissed suggestions and insert new ones atomically
    try:
        db.query(AIDisposalSuggestion).filter(
            AIDisposalSuggestion.family_id == current_user.family_id,
            AIDisposalSuggestion.is_dismissed == False,
        ).delete()

        # AgentResponse shape: suggestions are in recommendations; legacy shape used "suggestions" key
        raw_suggestions = data.get("suggestions") or data.get("recommendations", [])
        for s in raw_suggestions:
            db.add(AIDisposalSuggestion(
                family_id=current_user.family_id,
                asset_id=s["asset_id"],
                asset_name=s["asset_name"],
                category_name=s.get("category_name"),
                inefficiency_score=s.get("inefficiency_score", 0),
                suggested_channel=s.get("suggested_channel"),
                estimated_resale_range=s.get("estimated_resale_range"),
                suggestion=s.get("suggestion"),
                daily_cost=s.get("daily_cost"),
            ))
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"写入处置建议失败: {e}")
        raise AppError(ErrorCode.AI_DATA_WRITE_FAILED)

    return {"refreshed": len(raw_suggestions)}


@router.post("/{suggestion_id}/dismiss")
def dismiss_suggestion(
    suggestion_id: str,
    current_user: User = Depends(require_adult),
    db: Session = Depends(get_db),
):
    s = db.query(AIDisposalSuggestion).filter(
        AIDisposalSuggestion.id == int(suggestion_id),
        AIDisposalSuggestion.family_id == current_user.family_id,
    ).first()
    if not s:
        raise AppError(ErrorCode.AI_SUGGESTION_NOT_FOUND)
    s.is_dismissed = True
    s.dismissed_at = datetime.utcnow()
    db.commit()
    return {"ok": True}
