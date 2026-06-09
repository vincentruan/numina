---
title: ALTCHA Captcha Best Practices for Mobile-Focused Applications
date: 2026-04-03
category: best-practices
module: authentication
problem_type: best_practice
component: authentication
severity: medium
applies_when:
  - Implementing ALTCHA or similar PoW CAPTCHA systems
  - Mobile-first user bases where compute delays impact UX
  - Registration/authentication flows requiring abuse prevention
tags:
  - altcha
  - captcha
  - replay-attack-prevention
  - pow-difficulty
  - mobile-performance
  - vue
  - fastapi
---

# ALTCHA Captcha Best Practices for Mobile-Focused Applications

## Context

Proof-of-work (PoW) CAPTCHA systems like ALTCHA provide privacy-friendly bot protection without third-party tracking. However, without proper implementation, they suffer from two critical vulnerabilities:

1. **Replay attacks**: A solved challenge payload can be reused multiple times, allowing attackers to bypass CAPTCHA protection by capturing a single valid solution.

2. **Mobile performance degradation**: High PoW difficulty settings cause significant compute delays on mobile devices, creating poor user experience for legitimate users while the security benefit against automated attacks remains marginal.

These issues are particularly acute for applications targeting mobile-first or family-oriented user bases where UX friction directly impacts adoption.

## Guidance

Implement ALTCHA CAPTCHA with these core practices:

### 1. Replay Attack Prevention via Payload Registry

Store a SHA-256 hash of verified payloads in a cache with TTL matching the challenge expiry window. Reject any payload whose hash already exists in the registry.

```python
# server/apps/backend/app/auth/captcha.py
import hashlib
from app.services.cache import get_captcha_payload_cache

async def verify_captcha(request: Request) -> None:
    # ... standard ALTCHA verification first ...

    # Replay attack prevention
    cache = get_captcha_payload_cache()
    payload_hash = hashlib.sha256(altcha.encode()).hexdigest()
    cache_key = f"altcha:used:{payload_hash}"

    if cache.get(cache_key):
        _log_security_event(SecurityEventType.CAPTCHA_REPLAY_ATTACK, client_id=...)
        raise AppError(ErrorCode.CAPTCHA_REPLAY)  # → 400, localized via zh-CN/en-US

    # Store hash with TTL matching challenge expiry (typically 1 hour)
    cache.set(cache_key, "1", ttl_seconds=3600)
```

**Fail-closed posture**: If the cache is unavailable, return 503 Service Unavailable rather than allowing the request through. This prevents attackers from exploiting cache failures.

```python
except Exception as e:
    logger.error(f"Captcha cache error: {e}")
    raise AppError(ErrorCode.CAPTCHA_SERVICE_UNAVAILABLE)  # → 503, localized
```

### 2. Endpoint-Specific Difficulty Tuning

Configure different PoW difficulty levels based on endpoint risk profile and usage frequency:

```python
# server/apps/backend/app/routers/captcha.py
DIFFICULTY_MAP = {
    "login": 30000,        # Lower: high-frequency, returning users
    "register": 100000,    # Higher: abuse prevention for anonymous flow
    "join-family": 100000, # Higher: invite code abuse prevention
}
DEFAULT_DIFFICULTY = 50000  # Backward compatible default

@router.get("/challenge")
def get_challenge(endpoint: str | None = None):
    max_number = DIFFICULTY_MAP.get(endpoint, DEFAULT_DIFFICULTY)
    challenge = create_challenge(ChallengeOptions(
        hmac_key=settings.ALTCHA_HMAC_KEY,
        max_number=max_number,
    ))
    return challenge
```

The frontend passes the endpoint parameter when requesting a challenge:

```vue
<!-- frontend/src/components/common/AltchaWidget.vue -->
<altcha-widget
  challengeurl="/api/v1/captcha/challenge?endpoint=login"
  ...
/>
```

### 3. Dedicated Cache Factory with Reset Capability

Separate the CAPTCHA payload cache from other caches (rate limiting, session) for isolation and testing:

```python
# server/apps/backend/app/services/cache/factory.py
_captcha_payload_cache: CacheBackend | None = None

def get_captcha_payload_cache() -> CacheBackend:
    global _captcha_payload_cache
    if _captcha_payload_cache is None:
        if settings.CACHE_BACKEND == "redis":
            _captcha_payload_cache = RedisCacheBackend(settings.REDIS_URL)
        else:
            _captcha_payload_cache = MemoryCacheBackend()
    return _captcha_payload_cache

def reset_captcha_payload_cache() -> None:
    """Reset for testing - clears cache and resets singleton."""
    global _captcha_payload_cache
    if _captcha_payload_cache is not None:
        _captcha_payload_cache.clear()
    _captcha_payload_cache = None
```

### 4. Security Event Monitoring

Define a dedicated security event type for replay attacks to enable monitoring and alerting:

```python
# server/apps/backend/app/services/security_log.py
class SecurityEventType:
    CAPTCHA_VERIFICATION_FAILED = "captcha_verification_failed"
    CAPTCHA_REPLAY_ATTACK = "captcha_replay_attack"  # New type
```

### 5. Frontend UX Enhancements

Provide loading state feedback and accessibility attributes:

```vue
<div :aria-busy="isComputing" aria-live="polite">
  <div v-if="isComputing" class="altcha-loading">
    <van-loading>正在验证...</van-loading>
  </div>
  <div v-else-if="showSuccess" class="altcha-success">
    <van-icon name="success" />
    <span class="sr-only">验证成功</span>
  </div>
  <div v-if="errorMessage" role="alert">{{ errorMessage }}</div>
</div>
```

## Why This Matters

| Aspect | Without Implementation | With Implementation |
|--------|------------------------|---------------------|
| Replay attacks | Single solved challenge reused indefinitely | Each payload usable only once |
| Cache failure | Attackers exploit downtime to bypass | Service unavailable (fail-closed) |
| Mobile login UX | 10+ second PoW compute on low-end devices | 2-3 second compute with tuned difficulty |
| Security monitoring | No visibility into attack patterns | Structured events for replay attack detection |
| Accessibility | Silent state changes confuse users | ARIA attributes announce verification progress |

The endpoint-specific difficulty approach acknowledges that PoW difficulty is primarily a UX lever, not a security guarantee. The actual security comes from the cryptographic verification and replay prevention, not from making legitimate users wait longer.

## When to Apply

- Any application using ALTCHA or similar PoW CAPTCHA systems
- Mobile-first or mobile-heavy user bases where compute delays matter
- Registration/authentication flows that need abuse prevention
- Applications requiring security event audit trails
- Production deployments where cache reliability is critical

## Examples

**Challenge Request with Endpoint Parameter:**
```
GET /api/v1/captcha/challenge?endpoint=login
Response: { "challenge": "...", "max_number": 30000, ... }

GET /api/v1/captcha/challenge?endpoint=register
Response: { "challenge": "...", "max_number": 100000, ... }
```

**Replay Attack Detection:**
```
First request: Payload hash stored in cache
[security] captcha_verification_passed | client_id=192.168.1.1

Second request (same payload):
[security] captcha_replay_attack | client_id=192.168.1.1
Response: 400 Bad Request
```

**Cache Failure (Fail-Closed):**
```
Redis connection timeout:
[error] Captcha cache error: ConnectionTimeout
Response: 503 Service Unavailable
```

**Frontend Widget Integration:**
```vue
<AltchaWidget
  v-model="captchaPayload"
  endpoint="login"
/>
```

The widget automatically requests a lower-difficulty challenge for login, shows loading state during PoW computation, and emits the verified payload for form submission.

## Related

- [ALTCHA Captcha Implementation Plan](../../plans/2026-04-03-001-feat-altcha-captcha-plan.md) - Original R1-R22 requirements
- [ALTCHA Best Practices Plan](../../plans/2026-04-03-002-feat-altcha-best-practices-plan.md) - R23-R30 enhancement requirements
- [Security Protection Patterns](./security-protection.md) - Complementary rate limiting and cache patterns
- [Security Audit Patterns](./security-audit.md) - Security event logging infrastructure