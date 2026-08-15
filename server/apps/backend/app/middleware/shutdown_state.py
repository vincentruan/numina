"""Backend-local graceful shutdown state management.

Tracks whether the backend process is shutting down to reject new task creation.
This is a backend-process-local singleton - the agent has its own separate
ShutdownState in apps.agent.services.runtime.shutdown_state. The two processes
coordinate via their own SIGTERM handlers; cross-process coordination is not
needed because each process rejects new work independently during its own shutdown.
"""

from __future__ import annotations

import logging
from typing import ClassVar

logger = logging.getLogger(__name__)


class ShutdownState:
    """Global shutdown state for graceful shutdown coordination (backend-local).

    Used by ShutdownGuardMiddleware to reject new task creation during the
    backend's own shutdown window. The backend receives SIGTERM before its
    graceful shutdown sequence; the middleware returns 503 + Retry-After for
    task-creation endpoints until the process exits.
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
        """Mark that shutdown is in progress."""
        if not self._shutting_down:
            logger.info("[ShutdownState] Marking backend as shutting down")
            self._shutting_down = True

    def reset(self) -> None:
        """Reset shutdown state (for testing only)."""
        self._shutting_down = False


def is_shutting_down() -> bool:
    """Check if the backend is shutting down."""
    return ShutdownState().shutting_down


def mark_shutting_down() -> None:
    """Mark that the backend is shutting down."""
    ShutdownState().mark_shutting_down()
