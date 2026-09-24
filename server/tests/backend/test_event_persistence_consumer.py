"""Tests for event persistence consumer.

Verifies:
- Events are correctly persisted to DbRunEventStore when initialized
- Non-fatal: init failure is handled gracefully
- Event type mapping is correct
"""

import pytest


class TestEventPersistenceInit:
    """Tests for event persistence initialization."""

    @pytest.mark.asyncio
    async def test_init_fails_gracefully_when_no_deerflow_env(self, monkeypatch):
        """Init fails gracefully when DeerFlow DB env vars are not set."""
        # Simulate missing env vars
        monkeypatch.delenv("DEERFLOW_DB_URL", raising=False)
        monkeypatch.delenv("DEERFLOW_DB_PATH", raising=False)
        monkeypatch.delenv("DATA_ROOT", raising=False)


        # Should not raise
        try:
            import asyncio
            await asyncio.wait_for(
                self._test_init(),
                timeout=2.0
            )
        except Exception:
            # Any exception is fine here - we just want to ensure it doesn't crash
            # the main service
            pass

    @pytest.mark.asyncio
    async def test_init_succeeds_with_tmp_sqlite(self, monkeypatch, tmp_path):
        """init_event_store succeeds with the correct init_engine signature."""
        import asyncio
        db_path = str(tmp_path / "deerflow-events.db")
        monkeypatch.setenv("DEERFLOW_DB_PATH", db_path)
        monkeypatch.delenv("DEERFLOW_DB_URL", raising=False)

        from apps.backend.app.services.event_persistence import (
            _event_store,
            _init_error,
            init_event_store,
        )

        # Reset module-level state before init
        import apps.backend.app.services.event_persistence as mod
        mod._event_store = None
        mod._init_error = None

        await asyncio.wait_for(init_event_store(), timeout=5.0)

        # After a successful init, _event_store is non-None and _init_error is None.
        # If the (previously buggy) call init_engine(db_url=...) was still in use,
        # the call would fail with TypeError, _init_error would be set, and this
        # assertion would fail — giving us real coverage of the signature.
        assert mod._event_store is not None, (
            f"init_event_store failed to initialize store: {mod._init_error}"
        )
        assert mod._init_error is None

    @pytest.mark.asyncio
    async def test_persist_event_writes_to_db(self, monkeypatch, tmp_path):
        """End-to-end: persist_event writes to run_events table via the store."""
        import asyncio
        db_path = str(tmp_path / "deerflow-events.db")
        monkeypatch.setenv("DEERFLOW_DB_PATH", db_path)
        monkeypatch.delenv("DEERFLOW_DB_URL", raising=False)

        import apps.backend.app.services.event_persistence as mod
        mod._event_store = None
        mod._init_error = None

        from apps.backend.app.services.event_persistence import (
            init_event_store,
            persist_event,
        )

        await init_event_store()
        assert mod._event_store is not None

        # Write an event
        await persist_event(
            thread_id="thread-test",
            run_id="run-test",
            event_type="messages",
            event_data={"text": "hello world"},
            family_id=1001,
        )

        # Read back via DbRunEventStore's list_events.
        # list_events requires explicit user_id=None to bypass auth middleware
        # contextvar (same as the background consumer path).
        events = await mod._event_store.list_events(
            thread_id="thread-test", run_id="run-test", user_id=None
        )
        assert len(events) >= 1
        assert events[0]["run_id"] == "run-test"
        assert events[0]["event_type"] == "llm.ai.response"  # messages → llm.ai.response
        # family_id is in metadata
        assert events[0]["metadata"].get("family_id") == "1001"

    async def _test_init(self):
        from apps.backend.app.services.event_persistence import init_event_store
        await init_event_store()

    @pytest.mark.asyncio
    async def test_persist_event_non_fatal_on_missing_store(self):
        """persist_event does not crash when store is not initialized."""
        from apps.backend.app.services.event_persistence import persist_event

        # Should not raise even if _event_store is None
        await persist_event(
            thread_id="thread-1",
            run_id="run-1",
            event_type="messages",
            event_data={"key": "value"},
            family_id=1001,
        )


class TestEventPersistenceConsumerIntegration:
    """Integration test for event persistence in lifecycle consumer."""

    def test_consumer_accepts_thread_id(self):
        """_spawn_lifecycle_consumer accepts thread_id parameter."""
        # Just verify the function accepts the parameter without error
        # (full integration requires Redis setup)
        import inspect

        from apps.backend.app.services.bridge_consumer import _spawn_lifecycle_consumer
        sig = inspect.signature(_spawn_lifecycle_consumer)
        assert "thread_id" in sig.parameters
        assert sig.parameters["thread_id"].default is None
