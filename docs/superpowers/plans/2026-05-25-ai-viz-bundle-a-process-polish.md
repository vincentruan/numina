# AI Conversation Phase 3 — Bundle A: Process Polish Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add three visual polish enhancements to the existing AI process block: SVG-sprite logo with three states, reasoning body shimmer animation, and phase-driven title with elapsed-seconds subtitle.

**Architecture:** Inline SVG sprite component embedded in `AiProcessBlock.vue` replaces the text glyph, with CSS class-driven state transitions. Reasoning shimmer reuses the existing `.args-running` keyframe applied as `.body-streaming` on `AiProcessStep` body. Title becomes a `phase`-driven computed prop with an elapsed-seconds reactive ref that ticks every second while the block is running. No new dependencies; no Lottie.

**Tech Stack:** Vue 3 + TypeScript + Vant 4. Inline SVG via Vue template syntax. CSS-only animations using existing keyframes. `setInterval` for the elapsed timer with cleanup on unmount.

**Spec:** `docs/superpowers/specs/2026-05-25-ai-conversation-phase-3-design.md` §3 (Bundle A).

---

## File Structure

| File | Purpose | Action |
|------|---------|--------|
| `frontend/apps/main/src/components/ai/AiLogo.vue` | Inline-SVG three-state logo (idle/thinking/done/error) | Create |
| `frontend/apps/main/src/components/ai/AiProcessBlock.vue` | Replace text glyph with `<AiLogo>`; add phase prop; phase-driven title; elapsed-second tick | Modify |
| `frontend/apps/main/src/components/ai/AiProcessStep.vue` | Add `.body-streaming` shimmer class on reasoning body when streaming | Modify |
| `frontend/apps/main/src/pages/AIChatPage.vue` | Pass `phase` prop to `<AiProcessBlock>` so it can derive title | Modify |
| `frontend/apps/main/src/i18n/locales/zh-CN.ts` | Add `aiProcess.thinkingTitle / answeringTitle / errorTitle / elapsedSeconds` | Modify |
| `frontend/apps/main/src/i18n/locales/en-US.ts` | English translations for the above | Modify |
| `frontend/apps/main/src/components/ai/AiLogo.test.ts` | Unit test for state class switching | Create |

---

### Task 1: Create `AiLogo.vue` Component

**Files:**
- Create: `frontend/apps/main/src/components/ai/AiLogo.vue`

- [ ] **Step 1: Create the component file**

Write `frontend/apps/main/src/components/ai/AiLogo.vue`:

```vue
<template>
  <span class="ai-logo" :class="stateClass" :aria-label="ariaLabel" role="img">
    <svg
      class="ai-logo-svg"
      viewBox="0 0 24 24"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      aria-hidden="true"
    >
      <!-- idle / thinking shape: 4-point sparkle, animates via CSS -->
      <g class="logo-sparkle">
        <path
          d="M12 2 L13.5 10.5 L22 12 L13.5 13.5 L12 22 L10.5 13.5 L2 12 L10.5 10.5 Z"
          fill="currentColor"
        />
      </g>
      <!-- done shape: checkmark, shown when state=done -->
      <g class="logo-check">
        <path
          d="M5 12 L10 17 L19 7"
          stroke="currentColor"
          stroke-width="2.5"
          stroke-linecap="round"
          stroke-linejoin="round"
          fill="none"
        />
      </g>
      <!-- error shape: cross, shown when state=error -->
      <g class="logo-cross">
        <path
          d="M7 7 L17 17 M17 7 L7 17"
          stroke="currentColor"
          stroke-width="2.5"
          stroke-linecap="round"
          fill="none"
        />
      </g>
    </svg>
  </span>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

const props = defineProps<{
  state: 'idle' | 'thinking' | 'done' | 'error'
}>()

const { t } = useI18n()

const stateClass = computed(() => `state-${props.state}`)

const ariaLabel = computed(() => {
  switch (props.state) {
    case 'thinking':
      return t('aiProcess.statusRunning')
    case 'done':
      return t('aiProcess.statusDone')
    case 'error':
      return t('aiProcess.statusError')
    default:
      return t('aiProcess.title')
  }
})
</script>

<style scoped>
.ai-logo {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 100%;
  height: 100%;
  color: #ffffff;
}

.ai-logo-svg {
  width: 70%;
  height: 70%;
  transition: opacity 200ms ease-in-out;
}

.logo-sparkle,
.logo-check,
.logo-cross {
  opacity: 0;
  transition: opacity 200ms ease-in-out;
  transform-origin: center;
}

.state-idle .logo-sparkle,
.state-thinking .logo-sparkle {
  opacity: 1;
}

.state-thinking .logo-sparkle {
  animation: logo-spin 2.4s linear infinite;
}

.state-done .logo-check {
  opacity: 1;
}

.state-error .logo-cross {
  opacity: 1;
}

@keyframes logo-spin {
  0% {
    transform: rotate(0deg) scale(1);
  }
  50% {
    transform: rotate(180deg) scale(1.08);
  }
  100% {
    transform: rotate(360deg) scale(1);
  }
}

@media (prefers-reduced-motion: reduce) {
  .state-thinking .logo-sparkle {
    animation: none;
  }

  .ai-logo-svg,
  .logo-sparkle,
  .logo-check,
  .logo-cross {
    transition: none;
  }
}
</style>
```

- [ ] **Step 2: Run typecheck**

Run: `cd frontend/apps/main && npm run typecheck`
Expected: PASS with zero errors

- [ ] **Step 3: Commit**

```bash
git add frontend/apps/main/src/components/ai/AiLogo.vue
git commit -m "feat(ai): add AiLogo inline-SVG component with three states

Phase 3 Bundle A item A1. Replaces text glyph placeholder with an inline
SVG sprite supporting idle/thinking/done/error states via CSS class
switching. Sparkle path is the idle/thinking shape; checkmark for done;
cross for error. State transitions use opacity fades (200ms) for smooth
swaps. Thinking state adds a 2.4s slow-spin animation gated behind
prefers-reduced-motion.

Uses currentColor for fill/stroke so the logo adapts to dark mode and
any future themed container background without extra asset variants."
```

---

### Task 2: Add i18n Keys for Phase Titles and Elapsed Counter

**Files:**
- Modify: `frontend/apps/main/src/i18n/locales/zh-CN.ts:182-198`
- Modify: `frontend/apps/main/src/i18n/locales/en-US.ts:137-153`

- [ ] **Step 1: Add new keys to `zh-CN.ts`**

Edit `frontend/apps/main/src/i18n/locales/zh-CN.ts` — locate the `aiProcess: {` block at line 182 and replace lines 196-198 (the `errorMessage`, `retry`, and closing brace) with the expanded block:

```typescript
    errorMessage: '❌ AI 执行出错，请重试',
    retry: '重试',
    thinkingTitle: '正在思考...',
    answeringTitle: '正在生成回答...',
    errorTitle: '执行出错',
    elapsedSeconds: '已思考 {seconds} 秒',
  },
```

- [ ] **Step 2: Add corresponding keys to `en-US.ts`**

Edit `frontend/apps/main/src/i18n/locales/en-US.ts` — locate the `aiProcess: {` block at line 137 and replace lines 151-153 (the `errorMessage`, `retry`, and closing brace) with:

```typescript
    errorMessage: '❌ AI execution failed, please retry',
    retry: 'Retry',
    thinkingTitle: 'Thinking...',
    answeringTitle: 'Generating answer...',
    errorTitle: 'Execution failed',
    elapsedSeconds: 'Thought for {seconds}s',
  },
```

- [ ] **Step 3: Run typecheck**

Run: `cd frontend/apps/main && npm run typecheck`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add frontend/apps/main/src/i18n/locales/zh-CN.ts frontend/apps/main/src/i18n/locales/en-US.ts
git commit -m "feat(ai/i18n): add phase-aware title keys and elapsed counter

Phase 3 Bundle A item A3. Adds:
- thinkingTitle / answeringTitle / errorTitle — phase-driven primary titles
- elapsedSeconds — '已思考 X 秒' / 'Thought for Xs' subtitle counter

These coexist with the existing statusRunning/statusDone/statusError
strings so phase-less historical messages still render via the legacy
subtitle path."
```

---

### Task 3: Refactor `AiProcessBlock` to Use Phase-Driven Title and Logo

**Files:**
- Modify: `frontend/apps/main/src/components/ai/AiProcessBlock.vue`

- [ ] **Step 1: Replace text-glyph header with `<AiLogo>`**

Edit `frontend/apps/main/src/components/ai/AiProcessBlock.vue` template (lines 4-7):

Replace:

```vue
      <div class="process-icon" :class="statusClass">
        <span class="icon-symbol">{{ statusIcon }}</span>
      </div>
```

With:

```vue
      <div class="process-icon" :class="statusClass">
        <AiLogo :state="logoState" />
      </div>
```

- [ ] **Step 2: Update primary title to use phase-aware computed**

In the same file, replace the title line (line 9):

```vue
        <span class="process-title">{{ t('aiProcess.title') }}</span>
```

With:

```vue
        <span class="process-title">{{ titleLabel }}</span>
```

- [ ] **Step 3: Update subtitle to show elapsed seconds during thinking**

Replace the status line (line 10):

```vue
        <span class="process-status">{{ statusLabel }}</span>
```

With:

```vue
        <span class="process-status">{{ subtitleLabel }}</span>
```

- [ ] **Step 4: Add `phase` prop, imports, elapsed-seconds tick state, and new computeds to script**

Replace the entire `<script setup lang="ts">` block (lines 58-140) with:

```vue
<script setup lang="ts">
import { computed, onUnmounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import AiProcessStep from './AiProcessStep.vue'
import AiToolCallStep from './AiToolCallStep.vue'
import AiLogo from './AiLogo.vue'
import type { ProcessStep } from '@/types/agent-stream'

const props = defineProps<{
  status: 'running' | 'done' | 'error'
  elapsedMs: number
  steps: ProcessStep[]
  defaultExpanded?: boolean
  errorMessage?: string
  phase?: 'connecting' | 'thinking' | 'answering' | 'done' | 'error'
  reasoningStartTime?: number | null
}>()

const emit = defineEmits<{
  (e: 'toggle-expand', expanded: boolean): void
  (e: 'retry'): void
}>()

const { t } = useI18n()
const isExpanded = ref(props.defaultExpanded ?? props.status === 'running')

function toggleExpand() {
  isExpanded.value = !isExpanded.value
  emit('toggle-expand', isExpanded.value)
}

function onRetry() {
  emit('retry')
}

watch(
  () => props.status,
  (val, prev) => {
    if (val === 'done' && prev === 'running') {
      isExpanded.value = false
    }
    if (val === 'running' && prev !== 'running') {
      isExpanded.value = true
    }
    if (val === 'error') {
      isExpanded.value = true
    }
  },
)

// Tick once per second while phase is thinking, so the elapsed-seconds
// subtitle updates without per-token re-renders.
const nowMs = ref(Date.now())
let tickInterval: ReturnType<typeof setInterval> | null = null

function startTick() {
  if (tickInterval) return
  tickInterval = setInterval(() => {
    nowMs.value = Date.now()
  }, 1000)
}

function stopTick() {
  if (tickInterval) {
    clearInterval(tickInterval)
    tickInterval = null
  }
}

watch(
  () => props.phase,
  (val) => {
    if (val === 'thinking') {
      nowMs.value = Date.now()
      startTick()
    } else {
      stopTick()
    }
  },
  { immediate: true },
)

onUnmounted(stopTick)

const logoState = computed<'idle' | 'thinking' | 'done' | 'error'>(() => {
  if (props.status === 'error') return 'error'
  if (props.status === 'done') return 'done'
  if (props.phase === 'thinking' || props.phase === 'connecting') return 'thinking'
  return 'idle'
})

const statusClass = computed(() => {
  switch (props.status) {
    case 'running': return 'status-running'
    case 'done': return 'status-done'
    case 'error': return 'status-error'
    default: return ''
  }
})

const titleLabel = computed(() => {
  if (props.status === 'error') return t('aiProcess.errorTitle')
  if (props.phase === 'thinking' || props.phase === 'connecting') return t('aiProcess.thinkingTitle')
  if (props.phase === 'answering') return t('aiProcess.answeringTitle')
  return t('aiProcess.title')
})

const subtitleLabel = computed(() => {
  if (props.phase === 'thinking' && props.reasoningStartTime) {
    const seconds = Math.max(0, Math.floor((nowMs.value - props.reasoningStartTime) / 1000))
    return t('aiProcess.elapsedSeconds', { seconds })
  }
  switch (props.status) {
    case 'running': return t('aiProcess.statusRunning')
    case 'done': return t('aiProcess.statusDone')
    case 'error': return t('aiProcess.statusError')
    default: return ''
  }
})

const formattedElapsed = computed(() => {
  const ms = props.elapsedMs
  if (ms < 1000) return `${ms}ms`
  const s = Math.floor(ms / 1000)
  if (s < 60) return `${s}s`
  return `${Math.floor(s / 60)}m${s % 60}s`
})
</script>
```

- [ ] **Step 5: Remove the now-unused `.icon-symbol` and stale `statusIcon` / `statusLabel` CSS**

In `frontend/apps/main/src/components/ai/AiProcessBlock.vue`, delete the `.icon-symbol` rule (lines 188-191 in the current file):

```css
.icon-symbol {
  font-size: 14px;
  color: #ffffff;
}
```

Leave all other CSS untouched — the `.process-icon` background still drives the logo container color.

- [ ] **Step 6: Run typecheck**

Run: `cd frontend/apps/main && npm run typecheck`
Expected: PASS

- [ ] **Step 7: Run tests**

Run: `cd frontend/apps/main && npm run test:run`
Expected: PASS (no new tests yet, just confirm nothing regressed)

- [ ] **Step 8: Commit**

```bash
git add frontend/apps/main/src/components/ai/AiProcessBlock.vue
git commit -m "feat(ai): wire AiLogo and phase-driven title into AiProcessBlock

Phase 3 Bundle A items A1 and A3. Changes:
- Replace text glyph in process-icon with <AiLogo :state=...>; idle for
  connecting/initial, thinking for thinking-phase, done/error follow status.
- New props: phase (passed from parent) and reasoningStartTime (for the
  elapsed-seconds counter).
- Primary title becomes computed titleLabel that swaps on phase change.
- Subtitle shows '已思考 X 秒' during thinking phase via a 1s setInterval
  tick; legacy statusRunning/Done/Error remains for done/error and as
  fallback for messages without a phase field.
- setInterval is properly cleared on phase exit and unmount."
```

---

### Task 4: Add Reasoning Body Shimmer

**Files:**
- Modify: `frontend/apps/main/src/components/ai/AiProcessStep.vue`

- [ ] **Step 1: Add `.body-streaming` class binding to the step body**

Edit `frontend/apps/main/src/components/ai/AiProcessStep.vue` template (lines 11-21).

Replace:

```vue
      <div class="step-body">
```

With:

```vue
      <div class="step-body" :class="{ 'body-streaming': status === 'streaming' }">
```

- [ ] **Step 2: Add shimmer CSS to the `<style scoped>` block**

In the same file, after the existing `.step-body { ... }` rule (around line 135), append:

```css
.body-streaming {
  background: linear-gradient(
    90deg,
    var(--card-bg) 25%,
    var(--bg-secondary) 50%,
    var(--card-bg) 75%
  );
  background-size: 200%;
  animation: body-shimmer 1.5s linear infinite;
}

@keyframes body-shimmer {
  0% {
    background-position: 200% center;
  }
  100% {
    background-position: -200% center;
  }
}

@media (prefers-reduced-motion: reduce) {
  .body-streaming {
    animation: none;
    background: var(--card-bg);
  }
}
```

- [ ] **Step 3: Run typecheck**

Run: `cd frontend/apps/main && npm run typecheck`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add frontend/apps/main/src/components/ai/AiProcessStep.vue
git commit -m "feat(ai): add body shimmer to reasoning step while streaming

Phase 3 Bundle A item A2. Adds a horizontal shimmer animation on the
reasoning step body when status === 'streaming', matching the visual
weight of the existing .args-running shimmer on tool call args.

Pure CSS; new .body-streaming class is bound only while streaming so the
animation stops the instant reasoning completes. Gated behind
prefers-reduced-motion to respect accessibility settings."
```

---

### Task 5: Wire `phase` and `reasoningStartTime` from AIChatPage

**Files:**
- Modify: `frontend/apps/main/src/pages/AIChatPage.vue`

- [ ] **Step 1: Locate the AiProcessBlock invocation**

Run to confirm location:

```bash
cd frontend/apps/main && grep -n "AiProcessBlock" src/pages/AIChatPage.vue
```

Expected output: at least one `<AiProcessBlock` tag in the template and one `import AiProcessBlock` in the script.

- [ ] **Step 2: Add `:phase` and `:reasoning-start-time` props to the `<AiProcessBlock>` invocation**

Find the `<AiProcessBlock` opening tag in the template. Add these two prop bindings into the existing prop list (immediately before the `@retry` / `@toggle-expand` handlers or at the end of the prop block, whichever is closer to where existing `msg.*` props are bound):

```vue
        :phase="msg.phase"
        :reasoning-start-time="msg.reasoningStartTime ?? null"
```

The `msg.phase` field already exists on the `Message` interface per `AIChatPage.vue` line 485-517 (see existing `phase?: 'connecting' | 'thinking' | 'answering' | 'done' | 'error' | 'interrupted'`).

- [ ] **Step 3: Add `reasoningStartTime` to the `Message` interface**

Find the `Message` interface in `frontend/apps/main/src/pages/AIChatPage.vue` (around lines 485-517). Add `reasoningStartTime?: number | null` to it. Locate the existing line:

```typescript
  thinkSeconds?: number       // 思考耗时
```

Add directly after it:

```typescript
  reasoningStartTime?: number | null // captured when thinking phase starts; feeds AiProcessBlock elapsed counter
```

- [ ] **Step 4: Set `reasoningStartTime` when phase transitions to thinking**

Find the event handler that processes `phase_change` events in `AIChatPage.vue`. Search for it:

```bash
cd frontend/apps/main && grep -n "phase_change\|phase = 'thinking'\|phase === 'thinking'" src/pages/AIChatPage.vue | head -10
```

Find the branch that sets `msg.phase = 'thinking'` (or equivalent assignment). Immediately after that assignment, add:

```typescript
if (msg.reasoningStartTime == null) {
  msg.reasoningStartTime = Date.now()
}
```

The guard ensures we only capture the start time once per message, even if multiple `phase.thinking` events arrive.

- [ ] **Step 5: Run typecheck**

Run: `cd frontend/apps/main && npm run typecheck`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add frontend/apps/main/src/pages/AIChatPage.vue
git commit -m "feat(ai/chat): pass phase and reasoningStartTime to AiProcessBlock

Phase 3 Bundle A — feeds the new title/subtitle/logo state in
AiProcessBlock. msg.phase already existed; reasoningStartTime is new
and is captured once per message on the first phase.thinking event so
the elapsed-seconds subtitle has a stable origin."
```

---

### Task 6: Unit Test for `AiLogo` State Switching

**Files:**
- Create: `frontend/apps/main/src/components/ai/AiLogo.test.ts`

- [ ] **Step 1: Write the test**

Create `frontend/apps/main/src/components/ai/AiLogo.test.ts`:

```typescript
import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import { createI18n } from 'vue-i18n'
import AiLogo from './AiLogo.vue'

const i18n = createI18n({
  legacy: false,
  locale: 'zh-CN',
  messages: {
    'zh-CN': {
      aiProcess: {
        title: '执行过程',
        statusRunning: '正在执行',
        statusDone: '已完成',
        statusError: '执行出错',
      },
    },
  },
})

function mountLogo(state: 'idle' | 'thinking' | 'done' | 'error') {
  return mount(AiLogo, {
    props: { state },
    global: { plugins: [i18n] },
  })
}

describe('AiLogo', () => {
  it('applies state-idle class for idle state', () => {
    const wrapper = mountLogo('idle')
    expect(wrapper.classes()).toContain('state-idle')
  })

  it('applies state-thinking class for thinking state', () => {
    const wrapper = mountLogo('thinking')
    expect(wrapper.classes()).toContain('state-thinking')
  })

  it('applies state-done class for done state', () => {
    const wrapper = mountLogo('done')
    expect(wrapper.classes()).toContain('state-done')
  })

  it('applies state-error class for error state', () => {
    const wrapper = mountLogo('error')
    expect(wrapper.classes()).toContain('state-error')
  })

  it('renders an SVG element with role="img"', () => {
    const wrapper = mountLogo('idle')
    expect(wrapper.attributes('role')).toBe('img')
    expect(wrapper.find('svg').exists()).toBe(true)
  })

  it('sets aria-label to status text matching state', () => {
    expect(mountLogo('thinking').attributes('aria-label')).toBe('正在执行')
    expect(mountLogo('done').attributes('aria-label')).toBe('已完成')
    expect(mountLogo('error').attributes('aria-label')).toBe('执行出错')
    expect(mountLogo('idle').attributes('aria-label')).toBe('执行过程')
  })
})
```

- [ ] **Step 2: Run the test**

Run: `cd frontend/apps/main && npm run test:run -- AiLogo`
Expected: 6 tests PASS

- [ ] **Step 3: Commit**

```bash
git add frontend/apps/main/src/components/ai/AiLogo.test.ts
git commit -m "test(ai): cover AiLogo state class switching and a11y attributes

Phase 3 Bundle A — verifies each of the 4 states applies the correct
state-* class, renders an SVG with role=img, and exposes a localized
aria-label so screen readers announce the AI status."
```

---

### Task 7: Verify End-to-End

**Files:** (verification only — no edits)

- [ ] **Step 1: Run full typecheck**

Run: `cd frontend/apps/main && npm run typecheck`
Expected: PASS

- [ ] **Step 2: Run full test suite**

Run: `cd frontend/apps/main && npm run test:run`
Expected: All tests PASS (Bundle A added 6 new tests; existing tests still pass)

- [ ] **Step 3: Run lint**

Run: `cd frontend/apps/main && npm run lint`
Expected: No new warnings or errors

- [ ] **Step 4: Manual verification checklist**

The engineer should manually verify (start `npm run dev`, navigate to `/ai/chat`, send a message):

1. On submit, the process block icon shows a spinning sparkle (logo state=thinking)
2. Primary title reads "正在思考..." while reasoning streams
3. Subtitle reads "已思考 0 秒" → "已思考 1 秒" → ... ticking every second
4. Reasoning step body has a visible horizontal shimmer while streaming
5. When the answer begins, primary title swaps to "正在生成回答..."
6. On capability.end, primary title swaps to "执行过程", subtitle to "已完成", logo state to done (checkmark)
7. On capability.error, primary title swaps to "执行出错", logo state to error (cross)
8. Toggle the OS "Reduce motion" setting — logo spin and shimmer should both stop animating but state changes should still be visible

If any check fails, file as a follow-up; do not gate Bundle A on it (these are visual polish and a UX regression here is not catastrophic — but the engineer should still document what they saw vs. what was expected).

---

## Verification Checklist

### Build & types
- [ ] `npm run typecheck` passes with zero new errors
- [ ] `npm run test:run` passes including new `AiLogo.test.ts`
- [ ] `npm run lint` passes with no new warnings
- [ ] `npm run build` succeeds (smoke build at end of bundle)

### Spec coverage (`docs/superpowers/specs/2026-05-25-ai-conversation-phase-3-design.md` §3)

- [ ] A1: AI logo SVG sprite — three states with currentColor, opacity transition ≥150ms, no Lottie dep, asset ≤8KB (inline SVG is ~600 bytes)
- [ ] A2: Reasoning body shimmer — visible while `status === 'streaming'`, stops on done, mobile preserved, WCAG AA contrast unchanged
- [ ] A3: Phase-driven title — switches on connecting/thinking/answering/done/error; subtitle shows "已思考 X 秒" during thinking; no every-second re-render of children (only `nowMs` ref ticks)
- [ ] DESIGN.md compliance: 4/8px radius unchanged; CSS variables used for all colors; no hex literals introduced
- [ ] i18n: both `zh-CN.ts` and `en-US.ts` updated; no hardcoded strings in `.vue` files
- [ ] `prefers-reduced-motion: reduce` honored on logo spin and shimmer

### Behavioral guarantees

- [ ] `phase` prop is optional — `AiProcessBlock` still renders when caller does not pass `phase` (historical messages, legacy AIChatPage paths)
- [ ] `reasoningStartTime` prop is optional — subtitle gracefully falls back to legacy `statusRunning/Done/Error` when missing
- [ ] `setInterval` is cleared on phase exit AND on component unmount (no leaked timers)
- [ ] No new dependencies in `package.json` diff

---

## Notes

- The SVG is inline and uses `currentColor`, so dark-mode adaptation flows from the existing `.process-icon` background color tokens — no separate dark-mode asset variant.
- Title swap during thinking → answering deliberately keeps subtitle showing the final "已思考 X 秒" by leaving `nowMs` frozen at `stopTick()` time. If the spec later wants "已思考 X 秒，正在回答" combined, that's a follow-up.
- The 1-second tick interval only triggers a re-render of `subtitleLabel` (since `nowMs.value` only invalidates that computed). The rest of the block — including the streaming reasoning body — is unaffected.

---

## Deferred / Open Questions

None for this bundle. All Bundle A items are scoped to the three files modified and the one new file created. Bundle B (chat UX) and Bundle C (agent coupling) proceed independently per the requirements doc.
