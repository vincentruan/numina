"""AI 资产配置漂移端点。"""

import logging

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, field_validator
from sqlalchemy.orm import Session

from app.auth.ai_deps import require_ai_enabled
from app.auth.deps import get_current_user
from app.config import settings
from app.database import get_db
from app.models.ai_allocation_target import AIAllocationTarget
from app.models.user import User

router = APIRouter(prefix="/ai/allocation-target", tags=["ai-allocation"])
logger = logging.getLogger(__name__)


class AllocationTargetUpdate(BaseModel):
    category_targets: dict[str, float]
    drift_threshold: float = 10.0

    @field_validator("category_targets")
    @classmethod
    def validate_targets(cls, v: dict) -> dict:
        if v:
            total = sum(v.values())
            if abs(total - 100.0) > 0.5:
                raise ValueError(f"配置目标总和必须为100%，当前为{total:.1f}%")
        return v


@router.get("")
def get_target(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    target = db.query(AIAllocationTarget).filter(
        AIAllocationTarget.family_id == current_user.family_id
    ).first()
    if not target:
        return {"has_target": False}
    return {
        "has_target": True,
        "category_targets": target.category_targets,
        "drift_threshold": target.drift_threshold,
        "updated_at": target.updated_at.isoformat(),
    }


@router.put("")
def set_target(
    body: AllocationTargetUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    target = db.query(AIAllocationTarget).filter(
        AIAllocationTarget.family_id == current_user.family_id
    ).first()
    if target:
        target.category_targets = body.category_targets
        target.drift_threshold = body.drift_threshold
    else:
        target = AIAllocationTarget(
            family_id=current_user.family_id,
            category_targets=body.category_targets,
            drift_threshold=body.drift_threshold,
        )
        db.add(target)
    db.commit()
    return {"ok": True}


@router.get("/check")
async def check_drift(
    current_user: User = Depends(get_current_user),
    _ai: None = Depends(require_ai_enabled),
    db: Session = Depends(get_db),
):
    """检测当前配置与目标的漂移。"""
    target = db.query(AIAllocationTarget).filter(
        AIAllocationTarget.family_id == current_user.family_id
    ).first()
    if not target or not target.category_targets:
        return {"has_target": False, "message": "尚未设置配置目标"}

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{settings.AGENT_BASE_URL}/allocation/drift",
                json={
                    "targets": target.category_targets,
                    "threshold": target.drift_threshold,
                },
                headers={
                    "X-Family-Id": current_user.family_id,
                    "X-Agent-Token": settings.AGENT_INTERNAL_TOKEN,
                },
            )
            resp.raise_for_status()
            return resp.json()
    except Exception as e:
        logger.error(f"调用 agent allocation drift 失败: {e}")
        raise HTTPException(status_code=503, detail="AI 服务暂时不可用")
