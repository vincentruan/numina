"""Subscriber registry for SSE event forwarding (Phase 4A).

Tracks active SSE subscribers per task_id. Used by trigger endpoints to
register/unregister subscribers around StreamingResponse, enabling future
subscriber-aware optimizations (skip SSE formatting when no client is listening).

Process-local dict — not shared across Uvicorn workers. For single-worker
deployments (current), this is sufficient. Multi-worker would need Redis.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncGenerator, AsyncIterator

logger = logging.getLogger(__name__)


class SubscriberRegistry:
    """Track active SSE subscribers per task_id.

    Thread-safe for single-process asyncio (no locks needed — all operations
    happen on the event loop). Not safe for multi-process deployments.
    """

    def __init__(self):
        self._subscribers: dict[str, int] = {}  # task_id → active count

    def register(self, task_id: str) -> None:
        """Register a new subscriber for a task."""
        self._subscribers[task_id] = self._subscribers.get(task_id, 0) + 1
        logger.debug(
            "[subscriber_registry] register task=%s count=%d",
            task_id,
            self._subscribers[task_id],
        )

    def unregister(self, task_id: str) -> None:
        """Unregister a subscriber for a task."""
        count = self._subscribers.get(task_id, 0)
        if count > 0:
            self._subscribers[task_id] = count - 1
            # Prune zero entries to keep the dict clean
            if self._subscribers[task_id] == 0:
                del self._subscribers[task_id]
            logger.debug(
                "[subscriber_registry] unregister task=%s count=%d",
                task_id,
                self._subscribers.get(task_id, 0),
            )

    def has_subscriber(self, task_id: str) -> bool:
        """Check if a task has at least one active subscriber."""
        return self._subscribers.get(task_id, 0) > 0

    def get_count(self, task_id: str) -> int:
        """Get the active subscriber count for a task."""
        return self._subscribers.get(task_id, 0)


# Global singleton
registry = SubscriberRegistry()


async def tracked_sse_stream(
    task_id: str,
    stream_gen: AsyncIterator[str],
) -> AsyncGenerator[bytes, None]:
    """Wrap an SSE stream generator with subscriber registration.

    Registers the subscriber before the first yield and unregisters in the
    finally block (fires on client disconnect / generator cancellation).

    Args:
        task_id: AITask primary key (subscriber tracking key).
        stream_gen: AsyncIterator yielding SSE-formatted strings.
    """
    registry.register(task_id)
    try:
        async for sse_text in stream_gen:
            yield sse_text.encode("utf-8")
    finally:
        registry.unregister(task_id)
