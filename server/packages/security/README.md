# packages/security

Auth utilities for the Numina server monorepo. Provides JWT revocation (database-backed, persists across restarts), FastAPI auth middleware for the frontend app (`frontend_auth`), and service-to-service JWT auth for the agent (`service_auth`).

## Exports

| Symbol | Type | Description |
|--------|------|-------------|
| `revoke_jti` | function | Revokes a single JWT by JTI — persists to DB |
| `revoke_all_user_tokens` | function | Revokes all tokens for a user by recording their `iat` cutoff |
| `cleanup_expired_revoked_tokens` | function | Deletes expired revocation records — called by the scheduler worker |
| `frontend_auth` | subpackage | FastAPI auth dependencies for user-facing endpoints |
| `service_auth` | subpackage | Agent JWT auth via `agent_jwt.py` for service-to-service calls |
