"""AI session index — delegates all persistence to backend via HTTP.

The session metadata (title, status, last summary, etc.) is now stored in
backend's ai_chat_sessions table. This module provides the same interface as
before so callers (routers/sessions.py, deerflow_adapter, etc.) need no changes.

DeerFlow's own checkpointer tables remain in the local DeerFlow DB.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


class AiSessionRepository:
    """CRUD operations for ai_sessions, delegated to backend via HTTP.

    All methods are scoped to family_id — the BackendClient enforces this
    via the X-Family-Id header on every request.
    """

    def __init__(self, family_id: str) -> None:
        from apps.agent.core.backend_client import BackendClient
        self._client = BackendClient(family_id)
        self._family_id = family_id

    async def upsert(
        self,
        *,
        session_id: str,
        family_id: str,
        user_id: str | None,
        capability: str,
        jsonl_path: str,
        last_model: str | None = None,
    ) -> None:
        try:
            await self._client.upsert_session(
                session_id=session_id,
                user_id=user_id,
                capability=capability,
                jsonl_path=jsonl_path,
                last_model=last_model,
            )
        except Exception as e:
            logger.warning("session upsert failed for %s: %s", session_id, e)

    async def update_summary(
        self,
        *,
        session_id: str,
        family_id: str,
        summary: str | None,
        model: str | None = None,
        status: str = "completed",
        title: str | None = None,
    ) -> None:
        try:
            await self._client.update_session_summary(
                session_id=session_id,
                summary=summary,
                model=model,
                status=status,
                title=title,
            )
        except Exception as e:
            logger.warning("session summary update failed for %s: %s", session_id, e)

    async def list_sessions(
        self,
        family_id: str,
        *,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[dict], int]:
        try:
            return await self._client.list_sessions(limit=limit, offset=offset)
        except Exception as e:
            logger.warning("list_sessions failed for family %s: %s", family_id, e)
            return [], 0

    async def get_session(self, session_id: str, family_id: str) -> dict | None:
        try:
            return await self._client.get_session(session_id)
        except Exception as e:
            logger.warning("get_session failed for %s: %s", session_id, e)
            return None
