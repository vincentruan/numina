"""家庭资产体检报告端点。

- GET  /api/v1/ai/report          — 获取最新报告
- POST /api/v1/ai/report/generate — 触发生成（异步，通过 WebSocket 推送进度）
- WS   /api/v1/ai/report/ws       — WebSocket 实时进度推送
"""

import asyncio
import json
import logging
from datetime import datetime

import httpx
from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from app.auth.ai_deps import require_ai_enabled, require_owner
from app.auth.deps import get_current_user
from app.config import settings
from app.database import get_db
from app.models.ai_report import AIReport
from app.models.user import User
from jose import JWTError, jwt as jose_jwt
from app.config import settings as _settings
ALGORITHM = "HS256"

def decode_access_token(token: str) -> dict:
    payload = jose_jwt.decode(token, _settings.SECRET_KEY, algorithms=[ALGORITHM])
    if payload.get("type") != "access":
        raise ValueError("not an access token")
    return payload

router = APIRouter(prefix="/ai/report", tags=["ai-report"])
logger = logging.getLogger(__name__)


def _latest_report(family_id: str, db: Session) -> AIReport | None:
    return (
        db.query(AIReport)
        .filter(AIReport.family_id == family_id, AIReport.status == "completed")
        .order_by(AIReport.generated_at.desc())
        .first()
    )


@router.get("")
def get_report(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """获取家庭最新体检报告。"""
    report = _latest_report(current_user.family_id, db)
    if not report:
        return {"report": None}
    return {"report": report.report_json, "generated_at": report.generated_at.isoformat()}


@router.post("/generate")
async def trigger_generate(
    current_user: User = Depends(get_current_user),
    _ai: None = Depends(require_ai_enabled),
    _owner: None = Depends(require_owner),
    db: Session = Depends(get_db),
):
    """触发体检报告生成（同步等待，最长 60s）。"""
    # Create pending record
    pending = AIReport(
        family_id=current_user.family_id,
        report_json={},
        status="pending",
        generated_at=datetime.utcnow(),
    )
    db.add(pending)
    db.commit()
    db.refresh(pending)

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                f"{settings.AGENT_BASE_URL}/report/generate",
                headers={
                    "X-Family-Id": current_user.family_id,
                    "X-Agent-Token": settings.AGENT_INTERNAL_TOKEN,
                },
            )
            resp.raise_for_status()
            report_data = resp.json()
    except Exception as e:
        pending.status = "error"
        db.commit()
        logger.error(f"调用 agent 生成报告失败: {e}")
        from fastapi import HTTPException
        raise HTTPException(status_code=503, detail="AI 服务暂时不可用，请稍后重试")

    pending.report_json = report_data
    pending.overall_score = report_data.get("overall_score")
    pending.data_completeness_score = report_data.get("data_completeness_score")
    pending.status = "completed"
    pending.generated_at = datetime.utcnow()
    db.commit()

    return {"report": report_data, "generated_at": pending.generated_at.isoformat()}


@router.websocket("/ws")
async def report_ws(
    websocket: WebSocket,
    token: str = Query(...),
    db: Session = Depends(get_db),
):
    """WebSocket 端点：前端连接后触发报告生成，实时推送进度。

    鉴权：query param ?token=<access_token>
    """
    await websocket.accept()

    # Validate JWT
    try:
        payload = decode_access_token(token)
        user_id = payload.get("sub")
        if not user_id:
            raise ValueError("invalid token")
    except Exception:
        await websocket.send_json({"type": "error", "message": "鉴权失败"})
        await websocket.close(code=4001)
        return

    from app.models.user import User as UserModel
    user = db.query(UserModel).filter(UserModel.id == user_id).first()
    if not user:
        await websocket.send_json({"type": "error", "message": "用户不存在"})
        await websocket.close(code=4001)
        return

    # Check AI enabled
    from app.models.family import Family
    family = db.query(Family).filter(Family.id == user.family_id).first()
    if not family or not family.ai_enabled:
        await websocket.send_json({"type": "error", "message": "AI 功能未启用"})
        await websocket.close(code=4003)
        return

    await websocket.send_json({"type": "progress", "step": "collecting", "message": "正在收集家庭资产数据..."})
    await asyncio.sleep(0.5)
    await websocket.send_json({"type": "progress", "step": "analyzing", "message": "AI 正在分析数据..."})

    # Create pending record
    pending = AIReport(
        family_id=user.family_id,
        report_json={},
        status="pending",
        generated_at=datetime.utcnow(),
    )
    db.add(pending)
    db.commit()

    try:
        async with httpx.AsyncClient(timeout=90.0) as client:
            resp = await client.post(
                f"{settings.AGENT_BASE_URL}/report/generate",
                headers={
                    "X-Family-Id": user.family_id,
                    "X-Agent-Token": settings.AGENT_INTERNAL_TOKEN,
                },
            )
            resp.raise_for_status()
            report_data = resp.json()

        pending.report_json = report_data
        pending.overall_score = report_data.get("overall_score")
        pending.data_completeness_score = report_data.get("data_completeness_score")
        pending.status = "completed"
        pending.generated_at = datetime.utcnow()
        db.commit()

        await websocket.send_json({
            "type": "completed",
            "report": report_data,
            "generated_at": pending.generated_at.isoformat(),
        })

    except WebSocketDisconnect:
        pending.status = "error"
        db.commit()
    except Exception as e:
        logger.error(f"WebSocket 报告生成失败: {e}")
        pending.status = "error"
        db.commit()
        try:
            await websocket.send_json({"type": "error", "message": "报告生成失败，请稍后重试"})
        except Exception:
            pass
    finally:
        try:
            await websocket.close()
        except Exception:
            pass
