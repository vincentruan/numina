"""Global API rate limiting middleware."""

from fastapi import Request, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import settings
from app.services.security_log import _log_security_event, SecurityEventType


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Global API rate limiting middleware.

    Limits requests per client (IP or authenticated user) to prevent abuse.
    """

    # Skip rate limiting for these paths
    SKIP_PATHS = {
        "/api/health",
        "/api/v1/auth/login",
        "/api/v1/auth/register",
    }

    # Paths that don't count towards rate limit
    STATIC_PREFIXES = ("/uploads/", "/static/")

    async def dispatch(self, request: Request, call_next):
        # Skip rate limiting for health check and auth endpoints
        if request.url.path in self.SKIP_PATHS:
            return await call_next(request)

        # Skip for static files
        if any(request.url.path.startswith(prefix) for prefix in self.STATIC_PREFIXES):
            return await call_next(request)

        # Get client identifier
        client_id = self._get_client_id(request)

        # Check rate limit using in-memory storage
        # Note: For distributed deployments, replace with cache layer
        if not self._check_rate_limit(client_id):
            _log_security_event(SecurityEventType.GLOBAL_RATE_LIMITED, client_id=client_id, path=request.url.path)
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="请求次数过多，请稍后重试",
            )

        return await call_next(request)

    def _get_client_id(self, request: Request) -> str:
        """Identify client by IP address or authenticated user token."""
        # Try to get user from Authorization header (if present)
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            # For authenticated requests, use partial token as identifier
            # This provides per-user rate limiting
            token = auth_header[7:27]  # Use first 20 chars of token
            return f"user:{token}"

        # Fall back to IP address
        client_ip = request.client.host if request.client else "unknown"
        return f"ip:{client_ip}"

    def _check_rate_limit(self, client_id: str) -> bool:
        """Check if client is within rate limit.

        Uses in-memory dict for rate limiting.
        For distributed deployments, use cache layer instead.
        """
        import time

        # Use module-level storage for rate limiting
        if not hasattr(RateLimitMiddleware, "_rate_store"):
            RateLimitMiddleware._rate_store: dict[str, tuple[int, float]] = {}

        store = RateLimitMiddleware._rate_store
        current_time = time.time()
        window_start = current_time - 60  # 1 minute window

        # Clean up expired entries
        expired_keys = [
            k for k, (_, timestamp) in store.items()
            if timestamp < window_start
        ]
        for k in expired_keys:
            del store[k]

        # Get current count
        count, timestamp = store.get(client_id, (0, current_time))

        # Reset if outside window
        if timestamp < window_start:
            count = 0
            timestamp = current_time

        # Check limit
        limit = settings.GLOBAL_RATE_LIMIT_PER_MINUTE
        if count >= limit:
            return False

        # Increment count
        store[client_id] = (count + 1, timestamp)
        return True