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

from apps.agent.routers.threads import delete_thread, get_thread, search_threads
from apps.agent.routers.threads import ThreadSearchRequest


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
