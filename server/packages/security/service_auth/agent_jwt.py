"""Service-to-service JWT for backend → agent calls."""

from datetime import datetime, timedelta

from jose import jwt

from packages.core.settings import settings

ALGORITHM = "HS256"
_AGENT_TOKEN_TTL_SECONDS = 300


def create_agent_token(family_id: str, agent_instance_id: str = "backend") -> str:
    """Create a short-lived JWT for backend→agent service-to-service calls.

    Cryptographically binds family_id so it cannot be tampered with.
    """
    now = datetime.utcnow()
    payload = {
        "sub": "agent",
        "fid": family_id,
        "agt": agent_instance_id,
        "iat": now,
        "exp": now + timedelta(seconds=_AGENT_TOKEN_TTL_SECONDS),
        "type": "agent",
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=ALGORITHM)
