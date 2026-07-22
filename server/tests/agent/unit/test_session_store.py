"""Unit tests for services/session_store.py (HTTP-proxy implementation)."""

import os
import sys
from unittest.mock import AsyncMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

FAMILY_ID = "123456789012"


@pytest.fixture
def repo():
    from apps.agent.services.session_store import AiSessionRepository
    return AiSessionRepository(FAMILY_ID)


class TestAiSessionRepository:
    async def test_upsert_calls_backend(self, repo):
        with patch.object(repo._client, "upsert_session", new_callable=AsyncMock) as mock_upsert:
            await repo.upsert(
                session_id="s1",
                family_id=FAMILY_ID,
                user_id="u1",
                agent_id="agent-1",
                last_model="claude-3",
                source="test",
            )
            mock_upsert.assert_awaited_once_with(
                session_id="s1",
                user_id="u1",
                agent_id="agent-1",
                last_model="claude-3",
                source="test",
                parent_thread_id=None,
            )

    async def test_upsert_swallows_backend_error(self, repo):
        with patch.object(repo._client, "upsert_session", new_callable=AsyncMock, side_effect=Exception("network error")):
            # Should not raise
            await repo.upsert(
                session_id="s1",
                family_id=FAMILY_ID,
                user_id=None,
                agent_id=None,
                last_model=None,
                source=None,
            )

    async def test_get_session_returns_dict(self, repo):
        expected = {
            "session_id": "s1",
            "family_id": FAMILY_ID,
            "capability": "chat",
            "status": "active",
            "last_message_summary": None,
            "last_model": None,
        }
        with patch.object(repo._client, "get_session", new_callable=AsyncMock, return_value=expected):
            result = await repo.get_session("s1", FAMILY_ID)
            assert result is not None
            assert result["session_id"] == "s1"
            assert result["status"] == "active"

    async def test_get_session_not_found_returns_none(self, repo):
        with patch.object(repo._client, "get_session", new_callable=AsyncMock, return_value=None):
            result = await repo.get_session("no-such-session", FAMILY_ID)
            assert result is None

    async def test_get_session_backend_error_returns_none(self, repo):
        with patch.object(repo._client, "get_session", new_callable=AsyncMock, side_effect=Exception("timeout")):
            result = await repo.get_session("s1", FAMILY_ID)
            assert result is None

    async def test_list_sessions_returns_tuple(self, repo):
        sessions = [{"session_id": "s1"}, {"session_id": "s2"}]
        with patch.object(repo._client, "list_sessions", new_callable=AsyncMock, return_value=(sessions, 2)):
            result, total = await repo.list_sessions(FAMILY_ID, limit=10, offset=0)
            assert total == 2
            assert len(result) == 2

    async def test_list_sessions_does_not_pass_family_id_positionally(self, repo):
        """Regression: AiSessionRepository.list_sessions used to pass family_id
        as a positional arg to BackendClient.list_sessions, which is keyword-only
        (it uses self.family_id). The TypeError was swallowed by the except
        branch, making /api/threads/search always return []."""
        sessions = [{"session_id": "s1"}]
        with patch.object(repo._client, "list_sessions", new_callable=AsyncMock, return_value=(sessions, 1)) as mock_list:
            await repo.list_sessions(FAMILY_ID, limit=20, offset=0, sort_by="updated_at", sort_order="desc")
            mock_list.assert_awaited_once_with(limit=20, offset=0, sort_by="updated_at", sort_order="desc")

    async def test_list_sessions_backend_error_returns_empty(self, repo):
        with patch.object(repo._client, "list_sessions", new_callable=AsyncMock, side_effect=Exception("timeout")):
            result, total = await repo.list_sessions(FAMILY_ID)
            assert result == []
            assert total == 0

    async def test_update_summary_calls_backend(self, repo):
        with patch.object(repo._client, "update_session_summary", new_callable=AsyncMock) as mock_update:
            await repo.update_summary(
                session_id="s1",
                family_id=FAMILY_ID,
                summary="This is a summary",
                model="claude-3",
                status="completed",
            )
            mock_update.assert_awaited_once_with(
                session_id="s1",
                summary="This is a summary",
                model="claude-3",
                status="completed",
                title=None,
            )

    async def test_update_summary_swallows_backend_error(self, repo):
        with patch.object(repo._client, "update_session_summary", new_callable=AsyncMock, side_effect=Exception("network error")):
            # Should not raise
            await repo.update_summary(
                session_id="s1",
                family_id=FAMILY_ID,
                summary="summary",
                status="completed",
            )

    async def test_response_does_not_contain_jsonl_path(self, repo):
        session_data = {
            "session_id": "s1",
            "family_id": FAMILY_ID,
            "capability": "chat",
            "status": "active",
        }
        with patch.object(repo._client, "get_session", new_callable=AsyncMock, return_value=session_data):
            result = await repo.get_session("s1", FAMILY_ID)
            assert result is not None
            assert "jsonl_path" not in result
