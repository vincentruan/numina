"""Graceful shutdown state management for the agent worker.

Tracks whether the agent is shutting down to reject new tasks and drain in-flight tasks.
"""

from __future__ import annotations

import logging
from typing import ClassVar

logger = logging.getLogger(__name__)


class ShutdownState:
    """Global shutdown state for graceful shutdown coordination.

    Used by lifespan.py to coordinate shutdown across multiple components:
    - Reject new task creation (503 responses)
    - Drain in-flight tasks with configurable timeout
    - Force cancel remaining tasks after timeout

    This is a singleton pattern - all components check the same instance.
    """

    _instance: ClassVar[ShutdownState | None] = None
    _shutting_down: bool = False

    def __new__(cls) -> ShutdownState:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    @property
    def shutting_down(self) -> bool:
        """Check if shutdown is in progress."""
        return self._shutting_down

    def mark_shutting_down(self) -> None:
        """Mark that shutdown is in progress.

        Called by SIGTERM handler to signal all components to stop accepting
        new work and prepare for graceful shutdown.
        """
        if not self._shutting_down:
            logger.info("[ShutdownState] Marking as shutting down")
            self._shutting_down = True

    def reset(self) -> None:
        """Reset shutdown state (for testing only)."""
        self._shutting_down = False


def is_shutting_down() -> bool:
    """Check if the agent is shutting down.

    Convenience function that checks the global ShutdownState instance.
    Used by routers to reject new tasks during shutdown.
    """
    state = ShutdownState()
    return state.shutting_down


def mark_shutting_down() -> None:
    """Mark that shutdown is in progress.

    Convenience function that marks the global ShutdownState instance.
    Called by SIGTERM handler.
    """
    state = ShutdownState()
    state.mark_shutting_down()
