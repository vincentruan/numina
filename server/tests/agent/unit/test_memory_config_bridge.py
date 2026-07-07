"""Tests for the per-family memory-update config bridge.

Reproduces the root cause of the agent runtime error:

    IndexError: list index out of range
      File ".../deerflow/models/factory.py", line 61, in create_chat_model
        name = config.models[0].name

The memory update runs on a ``threading.Timer`` thread that does not inherit
the ``_current_app_config`` ContextVar, so ``get_app_config()`` fell back to
the base config (no ``models``) and ``get_memory_config()`` could resolve to
another family's ``storage_path``. The bridge snapshots the family config at
enqueue time and replays it on the timer thread.
"""

import threading
import types
from unittest.mock import patch

import pytest

from apps.agent.services.deerflow_adapter import memory_config_bridge


def _make_family_config(storage_path: str):
    """Build a lightweight family AppConfig stand-in.

    The bridge only touches ``cfg.memory`` (and pushes the object as the
    ContextVar override), so a SimpleNamespace carrying a real MemoryConfig is
    sufficient and avoids constructing a full AppConfig/SandboxConfig.
    """
    from deerflow.config.memory_config import MemoryConfig

    return types.SimpleNamespace(memory=MemoryConfig(storage_path=storage_path, enabled=True))


@pytest.fixture(autouse=True)
def _isolate_global_memory_config():
    """Save/restore the global memory singleton + stash around each test."""
    from deerflow.config.memory_config import get_memory_config, set_memory_config

    saved = get_memory_config()
    memory_config_bridge.clear_stash()
    yield
    set_memory_config(saved)
    memory_config_bridge.clear_stash()


def test_get_memory_config_is_contextvar_aware():
    """get_memory_config() returns the active runtime config's memory when one is pushed."""
    from deerflow.config.app_config import pop_current_app_config, push_current_app_config
    from deerflow.config.memory_config import MemoryConfig, get_memory_config, set_memory_config

    memory_config_bridge.install()

    # Global fallback when no runtime config is active.
    set_memory_config(MemoryConfig(storage_path="/tmp/global/memory.json"))
    assert get_memory_config().storage_path == "/tmp/global/memory.json"

    # Runtime override takes precedence while pushed.
    family_cfg = _make_family_config("/tmp/famA/memory.json")
    push_current_app_config(family_cfg)
    try:
        assert get_memory_config().storage_path == "/tmp/famA/memory.json"
    finally:
        pop_current_app_config()

    # Falls back to global once popped.
    assert get_memory_config().storage_path == "/tmp/global/memory.json"


def test_snapshot_and_pop_roundtrip():
    """snapshot_config captures the pushed config; pop_config returns and removes it."""
    from deerflow.config.app_config import pop_current_app_config, push_current_app_config

    memory_config_bridge.install()

    family_cfg = _make_family_config("/tmp/famB/memory.json")
    push_current_app_config(family_cfg)
    try:
        memory_config_bridge.snapshot_config("t-B", None, None)
    finally:
        pop_current_app_config()

    # pop_config works on a bare thread (no ContextVar) and returns the snapshot.
    popped = {}

    def _pop():
        popped["cfg"] = memory_config_bridge.pop_config("t-B", None, None)

    t = threading.Thread(target=_pop)
    t.start()
    t.join()

    assert popped["cfg"] is family_cfg
    # Second pop is None (already consumed).
    assert memory_config_bridge.pop_config("t-B", None, None) is None


def test_update_replays_family_config_on_background_thread():
    """A memory update run on a bare thread sees the enqueued family's config + storage_path.

    This is the core regression: without the bridge, peek_current_app_config()
    on the timer thread is None and get_memory_config() returns the wrong
    family's (or empty) config, causing the IndexError / cross-family leak.
    """
    from deerflow.agents.memory.queue import get_memory_queue, reset_memory_queue
    from deerflow.agents.memory.updater import MemoryUpdater
    from deerflow.config.app_config import (
        peek_current_app_config,
        pop_current_app_config,
        push_current_app_config,
    )
    from deerflow.config.memory_config import get_memory_config

    memory_config_bridge.install()

    family_cfg = _make_family_config("/tmp/famA/agent/memory.json")
    observed: dict = {}

    def fake_prepare(self, messages, agent_name, correction_detected, reinforcement_detected, user_id=None):
        # Runs inside _do_update_memory_sync, on the bare thread, AFTER the
        # bridge has replayed the family config.
        observed["app_cfg"] = peek_current_app_config()
        observed["storage_path"] = get_memory_config().storage_path
        return None  # short-circuit; _do_update_memory_sync returns False

    messages = [{"type": "human", "content": "hi"}, {"type": "ai", "content": "hello"}]

    # Enqueue while the family ContextVar is active (mirrors MemoryMiddleware.after_agent
    # running on the agent executor thread inside _produce).
    push_current_app_config(family_cfg)
    try:
        get_memory_queue().add(thread_id="t-A", messages=messages, agent_name=None, user_id=None)
    finally:
        pop_current_app_config()

    # Run the update on a bare thread — no ContextVar is inherited, exactly
    # like the threading.Timer callback.
    run_error: dict = {}

    def _run():
        try:
            with patch.object(MemoryUpdater, "_prepare_update_prompt", fake_prepare):
                MemoryUpdater().update_memory(
                    messages=messages, thread_id="t-A", agent_name=None, user_id=None
                )
        except Exception as exc:  # noqa: BLE001 — re-raised on the main thread
            run_error["exc"] = exc

    t = threading.Thread(target=_run)
    t.start()
    t.join()

    reset_memory_queue()

    assert "exc" not in run_error, f"background update raised: {run_error.get('exc')!r}"
    assert observed.get("app_cfg") is family_cfg, "family AppConfig was not replayed on the timer thread"
    assert observed.get("storage_path") == "/tmp/famA/agent/memory.json", "wrong family's storage_path used"


def test_update_without_snapshot_falls_back_gracefully():
    """A direct update call (no prior enqueue) does not crash when no snapshot exists."""
    from deerflow.agents.memory.updater import MemoryUpdater

    memory_config_bridge.install()

    observed: dict = {}

    def fake_prepare(self, messages, agent_name, correction_detected, reinforcement_detected, user_id=None):
        observed["called"] = True
        return None

    run_error: dict = {}

    def _run():
        try:
            with patch.object(MemoryUpdater, "_prepare_update_prompt", fake_prepare):
                MemoryUpdater().update_memory(
                    messages=[{"type": "human", "content": "x"}],
                    thread_id="t-no-snapshot",
                    agent_name=None,
                    user_id=None,
                )
        except Exception as exc:  # noqa: BLE001
            run_error["exc"] = exc

    t = threading.Thread(target=_run)
    t.start()
    t.join()

    assert "exc" not in run_error
    assert observed.get("called") is True
