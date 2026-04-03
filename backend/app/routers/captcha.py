"""ALTCHA captcha challenge endpoint."""

from fastapi import APIRouter
from altcha import create_challenge, ChallengeOptions

from app.config import settings

router = APIRouter(prefix="/captcha", tags=["captcha"])


@router.get("/challenge")
def get_challenge():
    """Generate an ALTCHA challenge for the client to solve.

    Returns challenge data that the client must solve via proof-of-work.
    The challenge is validated on protected endpoints in production mode.
    """
    challenge = create_challenge(ChallengeOptions(
        hmac_key=settings.ALTCHA_HMAC_KEY,
        max_number=50000,  # Low difficulty for mobile-friendly compute time
    ))
    return challenge