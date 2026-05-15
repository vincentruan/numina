"""
内存通知总线 — 管理 WebSocket 连接并广播事件到家庭成员
"""
import asyncio
import logging
from collections import defaultdict
from typing import Any

logger = logging.getLogger(__name__)


class NotificationBus:
    def __init__(self) -> None:
        # family_id -> set of WebSocket connections
        self._connections: dict[str, set] = defaultdict(set)

    def register(self, family_id: str, ws: Any) -> None:
        self._connections[family_id].add(ws)

    def unregister(self, family_id: str, ws: Any) -> None:
        self._connections[family_id].discard(ws)

    async def broadcast(self, family_id: str, event: dict[str, Any]) -> None:
        """广播事件到家庭所有连接"""
        dead: set = set()
        for ws in list(self._connections.get(family_id, [])):
            try:
                await ws.send_json(event)
            except Exception:
                dead.add(ws)
        for ws in dead:
            self._connections[family_id].discard(ws)


# 全局单例
notification_bus = NotificationBus()


def fire_notification(family_id: str, event: dict[str, Any]) -> None:
    """从同步代码触发异步广播。

    使用 asyncio.get_event_loop() 获取运行中的事件循环并创建 task。
    在 FastAPI 的 async 上下文中调用时，事件循环始终存在。
    在测试环境中，如果事件循环不存在或未运行，静默跳过。
    """
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(notification_bus.broadcast(family_id, event))
    except RuntimeError:
        # 没有运行中的事件循环（测试环境或同步上下文），静默跳过
        pass
    except Exception as e:
        logger.warning("通知广播失败（非致命）: %s", e)
