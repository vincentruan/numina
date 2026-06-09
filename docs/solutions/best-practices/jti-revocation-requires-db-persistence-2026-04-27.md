---
title: JTI Revocation Must Be Persisted to Database, Not Held In-Memory
date: 2026-04-27
category: docs/solutions/best-practices
module: backend
problem_type: best_practice
component: authentication
severity: high
applies_when:
  - Implementing JWT token revocation (logout, password change, device revocation)
  - Any security state that must survive server restarts
tags: [jwt, jti-revocation, token-security, persistence, server-restart, auth-security]
related_components: [database, background_job]
---

# JTI Revocation Must Be Persisted to Database, Not Held In-Memory

## Context

The original auth implementation stored revoked JTIs in in-memory dicts (`_revoked_jtis`, `_user_revocation_times`) in `server/apps/backend/app/auth/deps.py`. This works perfectly in development and single-process testing. The failure mode only appears in production: after any server restart or redeploy, the in-memory state is lost and previously revoked tokens become valid again.

A user who logs out (revoking their JTI) can have their token reused by an attacker who captured it — after the next server restart, the revocation is gone. This is a security boundary failure, not a data consistency issue.

## Guidance

Persist revoked JTIs to a database table with an `expires_at` column for automatic cleanup. The existing `RevokedToken` table handles both single-JTI revocation and user-level revocation.

**Model** (`server/packages/db/models/revoked_token.py`):

```python
class RevokedToken(Base):
    __tablename__ = "revoked_tokens"

    id: Mapped[int] = mapped_column(primary_key=True)
    jti: Mapped[str] = mapped_column(unique=True, index=True)   # single token
    user_id: Mapped[str] = mapped_column(index=True)            # user-level revocation
    revoked_at: Mapped[float] = mapped_column()                 # Unix timestamp
    expires_at: Mapped[float] = mapped_column(index=True)       # for cleanup

    __table_args__ = (
        Index("ix_revoked_tokens_user_expires", "user_id", "expires_at"),
    )
```

**Revocation functions** (`server/apps/backend/app/auth/deps.py`):

```python
# Before — lost on restart
_revoked_jtis: dict[str, float] = {}
_user_revocation_times: dict[str, float] = {}

def revoke_jti(jti: str, expiry: float) -> None:
    _revoked_jtis[jti] = expiry

# After — survives restart
def revoke_jti(jti: str, user_id: str, expires_at: float, db: Session) -> None:
    db.add(RevokedToken(jti=jti, user_id=user_id,
                        revoked_at=time.time(), expires_at=expires_at))
    db.commit()

def is_token_revoked(jti: str, user_id: str, issued_at: float, db: Session) -> bool:
    # Check user-level revocation first (faster — one row covers all tokens)
    user_revocation = db.query(RevokedToken).filter(
        RevokedToken.user_id == user_id,
        RevokedToken.jti == None,           # user-level entries have no jti
        RevokedToken.revoked_at > issued_at,
        RevokedToken.expires_at > time.time(),
    ).first()
    if user_revocation:
        return True
    # Then check specific JTI
    return db.query(RevokedToken).filter(
        RevokedToken.jti == jti,
        RevokedToken.expires_at > time.time(),
    ).first() is not None
```

**Cleanup** — APScheduler hourly task in `server/apps/scheduler_worker/scheduler.py`:

```python
def cleanup_expired_revoked_tokens(db: Session) -> None:
    """Delete expired revocation records to keep the table small."""
    db.query(RevokedToken).filter(
        RevokedToken.expires_at < time.time()
    ).delete()
    db.commit()

scheduler.add_job(cleanup_expired_revoked_tokens, "interval", hours=1)
```

**Device session revocation** reuses the same table — when a `DeviceSession` is revoked, its `refresh_jti` is inserted into `RevokedToken`. This keeps the token validation path unchanged: all revocation checks go through one table. (session history)

Revoked records are retained for 7 days after expiry for audit purposes before physical deletion. (session history)

## Why This Matters

In-memory revocation is invisible in development — it works perfectly until the first production restart. Deploys, crashes, and container restarts all clear in-memory state. An attacker who captures a token before logout can wait for the next restart and then use it. The fix is cheap: one DB table, one index, one hourly cleanup job.

The same argument applies to any security state: rate-limit counters, CAPTCHA payloads, session locks. If the state must hold across restarts, it must be persisted. See `security-protection.md` for the analogous pattern applied to login rate-limit counters.

## When to Apply

- JWT logout / token revocation
- Password change (invalidate all existing tokens for a user)
- Device session revocation (`DELETE /auth/devices/{id}`)
- Any security enforcement state that must survive process restart

## Examples

**Vulnerable** — revocation lost on restart:
```python
_revoked_jtis: dict[str, float] = {}  # cleared on every restart

def logout(token_jti: str):
    _revoked_jtis[token_jti] = expiry  # gone after next deploy
```

**Safe** — persisted to DB:
```python
def logout(token_jti: str, user_id: str, expires_at: float, db: Session):
    db.add(RevokedToken(jti=token_jti, user_id=user_id,
                        revoked_at=time.time(), expires_at=expires_at))
    db.commit()
    # Survives restarts, deploys, crashes
```

## Related

- `docs/solutions/best-practices/security-protection.md` — rate-limit counters use cache backend for restart-persistence (same architectural argument, different mechanism)
- Tech debt cleanup spec: `docs/superpowers/specs/2026-04-21-tech-debt-cleanup-design.md` §1.1
- Device auth spec: `docs/superpowers/specs/2026-04-25-device-auth-design.md` §5
