"""AI 老化预警端点。"""

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
from app.models.ai_asset_alert import AIAssetAlert
from app.models.user import User

router = APIRouter(prefix="/ai/asset-alerts", tags=["ai-alerts"])
logger = logging.getLogger(__name__)


@router.get("")
def get_alerts(
    current_user: User = Depends(require_adult),
    db: Session = Depends(get_db),
):
    alerts = (
        db.query(AIAssetAlert)
        .filter(
            AIAssetAlert.family_id == current_user.family_id,
            AIAssetAlert.is_dismissed == False,
        )
        .order_by(AIAssetAlert.created_at.desc())
        .all()
    )
    return [
        {
            "id": a.id,
            "asset_id": a.asset_id,
            "asset_name": a.asset_name,
            "alert_type": a.alert_type,
            "severity": a.severity,
            "suggestion": a.suggestion,
            "remaining_life_days": a.remaining_life_days,
            "daily_cost": a.daily_cost,
            "created_at": a.created_at.isoformat(),
        }
        for a in alerts
    ]


@router.post("/refresh")
async def refresh_alerts(
    current_user: User = Depends(require_adult),
    _ai: None = Depends(require_ai_enabled),
    db: Session = Depends(get_db),
):
    """触发 agent 扫描并刷新预警（清除旧预警，写入新预警）。"""
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                f"{settings.AGENT_BASE_URL}/alerts/aging",
                headers={
                    "X-Family-Id": current_user.family_id,
                    "X-Agent-Token": settings.AGENT_INTERNAL_TOKEN,
                },
            )
            resp.raise_for_status()
            data = resp.json()
    except Exception as e:
        logger.error(f"调用 agent alerts 失败: {e}")
        raise AppError(ErrorCode.AI_SERVICE_UNAVAILABLE)

    # Clear old undismissed alerts and insert new ones atomically
    try:
        db.query(AIAssetAlert).filter(
            AIAssetAlert.family_id == current_user.family_id,
            AIAssetAlert.is_dismissed == False,
        ).delete()

        # AgentResponse shape: alerts are in risk_flags; legacy shape used "alerts" key
        raw_alerts = data.get("alerts") or data.get("risk_flags", [])
        for alert in raw_alerts:
            db.add(AIAssetAlert(
                family_id=current_user.family_id,
                asset_id=alert["asset_id"],
                asset_name=alert["asset_name"],
                alert_type=alert["alert_type"],
                severity=alert["severity"],
                suggestion=alert.get("suggestion"),
                remaining_life_days=alert.get("remaining_life_days"),
                daily_cost=alert.get("daily_cost"),
            ))
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"写入预警数据失败: {e}")
        raise AppError(ErrorCode.AI_DATA_WRITE_FAILED)

    return {"refreshed": len(raw_alerts)}


@router.post("/{alert_id}/dismiss")
def dismiss_alert(
    alert_id: str,
    current_user: User = Depends(require_adult),
    db: Session = Depends(get_db),
):
    alert = db.query(AIAssetAlert).filter(
        AIAssetAlert.id == alert_id,
        AIAssetAlert.family_id == current_user.family_id,
    ).first()
    if not alert:
        raise AppError(ErrorCode.AI_ALERT_NOT_FOUND)
    alert.is_dismissed = True
    alert.dismissed_at = datetime.utcnow()
    db.commit()
    return {"ok": True}
