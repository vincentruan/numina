"""家庭资产体检报告端点。

- GET  /api/v1/ai/report          — 获取最新报告
- POST /api/v1/ai/report/generate — 触发生成（异步，通过 WebSocket 推送进度）
- POST /api/v1/ai/report/ws-ticket — 申请一次性 WebSocket 鉴权 ticket（30s 有效）
- WS   /api/v1/ai/report/ws       — WebSocket 实时进度推送（使用 ticket 鉴权）
"""

import asyncio
import contextlib
import logging
from datetime import datetime, timedelta

import httpx
from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from app.auth.ai_deps import require_ai_enabled, require_owner
from app.auth.deps import require_adult
from app.config import settings
from app.database import get_db
from app.errors import AppError, ErrorCode
from app.models.ai_report import AIReport
from app.models.ai_ws_ticket import AIWsTicket
from app.models.user import User

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
    current_user: User = Depends(require_adult),
    db: Session = Depends(get_db),
):
    """获取家庭最新体检报告。"""
    report = _latest_report(current_user.family_id, db)
    if not report:
        return {"report": None}
    return {"report": report.report_json, "generated_at": report.generated_at.isoformat()}


@router.post("/generate")
async def trigger_generate(
    current_user: User = Depends(require_adult),
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
                    "X-Family-Id": str(current_user.family_id),
                    "X-Agent-Token": settings.AGENT_INTERNAL_TOKEN,
                },
            )
            resp.raise_for_status()
            report_data = resp.json()
    except Exception as e:
        pending.status = "error"
        db.commit()
        logger.error(f"调用 agent 生成报告失败: {e}")
        raise AppError(ErrorCode.AI_SERVICE_UNAVAILABLE) from e

    pending.report_json = report_data
    pending.overall_score = report_data.get("overall_score")
    pending.data_completeness_score = report_data.get("data_completeness_score")
    pending.status = "completed"
    pending.generated_at = datetime.utcnow()
    db.commit()

    return {"report": report_data, "generated_at": pending.generated_at.isoformat()}


@router.post("/ws-ticket")
def create_ws_ticket(
    current_user: User = Depends(require_adult),
    _ai: None = Depends(require_ai_enabled),
    _owner: None = Depends(require_owner),
    db: Session = Depends(get_db),
):
    """申请一次性 WebSocket 鉴权 ticket，30 秒内有效，使用后立即失效。"""
    ticket = AIWsTicket(
        user_id=current_user.id,
        family_id=current_user.family_id,
        expires_at=datetime.utcnow() + timedelta(seconds=30),
    )
    db.add(ticket)
    db.commit()
    db.refresh(ticket)
    return {"ticket": ticket.id}


@router.websocket("/ws")
async def report_ws(
    websocket: WebSocket,
    ticket: str = Query(...),
    db: Session = Depends(get_db),
):
    """WebSocket 端点：前端连接后触发报告生成，实时推送进度。

    鉴权：query param ?ticket=<one-time-ticket>（通过 POST /ws-ticket 获取）
    """
    await websocket.accept()

    # Validate one-time ticket
    ws_ticket = db.query(AIWsTicket).filter(AIWsTicket.id == ticket).first()
    if not ws_ticket or ws_ticket.used or ws_ticket.expires_at < datetime.utcnow():
        await websocket.send_json({"type": "error", "message": "鉴权失败或 ticket 已过期"})
        await websocket.close(code=4001)
        return

    # Mark ticket as used immediately (single-use)
    ws_ticket.used = True
    db.commit()

    from app.models.user import User as UserModel
    user = db.query(UserModel).filter(UserModel.id == ws_ticket.user_id).first()
    if not user:
        await websocket.send_json({"type": "error", "message": "用户不存在"})
        await websocket.close(code=4001)
        return

    # Check AI enabled
    from app.models.ai_provider_config import AIProviderConfig
    active_config = (
        db.query(AIProviderConfig)
        .filter(
            AIProviderConfig.family_id == user.family_id,
            AIProviderConfig.is_active == True,  # noqa: E712
            AIProviderConfig.api_key_encrypted.isnot(None),
        )
        .first()
    )
    if not active_config:
        await websocket.send_json({"type": "error", "message": "AI 功能未启用"})
        await websocket.close(code=4003)
        return

    # Check owner role (same as HTTP POST /generate)
    if user.role != "owner":
        await websocket.send_json({"type": "error", "message": "此操作需要家庭管理员权限"})
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
                    "X-Family-Id": str(user.family_id),
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
        with contextlib.suppress(Exception):
            await websocket.send_json({"type": "error", "message": "报告生成失败，请稍后重试"})
    finally:
        with contextlib.suppress(Exception):
            await websocket.close()
