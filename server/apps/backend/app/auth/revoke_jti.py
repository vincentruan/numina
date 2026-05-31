# Re-export shim — implementation moved to packages/security/revoke_jti.py
from packages.security.revoke_jti import (  # noqa: F401
    _is_jti_revoked,
    _is_token_revoked_for_user,
    cleanup_expired_revoked_tokens,
    revoke_all_user_tokens,
    revoke_jti,
    revoke_jti_atomic,
)
