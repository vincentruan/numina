"""AgentRegistry — per-agent attribute cache using the unified Cache layer.

Agent attributes (memory_enabled, etc.) are stable and read from the backend
``ai_agents`` table. The registry caches them keyed by ``(family_id, agent_name)``
and lazily fetches on first access. System agents (family_id=0) are shared
across families.

In Redis mode, the cache is shared across all services (backend, agent,
scheduler), so backend/scheduler can read agent attributes directly.
In memory mode, each process has its own cache.
"""

from __future__ import annotations

import logging
from typing import Any

from apps.agent.core.backend_client import BackendClient
from packages.core.cache import get_cache
from packages.core.cache.keys import AGENT_REG

logger = logging.getLogger(__name__)

# How long a negative cache entry lives before re-fetching (seconds).
_NEGATIVE_CACHE_TTL_SECONDS = 60

# Default cache TTL for positive entries (seconds).
_DEFAULT_CACHE_TTL_SECONDS = 300


class AgentRegistry:
    """Caches agent attributes via the unified Cache layer."""

    async def get(self, agent_name: str, family_id: str) -> dict | None:
        """Return the cached agent dict, fetching from backend on miss.

        Returns None if the agent is not found (the caller falls back to
        defaults — memory_enabled=True). System agents (family_id=0) are
        matched server-side, so a family lookup of "asset-report" resolves to
        the shared system row.
        """
        cache = get_cache()
        key = f"{AGENT_REG}:{family_id}:{agent_name}"

        cached = await cache.get(key)
        if cached is not None:
            return cached

        # Cache miss — fetch from backend
        try:
            client = BackendClient(family_id=family_id)
            agent = await client.get_agent_by_name(agent_name)
            if agent is not None:
                await cache.set(key, agent, ttl=_DEFAULT_CACHE_TTL_SECONDS)
                logger.info(
                    "[AgentRegistry] cached agent %s family=%s memory_enabled=%s",
                    agent_name, family_id, agent.get("memory_enabled"),
                )
                return agent
            return None
        except Exception as exc:
            # Negative cache: short TTL to avoid pinning stale fallback
            await cache.set(key, None, ttl=_NEGATIVE_CACHE_TTL_SECONDS)
            logger.warning(
                "[AgentRegistry] lookup failed agent=%s family=%s: %s — "
                "falling back to defaults (memory_enabled=True, TTL=%ss)",
                agent_name, family_id, type(exc).__name__,
                int(_NEGATIVE_CACHE_TTL_SECONDS),
            )
            return None

    async def invalidate(
        self, family_id: str | None = None, agent_name: str | None = None
    ) -> None:
        """Drop cached entries. Called when an agent's attributes change.

        With no args, clears everything. With family_id, clears that family's
        entries. With both, clears one entry.
        """
        cache = get_cache()
        if family_id is None and agent_name is None:
            await cache.clear()
            return
        if family_id is not None and agent_name is not None:
            key = f"{AGENT_REG}:{family_id}:{agent_name}"
            await cache.delete(key)


# Module-level singleton.
_registry = AgentRegistry()


def get_agent_registry() -> AgentRegistry:
    """Return the process-wide AgentRegistry singleton."""
    return _registry
