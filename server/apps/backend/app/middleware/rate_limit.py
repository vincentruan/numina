"""Global API rate limiting middleware.

Rate Limiting Strategy:
- Uses in-memory storage (class-level dict) for rate limit counters
- Limits: 100 requests per minute per client (configurable via GLOBAL_RATE_LIMIT_PER_MINUTE)
- Client identification: Authenticated users by decoded user_id, unauthenticated by real IP

Trusted Proxy Validation:
- Only accepts X-Forwarded-For from IPs in TRUSTED_PROXY_IPS
- Parses X-Forwarded-For right-to-left to find first non-trusted IP
- Falls back to socket address if untrusted or invalid

Trade-offs:
- Single-worker deployment: Works as expected
- Multi-worker deployment: Each worker maintains independent rate limit state.
  This means the effective limit = workers × configured limit.
  For distributed rate limiting, implement RedisCacheBackend and modify
  _check_rate_limit() to use the cache layer.

See design.md for detailed trade-off analysis.
"""

import ipaddress
import logging

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

from apps.backend.app.config import settings
from apps.backend.app.errors import AppError, ErrorCode
from apps.backend.app.services.security_log import SecurityEventType, _log_security_event

logger = logging.getLogger(__name__)


def _is_ip_in_trusted_list(ip_str: str, trusted_ips: list[str]) -> bool:
    """Check if an IP address is in the trusted proxy list.

    Supports both individual IPs and CIDR ranges.

    Args:
        ip_str: IP address to check
        trusted_ips: List of trusted IPs/CIDR ranges

    Returns:
        True if IP is trusted, False otherwise
    """
    try:
        ip = ipaddress.ip_address(ip_str)
        for trusted in trusted_ips:
            if "/" in trusted:
                # CIDR range
                if ip in ipaddress.ip_network(trusted, strict=False):
                    return True
            else:
                # Individual IP
                if ip == ipaddress.ip_address(trusted):
                    return True
        return False
    except ValueError:
        return False


def _get_real_client_ip(request: Request) -> str:
    """Extract real client IP from request, with trusted proxy validation.

    Trusted proxy validation logic:
    1. Check if request source IP is in TRUSTED_PROXY_IPS
    2. If from trusted proxy: parse X-Forwarded-For, find first non-trusted IP
    3. If not from trusted proxy: use socket address, ignore all headers
    4. If cannot parse: fall back to socket address

    Args:
        request: FastAPI request object

    Returns:
        Real client IP address
    """
    trusted_ips = settings.TRUSTED_PROXY_IPS

    # Get socket address (direct connection)
    socket_ip = request.client.host if request.client else "unknown"

    # If no trusted proxies configured, use socket address
    if not trusted_ips:
        return socket_ip

    # Check if request is from a trusted proxy
    if not _is_ip_in_trusted_list(socket_ip, trusted_ips):
        # Not from trusted proxy, ignore headers
        return socket_ip

    # From trusted proxy, parse X-Forwarded-For
    xff = request.headers.get("X-Forwarded-For")
    if not xff:
        # Try X-Real-IP as fallback
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip.split(",")[0].strip()
        return socket_ip

    # Parse X-Forwarded-For (right to left)
    # Format: client, proxy1, proxy2
    ips = [ip.strip() for ip in xff.split(",")]

    # From right to left, find first IP not in trusted proxies
    for ip in reversed(ips):
        if not _is_ip_in_trusted_list(ip, trusted_ips):
            return ip

    # All IPs are trusted (shouldn't happen in normal operation)
    # Log anomaly and return leftmost IP
    logger.warning(
        f"IP resolution anomaly: all X-Forwarded-For IPs are trusted proxies. "
        f"X-Forwarded-For: {xff}, socket: {socket_ip}"
    )
    return ips[0] if ips else socket_ip


def _decode_jwt_user_id(token: str) -> str | None:
    """Extract user_id from JWT token without full validation.

    This is a lightweight extraction for rate limiting purposes.
    The actual auth validation happens separately.

    Args:
        token: JWT token string

    Returns:
        user_id (sub claim) if extractable, None otherwise
    """
    try:
        import base64
        import json

        # JWT format: header.payload.signature
        parts = token.split(".")
        if len(parts) != 3:
            return None

        # Decode payload (middle part)
        # Add padding if needed
        payload = parts[1]
        padding = 4 - len(payload) % 4
        if padding != 4:
            payload += "=" * padding

        decoded = base64.urlsafe_b64decode(payload)
        data = json.loads(decoded)

        return data.get("sub")  # user_id is in 'sub' claim
    except Exception:
        return None


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Global API rate limiting middleware.

    Limits requests per client (IP or authenticated user) to prevent abuse.
    """

    # Skip rate limiting for these paths
    SKIP_PATHS = {
        "/api/health",
        "/api/v1/auth/login",
        "/api/v1/auth/register",
        "/api/v1/captcha/challenge",  # Allow challenge fetch before auth attempt
    }

    # Paths that don't count towards rate limit
    STATIC_PREFIXES = ("/uploads/", "/static/")

    async def dispatch(self, request: Request, call_next):
        # Skip rate limiting entirely in development/CI
        # Production environments still need protection
        if settings.ENVIRONMENT != "production":
            return await call_next(request)

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
            raise AppError(ErrorCode.RATE_LIMITED)

        return await call_next(request)

    def _get_client_id(self, request: Request) -> str:
        """Identify client by decoded user_id or real IP address."""
        # Try to get user_id from JWT token (if present)
        # First check Authorization header, then check cookies
        token = None
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header[7:]  # Remove "Bearer " prefix
        elif hasattr(request, "cookies") and request.cookies.get("access_token"):
            token = request.cookies.get("access_token")

        if token:
            user_id = _decode_jwt_user_id(token)
            if user_id:
                return f"user:{user_id}"
            # If token decode fails, fall through to IP-based identification

        # Fall back to real IP address (with trusted proxy validation)
        client_ip = _get_real_client_ip(request)
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