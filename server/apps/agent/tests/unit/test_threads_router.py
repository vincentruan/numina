"""Tests for apps.agent.routers.threads — history management endpoints.

Regression guards for the /ai/chat/history feature:
- ``delete_thread`` must delete the persistent ``ai_chat_sessions`` row (not
  just best-effort drop the checkpointer state), so deleted threads don't
  reappear in search.
- ``search_threads`` / ``get_thread`` must surface ``original_title`` in
  metadata so the frontend can show the auto-generated title alongside a
  user-renamed title.
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException

from apps.agent.routers.threads import (
    ThreadSearchRequest,
    delete_thread,
    get_thread,
    get_thread_state,
    search_threads,
)


def _verified() -> SimpleNamespace:
    """Stand-in for VerifiedFamily — the endpoints never inspect it."""
    return SimpleNamespace(family_id="family-1")


async def test_delete_thread_deletes_session_row_and_checkpoint():
    """delete_thread must call repo.delete_session (DB row) + checkpointer cleanup."""
    with (
        patch("apps.agent.routers.threads.AiSessionRepository") as MockRepo,
        patch("apps.agent.routers.threads.get_checkpointer") as mock_get_ckpt,
    ):
        repo = MockRepo.return_value
        repo.delete_session = AsyncMock()
        checkpointer = mock_get_ckpt.return_value
        checkpointer.adelete_thread = AsyncMock()

        result = await delete_thread("thread-1", "family-1", verified=_verified())

        repo.delete_session.assert_awaited_once_with(
            session_id="thread-1", family_id="family-1"
        )
        checkpointer.adelete_thread.assert_awaited_once_with("thread-1")
        assert result.success is True


async def test_search_threads_surfaces_original_title_in_metadata():
    """search_threads must include original_title in the response metadata."""
    with patch("apps.agent.routers.threads.AiSessionRepository") as MockRepo:
        repo = MockRepo.return_value
        repo.list_sessions = AsyncMock(
            return_value=(
                [
                    {
                        "session_id": "thread-1",
                        "title": "我的重命名",
                        "original_title": "家庭资产总览",
                        "is_pinned": False,
                        "status": "idle",
                        "created_at": "2026-07-07T00:00:00Z",
                        "updated_at": "2026-07-07T00:00:00Z",
                    }
                ],
                1,
            )
        )

        result = await search_threads(
            ThreadSearchRequest(limit=20, offset=0), "family-1", verified=_verified()
        )

        assert len(result) == 1
        assert result[0].metadata["original_title"] == "家庭资产总览"
        assert result[0].metadata["title"] == "我的重命名"


async def test_get_thread_surfaces_original_title_in_metadata():
    """get_thread must merge original_title from the session record into metadata."""
    with (
        patch("apps.agent.routers.threads.AiSessionRepository") as MockRepo,
        patch("apps.agent.routers.threads.get_checkpointer") as mock_get_ckpt,
    ):
        repo = MockRepo.return_value
        repo.get_session = AsyncMock(
            return_value={
                "session_id": "thread-1",
                "title": "自定义标题",
                "original_title": "自动生成标题",
                "is_pinned": True,
                "status": "idle",
                "created_at": "2026-07-07T00:00:00Z",
                "updated_at": "2026-07-07T00:00:00Z",
                "metadata": {},
            }
        )
        checkpointer = mock_get_ckpt.return_value
        checkpointer.aget_tuple = AsyncMock(return_value=None)

        result = await get_thread("thread-1", "family-1", verified=_verified())

        assert result.metadata["original_title"] == "自动生成标题"
        assert result.metadata["title"] == "自定义标题"
        assert result.metadata["is_pinned"] is True


async def test_get_thread_state_404_when_no_checkpoint_and_no_session():
    """get_thread_state 404s when both checkpointer and session row are absent."""
    with (
        patch("apps.agent.routers.threads.AiSessionRepository") as MockRepo,
        patch("apps.agent.routers.threads.get_checkpointer") as mock_get_ckpt,
    ):
        repo = MockRepo.return_value
        repo.get_session = AsyncMock(return_value=None)
        checkpointer = mock_get_ckpt.return_value
        checkpointer.aget_tuple = AsyncMock(return_value=None)

        with pytest.raises(HTTPException) as exc:
            await get_thread_state("thread-1", "family-1", verified=_verified())
        assert exc.value.status_code == 404


async def test_get_thread_state_falls_back_to_session_when_no_checkpoint():
    """get_thread_state returns empty state (not 404) for orphan threads.

    Regression: a thread with an ai_chat_sessions row but no LangGraph
    checkpoint (e.g. pre-a97eb08c UUID threads) must still resolve so that
    loadHistory doesn't hard-404. Mirrors get_thread's dual-source logic.
    """
    with (
        patch("apps.agent.routers.threads.AiSessionRepository") as MockRepo,
        patch("apps.agent.routers.threads.get_checkpointer") as mock_get_ckpt,
    ):
        repo = MockRepo.return_value
        repo.get_session = AsyncMock(
            return_value={
                "session_id": "1c68f6b9-8173-439c-bdcf-1046478aeda4",
                "title": "孤儿会话",
                "is_pinned": False,
                "status": "idle",
                "created_at": "2026-05-11T12:18:22Z",
                "updated_at": "2026-05-11T12:18:22Z",
                "metadata": {},
            }
        )
        checkpointer = mock_get_ckpt.return_value
        checkpointer.aget_tuple = AsyncMock(return_value=None)

        result = await get_thread_state(
            "1c68f6b9-8173-439c-bdcf-1046478aeda4", "family-1", verified=_verified()
        )

        assert result.values == {}
        assert result.next == []
        assert result.tasks == []
        assert result.checkpoint_id is None
        assert result.parent_checkpoint_id is None
        assert result.metadata["title"] == "孤儿会话"
        assert result.created_at  # coerced ISO timestamp, not empty
