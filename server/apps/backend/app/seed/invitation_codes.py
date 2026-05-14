"""Seed fixed invitation codes for CI / development environments.

In non-production environments, insert a set of well-known codes so that
the E2E seed script can register test families without needing a pre-seeded
database or a separate admin API call.

These codes are intentionally predictable — they are only active when
ENVIRONMENT != "production".
"""

import logging

logger = logging.getLogger(__name__)

# Fixed codes used by tests/data/seed-data.sh in CI
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


def seed_invitation_codes(db) -> None:
    """Insert CI invitation codes if they don't already exist.

    Only runs in non-production environments.
    """
    from apps.backend.app.config import settings

    if settings.ENVIRONMENT == "production":
        return

    from apps.backend.app.models.family_invitation_code import FamilyInvitationCode
    from apps.backend.app.utils.snowflake import next_id

    inserted = 0
    for code in CI_INVITATION_CODES:
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
        logger.info(f"已插入 {inserted} 个 CI 邀请码")
