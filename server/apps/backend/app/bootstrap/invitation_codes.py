"""Bootstrap invitation codes for family registration.

Production: seeds a configurable set of initial codes (from INIT_INVITATION_CODES env).
Non-production: additionally seeds fixed CI codes for E2E testing.
"""

import logging

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

CI_INVITATION_CODES = [
    "CI0001",
    "CI0002",
    "CI0003",
    "CI0004",
    "CI0005",
    "CI0006",
    "CI0007",
    "CI0008",
]


def bootstrap_invitation_codes(db: Session) -> None:
    """Ensure invitation codes exist. Idempotent.

    - Production: seeds codes from INIT_INVITATION_CODES env var (comma-separated).
    - Non-production: seeds fixed CI codes for testing.
    """
    from apps.backend.app.config import settings
    from apps.backend.app.models.family_invitation_code import FamilyInvitationCode
    from apps.backend.app.utils.snowflake import next_id

    codes_to_seed: list[str] = []

    if settings.ENVIRONMENT == "production":
        init_codes = getattr(settings, "INIT_INVITATION_CODES", "") or ""
        if init_codes:
            codes_to_seed = [c.strip() for c in init_codes.split(",") if c.strip()]
    else:
        codes_to_seed = list(CI_INVITATION_CODES)

    if not codes_to_seed:
        return

    inserted = 0
    for code in codes_to_seed:
        exists = (
            db.query(FamilyInvitationCode)
            .filter(FamilyInvitationCode.code == code)
            .first()
        )
        if not exists:
            db.add(FamilyInvitationCode(id=next_id(), code=code))
            inserted += 1

    if inserted:
        db.commit()
        logger.info(f"已初始化 {inserted} 个邀请码")
