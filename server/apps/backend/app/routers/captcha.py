"""ALTCHA captcha challenge endpoint."""

from altcha import ChallengeOptions, create_challenge
from fastapi import APIRouter
from fastapi.responses import JSONResponse

from apps.backend.app.config import settings

router = APIRouter(prefix="/captcha", tags=["captcha"])

# Endpoint-specific difficulty configuration
# Note: Client can request low difficulty for high-risk endpoint. This is a UX
# optimization for mobile performance, not a security guarantee. The actual
# security comes from the proof-of-work itself, not the difficulty parameter.
DIFFICULTY_MAP = {
    "login": 30000,        # Fast for high-frequency login
    "register": 100000,    # Harder for abuse prevention
    "join-family": 100000, # Harder for abuse prevention
}
DEFAULT_DIFFICULTY = 50000  # Backward compatible default


@router.get("/config")
def get_captcha_config():
    """Return whether captcha is enabled for the current environment."""
    try:
        return {"captcha_enabled": settings.ENVIRONMENT == "production" and not settings.DISABLE_CAPTCHA}
    except Exception as e:
        import logging
        logging.exception(f"get_captcha_config error: {e}")
        raise


@router.get("/challenge", response_class=JSONResponse)
def get_challenge(endpoint: str | None = None):
    """Generate an ALTCHA challenge for the client to solve.

    Returns challenge data that the client must solve via proof-of-work.
    The challenge is validated on protected endpoints in production mode.

    NOTE: This endpoint uses JSONResponse directly (not EnvelopeResponse) because
    the altcha browser library fetches this URL and expects the raw challenge object,
    not the standard {code, data} envelope format.

    Args:
        endpoint: Optional endpoint type to adjust difficulty.
            - "login": Lower difficulty (30000) for faster mobile UX
            - "register": Higher difficulty (100000) for abuse prevention
            - "join-family": Higher difficulty (100000) for abuse prevention
            - None or unrecognized: Default difficulty (50000)
    """
    max_number = DIFFICULTY_MAP.get(endpoint or "", DEFAULT_DIFFICULTY)
    challenge = create_challenge(ChallengeOptions(
        hmac_key=settings.ALTCHA_HMAC_KEY,
        max_number=max_number,
    ))
    return JSONResponse(content={
        "algorithm": challenge.algorithm,
        "challenge": challenge.challenge,
        "max_number": challenge.max_number,
        "salt": challenge.salt,
        "signature": challenge.signature,
    })
