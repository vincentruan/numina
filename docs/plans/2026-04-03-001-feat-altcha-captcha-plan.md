---
title: feat: ALTCHA captcha protection for auth endpoints
type: feat
status: completed
date: 2026-04-03
origin: docs/brainstorms/2026-04-02-altcha-captcha-requirements.md
---

# ALTCHA Captcha Protection for Auth Endpoints

## Overview

Add proof-of-work captcha verification to public authentication endpoints (register, login, family/join) using ALTCHA library. The captcha activates only in production environment, providing a friction barrier against automated attacks while maintaining smooth development experience.

## Problem Frame

Numina 作为自托管家庭资产管理系统，部署到生产服务器后面临公开端点的流量攻击风险：恶意账号批量注册、凭证填充攻击、邀请码滥用。现有 rate limiting 在攻击者发起请求后才生效，缺乏前置屏障。ALTCHA 通过 proof-of-work 机制要求客户端完成计算任务，显著提高自动化攻击成本。

## Requirements Trace

- R1-R3. 保护 register, login, family/join 端点
- R4-R7. 后端 challenge 端点和验证逻辑
- R8. 创建 AltchaWidget.vue 组件封装 web component
- R9. LoginPage、RegisterPage、JoinFamilyPage 集成 AltchaWidget
- R10. 组件通过 v-model 或事件将 `altcha` payload 暴露给父组件，父组件在表单提交时包含在请求中
- R11-R12. 仅生产环境启用验证
- R13-R15. 配置参数（HMAC key, 难度, 有效期）
- R16-R18. Widget 标准模式和 auto 提交
- R19-R20. Widget 状态和错误恢复
- R21. 区分错误消息
- R22. 测试覆盖

## Scope Boundaries

- 不实现 Sentinel spam filter
- 不扩展到其他端点
- 不持久化 challenge（altcha 库内置防重放）

## Context & Research

### Relevant Code and Patterns

**Backend:**
- `backend/app/config.py` — Settings pattern with environment variables and production validation
- `backend/app/routers/auth.py` — Auth router with login, register, join-family endpoints
- `backend/app/schemas/auth.py` — LoginRequest, RegisterRequest, JoinFamilyRequest schemas
- `backend/app/services/auth.py` — Auth business logic
- `backend/app/middleware/rate_limit.py` — SKIP_PATHS for public endpoints
- `backend/app/main.py` — Router registration and middleware setup

**Frontend:**
- `frontend/src/api/index.ts` — Axios instance with request interceptor (auto-adds auth header when token exists, skips when absent)
- `frontend/src/api/auth.ts` — Auth API functions
- `frontend/src/pages/LoginPage.vue` — Login form with Vant components
- `frontend/src/pages/RegisterPage.vue` — Registration form
- `frontend/src/pages/JoinFamilyPage.vue` — Join family form
- `frontend/src/types/index.ts` — TypeScript interfaces

### Institutional Learnings

From `docs/solutions/best-practices/security-protection.md`:
- Environment configuration pattern: Security settings defined in `config.py` with defaults and env var overrides
- Feature toggle pattern: `ENABLE_SECURITY_LOGGING` shows configurable security features
- Production secret validation: `SECRET_KEY` pattern with startup RuntimeError if unset

From `docs/solutions/best-practices/security-audit.md`:
- Security logging pattern: Structured format for audit trail
- Configurable toggle for security features

## Key Technical Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Challenge endpoint path | `/api/v1/captcha/challenge` | Follows existing `/api/v1` prefix convention |
| Altcha field location | JSON body, optional `altcha: str \| None` | Consistent with existing auth request schemas |
| Environment detection | `settings.ENVIRONMENT == 'production'` | Follows existing pattern in config.py Settings class |
| HMAC key validation | Startup RuntimeError if unset in production | Mirrors SECRET_KEY pattern |
| Frontend script loading | CDN with SRI integrity hash | Security best practice, user chose CDN over self-host |
| Widget state handling | Vue component wrapping web component | Clean abstraction, reusable across pages |

## Open Questions

### Resolved During Planning

- **Challenge endpoint auth**: Axios interceptor already handles public endpoints correctly (no token = no auth header). No special handling needed. (see origin: Deferred Questions)
- **Environment detection**: Use `settings.ENVIRONMENT == 'production'` directly, matching existing pattern in config.py Settings class. (see origin: Deferred Questions)
- **Schema field location**: Add `altcha: str | None = None` to auth request schemas in JSON body. (see origin: Deferred Questions)

### Deferred to Implementation

- **SRI hash value**: Must be computed from actual CDN script at implementation time
- **Vue web component event handling**: Exact v-model vs emit pattern depends on ALTCHA widget API behavior
- **Challenge endpoint URL in widget**: May need full URL or relative path depending on CORS and deployment

## High-Level Technical Design

> *This illustrates the intended approach and is directional guidance for review, not implementation specification.*

```
┌─────────────────────────────────────────────────────────────────┐
│                        Frontend (Vue 3)                          │
├─────────────────────────────────────────────────────────────────┤
│  LoginPage.vue / RegisterPage.vue / JoinFamilyPage.vue          │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  <van-form @submit="onSubmit">                           │    │
│  │    ... form fields ...                                   │    │
│  │    <AltchaWidget v-model="altchaPayload" />              │    │
│  │    <van-button native-type="submit">                     │    │
│  │  </van-form>                                             │    │
│  └─────────────────────────────────────────────────────────┘    │
│                              │                                   │
│                              ▼                                   │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  AltchaWidget.vue                                        │    │
│  │  - Loads altcha.min.js from CDN with SRI                 │    │
│  │  - Renders <altcha-widget challengeurl="...">            │    │
│  │  - Emits solved payload via v-model                      │    │
│  │  - Shows test mode in non-production                     │    │
│  └─────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
                               │
                               │ POST /auth/login { ..., altcha: "<payload>" }
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                        Backend (FastAPI)                         │
├─────────────────────────────────────────────────────────────────┤
│  POST /api/v1/auth/login                                         │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  verify_captcha_dependency                               │    │
│  │  - Check settings.ENVIRONMENT == 'production'            │    │
│  │  - If production: verify_solution(altcha, HMAC_KEY)      │    │
│  │  - Return 400 with specific error if invalid             │    │
│  └─────────────────────────────────────────────────────────┘    │
│                              │                                   │
│                              ▼                                   │
│  GET /api/v1/captcha/challenge  ◄─── Widget fetches on mount    │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  create_challenge(ChallengeOptions(                      │    │
│  │    hmac_key=settings.ALTCHA_HMAC_KEY,                    │    │
│  │    max_number=50000                                      │    │
│  │  ))                                                      │    │
│  └─────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
```

## Implementation Units

### Unit Dependency Graph

```mermaid
flow TB
    U1[Unit 1: Backend config and dependency] --> U2[Unit 2: Challenge endpoint]
    U1 --> U3[Unit 3: Captcha verification dependency]
    U3 --> U4[Unit 4: Auth schema updates]
    U4 --> U5[Unit 5: Auth endpoint integration]
    U5 --> U6[Unit 6: Frontend AltchaWidget component]
    U6 --> U7[Unit 7: Auth pages integration]
    U7 --> U8[Unit 8: Backend tests]
```

---

- [ ] **Unit 1: Backend config and dependency setup**

**Goal:** Add ALTCHA configuration to Settings and install Python library

**Requirements:** R13, R14

**Dependencies:** None

**Files:**
- Modify: `backend/pyproject.toml`
- Modify: `backend/app/config.py`

**Approach:**
1. Add `altcha` to dependencies in pyproject.toml
2. Add `ALTCHA_HMAC_KEY` to Settings with default empty string (for dev auto-generation)
3. Add startup validation: if ENVIRONMENT=production and ALTCHA_HMAC_KEY is empty, raise RuntimeError
4. Follow existing SECRET_KEY validation pattern from config.py lines 48-55

**Patterns to follow:**
- `backend/app/config.py` Settings class pattern
- SECRET_KEY validation pattern with production check

**Test scenarios:**
- Happy path: Settings loads with ALTCHA_HMAC_KEY from environment
- Error path: Production startup raises RuntimeError when ALTCHA_HMAC_KEY is empty
- Edge case: Development mode allows empty ALTCHA_HMAC_KEY with auto-generation warning

**Verification:**
- `uv sync` completes successfully
- Backend starts without error in development mode
- Backend raises RuntimeError in production mode without ALTCHA_HMAC_KEY

---

- [ ] **Unit 2: Challenge endpoint**

**Goal:** Create GET /api/v1/captcha/challenge endpoint that returns ALTCHA challenge

**Requirements:** R4, R7, R14, R15

**Dependencies:** Unit 1

**Files:**
- Create: `backend/app/routers/captcha.py`
- Modify: `backend/app/main.py`
- Modify: `backend/app/middleware/rate_limit.py`

**Approach:**
1. Create `captcha.py` router with `/captcha` prefix
2. Implement `GET /challenge` using `from altcha import create_challenge, ChallengeOptions` then `create_challenge(ChallengeOptions(...))`
3. Register router in main.py with `/api/v1` prefix
4. Add `/api/v1/captcha/challenge` to RateLimitMiddleware.SKIP_PATHS to allow challenge fetch before auth attempt. Note: auth endpoints `/api/v1/auth/login` and `/api/v1/auth/register` are already in SKIP_PATHS for different reasons (allow legitimate auth attempts).

**Patterns to follow:**
- `backend/app/routers/auth.py` router pattern
- `backend/app/middleware/rate_limit.py` SKIP_PATHS pattern

**Test scenarios:**
- Happy path: GET /api/v1/captcha/challenge returns challenge JSON with algorithm, challenge, maxnumber, salt, signature
- Integration: Challenge endpoint is not rate-limited (SKIP_PATHS)
- Edge case: Challenge response includes correct max_number=50000

**Verification:**
- `curl http://localhost:8000/api/v1/captcha/challenge` returns valid challenge JSON
- Challenge endpoint accessible without authentication

---

- [ ] **Unit 3: Captcha verification dependency**

**Goal:** Create FastAPI dependency for verifying altcha payload

**Requirements:** R5, R7, R11, R21

**Dependencies:** Unit 1

**Files:**
- Create: `backend/app/auth/captcha.py`

**Approach:**
1. Create `verify_captcha` dependency function
2. Check `settings.ENVIRONMENT == 'production'` — skip if not production
3. Extract `altcha` field from request body
4. Handle missing/empty/invalid cases with specific error messages (R21)
5. Use `from altcha import verify_solution` then `verify_solution(payload, hmac_key, check_expires=True)`
6. Log captcha verification failures for security audit (follow security_log.py pattern with SecurityEventType.CAPTCHA_VERIFICATION_FAILED)

**Technical design:**

```python
# Directional pseudo-code
async def verify_captcha(request: Request, db: Session = Depends(get_db)):
    if settings.ENVIRONMENT != 'production':
        return  # Skip in development

    body = await request.json()
    altcha = body.get('altcha')

    if altcha is None:
        raise HTTPException(400, "请完成验证码验证")
    if altcha == '':
        raise HTTPException(400, "验证码不能为空")

    verified, err = verify_solution(altcha, settings.ALTCHA_HMAC_KEY, True)
    if not verified:
        # Log security event for audit trail
        _log_security_event(SecurityEventType.CAPTCHA_VERIFICATION_FAILED, client_id=client_ip, error_type="invalid")
        raise HTTPException(400, "验证码验证失败，请重试")
```

**Patterns to follow:**
- `backend/app/auth/deps.py` get_current_user dependency pattern

**Test scenarios:**
- Happy path: Valid altcha payload passes verification
- Error path: Missing altcha returns 400 with "请完成验证码验证"
- Error path: Empty altcha returns 400 with "验证码不能为空"
- Error path: Invalid altcha returns 400 with "验证码验证失败，请重试"
- Edge case: Development mode skips verification entirely

**Verification:**
- Dependency correctly validates/invalidates test payloads
- Error messages match R21 specification

---

- [ ] **Unit 4: Auth schema updates**

**Goal:** Add optional altcha field to auth request schemas

**Requirements:** R5

**Dependencies:** None (parallel with Unit 2)

**Files:**
- Modify: `backend/app/schemas/auth.py`
- Modify: `frontend/src/types/index.ts`

**Approach:**
1. Add `altcha: str | None = None` to LoginRequest, RegisterRequest, JoinFamilyRequest
2. Update TypeScript interfaces to match

**Patterns to follow:**
- `backend/app/schemas/auth.py` existing schema pattern
- `frontend/src/types/index.ts` interface pattern

**Test scenarios:**
- Happy path: Schema accepts altcha field
- Edge case: Schema accepts request without altcha field (optional)

**Verification:**
- Backend schemas parse requests with/without altcha field
- Frontend types compile without errors

---

- [ ] **Unit 5: Auth endpoint integration**

**Goal:** Integrate captcha verification into auth endpoints

**Requirements:** R1, R2, R3, R5

**Dependencies:** Unit 3, Unit 4

**Files:**
- Modify: `backend/app/routers/auth.py`

**Approach:**
1. Add `verify_captcha` dependency to login, register, join-family endpoints
2. Dependency runs before endpoint logic
3. Verification happens transparently — endpoints unchanged otherwise

**Patterns to follow:**
- `backend/app/routers/auth.py` existing dependency injection pattern

**Test scenarios:**
- Happy path: Valid captcha allows login/register/join-family to proceed
- Error path: Invalid captcha returns 400 before endpoint logic
- Integration: Existing auth tests still pass (they run in development mode)

**Verification:**
- Manual test: Login with valid captcha succeeds
- Manual test: Login without captcha in production mode returns 400
- `uv run pytest tests/test_auth.py -v` passes

---

- [ ] **Unit 6: Frontend AltchaWidget component**

**Goal:** Create reusable Vue component wrapping ALTCHA web component

**Requirements:** R8, R10, R16, R17, R18, R19, R20

**Dependencies:** Unit 2

**Files:**
- Create: `frontend/src/components/common/AltchaWidget.vue`
- Modify: `frontend/index.html` (add CDN script with SRI)

**Approach:**
1. Add altcha.min.js script to index.html with SRI integrity hash
2. Create AltchaWidget.vue component:
   - Props: `modelValue` for v-model binding
   - Renders `<altcha-widget challengeurl="/api/v1/captcha/challenge" auto="onsubmit">`
   - Listen for `statechange` event to track verification status
   - Emit solved payload via `update:modelValue`
3. Show test mode indicator in non-production (check import.meta.env.DEV)
4. Handle error states with retry capability (R20)

**Technical design:**

```vue
<!-- Directional pseudo-code -->
<script setup lang="ts">
const props = defineProps<{ modelValue?: string }>()
const emit = defineEmits<{ 'update:modelValue': [value: string] }>()

function onStateChange(event: CustomEvent) {
  if (event.detail.state === 'verified') {
    emit('update:modelValue', event.detail.payload)
  }
}
</script>

<template>
  <altcha-widget
    challengeurl="/api/v1/captcha/challenge"
    auto="onsubmit"
    @statechange="onStateChange"
  />
</template>
```

**Patterns to follow:**
- `frontend/src/components/common/` component pattern
- Vue 3 Composition API with `<script setup lang="ts">`
- Vant 4 form integration pattern

**Test scenarios:**
- Happy path: Widget renders and fetches challenge
- Happy path: Widget emits payload when verification completes
- Edge case: Widget shows test mode in development
- Error path: Widget shows error state on challenge failure with retry option

**Verification:**
- Widget renders in LoginPage without errors
- Widget fetches challenge from backend
- Payload emitted on successful verification

---

- [ ] **Unit 7: Auth pages integration**

**Goal:** Integrate AltchaWidget into LoginPage, RegisterPage, JoinFamilyPage

**Requirements:** R9, R10

**Dependencies:** Unit 6

**Files:**
- Modify: `frontend/src/pages/LoginPage.vue`
- Modify: `frontend/src/pages/RegisterPage.vue`
- Modify: `frontend/src/pages/JoinFamilyPage.vue`
- Modify: `frontend/src/api/auth.ts` (no changes needed if types updated)

**Approach:**
1. Import AltchaWidget component
2. Add `altcha` field to form state
3. Add `<AltchaWidget v-model="form.altcha" />` before submit button
4. Form submission already sends entire form object including altcha

**Patterns to follow:**
- `frontend/src/pages/LoginPage.vue` van-form pattern
- Vant 4 van-field placement

**Test scenarios:**
- Happy path: Form submits with altcha payload
- Integration: Full login flow works with captcha
- Integration: Full registration flow works with captcha

**Verification:**
- `npm run build` succeeds
- Login flow completes with captcha verification
- Register flow completes with captcha verification

---

- [ ] **Unit 8: Backend tests**

**Goal:** Add captcha verification tests

**Requirements:** R22

**Dependencies:** Unit 5

**Files:**
- Create: `backend/tests/test_captcha.py`
- Modify: `backend/tests/conftest.py` (if needed for production mode fixture)

**Approach:**
1. Create test_captcha.py with test cases for R22
2. Test missing/empty/invalid altcha returns 400 in production mode
3. Test development mode skips verification
4. Mock ENVIRONMENT or create production-mode fixture

**Patterns to follow:**
- `backend/tests/test_auth.py` test pattern
- `backend/tests/conftest.py` fixture pattern

**Test scenarios:**
- Happy path: Valid altcha payload passes in production mode
- Error path: Missing altcha returns 400 "请完成验证码验证" in production
- Error path: Empty altcha returns 400 "验证码不能为空" in production
- Error path: Invalid altcha returns 400 "验证码验证失败，请重试" in production
- Edge case: Development mode skips verification (all payloads accepted)

**Verification:**
- `uv run pytest tests/test_captcha.py -v` passes all tests
- All existing tests still pass: `uv run pytest tests/ -v`

---

## System-Wide Impact

**Interaction graph:**
- RateLimitMiddleware: Challenge endpoint added to SKIP_PATHS
- Axios interceptor: Already handles public endpoints correctly (no change needed)
- Auth endpoints: New verification dependency runs before business logic

**Error propagation:**
- Captcha errors return HTTP 400 with Chinese error messages
- Errors occur before auth logic executes, preventing unnecessary processing

**State lifecycle risks:**
- Challenge is single-use, verified by altcha library via embedded nonce
- No server-side state to clean up

**Integration coverage:**
- E2E test scripts in `tests/` may need adjustment for production mode captcha

**Unchanged invariants:**
- Auth response schemas unchanged (TokenResponse, UserResponse)
- JWT token generation unchanged
- Rate limiting unchanged (captcha is pre-check, not replacement)

## Risks & Dependencies

| Risk | Mitigation |
|------|------------|
| CDN unavailable blocks auth | Accept risk — jsdelivr has high availability; document fallback if needed |
| SRI hash becomes stale | Pin to specific version/commit instead of @main branch |
| Mobile performance varies | Low difficulty (50000) chosen for mobile-friendly compute time |
| Test mode leaks into production | Explicit ENVIRONMENT check, test mode only when ENVIRONMENT != 'production' |
| HMAC key rotation | Document rotation procedure: update env var, restart service (no migration needed) |

## Documentation / Operational Notes

**Environment variables for production:**
```bash
ENVIRONMENT=production
ALTCHA_HMAC_KEY=<secure-random-string>  # Generate with: openssl rand -hex 32
```

**SRI hash computation:**
```bash
curl -s https://cdn.jsdelivr.net/gh/altcha-org/altcha@<version>/dist/altcha.min.js | openssl dgst -sha384 -binary | openssl base64 -A
```

**Testing in production mode locally:**
```bash
ENVIRONMENT=production ALTCHA_HMAC_KEY=test-key uv run uvicorn app.main:app --reload
```

## Sources & References

- **Origin document:** [docs/brainstorms/2026-04-02-altcha-captcha-requirements.md](docs/brainstorms/2026-04-02-altcha-captcha-requirements.md)
- ALTCHA docs: https://altcha.org/docs/
- ALTCHA Python lib: https://github.com/altcha-org/altcha-lib-py
- Related code: `backend/app/auth/deps.py` (dependency pattern)
- Related code: `backend/app/config.py` (settings validation pattern)