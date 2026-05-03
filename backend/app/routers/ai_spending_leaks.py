"""AI 消费漏洞检测端点。"""

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
from app.models.ai_spending_leak import AISpendingLeak
from app.models.user import User

router = APIRouter(prefix="/ai/spending-leaks", tags=["ai-spending-leaks"])
logger = logging.getLogger(__name__)


@router.get("")
def get_leaks(
    current_user: User = Depends(require_adult),
    db: Session = Depends(get_db),
):
    leaks = (
        db.query(AISpendingLeak)
        .filter(
            AISpendingLeak.family_id == current_user.family_id,
            AISpendingLeak.is_dismissed == False,
        )
        .order_by(AISpendingLeak.created_at.desc())
        .all()
    )
    return [
        {
            "id": str(l.id),
            "asset_id": l.asset_id,
            "asset_name": l.asset_name,
            "leak_type": l.leak_type,
            "severity": l.severity,
            "estimated_annual_waste": l.estimated_annual_waste,
            "suggestion": l.suggestion,
            "created_at": l.created_at.isoformat(),
        }
        for l in leaks
    ]


@router.post("/refresh")
async def refresh_leaks(
    current_user: User = Depends(require_adult),
    _ai: None = Depends(require_ai_enabled),
    db: Session = Depends(get_db),
):
    """触发 agent 扫描并刷新消费漏洞（清除旧记录，写入新记录）。"""
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                f"{settings.AGENT_BASE_URL}/spending-leak",
                headers={
                    "X-Family-Id": str(current_user.family_id),
                    "X-Agent-Token": settings.AGENT_INTERNAL_TOKEN,
                },
            )
            resp.raise_for_status()
            data = resp.json()
    except Exception as e:
        logger.error(f"调用 agent spending-leak 失败: {e}")
        raise AppError(ErrorCode.AI_SERVICE_UNAVAILABLE)

    raw_leaks = data.get("leaks", [])

    try:
        db.query(AISpendingLeak).filter(
            AISpendingLeak.family_id == current_user.family_id,
            AISpendingLeak.is_dismissed == False,
        ).delete()

        for leak in raw_leaks:
            db.add(AISpendingLeak(
                family_id=current_user.family_id,
                asset_id=leak["asset_id"],
                asset_name=leak["asset_name"],
                leak_type=leak["leak_type"],
                severity=leak["severity"],
                estimated_annual_waste=leak.get("estimated_annual_waste"),
                suggestion=leak.get("suggestion"),
            ))
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"写入消费漏洞数据失败: {e}")
        raise AppError(ErrorCode.AI_DATA_WRITE_FAILED)

    return {"refreshed": len(raw_leaks)}


@router.post("/{leak_id}/dismiss")
def dismiss_leak(
    leak_id: str,
    current_user: User = Depends(require_adult),
    db: Session = Depends(get_db),
):
    leak = db.query(AISpendingLeak).filter(
        AISpendingLeak.id == int(leak_id),
        AISpendingLeak.family_id == current_user.family_id,
    ).first()
    if not leak:
        raise AppError(ErrorCode.AI_SPENDING_LEAK_NOT_FOUND)
    leak.is_dismissed = True
    leak.dismissed_at = datetime.utcnow()
    db.commit()
    return {"ok": True}
