"""Chat session service.

对话消息持久化已迁移至 DeerFlow checkpointer（agent /api/threads/{id}/runs/stream），
本模块仅保留会话元数据的创建与查询（ai_chat_sessions 行），不再做 JSONL 文件 I/O。
旧的 JSONL 读写路径（append_message / read_messages / fork_session）已移除。
"""

import logging

from sqlalchemy.orm import Session

from apps.backend.app.models.ai_chat_session import AIChatSession
from apps.backend.app.utils.snowflake import next_id

logger = logging.getLogger(__name__)


class ChatSessionService:
    """Service for managing ai_chat_sessions rows (metadata only)."""

    @staticmethod
    async def create_session(
        family_id: int,
        user_id: int,
        db: Session,
        agent_id: int | None = None,
    ) -> AIChatSession:
        """Create a new chat session row.

        消息内容由 DeerFlow checkpointer 持久化，这里只创建会话元数据行
        （ai_tasks.session_id 等外键需要引用该行）。
        """
        session_id = next_id()
        session = AIChatSession(
            id=session_id,
            family_id=family_id,
            user_id=user_id,
            agent_id=agent_id,
        )
        db.add(session)
        db.commit()
        db.refresh(session)

        return session

    @staticmethod
    def get_session(
        session_id: int | str,
        family_id: int | str,
        db: Session,
    ) -> AIChatSession | None:
        """Fetch an existing session by ID, scoped to the family."""
        return (
            db.query(AIChatSession)
            .filter(
                AIChatSession.id == session_id,
                AIChatSession.family_id == int(family_id),
            )
            .first()
        )
