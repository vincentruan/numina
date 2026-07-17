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
        agent_id: str | None = None,
        last_model: str | None = None,
        source: str | None = None,
        parent_thread_id: str | None = None,
    ) -> None:
        try:
            await self._client.upsert_session(
                session_id=session_id,
                user_id=user_id,
                agent_id=agent_id,
                last_model=last_model,
                source=source,
                parent_thread_id=parent_thread_id,
            )
        except Exception as e:
            logger.warning("session upsert failed for %s: %s", session_id, e)

    async def get_title(self, *, session_id: str, family_id: str) -> str | None:
        """Return the existing title for a session, or None if not set."""
        try:
            session = await self._client.get_session(session_id)
            if session:
                return session.get("title")
        except Exception as e:
            logger.warning("session get_title failed for %s: %s", session_id, e)
        return None

    async def get_session(self, session_id: str, family_id: str | None = None) -> dict | None:
        """Return session metadata dict, or None if not found or on error."""
        try:
            return await self._client.get_session(session_id)
        except Exception as e:
            logger.warning("session get failed for %s: %s", session_id, e)
            return None

    async def list_sessions(
        self,
        family_id: str,
        limit: int = 20,
        offset: int = 0,
        sort_by: str = "updated_at",
        sort_order: str = "desc",
    ) -> tuple[list[dict], int]:
        """Return (sessions, total) for the family, or ([], 0) on error."""
        try:
            # BackendClient is already bound to family_id at construction; do
            # NOT pass it again here; BackendClient.list_sessions takes only
            # keyword-only params (limit/offset/sort_by/sort_order) and the
            # extra positional arg raised TypeError, which was swallowed by
            # the except below, making /api/threads/search return [] always.
            return await self._client.list_sessions(
                limit=limit,
                offset=offset,
                sort_by=sort_by,
                sort_order=sort_order,
            )
        except Exception as e:
            logger.warning("session list failed for family %s: %s", family_id, e)
            return [], 0

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

    async def update_session(
        self,
        *,
        session_id: str,
        title: str | None = None,
        is_pinned: bool | None = None,
    ) -> None:
        """Update session metadata (title, is_pinned) via backend."""
        try:
            await self._client.update_session(
                session_id=session_id,
                title=title,
                is_pinned=is_pinned,
            )
        except Exception as e:
            logger.warning("session update failed for %s: %s", session_id, e)

    async def delete_session(self, *, session_id: str, family_id: str) -> bool:
        """Delete a session row via backend.

        Returns:
            True if deleted successfully, False if not found or on error.
        """
        try:
            return await self._client.delete_session(session_id)
        except Exception as e:
            logger.warning("session delete failed for %s: %s", session_id, e)
            return False
