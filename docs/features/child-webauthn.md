# Child WebAuthn Authentication

## Overview

Children can log in using biometric authentication (Face ID, Touch ID, fingerprint) via WebAuthn passkeys, with emoji PIN as fallback.

## User Flow

### Daily Login
1. Child opens app → `/child/select`
2. Taps their avatar
3. If passkey registered on this device: shows "使用面容或指纹解锁" button
4. Child taps → browser prompts for biometric
5. On success → logged in to `/child/`

### Fallback to PIN
- Tap "使用图形密码" to switch to emoji PIN grid
- Enter 4-emoji sequence
- Tap "使用面容/指纹" to switch back if WebAuthn available

### First-time Passkey Registration (Phase 2)
- Currently: passkey registration is available via API but not yet surfaced in UI
- Planned: prompt during child account binding flow

## Security Model

- **Device-bound**: Passkeys cannot be exported or copied between devices
- **Biometric-protected**: OS-level security (Face ID / Touch ID / fingerprint)
- **PIN fallback**: Always available as backup authentication method
- **Revocable**: Parents can delete passkeys via family settings (Phase 2)

## Browser Support

| Browser | Support |
|---------|---------|
| iOS Safari 14+ | ✅ |
| Android Chrome 70+ | ✅ |
| Desktop Chrome/Edge | ✅ (with platform authenticator) |
| Firefox | ✅ (with platform authenticator) |
| Older browsers | Falls back to PIN automatically |

## API Endpoints

### Registration
- `POST /api/v1/auth/child/webauthn/register-options` — Get registration challenge
- `POST /api/v1/auth/child/webauthn/register` — Store verified credential

### Authentication
- `POST /api/v1/auth/child/webauthn/login-options` — Get authentication challenge
- `POST /api/v1/auth/child/webauthn/login` — Verify credential, issue tokens

## Configuration

```python
# backend/app/config.py
WEBAUTHN_RP_ID = "localhost"       # Domain only (no protocol/port)
WEBAUTHN_RP_NAME = "Numina"        # Human-readable app name
WEBAUTHN_ORIGIN = "http://localhost:8080"  # Full origin with protocol
```

For production, set via environment variables:
```bash
WEBAUTHN_RP_ID=yourdomain.com
WEBAUTHN_RP_NAME=Numina
WEBAUTHN_ORIGIN=https://yourdomain.com
```

## Database Schema

```sql
-- Added to users table
ALTER TABLE users ADD COLUMN webauthn_credentials TEXT;
-- JSON array: [{"id": "hex", "public_key": "hex", "sign_count": 0}]
```

## Key Files

**Backend:**
- `backend/app/auth/webauthn.py` — WebAuthn helper functions
- `backend/app/schemas/webauthn.py` — Request/response schemas
- `backend/app/routers/auth.py` — 4 WebAuthn endpoints (after `child_logout`)

**Frontend:**
- `frontend/src/utils/webauthn.ts` — Browser WebAuthn API wrapper
- `frontend/src/api/webauthn.ts` — API client functions
- `frontend/src/pages/ChildAuthPage.vue` — Auth page (WebAuthn + PIN)

## Phase 2 Roadmap

- [ ] Passkey registration UI during child account binding
- [ ] Parent management panel (view/delete registered devices)
- [ ] Multi-device passkey sync guidance
