"""通知 WebSocket 路由

- POST /notifications/ws-ticket  获取一次性 ticket（30s 有效）
- WS   /notifications/ws         WebSocket 连接，接收实时通知
"""

import asyncio
import contextlib
import logging
import uuid
from datetime import datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from apps.backend.app.auth.deps import get_current_child_user, get_current_user
from apps.backend.app.database import get_db
from apps.backend.app.models.user import User
from apps.backend.app.services.notification_bus import notification_bus

router = APIRouter(prefix="/notifications", tags=["notifications"])
logger = logging.getLogger(__name__)

# 内存 ticket 存储: ticket_id -> {user_id, family_id, expires_at}
_tickets: dict[str, dict[str, Any]] = {}


def _purge_expired_tickets() -> None:
    now = datetime.utcnow()
    expired = [k for k, v in list(_tickets.items()) if v["expires_at"] < now]
    for k in expired:
        del _tickets[k]


@router.post("/ws-ticket")
def create_ws_ticket(
    current_user: User = Depends(get_current_user),
) -> dict[str, str]:
    """申请一次性 WebSocket 鉴权 ticket，30 秒内有效，使用后立即失效。"""
    _purge_expired_tickets()
    ticket_id = str(uuid.uuid4())
    _tickets[ticket_id] = {
        "user_id": current_user.id,
        "family_id": current_user.family_id,
        "expires_at": datetime.utcnow() + timedelta(seconds=30),
    }
    return {"ticket": ticket_id}


@router.post("/ws-ticket/child")
def create_child_ws_ticket(
    current_user: User = Depends(get_current_child_user),
) -> dict[str, str]:
    """儿童账户申请 WebSocket ticket。"""
    _purge_expired_tickets()
    ticket_id = str(uuid.uuid4())
    _tickets[ticket_id] = {
        "user_id": current_user.id,
        "family_id": current_user.family_id,
        "expires_at": datetime.utcnow() + timedelta(seconds=30),
    }
    return {"ticket": ticket_id}


@router.websocket("/ws")
async def notifications_ws(
    websocket: WebSocket,
    ticket: str = Query(...),
    db: Session = Depends(get_db),
) -> None:
    """WebSocket 端点：使用 ticket 鉴权，连接后接收家庭实时通知。"""
    await websocket.accept()

    # 验证 ticket
    _purge_expired_tickets()
    ticket_data = _tickets.pop(ticket, None)
    if ticket_data is None or ticket_data["expires_at"] < datetime.utcnow():
        await websocket.send_json({"type": "error", "message": "鉴权失败或 ticket 已过期"})
        await websocket.close(code=4001)
        return

    family_id: str = ticket_data["family_id"]
    notification_bus.register(family_id, websocket)

    try:
        while True:
            # 每 30 秒发送心跳，同时等待客户端消息（客户端断开会触发 WebSocketDisconnect）
            try:
                await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
            except TimeoutError:
                with contextlib.suppress(Exception):
                    await websocket.send_json({"type": "ping"})
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.debug("通知 WebSocket 异常: %s", e)
    finally:
        notification_bus.unregister(family_id, websocket)
