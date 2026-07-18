"""AgentRegistry — per-agent attribute cache for the DeerFlow adapter.

Agent attributes (memory_enabled, etc.) are stable and read from the backend
``ai_agents`` table. To avoid threading them through every adapter call site,
the registry caches them keyed by ``(family_id, agent_name)`` and lazily fetches
on first access. System agents (family_id=0) are shared across families.

Usage (plan U4 memory architecture): ``_generate_temp_config`` calls
``await AgentRegistry.get(agent_name, family_id)`` and reads ``memory_enabled``
to decide whether to disable DeerMem injection + write — replacing the earlier
adapter-layer ``if agent_name == "asset-report"`` hardcode (which would become
historical debt as more stateless agents are added). The flag lives on the
agent row (ai_agents.memory_enabled), so adding a new stateless agent is just
setting the column — no adapter code change.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from apps.agent.core.backend_client import BackendClient

logger = logging.getLogger(__name__)

# Sentinel for "lookup failed / not found" — distinct from a cached None.
_NOT_FOUND = object()


class AgentRegistry:
    """Async singleton caching agent attributes by (family_id, agent_name)."""

    def __init__(self) -> None:
        # key: (family_id, agent_name) → agent dict (or _NOT_FOUND on miss)
        self._cache: dict[tuple[str, str], Any] = {}
        # Per-key locks so concurrent first-access calls don't double-fetch.
        self._locks: dict[tuple[str, str], asyncio.Lock] = {}
        self._lock = asyncio.Lock()

    async def get(self, agent_name: str, family_id: str) -> dict | None:
        """Return the cached agent dict, fetching from backend on miss.

        Returns None if the agent is not found (the caller falls back to
        defaults — memory_enabled=True). System agents (family_id=0) are
        matched server-side, so a family lookup of "asset-report" resolves to
        the shared system row.
        """
        key = (family_id, agent_name)
        cached = self._cache.get(key)
        if cached is _NOT_FOUND:
            return None
        if cached is not None:
            return cached

        # Per-key lock: avoid double-fetch on concurrent first access.
        async with self._lock:
            lock = self._locks.setdefault(key, asyncio.Lock())
        async with lock:
            # Re-check after acquiring the per-key lock.
            cached = self._cache.get(key)
            if cached is _NOT_FOUND:
                return None
            if cached is not None:
                return cached

            try:
                client = BackendClient(family_id=family_id)
                agent = await client.get_agent_by_name(agent_name)
                self._cache[key] = agent
                logger.info(
                    "[AgentRegistry] cached agent %s family=%s memory_enabled=%s",
                    agent_name, family_id, agent.get("memory_enabled"),
                )
                return agent
            except Exception as exc:
                # Backend unreachable / 404 — cache the miss so we don't retry
                # every run (the caller falls back to memory_enabled=True).
                self._cache[key] = _NOT_FOUND
                logger.warning(
                    "[AgentRegistry] lookup failed agent=%s family=%s: %s — "
                    "falling back to defaults (memory_enabled=True)",
                    agent_name, family_id, type(exc).__name__,
                )
                return None

    def invalidate(self, family_id: str | None = None, agent_name: str | None = None) -> None:
        """Drop cached entries. Called when an agent's attributes change.

        With no args, clears everything. With family_id, clears that family's
        entries. With both, clears one entry.
        """
        if family_id is None and agent_name is None:
            self._cache.clear()
            return
        keys_to_drop = [
            k for k in self._cache
            if (family_id is None or k[0] == family_id)
            and (agent_name is None or k[1] == agent_name)
        ]
        for k in keys_to_drop:
            self._cache.pop(k, None)


# Module-level singleton.
_registry = AgentRegistry()


def get_agent_registry() -> AgentRegistry:
    """Return the process-wide AgentRegistry singleton."""
    return _registry
