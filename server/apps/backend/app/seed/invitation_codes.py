"""Backward-compatible shim — implementation moved to app/bootstrap/invitation_codes.py."""
from apps.backend.app.bootstrap.invitation_codes import (
    CI_INVITATION_CODES,
    bootstrap_invitation_codes,
)

seed_invitation_codes = bootstrap_invitation_codes

__all__ = ["CI_INVITATION_CODES", "seed_invitation_codes"]
