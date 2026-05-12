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
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.auth.ai_deps import require_ai_enabled, require_owner
from app.auth.deps import require_adult
from app.config import settings
from app.database import get_db
from app.errors import AppError, ErrorCode
from app.models.ai_report import AIReport
from app.models.ai_ws_ticket import AIWsTicket
from app.models.user import User
from app.services.ai_task_service import AITaskService
from app.services.chat_session import ChatSessionService

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
    """触发体检报告生成（streaming，任务状态追踪）。"""
    # 1. 检查在途任务
    existing = AITaskService.get_running_task(current_user.family_id, "report", db)
    if existing:
        raise AppError(ErrorCode.AI_TASK_IN_PROGRESS, "⏳ 报告生成中，请稍后")

    # 2. 创建 AIChatSession
    session = await ChatSessionService.create_session(
        family_id=str(current_user.family_id),
        user_id=str(current_user.id),
        db=db,
    )

    # 3. 创建 AITask
    task = AITaskService.create_task(
        family_id=current_user.family_id,
        capability="report",
        session_id=session.id,
        db=db,
    )

    # 4. 透传 agent streaming
    async def proxy_stream():
        buffer: list[str] = []
        try:
            async with (
                httpx.AsyncClient(timeout=httpx.Timeout(connect=5.0, read=300.0, write=10.0, pool=5.0)) as client,
                client.stream(
                    "POST",
                    f"{settings.AGENT_BASE_URL}/report/generate/stream",
                    headers={
                        "X-Family-Id": str(current_user.family_id),
                        "X-Agent-Token": settings.AGENT_INTERNAL_TOKEN,
                        "X-Task-Id": task.id,
                        "X-Thread-Id": session.id,
                    },
                ) as resp,
            ):
                    async for chunk in resp.aiter_text():
                        buffer.append(chunk)
                        yield chunk.encode("utf-8")
                        if chunk.endswith(("。", "！", "？", ".", "!", "?", "\n")):
                            await ChatSessionService.append_message(
                                session, "assistant", "".join(buffer), current_user, db
                            )
                            buffer.clear()
            if buffer:
                await ChatSessionService.append_message(
                    session, "assistant", "".join(buffer), current_user, db
                )
            AITaskService.complete_task(task.id, db)
        except Exception as e:
            logger.error(f"[ai_report] proxy_stream failed: {e}")
            if buffer:
                await ChatSessionService.append_message(
                    session, "assistant", "".join(buffer), current_user, db
                )
            AITaskService.fail_task(task.id, "agent_stream_error", db)
            raise

    return StreamingResponse(proxy_stream(), media_type="text/plain; charset=utf-8")


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
    return {"ticket": str(ticket.id)}


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

    # Validate one-time ticket (ticket param is str from query, id column is BigInteger)
    try:
        ticket_id = int(ticket)
    except (ValueError, TypeError):
        await websocket.send_json({"type": "error", "message": "鉴权失败或 ticket 已过期"})
        await websocket.close(code=4001)
        return
    ws_ticket = db.query(AIWsTicket).filter(AIWsTicket.id == ticket_id).first()
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
