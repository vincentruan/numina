# StepGuide 引导触发逻辑优化 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 优化引导显示触发逻辑——服务端存储引导状态（跨设备一致），仅在版本重大变更、首次访问、或引导完成率不足 20% 时显示，并在用户高级设置中添加重置引导选项。

**Architecture:** 利用现有 user settings 系统（`config_registry.py` + `GET/PATCH /user/config`）新增 3 个引导状态字段。前端 `shouldShowGuide()` 从服务端读取状态判断，仅 `last_shown`（24h 本地节流）保留在 localStorage。

**Tech Stack:** Vue 3, TypeScript, Python FastAPI, vitest, pytest

## Global Constraints

- `<script setup lang="ts">` only
- No `any` / `@ts-ignore`
- i18n required for all UI strings
- 后端 user setting 定义在 `config_registry.py` 的 `USER_SETTING_DEFINITIONS`，无需 migration
- 前端通过 `getUserConfig()` / `updateUserConfig()` 读写

## 数据存储分层

| 数据 | 存储 | 理由 |
|------|------|------|
| `onboarding_guide_version` | 服务端 user setting | 跨设备一致，清缓存不丢失 |
| `onboarding_attempts` | 服务端 user setting | 跨设备累计，防重置后重复打扰 |
| `onboarding_completions` | 服务端 user setting | 跨设备累计，真实引导率 |
| `guide_last_shown_ts` | localStorage | 仅本地 24h 节流，不需跨设备 |
| `GUIDE_VERSION` | 代码常量 | 跟随代码发布 |

## 触发规则

```
shouldShowGuide(serverState, currentVersion):
  1. serverState.guide_version >= currentVersion → 不显示（已是最新版本）
  2. attempts >= 3 且 completions/attempts < 20% → 不显示（反复跳过，停止打扰）
  3. localStorage last_shown < 24h 前 → 不显示（本地节流）
  4. 其余情况 → 显示
     - 首次（attempts=0）→ reason: first_visit
     - 版本变更 → reason: version_bump
```

---

### Task 1: 后端 — 新增 user setting 定义

**Files:**
- Modify: `server/apps/backend/app/services/config_registry.py`
- Modify: `server/apps/backend/app/schemas/config.py`
- Test: `server/tests/backend/test_config_registry.py` (或新建)

**Interfaces:**
- Produces: 3 个新 user setting keys: `onboarding_guide_version` (int, default 0), `onboarding_attempts` (int, default 0), `onboarding_completions` (int, default 0)

- [ ] **Step 1: Write failing test**

```python
# server/tests/backend/test_onboarding_settings.py
import pytest
from apps.backend.app.services.config_registry import USER_SETTING_DEFINITIONS, validate_value

def test_onboarding_settings_registered():
    assert "onboarding_guide_version" in USER_SETTING_DEFINITIONS
    assert "onboarding_attempts" in USER_SETTING_DEFINITIONS
    assert "onboarding_completions" in USER_SETTING_DEFINITIONS

def test_onboarding_defaults():
    assert USER_SETTING_DEFINITIONS["onboarding_guide_version"].default == 0
    assert USER_SETTING_DEFINITIONS["onboarding_attempts"].default == 0
    assert USER_SETTING_DEFINITIONS["onboarding_completions"].default == 0

def test_onboarding_validation():
    assert validate_value("user", "onboarding_guide_version", 2) == 2
    assert validate_value("user", "onboarding_attempts", 5) == 5
    assert validate_value("user", "onboarding_completions", 3) == 3

def test_onboarding_rejects_negative():
    with pytest.raises(ValueError):
        validate_value("user", "onboarding_attempts", -1)
```

- [ ] **Step 2: Run to verify fail**

Run: `cd server && uv run pytest tests/backend/test_onboarding_settings.py -v`

- [ ] **Step 3: Add registry definitions**

在 `server/apps/backend/app/services/config_registry.py` 的 `USER_SETTING_DEFINITIONS` 追加：

```python
    # --- Onboarding guide state ---
    "onboarding_guide_version": SettingDefinition(
        type="int", default=0, min=0, max=999,
        label_key="userConfig.onboardingGuideVersion",
        description_key="userConfig.onboardingGuideVersionDesc",
    ),
    "onboarding_attempts": SettingDefinition(
        type="int", default=0, min=0, max=9999,
        label_key="userConfig.onboardingAttempts",
        description_key="userConfig.onboardingAttemptsDesc",
    ),
    "onboarding_completions": SettingDefinition(
        type="int", default=0, min=0, max=9999,
        label_key="userConfig.onboardingCompletions",
        description_key="userConfig.onboardingCompletionsDesc",
    ),
```

在 `server/apps/backend/app/schemas/config.py` 的 `UserConfigResponse` 追加：

```python
    onboarding_guide_version: int
    onboarding_attempts: int
    onboarding_completions: int
```

- [ ] **Step 4: Run to verify pass**

- [ ] **Step 5: Commit**

```bash
git add server/apps/backend/app/services/config_registry.py server/apps/backend/app/schemas/config.py server/tests/backend/test_onboarding_settings.py
git commit -m "feat(config): add onboarding guide state user settings

onboarding_guide_version/attempts/completions — server-side storage for cross-device consistency"
```

---

### Task 2: 前端 — 扩展 UserConfigValues + 引导触发 composable

**Files:**
- Modify: `frontend/apps/main/src/api/config.ts`
- Create: `frontend/apps/main/src/composables/useGuideTrigger.ts`
- Test: `frontend/apps/main/src/composables/__tests__/useGuideTrigger.spec.ts`

**Interfaces:**
- Consumes: `getUserConfig`, `updateUserConfig` from `@/api/config`
- Produces: `shouldShowGuide(config): { shouldShow, reason }`, `recordGuideShown(config)`, `recordGuideCompletion(config, version)`, `resetGuideState(): Promise<void>`

- [ ] **Step 1: Extend UserConfigValues**

在 `frontend/apps/main/src/api/config.ts` 的 `UserConfigValues` 追加：

```ts
export interface UserConfigValues {
  dashboard_trend_period: string
  activity_feed_page_size: number
  onboarding_guide_version: number
  onboarding_attempts: number
  onboarding_completions: number
}
```

- [ ] **Step 2: Write failing tests for useGuideTrigger**

```ts
// frontend/apps/main/src/composables/__tests__/useGuideTrigger.spec.ts
import { describe, it, expect, beforeEach } from 'vitest'
import { shouldShowGuide, recordGuideShown, recordGuideCompletion } from '../useGuideTrigger'

describe('shouldShowGuide', () => {
  const CURRENT_VERSION = 2

  function config(overrides: Partial<{ onboarding_guide_version: number; onboarding_attempts: number; onboarding_completions: number }> = {}) {
    return {
      dashboard_trend_period: 'month',
      activity_feed_page_size: 20,
      onboarding_guide_version: 0,
      onboarding_attempts: 0,
      onboarding_completions: 0,
      ...overrides,
    }
  }

  beforeEach(() => localStorage.clear())

  it('shows on first visit (attempts=0)', () => {
    const { shouldShow, reason } = shouldShowGuide(config(), CURRENT_VERSION)
    expect(shouldShow).toBe(true)
    expect(reason).toBe('first_visit')
  })

  it('does NOT show when version matches', () => {
    const { shouldShow } = shouldShowGuide(config({ onboarding_guide_version: 2 }), CURRENT_VERSION)
    expect(shouldShow).toBe(false)
  })

  it('shows when version bumped', () => {
    const { shouldShow, reason } = shouldShowGuide(
      config({ onboarding_guide_version: 1, onboarding_attempts: 1, onboarding_completions: 1 }),
      CURRENT_VERSION,
    )
    expect(shouldShow).toBe(true)
    expect(reason).toBe('version_bump')
  })

  it('does NOT show when completion rate < 20% (attempts >= 3)', () => {
    const { shouldShow, reason } = shouldShowGuide(
      config({ onboarding_attempts: 5, onboarding_completions: 0 }),
      CURRENT_VERSION,
    )
    expect(shouldShow).toBe(false)
    expect(reason).toBe('low_completion_rate')
  })

  it('shows when rate >= 20% even with attempts', () => {
    const { shouldShow } = shouldShowGuide(
      config({ onboarding_attempts: 5, onboarding_completions: 1 }), // 20%
      CURRENT_VERSION,
    )
    expect(shouldShow).toBe(true)
  })

  it('does NOT show within 24h (localStorage throttle)', () => {
    localStorage.setItem('guide_last_shown_ts', String(Date.now()))
    const { shouldShow, reason } = shouldShowGuide(config(), CURRENT_VERSION)
    expect(shouldShow).toBe(false)
    expect(reason).toBe('recently_shown')
  })

  it('shows when > 24h since last shown', () => {
    localStorage.setItem('guide_last_shown_ts', String(Date.now() - 25 * 60 * 60 * 1000))
    const { shouldShow } = shouldShowGuide(config(), CURRENT_VERSION)
    expect(shouldShow).toBe(true)
  })
})

describe('recordGuideShown', () => {
  it('updates localStorage timestamp', () => {
    recordGuideShown()
    const ts = Number(localStorage.getItem('guide_last_shown_ts'))
    expect(ts).toBeGreaterThan(0)
  })
})
```

- [ ] **Step 3: Run to verify fail**

- [ ] **Step 4: Implement useGuideTrigger**

```ts
// frontend/apps/main/src/composables/useGuideTrigger.ts
import type { UserConfigValues } from '@/api/config'
import { updateUserConfig } from '@/api/config'

const COMPLETION_RATE_THRESHOLD = 20 // percent
const MIN_ATTEMPTS_FOR_RATE_CHECK = 3
const MIN_INTERVAL_MS = 24 * 60 * 60 * 1000 // 24 hours
const LAST_SHOWN_KEY = 'guide_last_shown_ts'

export interface GuideTriggerResult {
  shouldShow: boolean
  reason: string
}

export function shouldShowGuide(
  config: Pick<UserConfigValues, 'onboarding_guide_version' | 'onboarding_attempts' | 'onboarding_completions'>,
  currentVersion: number,
): GuideTriggerResult {
  const { onboarding_guide_version: version, onboarding_attempts: attempts, onboarding_completions: completions } = config

  // 1. Already up to date
  if (version >= currentVersion) {
    return { shouldShow: false, reason: 'already_done' }
  }

  // 2. Low completion rate → stop disturbing
  if (attempts >= MIN_ATTEMPTS_FOR_RATE_CHECK) {
    const rate = Math.round((completions / attempts) * 100)
    if (rate < COMPLETION_RATE_THRESHOLD) {
      return { shouldShow: false, reason: 'low_completion_rate' }
    }
  }

  // 3. Local 24h throttle
  const lastShown = Number(localStorage.getItem(LAST_SHOWN_KEY) ?? 0)
  if (lastShown > 0 && Date.now() - lastShown < MIN_INTERVAL_MS) {
    return { shouldShow: false, reason: 'recently_shown' }
  }

  // 4. Show
  const reason = attempts === 0 ? 'first_visit' : 'version_bump'
  return { shouldShow: true, reason }
}

export function recordGuideShown(): void {
  localStorage.setItem(LAST_SHOWN_KEY, String(Date.now()))
}

export async function recordGuideAttempt(config: UserConfigValues): Promise<void> {
  await updateUserConfig({ onboarding_attempts: config.onboarding_attempts + 1 })
}

export async function recordGuideCompletion(config: UserConfigValues, version: number): Promise<void> {
  await updateUserConfig({
    onboarding_guide_version: version,
    onboarding_completions: config.onboarding_completions + 1,
  })
}

export async function resetGuideState(): Promise<void> {
  localStorage.removeItem(LAST_SHOWN_KEY)
  await updateUserConfig({
    onboarding_guide_version: 0,
    onboarding_attempts: 0,
    onboarding_completions: 0,
  })
}
```

- [ ] **Step 5: Run to verify pass**

- [ ] **Step 6: Commit**

---

### Task 3: DashboardPage 集成 + 删除旧逻辑

**Files:**
- Modify: `frontend/apps/main/src/pages/DashboardPage.vue`

**Interfaces:**
- Consumes: `shouldShowGuide`, `recordGuideShown`, `recordGuideAttempt`, `recordGuideCompletion` from `@/composables/useGuideTrigger`
- Consumes: `getUserConfig` from `@/api/config`

- [ ] **Step 1: Update DashboardPage.vue**

Replace the existing `maybeShowOnboarding()` with:

```ts
import { getUserConfig, type UserConfigValues } from '@/api/config'
import { shouldShowGuide, recordGuideShown, recordGuideAttempt, recordGuideCompletion } from '@/composables/useGuideTrigger'

const GUIDE_VERSION = 2 // Bump when guide content changes significantly
let userConfig: UserConfigValues | null = null

async function maybeShowOnboarding() {
  if (router.currentRoute.value.path !== '/') return

  // Fetch server-side state (cached by axios or component)
  if (!userConfig) {
    try {
      const res = await getUserConfig()
      userConfig = res.data
    } catch {
      return // API failure → don't show guide
    }
  }

  const { shouldShow } = shouldShowGuide(userConfig, GUIDE_VERSION)
  if (!shouldShow) return

  // Record attempt (server + local)
  recordGuideShown()
  await recordGuideAttempt(userConfig)

  guide.start()
}

const guide = useStepGuide({
  key: 'guide_main-onboarding-v2',
  steps: guideSteps.value,
  onComplete: async () => {
    if (userConfig) {
      await recordGuideCompletion(userConfig, GUIDE_VERSION)
    }
  },
  onSkip: () => {
    // Skip doesn't update server version — user didn't complete
    // But we still mark locally so the overlay closes
  },
})
```

Remove old imports: `migrateOldOnboardingKey` (no longer needed since state is server-side).

- [ ] **Step 2: Run typecheck**

- [ ] **Step 3: Commit**

---

### Task 4: UserConfigPage 重置引导入口 + i18n

**Files:**
- Modify: `frontend/apps/main/src/pages/UserConfigPage.vue`
- Modify: `frontend/apps/main/src/i18n/locales/zh-CN.ts`
- Modify: `frontend/apps/main/src/i18n/locales/en-US.ts`

- [ ] **Step 1: Add reset section to UserConfigPage**

在 template 末尾添加：

```vue
<van-cell-group inset :title="t('userConfig.guideGroup')" class="section">
  <van-cell
    :title="t('userConfig.resetGuide')"
    :label="t('userConfig.resetGuideDesc')"
    icon="guide-o"
    is-link
    @click="onResetGuide"
  />
</van-cell-group>
```

Script:

```ts
import { resetGuideState } from '@/composables/useGuideTrigger'
import { showConfirmDialog } from 'vant'
import { useRouter } from 'vue-router'

const router = useRouter()

async function onResetGuide() {
  try {
    await showConfirmDialog({
      title: t('userConfig.resetGuideConfirmTitle'),
      message: t('userConfig.resetGuideConfirmMsg'),
    })
    await resetGuideState()
    router.push('/')
  } catch {
    // cancelled
  }
}
```

- [ ] **Step 2: Add i18n keys**

zh-CN.ts `userConfig` section:
```ts
guideGroup: '引导设置',
resetGuide: '重新播放新手引导',
resetGuideDesc: '清除引导记录，下次进入时重新显示',
resetGuideConfirmTitle: '重置引导',
resetGuideConfirmMsg: '将清除所有引导记录，下次进入首页时会重新显示引导。确定要重置吗？',
```

en-US.ts:
```ts
guideGroup: 'Onboarding',
resetGuide: 'Replay onboarding',
resetGuideDesc: 'Clear onboarding records to show again next visit',
resetGuideConfirmTitle: 'Reset onboarding',
resetGuideConfirmMsg: 'This will clear all onboarding records. The guide will appear again on your next visit. Continue?',
```

- [ ] **Step 3: Run typecheck + commit**

---

### Task 5: 清理旧 localStorage 逻辑

**Files:**
- Modify: `frontend/apps/main/src/utils/storage.ts`
- Modify: `frontend/apps/main/src/utils/__tests__/storage-guide.spec.ts`

- [ ] **Step 1: Simplify storage.ts**

移除 `isGuideDone`、`markGuideDone`、`migrateOldOnboardingKey` 和 `clearAllGuideKeys` 中的 `guide_` 前缀逻辑（引导状态已迁移到服务端）。保留 `clearAllGuideKeys` 但改为仅清理旧的 localStorage 残留（兼容迁移）：

```ts
/**
 * Clean up legacy onboarding localStorage keys.
 * Guide state is now stored server-side (user config API).
 * This function only clears old client-side remnants.
 */
export function clearLegacyOnboardingKeys(): void {
  const keysToRemove = Object.keys(localStorage).filter(k =>
    k.startsWith('guide_') || k.startsWith('gesture_') || k.startsWith('tip_')
  )
  keysToRemove.forEach(k => localStorage.removeItem(k))
  localStorage.removeItem('onboarding_completed')
}
```

- [ ] **Step 2: Update tests**

- [ ] **Step 3: Update DashboardPage imports if needed**

- [ ] **Step 4: Run typecheck + tests + commit**

---

### Task 6: Child app 同步

**Files:**
- Modify: `frontend/apps/child/src/composables/useGuideTrigger.ts` (或新建)
- Modify: `frontend/apps/child/src/pages/ChildTasksPage.vue`

- [ ] **Step 1: Create/update child useGuideTrigger**

Child app 复用相同逻辑但直接调 user config API：

```ts
// frontend/apps/child/src/composables/useGuideTrigger.ts
import http from '@/api/index' // child 的 axios 实例

const COMPLETION_RATE_THRESHOLD = 20
const MIN_ATTEMPTS_FOR_RATE_CHECK = 3
const MIN_INTERVAL_MS = 24 * 60 * 60 * 1000
const LAST_SHOWN_KEY = 'guide_last_shown_ts'

interface OnboardingConfig {
  onboarding_guide_version: number
  onboarding_attempts: number
  onboarding_completions: number
}

async function fetchConfig(): Promise<OnboardingConfig> {
  const res = await http.get<OnboardingConfig>('/user/config')
  return res.data
}

export async function shouldShowChildGuide(currentVersion: number): Promise<{ shouldShow: boolean; reason: string; config: OnboardingConfig }> {
  const config = await fetchConfig()

  if (config.onboarding_guide_version >= currentVersion) return { shouldShow: false, reason: 'already_done', config }
  if (config.onboarding_attempts >= MIN_ATTEMPTS_FOR_RATE_CHECK) {
    const rate = Math.round((config.onboarding_completions / config.onboarding_attempts) * 100)
    if (rate < COMPLETION_RATE_THRESHOLD) return { shouldShow: false, reason: 'low_completion_rate', config }
  }
  const lastShown = Number(localStorage.getItem(LAST_SHOWN_KEY) ?? 0)
  if (lastShown > 0 && Date.now() - lastShown < MIN_INTERVAL_MS) return { shouldShow: false, reason: 'recently_shown', config }

  const reason = config.onboarding_attempts === 0 ? 'first_visit' : 'version_bump'
  return { shouldShow: true, reason, config }
}

export function recordChildGuideShown(): void {
  localStorage.setItem(LAST_SHOWN_KEY, String(Date.now()))
}

export async function recordChildGuideAttempt(config: OnboardingConfig): Promise<void> {
  await http.patch('/user/config', { settings: { onboarding_attempts: config.onboarding_attempts + 1 } })
}

export async function recordChildGuideCompletion(config: OnboardingConfig, version: number): Promise<void> {
  await http.patch('/user/config', { settings: { onboarding_guide_version: version, onboarding_completions: config.onboarding_completions + 1 } })
}
```

- [ ] **Step 2: Update ChildTasksPage.vue**

```ts
import { shouldShowChildGuide, recordChildGuideShown, recordChildGuideAttempt, recordChildGuideCompletion } from '@/composables/useGuideTrigger'

const CHILD_GUIDE_VERSION = 1
let childConfig: Awaited<ReturnType<typeof shouldShowChildGuide>>['config'] | null = null

async function maybeShowChildOnboarding() {
  const result = await shouldShowChildGuide(CHILD_GUIDE_VERSION)
  if (!result.shouldShow) return

  childConfig = result.config
  recordChildGuideShown()
  await recordChildGuideAttempt(result.config)
  guide.start()
}

const guide = useStepGuide({
  key: 'guide_child-onboarding-v1',
  steps: guideSteps.value,
  onComplete: async () => {
    if (childConfig) await recordChildGuideCompletion(childConfig, CHILD_GUIDE_VERSION)
  },
})
```

Replace existing `guide.start()` in `onMounted` with `maybeShowChildOnboarding()`.

- [ ] **Step 3: Run typecheck + tests for child + commit**

---

### Task 7: Final Verification

- [ ] **Step 1: Run full test suites**

```bash
cd server && uv run pytest tests/backend/ -v -k "onboarding or config"
cd frontend/apps/main && pnpm typecheck && pnpm test:run
cd frontend/apps/child && pnpm typecheck && pnpm test:run
```

- [ ] **Step 2: Verify**

- 新用户首次访问 → 显示引导
- 完成后刷新 → 不再显示
- 清除 localStorage → 仍不显示（服务端状态）
- 换设备（模拟：新 localStorage）→ 如果服务端 version 已设置，不显示
- UserConfigPage "重置引导" → 清除服务端状态 → 下次访问重新显示
- 引导 3 次都跳过 → 不再自动显示（低完成率保护）

- [ ] **Step 3: Commit any fixes**
