---
title: feat: ALTCHA captcha best practices enhancements
type: feat
status: active
date: 2026-04-03
origin: docs/brainstorms/2026-04-02-altcha-captcha-requirements.md
---

# ALTCHA Captcha Best Practices Enhancements

## Overview

Extend the existing ALTCHA captcha implementation with security hardening (replay attack prevention), mobile-optimized endpoint-specific difficulty, and UX enhancements (retry flow, dark mode, accessibility, loading states). Build on the foundation implemented in `2026-04-03-001-feat-altcha-captcha-plan.md`.

## Problem Frame

基础 ALTCHA 验证码已实现，但存在以下改进空间：

1. **重放攻击风险**：当前 `check_expires=True` 仅验证时效，同一 payload 在有效期内可被重复使用
2. **移动端性能**：统一难度无法平衡高频登录的 UX 和高风险注册的安全需求
3. **用户体验**：缺少深色模式、无障碍访问、加载状态反馈等最佳实践

## Requirements Trace

**From Best Practices Extensions (2026-04-03):**
- R23. 实现 payload registry 防重放攻击
- R24. 端点差异化难度：login=30000, register/join=100000
- R25. 重试流程优化
- R26. 视觉集成优化（深色模式、Vant 风格统一）
- R27. 无障碍访问（a11y）
- R28. 加载状态反馈
- R29. 跨平台一致性
- R30. 安全日志增强（CAPTCHA_REPLAY_ATTACK 事件）

**Prerequisites from base implementation:**
- R1-R22. 基础 captcha 功能（已完成）

## Scope Boundaries

- **不实现** Sentinel spam filter
- **不扩展** 到其他端点（仅 auth 端点）
- **不实现** 设备检测动态难度
- **不实现** 请求签名完整性验证（记录为未来选项）
- payload registry **仅存储 hash**，非完整 challenge

## Context & Research

### Relevant Code and Patterns

**Backend - Cache Infrastructure:**
- `backend/app/services/cache/` — General-purpose CacheBackend with memory/Redis support
- `backend/app/services/cache/factory.py` — `get_rate_limit_cache()` singleton pattern
- `backend/app/config.py` — `CACHE_BACKEND` config (memory/redis)

**Backend - Captcha Core:**
- `backend/app/auth/captcha.py` — `verify_captcha` dependency
- `backend/app/routers/captcha.py` — Challenge endpoint (currently hardcoded max_number=50000)
- `backend/app/services/security_log.py` — SecurityEventType enum

**Frontend:**
- `frontend/src/components/common/AltchaWidget.vue` — Current widget wrapper
- `frontend/src/stores/auth.ts` — Theme state (user.theme)
- `frontend/src/App.vue` — Dark mode handling via `data-theme` attribute

### Institutional Learnings

From `docs/solutions/best-practices/redis-fail-fast-strategy.md`:
- When `CACHE_BACKEND=redis`, must fail fast if Redis unavailable — NOT silently fall back to memory
- Silent fallback causes split-brain in clustered deployments

From `docs/solutions/best-practices/security-protection.md`:
- CacheBackend abstraction supports any TTL-based caching
- Key format pattern: `{namespace}:{identifier}`

### External References

- ALTCHA widget attributes: `dark` attribute for dark mode support
- ALTCHA events: `statechange` event with `detail.state` values (loading, computing, verified, error)

## Key Technical Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Payload registry backend | Reuse CacheBackend via `get_captcha_payload_cache()` | Leverages existing infrastructure; separation from rate limit cache |
| Registry key format | `altcha:used:{payload_hash}` | Namespace collision prevention; hash for fixed-length key |
| Registry TTL | 1 hour (matches challenge expiry) | After challenge expires, replay is harmless |
| Default difficulty | 50000 when endpoint param missing | Backward compatibility with existing clients |
| Cache failure behavior | Fail-closed (reject request) | Security posture: degrade to blocking, not bypass |
| Dark mode approach | CSS `data-theme` attribute + widget `dark` prop | Matches existing App.vue pattern |
| Endpoint parameter | Query param `?endpoint=login\|register\|join-family` | Simple, explicit, cacheable |

## Open Questions

### Resolved During Planning

- **Payload registry storage**: Use existing CacheBackend abstraction with dedicated factory function. Redis for production, memory for dev. (see origin: Dependencies)
- **Endpoint parameter format**: Query parameter `?endpoint=<type>` on challenge URL. Frontend passes endpoint type based on page context.
- **Cache failure behavior**: Fail-closed. If cache unavailable, return 503 "验证服务暂时不可用". Security over availability.

### Deferred to Implementation

- **ALTCHA widget dark attribute support**: Verify if `dark` prop exists or requires CSS workaround
- **ARIA attribute implementation details**: Exact Vue ref/attribute binding pattern for web component
- **Progress event availability**: Whether ALTCHA widget exposes computation progress (R28)
- **SRI hash for CDN script**: Compute from actual script version at implementation time

## High-Level Technical Design

> *This illustrates the intended approach and is directional guidance for review, not implementation specification.*

```
┌─────────────────────────────────────────────────────────────────────┐
│                         Verification Flow (R23)                      │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  POST /auth/login { altcha: "<payload>" }                           │
│              │                                                       │
│              ▼                                                       │
│  ┌─────────────────────────────────────────┐                        │
│  │  1. verify_solution(payload, HMAC_KEY)  │                        │
│  │     - Validates signature & expiry      │                        │
│  └─────────────────────────────────────────┘                        │
│              │ ✓ verified                                             │
│              ▼                                                       │
│  ┌─────────────────────────────────────────┐                        │
│  │  2. Compute payload_hash = SHA256       │                        │
│  │     Check cache.get(altcha:used:{hash}) │                        │
│  └─────────────────────────────────────────┘                        │
│              │                                                       │
│       ┌──────┴──────┐                                                │
│       │             │                                                │
│   hash exists   hash not found                                       │
│       │             │                                                │
│       ▼             ▼                                                │
│  ┌─────────┐   ┌──────────────────────────┐                          │
│  │ 400     │   │ cache.set(hash, "1", TTL)│                          │
│  │ REPLAY  │   │ Continue to auth logic   │                          │
│  │ ATTACK  │   └──────────────────────────┘                          │
│  └─────────┘                                                         │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│                    Endpoint-Specific Difficulty (R24)                │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  Frontend                      Backend                               │
│  ┌─────────────┐              ┌─────────────────────────┐           │
│  │ LoginPage   │              │ GET /captcha/challenge  │           │
│  │ challengeurl│──?endpoint=login──►│ max_number=30000   │           │
│  └─────────────┘              └─────────────────────────┘           │
│                                                                      │
│  ┌─────────────┐              ┌─────────────────────────┐           │
│  │ RegisterPage│              │ GET /captcha/challenge  │           │
│  │ challengeurl│──?endpoint=register──►│ max_number=100000│         │
│  └─────────────┘              └─────────────────────────┘           │
│                                                                      │
│  ┌─────────────┐              ┌─────────────────────────┐           │
│  │JoinFamily   │              │ GET /captcha/challenge  │           │
│  │ challengeurl│──?endpoint=join-family──►│ max_number=100000│      │
│  └─────────────┘              └─────────────────────────┘           │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

## Implementation Units

### Unit Dependency Graph

```mermaid
flow TB
    U1[Unit 1: Payload registry cache factory] --> U2[Unit 2: Replay attack prevention]
    U3[Unit 3: Security logging enhancement] --> U2
    U4[Unit 4: Endpoint-specific difficulty] --> U5[Unit 5: Frontend endpoint parameter]
    U5 --> U6[Unit 6: Dark mode support]
    U6 --> U7[Unit 7: Accessibility enhancements]
    U7 --> U8[Unit 8: Loading state feedback]
    U2 --> U9[Unit 9: Backend tests]
    U3 --> U9
    U4 --> U9
    U8 --> U10[Unit 10: Retry flow optimization]
```

---

- [ ] **Unit 1: Payload registry cache factory**

**Goal:** Create dedicated cache factory for captcha payload registry

**Requirements:** R23

**Dependencies:** None

**Files:**
- Modify: `backend/app/services/cache/__init__.py`
- Modify: `backend/app/services/cache/factory.py`

**Approach:**
1. Add `get_captcha_payload_cache()` factory function to factory.py
2. Follow existing `get_rate_limit_cache()` singleton pattern
3. Return CacheBackend instance (memory or Redis based on config)
4. Export from `__init__.py`

**Patterns to follow:**
- `backend/app/services/cache/factory.py` existing factory pattern

**Test scenarios:**
- Happy path: `get_captcha_payload_cache()` returns CacheBackend instance
- Integration: Memory cache works in development
- Edge case: Redis cache throws NotImplementedError if called (Redis not yet implemented)

**Verification:**
- Factory function exists and returns valid CacheBackend
- No conflict with rate limit cache singleton

---

- [ ] **Unit 2: Replay attack prevention**

**Goal:** Implement payload registry check in verify_captcha dependency

**Requirements:** R23

**Dependencies:** Unit 1, Unit 3

**Files:**
- Modify: `backend/app/auth/captcha.py`
- Modify: `backend/app/services/security_log.py`

**Approach:**
1. After `verify_solution()` succeeds, compute SHA-256 hash of payload
2. Check if hash exists in cache with key `altcha:used:{hash}`
3. If exists: log CAPTCHA_REPLAY_ATTACK event, raise HTTP 400 "验证码验证失败，请重试"
4. If not exists: store hash with TTL=3600 (1 hour), continue to auth logic
5. Handle cache unavailability: fail-closed (reject request) with error "验证服务暂时不可用"

**Technical design:**

```python
# Directional pseudo-code
import hashlib
from app.services.cache import get_captcha_payload_cache

async def verify_captcha(request: Request, ...):
    # ... existing verification logic ...

    verified, err = verify_solution(altcha, settings.ALTCHA_HMAC_KEY, True)
    if not verified:
        raise HTTPException(400, "验证码验证失败，请重试")

    # R23: Replay attack prevention
    cache = get_captcha_payload_cache()
    payload_hash = hashlib.sha256(altcha.encode()).hexdigest()
    cache_key = f"altcha:used:{payload_hash}"

    try:
        if cache.get(cache_key):
            _log_security_event(SecurityEventType.CAPTCHA_REPLAY_ATTACK, client_id=client_ip)
            raise HTTPException(400, "验证码验证失败，请重试")
        cache.set(cache_key, "1", ttl_seconds=3600)  # 1 hour TTL
    except Exception as e:
        # Fail-closed: if cache unavailable, reject
        logger.error(f"Captcha cache error: {e}")
        raise HTTPException(503, "验证服务暂时不可用")
```

**Patterns to follow:**
- `backend/app/auth/captcha.py` existing verification pattern
- `backend/app/services/security_log.py` event logging pattern

**Test scenarios:**
- Happy path: First use of valid payload passes
- Error path: Replay of same payload within 1 hour returns 400
- Edge case: Replay after TTL expiry succeeds (hash expired)
- Error path: Cache unavailable returns 503 (fail-closed)

**Verification:**
- Replay attack correctly detected and logged
- Cache entries have correct TTL

---

- [ ] **Unit 3: Security logging enhancement**

**Goal:** Add CAPTCHA_REPLAY_ATTACK event type

**Requirements:** R30

**Dependencies:** None

**Files:**
- Modify: `backend/app/services/security_log.py`

**Approach:**
1. Add `CAPTCHA_REPLAY_ATTACK = "captcha_replay_attack"` to SecurityEventType class
2. Event logged in Unit 2 when replay detected

**Patterns to follow:**
- `backend/app/services/security_log.py` existing event type pattern

**Test scenarios:**
- Happy path: Event logged with correct type and client_id

**Verification:**
- Event type exists in SecurityEventType
- Log entry format matches security audit pattern

---

- [ ] **Unit 4: Endpoint-specific difficulty**

**Goal:** Challenge endpoint accepts endpoint parameter and returns appropriate difficulty

**Requirements:** R24

**Dependencies:** None

**Files:**
- Modify: `backend/app/routers/captcha.py`

**Approach:**
1. Add optional `endpoint` query parameter to `GET /captcha/challenge`
2. Map endpoint types to max_number:
   - `login` → 30000 (fast for high-frequency)
   - `register`, `join-family` → 100000 (harder for abuse prevention)
   - missing/unrecognized → 50000 (default, backward compatible)
3. Pass appropriate max_number to create_challenge()

**Technical design:**

```python
# Directional pseudo-code
DIFFICULTY_MAP = {
    "login": 30000,
    "register": 100000,
    "join-family": 100000,
}
DEFAULT_DIFFICULTY = 50000

@router.get("/challenge")
def get_challenge(endpoint: str | None = None):
    max_number = DIFFICULTY_MAP.get(endpoint, DEFAULT_DIFFICULTY)
    challenge = create_challenge(ChallengeOptions(
        hmac_key=settings.ALTCHA_HMAC_KEY,
        max_number=max_number,
    ))
    return challenge
```

**Patterns to follow:**
- `backend/app/routers/captcha.py` existing endpoint pattern

**Test scenarios:**
- Happy path: `?endpoint=login` returns challenge with max_number=30000
- Happy path: `?endpoint=register` returns challenge with max_number=100000
- Edge case: Missing endpoint returns default max_number=50000
- Edge case: Unknown endpoint returns default max_number=50000

**Verification:**
- Challenge response reflects correct difficulty per endpoint
- Default behavior unchanged for backward compatibility

---

- [ ] **Unit 5: Frontend endpoint parameter**

**Goal:** Frontend passes endpoint parameter when fetching challenge

**Requirements:** R24

**Dependencies:** Unit 4

**Files:**
- Modify: `frontend/src/components/common/AltchaWidget.vue`

**Approach:**
1. Add `endpoint` prop to AltchaWidget component
2. Construct challengeurl with query parameter: `/api/v1/captcha/challenge?endpoint={endpoint}`
3. Update LoginPage, RegisterPage, JoinFamilyPage to pass appropriate endpoint prop

**Technical design:**

```vue
<!-- Directional pseudo-code -->
<script setup lang="ts">
const props = defineProps<{
  modelValue?: string
  endpoint: 'login' | 'register' | 'join-family'
}>()

const challengeUrl = computed(() =>
  `/api/v1/captcha/challenge?endpoint=${props.endpoint}`
)
</script>

<template>
  <altcha-widget :challengeurl="challengeUrl" ... />
</template>
```

**Patterns to follow:**
- `frontend/src/components/common/AltchaWidget.vue` existing pattern

**Test scenarios:**
- Happy path: Widget fetches challenge with correct endpoint parameter
- Integration: LoginPage passes endpoint="login"

**Verification:**
- Network request includes correct query parameter
- Challenge reflects appropriate difficulty

---

- [ ] **Unit 6: Dark mode support**

**Goal:** Widget adapts to dark theme

**Requirements:** R26

**Dependencies:** Unit 5

**Files:**
- Modify: `frontend/src/components/common/AltchaWidget.vue`

**Approach:**
1. Detect current theme from `data-theme` attribute on document root
2. If ALTCHA widget supports `dark` attribute, set it conditionally
3. Alternatively, use CSS custom properties for dark mode styling
4. Watch for theme changes (user may toggle in settings)

**Technical design:**

```vue
<!-- Directional pseudo-code -->
<script setup lang="ts">
const isDark = computed(() =>
  document.documentElement.getAttribute('data-theme') === 'dark'
)

// Watch for theme changes
watch(isDark, (dark) => {
  const widget = altchaRef.value
  if (widget) {
    if (dark) {
      widget.setAttribute('dark', '')
    } else {
      widget.removeAttribute('dark')
    }
  }
})
</script>
```

**Patterns to follow:**
- `frontend/src/App.vue` theme resolution pattern

**Test scenarios:**
- Happy path: Widget uses dark styling when theme is dark
- Edge case: Widget updates when user toggles theme
- Edge case: Widget uses light styling by default

**Verification:**
- Visual inspection in dark mode
- Theme toggle updates widget appearance

---

- [ ] **Unit 7: Accessibility enhancements**

**Goal:** Add ARIA attributes for screen reader support

**Requirements:** R27

**Dependencies:** Unit 6

**Files:**
- Modify: `frontend/src/components/common/AltchaWidget.vue`

**Approach:**
1. Wrap widget in container with `aria-live="polite"` for state announcements
2. Set `aria-busy="true"` during computation
3. Use `role="alert"` for error messages
4. Ensure keyboard navigation: Tab to focus, Enter to trigger (if supported by widget)

**Technical design:**

```vue
<!-- Directional pseudo-code -->
<template>
  <div
    class="altcha-wrapper"
    :aria-busy="isComputing"
    aria-live="polite"
  >
    <altcha-widget ref="altchaRef" ... />
    <div v-if="errorMessage" role="alert" class="error-message">
      {{ errorMessage }}
    </div>
  </div>
</template>
```

**Patterns to follow:**
- WCAG 2.1 ARIA patterns for form controls

**Test scenarios:**
- Happy path: Screen reader announces loading state
- Error path: Screen reader announces error message immediately
- Edge case: Tab navigation reaches widget

**Verification:**
- Accessibility audit with screen reader (VoiceOver/NVDA)
- Keyboard navigation works

---

- [ ] **Unit 8: Loading state feedback**

**Goal:** Show progress indicator during PoW computation

**Requirements:** R28

**Dependencies:** Unit 7

**Files:**
- Modify: `frontend/src/components/common/AltchaWidget.vue`

**Approach:**
1. Listen for ALTCHA widget state changes
2. Display loading spinner during 'computing' state
3. Show success indicator briefly after 'verified' state
4. For low-end devices, display estimated time hint (may not be deterministic)

**Technical design:**

```vue
<!-- Directional pseudo-code -->
<script setup lang="ts">
const widgetState = ref<'loading' | 'computing' | 'verified' | 'error'>('loading')

function onStateChange(event: CustomEvent) {
  widgetState.value = event.detail.state
  if (event.detail.state === 'verified') {
    emit('update:modelValue', event.detail.payload)
    // Brief success indicator
    setTimeout(() => widgetState.value = 'verified', 500)
  }
}
</script>

<template>
  <div class="altcha-container">
    <van-loading v-if="widgetState === 'computing'" size="24px">
      正在验证...
    </van-loading>
    <van-icon v-else-if="widgetState === 'verified'" name="success" color="#07c160" />
    <altcha-widget @statechange="onStateChange" ... />
  </div>
</template>
```

**Patterns to follow:**
- Vant 4 loading/icon component usage

**Test scenarios:**
- Happy path: Spinner shows during computation
- Happy path: Success icon shows briefly after verification
- Edge case: Low-end device shows longer computation time

**Verification:**
- Visual feedback matches computation state
- Timing acceptable on test devices

---

- [ ] **Unit 9: Backend tests**

**Goal:** Test payload registry and endpoint-specific difficulty

**Requirements:** R23, R24, R30

**Dependencies:** Unit 2, Unit 3, Unit 4

**Files:**
- Create: `backend/tests/test_captcha.py` (or extend if exists)

**Approach:**
1. Test payload registry prevents replay
2. Test endpoint parameter affects difficulty
3. Test cache failure behavior (fail-closed)
4. Test CAPTCHA_REPLAY_ATTACK logging

**Test scenarios:**
- Happy path: First valid payload passes
- Error path: Replayed payload returns 400
- Happy path: `?endpoint=login` returns lower difficulty
- Happy path: `?endpoint=register` returns higher difficulty
- Error path: Cache unavailable returns 503

**Verification:**
- `uv run pytest tests/test_captcha.py -v` passes
- All existing tests pass: `uv run pytest tests/ -v`

---

- [ ] **Unit 10: Retry flow optimization**

**Goal:** Auto-reset widget and preserve form data on verification failure

**Requirements:** R25

**Dependencies:** Unit 8

**Files:**
- Modify: `frontend/src/components/common/AltchaWidget.vue`
- Modify: `frontend/src/pages/LoginPage.vue`
- Modify: `frontend/src/pages/RegisterPage.vue`
- Modify: `frontend/src/pages/JoinFamilyPage.vue`

**Approach:**
1. Expose `reset()` method on AltchaWidget component
2. Parent pages catch 400 captcha errors and call `widgetRef.reset()`
3. Show toast with error message from server
4. Form data preserved (only captcha state reset)

**Technical design:**

```vue
<!-- AltchaWidget.vue - Directional pseudo-code -->
<script setup lang="ts">
const altchaRef = ref<HTMLElement | null>(null)

defineExpose({
  reset: () => {
    if (altchaRef.value && 'reset' in altchaRef.value) {
      ;(altchaRef.value as any).reset()
      emit('update:modelValue', undefined)
    }
  }
})
</script>

<!-- LoginPage.vue - Directional pseudo-code -->
<script setup lang="ts">
const altchaRef = ref()

async function onSubmit() {
  try {
    await authStore.login(form.value)
  } catch (error) {
    if (error.response?.data?.detail?.includes('验证码')) {
      altchaRef.value?.reset()
      showToast(error.response.data.detail)
    }
  }
}
</script>
```

**Patterns to follow:**
- Vant 4 showToast pattern
- Vue 3 defineExpose pattern

**Test scenarios:**
- Error path: Backend captcha error resets widget, preserves form
- Integration: Network error shows different message
- Happy path: Retry after error succeeds

**Verification:**
- Form data preserved after captcha reset
- User can retry without re-entering credentials

---

## System-Wide Impact

**Interaction graph:**
- Cache layer: New captcha payload cache namespace (`altcha:*`)
- Security logging: New event type CAPTCHA_REPLAY_ATTACK
- Challenge endpoint: New query parameter behavior

**Error propagation:**
- Cache unavailable → 503 "验证服务暂时不可用" (fail-closed)
- Replay detected → 400 "验证码验证失败，请重试"
- Captcha verification failure → 400 with specific message

**State lifecycle risks:**
- Payload registry TTL (1 hour) must align with challenge expiry
- Memory cache lost on restart → short replay window acceptable

**Integration coverage:**
- Frontend form retry behavior
- Backend cache failure handling
- Cross-instance cache consistency (Redis required for multi-worker)

**Unchanged invariants:**
- Existing auth flow unchanged (captcha is pre-check)
- Token generation unchanged
- Rate limiting unchanged

## Risks & Dependencies

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Memory cache lost on restart | Medium | Low | Acceptable risk: short replay window within 1-hour TTL |
| Redis not implemented | High | Low | Memory cache works for single-instance; Redis for clusters |
| Widget dark attribute unsupported | Medium | Low | CSS workaround as fallback |
| ARIA not fully supported by widget | Medium | Medium | Wrapper component provides accessibility layer |
| Cache unavailable blocks auth | Low | Medium | Document as security posture; monitor cache health |

## Documentation / Operational Notes

**Environment variables:**
- `CACHE_BACKEND=memory` (dev) or `redis` (production clusters)
- `ALTCHA_HMAC_KEY` — must be consistent across all instances

**Monitoring:**
- Track CAPTCHA_REPLAY_ATTACK events for attack detection
- Monitor cache hit/miss ratio for payload registry

**Testing in production mode:**
```bash
ENVIRONMENT=production ALTCHA_HMAC_KEY=test-key CACHE_BACKEND=memory \
  uv run uvicorn app.main:app --reload
```

## Sources & References

- **Origin document:** [docs/brainstorms/2026-04-02-altcha-captcha-requirements.md](docs/brainstorms/2026-04-02-altcha-captcha-requirements.md)
- **Base implementation plan:** [docs/plans/2026-04-03-001-feat-altcha-captcha-plan.md](docs/plans/2026-04-03-001-feat-altcha-captcha-plan.md)
- ALTCHA docs: https://altcha.org/docs/
- Related code: `backend/app/services/cache/`