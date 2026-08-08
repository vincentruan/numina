"""Bridge the per-family DeerFlow ``AppConfig`` into the background memory-update path.

Why this exists
---------------
``MemoryMiddleware.after_agent`` queues a memory update on the global
``MemoryUpdateQueue``.  The queue fires on a ``threading.Timer`` thread after a
~30 s debounce.  ContextVars do **not** propagate across ``threading.Timer``
threads, so on that background thread:

* ``get_app_config()`` falls back to ``DEER_FLOW_CONFIG_PATH`` (the base
  config, whose ``models`` list is empty — models are injected per-family into
  temp configs) → ``create_chat_model(name=None)`` → ``config.models[0]`` →
  ``IndexError: list index out of range``.
* ``get_memory_config()`` is a process-global singleton overwritten by every
  ``reload_app_config()``, so it may belong to a *different* family — the
  memory update would then be written to that other family's ``memory.json``
  (cross-family data leak).

The streaming path already pushes the family ``AppConfig`` via
``push_current_app_config`` (ContextVar) inside ``DeerFlowAdapter._produce``,
but that ContextVar is invisible to the timer thread.

Fix
---
1. **Snapshot at enqueue time.** ``MemoryUpdateQueue.add`` / ``add_nowait``
   run on the agent executor thread where the family ContextVar is active.
   Capture ``peek_current_app_config()`` keyed by ``(thread_id, user_id,
   agent_name)``.
2. **Replay at processing time.** ``MemoryUpdater._do_update_memory_sync``
   runs on the timer thread; look up the snapshot and
   ``push_current_app_config`` it so ``get_app_config()`` resolves the
   family's models.
3. **Make ``get_memory_config()`` ContextVar-aware** (return
   ``peek_current_app_config().memory`` while a runtime config is active) so
   the family's absolute ``storage_path`` is used — keeping ``memory.json``
   isolated per family.

This restores memory auto-update (broken since commit 1fad8d9f, 2026-06-06,
which moved the streaming path from a global env var to a ContextVar) without
regressing the per-family ContextVar refactor.

Cross-family safety: the snapshot is keyed by ``(thread_id, user_id,
agent_name)`` — ``thread_id`` is unique per conversation — so family A's
snapshot is never replayed for family B's update.
"""

from __future__ import annotations

import importlib
import logging
import threading
from typing import Any

from deerflow.config import memory_config as _memory_config_mod
from deerflow.config.app_config import (
    AppConfig,
    peek_current_app_config,
    pop_current_app_config,
    push_current_app_config,
)

# DeerFlow rev >=10890e10 (#4122 pluggable memory abstraction) moved the
# deermem backend's queue/updater classes out of the top-level
# ``deerflow.agents.memory`` package into
# ``deerflow.agents.memory.backends.deermem.deermem.core.*``. The classes
# themselves (``MemoryUpdateQueue``, ``MemoryUpdater``) and the patched method
# (``_do_update_memory_sync``) are unchanged — only the import path moved.
# Try the new path first, fall back to the legacy path for older harness revs.
try:
    from deerflow.agents.memory.backends.deermem.deermem.core import (
        queue as _queue_mod,  # type: ignore
    )
    from deerflow.agents.memory.backends.deermem.deermem.core import (
        updater as _updater_mod,  # type: ignore
    )
except ImportError:  # legacy harness (pre-#4122)
    from deerflow.agents.memory import queue as _queue_mod  # type: ignore
    from deerflow.agents.memory import updater as _updater_mod  # type: ignore

logger = logging.getLogger(__name__)

# (thread_id, user_id, agent_name) → family AppConfig snapshot captured at
# enqueue time, replayed on the background timer thread.
_config_store: dict[tuple[str | None, str | None, str | None], AppConfig] = {}
_store_lock = threading.Lock()

# Modules that bound ``get_memory_config`` via ``from ... import`` and must be
# re-bound to the ContextVar-aware version (importing the name copies the
# reference into the module namespace, so patching the source alone is not
# enough).
_MEMORY_CONFIG_IMPORTERS = (
    "deerflow.client",
    "deerflow.agents.memory.queue",
    "deerflow.agents.memory.storage",
    "deerflow.agents.memory.updater",
    "deerflow.agents.memory.summarization_hook",
    "deerflow.agents.middlewares.memory_middleware",
    "deerflow.agents.lead_agent.prompt",
)

_installed = False


def _queue_key(
    thread_id: str | None,
    user_id: str | None,
    agent_name: str | None,
) -> tuple[str | None, str | None, str | None]:
    return (thread_id, user_id, agent_name)


def snapshot_config(
    thread_id: str | None,
    user_id: str | None,
    agent_name: str | None,
) -> None:
    """Capture the active family AppConfig for replay on the timer thread.

    Called from the (patched) queue enqueue path, which runs on the agent
    executor thread where ``push_current_app_config`` is active. No-op when
    no runtime config is active (the update will then fall back to legacy
    behavior).
    """
    cfg = peek_current_app_config()
    if cfg is None:
        return
    with _store_lock:
        _config_store[_queue_key(thread_id, user_id, agent_name)] = cfg


def pop_config(
    thread_id: str | None,
    user_id: str | None,
    agent_name: str | None,
) -> AppConfig | None:
    """Remove and return the snapshot for this conversation (timer thread)."""
    with _store_lock:
        return _config_store.pop(_queue_key(thread_id, user_id, agent_name), None)


def clear_stash() -> None:
    """Drop all snapshots (used when the queue is cleared/reset)."""
    with _store_lock:
        _config_store.clear()


def install() -> None:
    """Apply the memory-update config bridge patches (idempotent)."""
    global _installed
    if _installed:
        return
    _installed = True

    # 1. Make get_memory_config() ContextVar-aware so the family's
    #    storage_path (and enabled/model_name) are used whenever a runtime
    #    AppConfig is active — on both the enqueue thread and the replayed
    #    timer thread.
    _orig_get_memory_config = _memory_config_mod.get_memory_config

    def _contextual_get_memory_config():
        cfg = peek_current_app_config()
        if cfg is not None:
            return cfg.memory
        return _orig_get_memory_config()

    _memory_config_mod.get_memory_config = _contextual_get_memory_config  # type: ignore[attr-defined]
    for module_path in _MEMORY_CONFIG_IMPORTERS:
        try:
            mod = importlib.import_module(module_path)
        except ImportError:
            continue
        if hasattr(mod, "get_memory_config"):
            mod.get_memory_config = _contextual_get_memory_config  # type: ignore[attr-defined]

    # 2. Snapshot the family config at enqueue time.
    _orig_add = _queue_mod.MemoryUpdateQueue.add
    _orig_add_nowait = _queue_mod.MemoryUpdateQueue.add_nowait

    def _snapshot_from_call(args: tuple, kwargs: dict) -> None:
        """Extract (thread_id, user_id, agent_name) from an add/add_nowait call.

        Signature: add(self, thread_id, messages, agent_name=None, user_id=None,
        trace_id=None, ...). args excludes ``self`` (it is bound to the method).
        thread_id is positional args[0]; agent_name/user_id may be positional
        (args[2]/args[3]) or keyword.
        """
        thread_id = kwargs.get("thread_id") or (args[0] if len(args) > 0 else None)
        agent_name = kwargs.get("agent_name") or (args[2] if len(args) > 2 else None)
        user_id = kwargs.get("user_id") or (args[3] if len(args) > 3 else None)
        snapshot_config(thread_id, user_id, agent_name)

    def _patched_add(self: Any, *args: Any, **kwargs: Any) -> None:
        _snapshot_from_call(args, kwargs)
        _orig_add(self, *args, **kwargs)

    def _patched_add_nowait(self: Any, *args: Any, **kwargs: Any) -> None:
        _snapshot_from_call(args, kwargs)
        _orig_add_nowait(self, *args, **kwargs)

    _queue_mod.MemoryUpdateQueue.add = _patched_add
    _queue_mod.MemoryUpdateQueue.add_nowait = _patched_add_nowait

    # 3. Replay the family config on the background timer thread.
    _orig_do_update = _updater_mod.MemoryUpdater._do_update_memory_sync

    def _patched_do_update(
        self: Any,
        messages: list[Any],
        thread_id: str | None = None,
        agent_name: str | None = None,
        correction_detected: bool = False,
        reinforcement_detected: bool = False,
        user_id: str | None = None,
        trace_id: str | None = None,
    ) -> bool:
        cfg = pop_config(thread_id, user_id, agent_name)
        if cfg is None:
            # No snapshot (e.g. a direct call that bypassed the queue) — fall
            # back to whatever the caller's context/global provides.
            return bool(_orig_do_update(
                self,
                messages,
                thread_id=thread_id,
                agent_name=agent_name,
                correction_detected=correction_detected,
                reinforcement_detected=reinforcement_detected,
                user_id=user_id,
                trace_id=trace_id,
            ))
        push_current_app_config(cfg)
        try:
            return bool(_orig_do_update(
                self,
                messages,
                thread_id=thread_id,
                agent_name=agent_name,
                correction_detected=correction_detected,
                reinforcement_detected=reinforcement_detected,
                user_id=user_id,
                trace_id=trace_id,
            ))
        finally:
            pop_current_app_config()

    _updater_mod.MemoryUpdater._do_update_memory_sync = _patched_do_update

    # 4. Drop snapshots when the queue is cleared (test/reset path) so the
    #    stash cannot leak entries for conversations that will never process.
    _orig_clear = _queue_mod.MemoryUpdateQueue.clear

    def _patched_clear(self: Any) -> None:
        clear_stash()
        _orig_clear(self)

    _queue_mod.MemoryUpdateQueue.clear = _patched_clear

    logger.info("[memory_bridge] installed per-family config bridge for memory updates")


# Auto-install on import so the patch is active wherever the agent runs.
install()
