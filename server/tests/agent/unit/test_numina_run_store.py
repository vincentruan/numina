"""Tests for NuminaSqliteRunStore.

Verifies:
- put/get/delete cycle
- update_status transitions
- list_inflight / list_pending
- lease management (update_lease, claim_for_takeover)
- aggregate_tokens_by_thread
- start_run atomicity
"""

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine


def make_store():
    """Create an in-memory SQLite engine + store for testing."""

    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    factory = async_sessionmaker(engine, expire_on_commit=False)
    return engine, factory


@pytest.fixture
async def store_and_factory():
    engine, factory = make_store()
    from apps.agent.services.runtime.numina_run_store import NuminaSqliteRunStore

    store = NuminaSqliteRunStore(factory)
    await store._ensure_table()
    yield store
    await engine.dispose()


class TestPutGetDelete:
    """Core CRUD tests."""

    @pytest.mark.asyncio
    async def test_put_and_get(self, store_and_factory):
        store = store_and_factory
        await store.put("run-1", thread_id="thread-1", metadata={"app": "asset-report"})
        result = await store.get("run-1")
        assert result is not None
        assert result["run_id"] == "run-1"
        assert result["thread_id"] == "thread-1"

    @pytest.mark.asyncio
    async def test_get_missing_returns_none(self, store_and_factory):
        store = store_and_factory
        result = await store.get("nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_delete(self, store_and_factory):
        store = store_and_factory
        await store.put("run-1", thread_id="thread-1")
        await store.delete("run-1")
        result = await store.get("run-1")
        assert result is None


class TestListByThread:
    """Thread listing tests."""

    @pytest.mark.asyncio
    async def test_list_by_thread(self, store_and_factory):
        store = store_and_factory
        await store.put("run-1", thread_id="thread-1")
        await store.put("run-2", thread_id="thread-1")
        await store.put("run-3", thread_id="thread-2")
        result = await store.list_by_thread("thread-1")
        assert len(result) == 2
        ids = {r["run_id"] for r in result}
        assert ids == {"run-1", "run-2"}


class TestUpdateStatus:
    """Status transition tests."""

    @pytest.mark.asyncio
    async def test_update_status(self, store_and_factory):
        store = store_and_factory
        await store.put("run-1", thread_id="thread-1", status="pending")
        ok = await store.update_status("run-1", "running")
        assert ok is True
        result = await store.get("run-1")
        assert result["status"] == "running"

    @pytest.mark.asyncio
    async def test_update_status_nonexistent(self, store_and_factory):
        store = store_and_factory
        ok = await store.update_status("missing", "running")
        assert ok is False


class TestStartRun:
    """Atomic start_run tests."""

    @pytest.mark.asyncio
    async def test_start_run_success(self, store_and_factory):
        store = store_and_factory
        await store.put("run-1", thread_id="thread-1", status="pending")
        ok = await store.start_run("run-1")
        assert ok is True
        result = await store.get("run-1")
        assert result["status"] == "running"

    @pytest.mark.asyncio
    async def test_start_run_already_running(self, store_and_factory):
        store = store_and_factory
        await store.put("run-1", thread_id="thread-1", status="running")
        ok = await store.start_run("run-1")
        assert ok is False


class TestListPendingAndInflight:
    """Pending and inflight listing tests."""

    @pytest.mark.asyncio
    async def test_list_pending(self, store_and_factory):
        store = store_and_factory
        await store.put("run-1", thread_id="thread-1", status="pending")
        await store.put("run-2", thread_id="thread-1", status="pending")
        await store.put("run-3", thread_id="thread-1", status="running")
        pending = await store.list_pending()
        assert len(pending) == 2
        ids = {r["run_id"] for r in pending}
        assert ids == {"run-1", "run-2"}

    @pytest.mark.asyncio
    async def test_list_inflight(self, store_and_factory):
        store = store_and_factory
        await store.put("run-1", thread_id="thread-1", status="running")
        inflight = await store.list_inflight()
        assert len(inflight) == 1
        assert inflight[0]["run_id"] == "run-1"


class TestLeaseManagement:
    """Lease lifecycle tests."""

    @pytest.mark.asyncio
    async def test_update_lease(self, store_and_factory):
        store = store_and_factory
        await store.put("run-1", thread_id="thread-1", status="running")
        ok = await store.update_lease("run-1", expires_at="2099-01-01T00:00:00+00:00")
        assert ok is True

    @pytest.mark.asyncio
    async def test_claim_for_takeover(self, store_and_factory):
        store = store_and_factory
        await store.put("run-1", thread_id="thread-1", status="running")
        ok = await store.claim_for_takeover("run-1", new_owner_worker_id="worker-2")
        assert ok is True
        result = await store.get("run-1")
        assert result["owner_worker_id"] == "worker-2"


class TestTokenAggregation:
    """Token usage aggregation tests."""

    @pytest.mark.asyncio
    async def test_aggregate_tokens(self, store_and_factory):
        store = store_and_factory
        await store.put("run-1", thread_id="thread-1", status="running")
        ok = await store.update_run_completion(
            "run-1",
            status="completed",
            total_input_tokens=100,
            total_output_tokens=50,
        )
        assert ok is True
        agg = await store.aggregate_tokens_by_thread("thread-1")
        assert agg["input_tokens"] == 100
        assert agg["output_tokens"] == 50

    @pytest.mark.asyncio
    async def test_completion_guard_blocks_conflicting_terminal(self, store_and_factory):
        """update_run_completion never overwrites a different terminal status."""
        store = store_and_factory
        await store.put("run-1", thread_id="thread-1", status="running")
        ok = await store.update_run_completion("run-1", status="completed")
        assert ok is True
        # Second completion attempt with conflicting terminal status is blocked
        ok2 = await store.update_run_completion("run-1", status="failed")
        assert ok2 is False
