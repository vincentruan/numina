"""Backend middleware for graceful shutdown coordination.

Rejects new task creation requests during shutdown with 503 + Retry-After header.
"""

from __future__ import annotations

import logging
from collections.abc import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

logger = logging.getLogger(__name__)


class ShutdownGuardMiddleware(BaseHTTPMiddleware):
    """Middleware that rejects new task creation during shutdown.

    Checks if the backend is shutting down (via ShutdownState) and rejects
    POST requests to task-creation endpoints with 503 + Retry-After header.

    Existing SSE connections remain open during drain — only new task creation
    is blocked.
    """

    # Endpoints that create new tasks (should be blocked during shutdown)
    TASK_CREATION_PATHS = {
        "/api/v1/ai/report/generate/events",
        "/api/v1/ai/finance-coach/generate",
        "/api/v1/ai/wish-advice/generate",
        "/api/v1/ai/import/parse",
        "/api/v1/ai/literacy/generate",
        # Add other task-creation endpoints as needed
    }

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Check shutdown state and reject task creation if shutting down."""
        # Use backend-local ShutdownState (not the agent's - separate processes)
        from apps.backend.app.middleware.shutdown_state import is_shutting_down

        # Only check POST requests to task-creation endpoints
        if request.method == "POST" and request.url.path in self.TASK_CREATION_PATHS and is_shutting_down():
                logger.warning(
                    f"[ShutdownGuard] Rejecting task creation during shutdown: "
                    f"{request.method} {request.url.path}"
                )
                return JSONResponse(
                    status_code=503,
                    content={
                        "code": "SERVICE_UNAVAILABLE",
                        "message": "服务正在关停，暂不接受新任务。请稍后重试。",
                        "data": None,
                    },
                    headers={"Retry-After": "30"},  # Suggest retry after 30s
                )

        # Pass through all other requests
        return await call_next(request)
