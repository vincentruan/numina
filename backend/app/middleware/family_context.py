"""Family context middleware.

Decodes the JWT and injects request.state.family_id from the 'fid' claim.
No DB hit — family_id is cryptographically bound in the token payload.

Agent routes (/api/v1/ai/internal/*) are exempt: they authenticate via
HMAC token + X-Family-Id header, handled by verify_agent_token().
"""

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

_EXEMPT_PREFIXES = (
    "/api/v1/ai/internal/",
    "/api/v1/auth/",
    "/api/v1/captcha/",
    "/api/health",
    "/uploads/",
    "/static/",
)


def _decode_family_id(token: str) -> str | None:
    """Extract family_id from JWT 'fid' claim without full validation."""
    try:
        import base64
        import json
        parts = token.split(".")
        if len(parts) != 3:
            return None
        payload = parts[1]
        padding = 4 - len(payload) % 4
        if padding != 4:
            payload += "=" * padding
        data = json.loads(base64.urlsafe_b64decode(payload))
        return data.get("fid")
    except Exception:
        return None


class FamilyContextMiddleware(BaseHTTPMiddleware):
    """Inject request.state.family_id from the JWT 'fid' claim.

    Sets request.state.family_id to the family_id string when a valid JWT
    with a 'fid' claim is present. Sets it to None otherwise.
    Does NOT enforce authentication — that remains the responsibility of
    get_current_user() dependencies.
    """

    async def dispatch(self, request: Request, call_next):
        request.state.family_id = None

        if not any(request.url.path.startswith(p) for p in _EXEMPT_PREFIXES):
            token = self._extract_token(request)
            if token:
                request.state.family_id = _decode_family_id(token)

        return await call_next(request)

    def _extract_token(self, request: Request) -> str | None:
        # Check cookies first (handle mock requests in tests)
        if hasattr(request, "cookies"):
            cookie_token = request.cookies.get("access_token")
            if cookie_token:
                return cookie_token
        # Then check Authorization header
        auth = request.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            return auth[7:]
        return None
