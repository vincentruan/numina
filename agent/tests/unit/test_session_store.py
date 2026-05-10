"""Unit tests for services/session_store.py."""

import os
import sys

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))


@pytest.fixture
async def repo():
    """In-memory SQLite repo for testing."""
    from deerflow.persistence.base import Base
    from services.session_store import AiSessionRepository

    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    sf = async_sessionmaker(engine, expire_on_commit=False)
    yield AiSessionRepository(sf)
    await engine.dispose()


class TestAiSessionRepository:
    async def test_upsert_creates_record(self, repo):
        await repo.upsert(
            session_id="s1",
            family_id="f1",
            user_id="u1",
            capability="chat",
            jsonl_path="data/sessions/f1/s1.jsonl",
        )
        result = await repo.get_session("s1", "f1")
        assert result is not None
        assert result["session_id"] == "s1"
        assert result["capability"] == "chat"
        assert result["status"] == "active"

    async def test_upsert_is_idempotent(self, repo):
        for _ in range(3):
            await repo.upsert(
                session_id="s1",
                family_id="f1",
                user_id="u1",
                capability="chat",
                jsonl_path="data/sessions/f1/s1.jsonl",
            )
        sessions, total = await repo.list_sessions("f1")
        assert total == 1

    async def test_get_session_wrong_family_returns_none(self, repo):
        await repo.upsert(
            session_id="s1",
            family_id="f1",
            user_id=None,
            capability="chat",
            jsonl_path="data/sessions/f1/s1.jsonl",
        )
        result = await repo.get_session("s1", "f2")
        assert result is None

    async def test_get_session_nonexistent_returns_none(self, repo):
        result = await repo.get_session("no-such-session", "f1")
        assert result is None

    async def test_list_sessions_family_isolation(self, repo):
        await repo.upsert(
            session_id="s1", family_id="f1", user_id=None,
            capability="chat", jsonl_path="p1",
        )
        await repo.upsert(
            session_id="s2", family_id="f2", user_id=None,
            capability="chat", jsonl_path="p2",
        )
        f1_sessions, f1_total = await repo.list_sessions("f1")
        assert f1_total == 1
        assert f1_sessions[0]["session_id"] == "s1"

        f2_sessions, f2_total = await repo.list_sessions("f2")
        assert f2_total == 1
        assert f2_sessions[0]["session_id"] == "s2"

    async def test_list_sessions_ordered_by_updated_at_desc(self, repo):
        import asyncio
        await repo.upsert(
            session_id="s1", family_id="f1", user_id=None,
            capability="chat", jsonl_path="p1",
        )
        await asyncio.sleep(0.01)
        await repo.upsert(
            session_id="s2", family_id="f1", user_id=None,
            capability="chat", jsonl_path="p2",
        )
        sessions, _ = await repo.list_sessions("f1")
        assert sessions[0]["session_id"] == "s2"

    async def test_update_summary(self, repo):
        await repo.upsert(
            session_id="s1", family_id="f1", user_id=None,
            capability="chat", jsonl_path="p1",
        )
        await repo.update_summary(
            session_id="s1",
            family_id="f1",
            summary="This is a summary",
            model="claude-3",
            status="completed",
        )
        result = await repo.get_session("s1", "f1")
        assert result["last_message_summary"] == "This is a summary"
        assert result["status"] == "completed"
        assert result["last_model"] == "claude-3"

    async def test_update_summary_wrong_family_is_noop(self, repo):
        await repo.upsert(
            session_id="s1", family_id="f1", user_id=None,
            capability="chat", jsonl_path="p1",
        )
        await repo.update_summary(
            session_id="s1", family_id="f2", summary="hacked", status="completed"
        )
        result = await repo.get_session("s1", "f1")
        assert result["last_message_summary"] is None

    async def test_list_sessions_pagination(self, repo):
        for i in range(5):
            await repo.upsert(
                session_id=f"s{i}", family_id="f1", user_id=None,
                capability="chat", jsonl_path=f"p{i}",
            )
        page1, total = await repo.list_sessions("f1", limit=3, offset=0)
        assert total == 5
        assert len(page1) == 3

        page2, _ = await repo.list_sessions("f1", limit=3, offset=3)
        assert len(page2) == 2

    async def test_jsonl_path_not_exposed_in_public_dict(self, repo):
        await repo.upsert(
            session_id="s1", family_id="f1", user_id=None,
            capability="chat", jsonl_path="secret/path.jsonl",
        )
        # _row_to_dict intentionally excludes jsonl_path from the public dict
        # (the router also strips it from list responses)
        result = await repo.get_session("s1", "f1")
        assert result is not None
        assert "jsonl_path" not in result
        assert result["session_id"] == "s1"
