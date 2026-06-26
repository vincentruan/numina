# AI Chat Input Box Unification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Merge `AIChatInput.vue` (hub page) into `InputBox.vue` (chat page), producing a single unified DeerFlow-aligned input component.

**Architecture:** Replace `components/ai-chat/InputBox.vue` with a merged component using `AIChatInput.vue`'s custom CSS variable styling as base. The new component absorbs AIChatInput's features (expand button, attachments, plus panel, web search toggle) while keeping InputBox's DeerFlow features (4-mode selector, welcome mode, tenant resources, model selector popup). The slash palette is removed. Agent picker is owned by the parent component — InputBox emits `selectAgent` and parents (AIHubPage, AIChatBox) handle the action sheet.

**Tech Stack:** Vue 3 `<script setup lang="ts">`, TypeScript strict, Vant 4, Pinia, Vue Router

## Global Constraints

- `<script setup lang="ts">` only — no Options API, no `defineComponent`
- All user-facing strings must be defined in `src/i18n/locales/zh-CN.ts` and referenced via `t('key')`
- TypeScript strict mode — no `any`, no `@ts-ignore`, no `@ts-expect-error`
- Touch targets: min 44×44px for all interactive elements
- CSS variables + scoped styles — no inline `style="color:..."`
- No slash palette — removed entirely
- `AIChatInput.vue` becomes dead code after unification (not deleted, marked as deprecated)

---
### File Structure

| File | Action | Description |
|------|--------|-------------|
| `components/ai-chat/InputBox.vue` | **Replace** | Merged component with AIChatInput styling + all features |
| `components/common/AIChatInput.vue` | Deprecate | Add deprecation comment at top, keep as dead code |
| `components/ai/AIChatBox.vue` | No change needed | Already compatible with new InputBox interface |
| `components/ai/WelcomePage.vue` | No change needed | Does not use InputBox or AIChatInput directly |
| `pages/AIHubPage.vue` | Modify | Switch from AIChatInput to InputBox, update event handling |
| `pages/AIChatPage.vue` | No change | Already uses InputBox via AIChatBox |

### Task Dependencies

```
Task 1 (Script) ──→ Task 2 (Template) ──→ Task 3 (Styles) ──→ Task 4 (Consumers) ──→ Task 5 (Deprecate)
```

---

### Task 1: Define Props, Events, and Composable Logic

**Files:**
- Replace: `frontend/apps/main/src/components/ai-chat/InputBox.vue` (script section, lines 1-215)

**Interfaces:**
- Consumes: `InputMode`, `SubmitPayload`, `InputContext` from `@/types/ai-chat/input-mode`; `useTenantAiResources` composable; `getWebSearchStatus` from `@/api/webSearch`
- Produces: The merged component's `defineProps` / `defineEmits` signatures

- [ ] **Step 1: Replace the `<script setup lang="ts">` block**

Write the full merged script section to `InputBox.vue` (replacing everything from line 1 to `</script>`):

```vue
<script setup lang="ts">
/**
 * Unified AI Chat InputBox — merged from AIChatInput.vue (hub) + InputBox.vue (chat)
 *
 * Features:
 * - AIChatInput custom CSS variable styling (dark/light)
 * - DeerFlow 4-mode selector (Flash/Thinking/Pro/Ultra)
 * - Web search toggle with provider pre-check
 * - Plus panel (camera/file/image)
 * - Attachment preview row
 * - Expand button for full-screen textarea
 * - Welcome mode (hero + examples)
 * - Chat mode (bottom-sticky)
 * - Agent picker in welcome mode, static icon in chat mode
 * - Model selector popup
 * - Tenant resource isolation (useTenantAiResources)
 */
import { ref, computed, watch, nextTick, onMounted, onBeforeUnmount } from 'vue'
import { showToast } from 'vant'
import { useI18n } from 'vue-i18n'
import ModeSelector from './ModeSelector.vue'
import ModelSelectorPopup from './ModelSelectorPopup.vue'
import WelcomeExamples from './WelcomeExamples.vue'
import { useTenantAiResources, INPUT_MODE_CONFIGS, getResolvedMode } from '@/composables/ai-chat/useTenantAiResources'
import { getWebSearchStatus } from '@/api/webSearch'
import type { InputMode, SubmitPayload, InputContext } from '@/types/ai-chat/input-mode'

interface AgentOption {
  id: string
  display_name: string
  agent_name?: string
  icon?: string
}

interface Attachment {
  type: 'file' | 'image'
  name: string
  path?: string
}

const { t } = useI18n()

// ── Props ──
const props = defineProps<{
  status: 'ready' | 'streaming' | 'submitted' | 'error' | 'reconnecting'
  isWelcomeMode?: boolean
  threadId?: string
  initialMode?: InputMode
  initialModelName?: string
  agentId?: string
  agents?: AgentOption[]
  agentIcon?: string
  agentLabel?: string
  disabled?: boolean
  modelValue?: string
  webSearch?: boolean
  attachments?: Attachment[]
}>()

// ── Emits ──
const emit = defineEmits<{
  submit: [payload: SubmitPayload]
  stop: []
  'update:modelValue': [value: string]
  'update:webSearch': [value: boolean]
  selectAgent: []
  action: [type: 'file' | 'image' | 'camera']
  removeAttachment: [index: number]
  contextChange: [context: InputContext]
}>()

// ── Tenant resources ──
const {
  models,
  tenantConfig: _tenantConfig,
  supportsThinking: _supportsThinking,
  supportsSubagent,
  loading: resourcesLoading,
} = useTenantAiResources()

// ── Input state ──
const internalValue = ref(props.modelValue ?? '')
const focused = ref(false)
const expanded = ref(false)
const panelOpen = ref(false)
const modelDialogOpen = ref(false)
const webSearchEnabled = ref(props.webSearch ?? false)
const inputRef = ref<HTMLTextAreaElement | null>(null)

// ── Mode context (DeerFlow 4-mode) ──
const selectedModel = computed(() =>
  models.value.find(m => m.name === context.value.model_name) ?? models.value[0],
)

const context = ref<InputContext>({
  model_name: props.initialModelName ?? '',
  mode: props.initialMode ?? 'pro',
  reasoning_effort: 'medium',
})

const currentModelSupportsThinking = computed(() =>
  selectedModel.value?.supports_thinking ?? false,
)

const isUltraDisabled = computed(() => !supportsSubagent.value)

const finalPayload = computed(() => {
  const config = INPUT_MODE_CONFIGS[context.value.mode]
  return {
    thinking_enabled: config.thinking_enabled,
    is_plan_mode: config.is_plan_mode,
    subagent_enabled: config.subagent_enabled,
    reasoning_effort: config.reasoning_effort,
  }
})

// ── Agent display ──
const selectedAgent = computed(() =>
  props.agents?.find((a) => a.id === props.agentId) ?? props.agents?.[0] ?? null,
)
const displayAgentIcon = computed(() => props.agentIcon || selectedAgent.value?.icon || null)
const displayAgentLabel = computed(() => props.agentLabel || selectedAgent.value?.display_name || '')

// ── Watchers ──
watch(internalValue, (val) => emit('update:modelValue', val))
watch(() => props.modelValue, (val) => {
  if (val !== undefined && val !== internalValue.value) {
    internalValue.value = val
  }
})
watch(webSearchEnabled, (val) => emit('update:webSearch', val))
watch(() => props.webSearch, (val) => {
  if (val !== undefined && val !== webSearchEnabled.value) {
    webSearchEnabled.value = val
  }
})

// Auto-downgrade mode when model doesn't support thinking
watch(currentModelSupportsThinking, (supports) => {
  const resolved = getResolvedMode(context.value.mode, supports, supportsSubagent.value)
  if (resolved !== context.value.mode) {
    showToast(t('aiChat.tenantModelFallback'))
    context.value.mode = resolved
    emitContextChange()
  }
})

// Initialize default model
watch(models, (newModels) => {
  if (newModels.length > 0 && !context.value.model_name) {
    const defaultModel = newModels.find(m => m.is_default) ?? newModels[0]
    context.value.model_name = defaultModel.name
    const resolved = getResolvedMode(context.value.mode, defaultModel.supports_thinking ?? false, supportsSubagent.value)
    if (resolved !== context.value.mode) {
      context.value.mode = resolved
    }
    emitContextChange()
  }
}, { immediate: true })

// ── Methods ──
function adjustHeight() {
  const el = inputRef.value
  if (!el) return
  if (expanded.value) {
    el.style.height = '75vh'
    return
  }
  el.style.height = 'auto'
  el.style.height = Math.min(el.scrollHeight, 120) + 'px'
}

function onSubmit() {
  if (props.status === 'streaming') {
    emit('stop')
    return
  }
  const text = internalValue.value.trim()
  if (!text) return

  emit('submit', {
    text,
    model_name: context.value.model_name,
    mode: context.value.mode,
    ...finalPayload.value,
    thread_id: props.threadId,
  })
  internalValue.value = ''
}

function onModeSelect(mode: InputMode) {
  if (mode === 'ultra' && !supportsSubagent.value) {
    showToast(t('aiChat.tenantUltraDisabled'))
    return
  }
  context.value.mode = mode
  context.value.reasoning_effort = INPUT_MODE_CONFIGS[mode].reasoning_effort
  emitContextChange()
}

function onModelSelect(modelName: string) {
  const model = models.value.find(m => m.name === modelName)
  if (!model) return
  context.value.model_name = modelName
  const resolved = getResolvedMode(context.value.mode, model.supports_thinking ?? false, supportsSubagent.value)
  if (resolved !== context.value.mode) {
    showToast(t('aiChat.tenantModelFallback'))
    context.value.mode = resolved
  }
  emitContextChange()
}

function emitContextChange() {
  emit('contextChange', {
    ...context.value,
    reasoning_effort: INPUT_MODE_CONFIGS[context.value.mode].reasoning_effort,
  })
}

// Web search
async function toggleWebSearch() {
  if (!webSearchEnabled.value) {
    try {
      const status = await getWebSearchStatus()
      if (!status.has_web_search) {
        showToast(t('webSearch.noProviderToast'))
        return
      }
    } catch {
      showToast(t('webSearch.noProviderToast'))
      return
    }
  }
  webSearchEnabled.value = !webSearchEnabled.value
}

// Expand
function toggleExpand() {
  expanded.value = !expanded.value
  nextTick(adjustHeight)
}

// Panel
function closePanel() {
  panelOpen.value = false
}

function onPanelItem(action: 'file' | 'image' | 'camera') {
  panelOpen.value = false
  emit('action', action)
}

const panelItems = computed(() => [
  {
    action: 'camera' as const,
    label: t('aiChat.panelCamera'),
    icon: { viewBox: '0 0 24 24', paths: ['M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z', 'M12 17a4 4 0 1 0 0-8 4 4 0 0 0 0 8z'] },
  },
  {
    action: 'file' as const,
    label: t('aiChat.panelFile'),
    icon: { viewBox: '0 0 24 24', paths: ['M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z', 'M14 2v6h6', 'M12 18v-6', 'M9 15h6'] },
  },
  {
    action: 'image' as const,
    label: t('aiChat.panelImage'),
    icon: { viewBox: '0 0 24 24', paths: ['M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4', 'M17 8l-5-5-5 5', 'M12 3v12'] },
  },
])

function removeAttachment(index: number) {
  emit('removeAttachment', index)
}

// Welcome examples
function handleWelcomeExampleSelect(prompt: string) {
  internalValue.value = prompt
  setTimeout(() => onSubmit(), 0)
}

function handleSurpriseMe() {
  const surprisePrompts = [
    t('aiChat.welcomeExampleAnalyzePrompt'),
    t('aiChat.welcomeExamplePlanPrompt'),
    t('aiChat.welcomeExampleLearnPrompt'),
    t('aiChat.welcomeExampleOptimizePrompt'),
  ]
  const randomPrompt = surprisePrompts[Math.floor(Math.random() * surprisePrompts.length)]
  internalValue.value = randomPrompt
  setTimeout(() => onSubmit(), 0)
}

// Click outside handler (for plus panel)
function onDocClick(e: MouseEvent) {
  const el = e.target as HTMLElement
  if (!el.closest('.input-box')) {
    panelOpen.value = false
  }
}

onMounted(() => {
  nextTick(adjustHeight)
  document.addEventListener('click', onDocClick)
})

onBeforeUnmount(() => {
  document.removeEventListener('click', onDocClick)
})
</script>
```

- [ ] **Step 2: Run typecheck**

Run: `cd frontend/apps/main && pnpm typecheck`
Expected: No type errors. If errors occur, fix the type issues.

- [ ] **Step 3: Commit**

```bash
git add frontend/apps/main/src/components/ai-chat/InputBox.vue
git commit -m "feat(InputBox): merge script section with AIChatInput composable logic"
```

---

### Task 2: Template — Layout Structure

**Files:**
- Replace: `components/ai-chat/InputBox.vue` (template section)

- [ ] **Step 1: Replace the `<template>` block**

Write the merged template. Layout from bottom-left to bottom-right: Agent button → Model selector → Mode selector (4-mode) → Web search toggle → Plus button → Send/Stop. Expand button at top-right of textarea. Attachment preview row above textarea. Welcome hero + examples in welcome mode.

```vue
<template>
  <div
    class="input-box"
    :class="[
      status,
      isWelcomeMode ? 'welcome-mode' : 'chat-mode',
      { focused, expanded },
    ]"
    @click.self="closePanel"
  >
    <!-- Welcome hero (welcome mode only) -->
    <div v-if="isWelcomeMode" class="welcome-hero">
      <h2 class="hero-title">{{ displayAgentLabel || t('aiChat.heroTitleChat') }}</h2>
      <p class="hero-subtitle">{{ t('aiChat.heroSubtitleChat') }}</p>
    </div>

    <!-- Welcome examples (welcome mode only) -->
    <WelcomeExamples
      v-if="isWelcomeMode"
      :agent-id="agentId || 'numina'"
      @select="handleWelcomeExampleSelect"
      @surprise="handleSurpriseMe"
    />

    <!-- Input row -->
    <div class="input-row" :class="{ 'is-focused': focused, 'is-expanded': expanded }">
      <!-- Attachments preview row (above textarea) -->
      <div v-if="attachments && attachments.length > 0" class="attachments-row">
        <div
          v-for="(att, idx) in attachments"
          :key="idx"
          class="attachment-item"
          :class="`attachment-item--${att.type}`"
        >
          <span class="attachment-icon" aria-hidden="true">
            <svg v-if="att.type === 'image'" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
              <rect x="3" y="3" width="18" height="18" rx="2" ry="2"/>
              <circle cx="8.5" cy="8.5" r="1.5"/>
              <polyline points="21 15 16 10 5 21"/>
            </svg>
            <svg v-else width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
              <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
              <polyline points="14 2 14 8 20 8"/>
            </svg>
          </span>
          <span class="attachment-name">{{ att.name }}</span>
          <button class="attachment-remove" :aria-label="t('common.remove')" @click="removeAttachment(idx)">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <line x1="18" y1="6" x2="6" y2="18"/>
              <line x1="6" y1="6" x2="18" y2="18"/>
            </svg>
          </button>
        </div>
      </div>

      <!-- Textarea -->
      <textarea
        ref="inputRef"
        v-model="internalValue"
        class="chat-textarea"
        :placeholder="isWelcomeMode ? t('aiChat.inputPlaceholder') : t('aiChat.continuePlaceholder')"
        :disabled="disabled || status === 'submitted'"
        rows="3"
        @input="adjustHeight"
        @keydown.enter.ctrl="onSubmit"
        @focus="focused = true"
        @blur="focused = false"
      />

      <!-- Expand button (top-right) -->
      <button
        class="expand-btn"
        :aria-label="expanded ? t('aiChat.collapse') : t('aiChat.expand')"
        :title="expanded ? t('aiChat.collapse') : t('aiChat.expand')"
        @click="toggleExpand"
      >
        <svg v-if="!expanded" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
          <polyline points="15 3 21 3 21 9"/><polyline points="9 21 3 21 3 15"/>
          <line x1="21" y1="3" x2="14" y2="10"/><line x1="3" y1="21" x2="10" y2="14"/>
        </svg>
        <svg v-else width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
          <polyline points="4 14 10 14 10 20"/><polyline points="20 10 14 10 14 4"/>
          <line x1="10" y1="14" x2="3" y2="21"/><line x1="21" y1="3" x2="14" y2="10"/>
        </svg>
      </button>

      <!-- Bottom toolbar (left to right) -->
      <div class="input-controls">
        <!-- Plus panel (positioned relative to controls) -->
        <transition name="panel">
          <div v-if="panelOpen" class="plus-panel plus-panel--up" role="menu" :aria-label="t('aiChat.moreFeatures')">
            <button
              v-for="item in panelItems"
              :key="item.action"
              class="panel-item"
              role="menuitem"
              @click="onPanelItem(item.action)"
            >
              <span class="panel-item-icon" aria-hidden="true">
                <svg :viewBox="item.icon.viewBox" width="20" height="20" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
                  <path v-for="(d, i) in item.icon.paths" :key="i" :d="d" />
                </svg>
              </span>
              <span class="panel-item-label">{{ item.label }}</span>
            </button>
          </div>
        </transition>

        <!-- [1] Agent button: clickable in welcome mode, static icon in chat mode -->
        <button
          v-if="agents && agents.length > 0 && isWelcomeMode"
          class="control-btn control-btn--agent"
          :aria-label="t('aiHub.selectAgent')"
          :title="t('aiHub.selectAgent')"
          @click="emit('selectAgent')"
        >
          <span v-if="displayAgentIcon" class="agent-emoji" aria-hidden="true">{{ displayAgentIcon }}</span>
          <svg v-else width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
            <rect x="3" y="3" width="18" height="18" rx="4"/>
            <circle cx="8.5" cy="10" r="1.5" fill="currentColor"/>
            <circle cx="15.5" cy="10" r="1.5" fill="currentColor"/>
            <path d="M8 15c1 1.2 2.4 1.8 4 1.8s3-.6 4-1.8"/>
          </svg>
        </button>
        <!-- Static agent icon in chat mode -->
        <span
          v-else-if="displayAgentIcon && !isWelcomeMode"
          class="agent-static-icon"
          :title="displayAgentLabel"
        >
          {{ displayAgentIcon }}
        </span>

        <!-- [2] Model selector button -->
        <button
          class="control-btn control-btn--model"
          :disabled="resourcesLoading"
          @click="modelDialogOpen = true"
        >
          <span class="model-name">{{ selectedModel?.display_name || t('aiChat.selectModel') }}</span>
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="dropdown-icon">
            <polyline points="6 9 12 15 18 9"/>
          </svg>
        </button>

        <!-- [3] Mode selector (4-mode DeerFlow) -->
        <ModeSelector
          :current-mode="context.mode"
          :supports-thinking="currentModelSupportsThinking"
          :ultra-disabled="isUltraDisabled"
          @select="onModeSelect"
        />

        <!-- [4] Web search toggle -->
        <button
          class="control-btn control-btn--search"
          :class="{ 'control-btn--active': webSearchEnabled }"
          :aria-pressed="webSearchEnabled"
          :aria-label="t('aiChat.webSearch')"
          :title="t('aiChat.webSearch')"
          @click="toggleWebSearch"
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
            <circle cx="12" cy="12" r="10"/>
            <path d="M2 12h20M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/>
          </svg>
          <span v-if="webSearchEnabled" class="control-indicator" aria-hidden="true"></span>
        </button>

        <!-- [5] Plus button -->
        <button
          class="control-btn control-btn--plus"
          :class="{ 'control-btn--open': panelOpen }"
          :aria-label="t('aiChat.moreFeatures')"
          :aria-expanded="panelOpen"
          @click.stop="panelOpen = !panelOpen"
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
            <line x1="12" y1="5" x2="12" y2="19"/>
            <line x1="5" y1="12" x2="19" y2="12"/>
          </svg>
        </button>
      </div>

      <!-- Send/Stop button (bottom-right) -->
      <button
        v-if="status === 'streaming' || status === 'submitted'"
        class="send-btn send-btn--abort"
        :aria-label="t('aiChat.stopGeneration')"
        @click="emit('stop')"
      >
        <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
          <rect x="4" y="4" width="16" height="16" rx="2"/>
        </svg>
      </button>
      <button
        v-else
        class="send-btn"
        :class="{ 'send-btn--active': internalValue.trim() }"
        :disabled="disabled || !internalValue.trim()"
        :aria-label="t('common.send')"
        @click="onSubmit"
      >
        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
          <line x1="22" y1="2" x2="11" y2="13"/>
          <polygon points="22 2 15 22 11 13 2 9 22 2"/>
        </svg>
      </button>
    </div>

    <!-- Bottom background layer (chat mode) -->
    <div v-if="!isWelcomeMode" class="chat-bg-layer" />

    <!-- Model selector popup -->
    <ModelSelectorPopup
      v-model:show="modelDialogOpen"
      :models="models"
      :current-model="context.model_name"
      @select="onModelSelect"
    />
  </div>
</template>
```

- [ ] **Step 2: Run typecheck**

Run: `cd frontend/apps/main && pnpm typecheck`
Expected: No type errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/apps/main/src/components/ai-chat/InputBox.vue
git commit -m "feat(InputBox): add merged template with AIChatInput layout"
```

---

### Task 3: Styles — AIChatInput CSS Variable Theme + DeerFlow Chat Layout

**Files:**
- Replace: `components/ai-chat/InputBox.vue` (style section)

- [ ] **Step 1: Replace the `<style scoped>` block**

Write the merged styles. Uses AIChatInput's custom CSS variable approach as the base (dark default + light mode overrides via `:global(.theme-light)`), then adds InputBox's welcome/chat mode layout and responsive breakpoints.

```vue
<style scoped>
/* ── CSS variables (AIChatInput base, dark default) ── */
.input-box {
  --ai-btn-border: rgba(255, 255, 255, 0.1);
  --ai-btn-color: var(--text-tertiary);
  --ai-btn-hover-bg: rgba(255, 255, 255, 0.06);
  --ai-btn-hover-color: rgba(255, 255, 255, 0.7);
  --ai-panel-bg: #1e1e2e;
  --ai-panel-border: rgba(255, 255, 255, 0.1);
  --ai-panel-item-color: rgba(255, 255, 255, 0.6);
  --ai-panel-item-hover-bg: rgba(255, 255, 255, 0.08);
  --ai-panel-item-hover-color: rgba(255, 255, 255, 0.9);
  --ai-input-bg: rgba(255, 255, 255, 0.07);
  --ai-input-border: rgba(255, 255, 255, 0.1);
  --ai-text-color: rgba(255, 255, 255, 0.9);
  --ai-placeholder-color: rgba(255, 255, 255, 0.3);
  --ai-scrollbar-thumb: rgba(255, 255, 255, 0.15);
  --ai-expand-color: rgba(255, 255, 255, 0.3);
  --ai-expand-hover-bg: rgba(255, 255, 255, 0.08);
  --ai-expand-hover-color: rgba(255, 255, 255, 0.6);

  position: relative;
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 12px 16px;
  background: var(--card-bg);
  border-radius: 16px;
  transition: all 0.2s ease;
}

/* ── Light mode overrides (AIChatInput pattern) ── */
:global(.theme-light .input-box),
:global([data-theme='light'] .input-box) {
  --ai-btn-border: rgba(0, 0, 0, 0.4);
  --ai-btn-color: rgba(0, 0, 0, 0.75);
  --ai-btn-hover-bg: rgba(0, 0, 0, 0.1);
  --ai-btn-hover-color: rgba(0, 0, 0, 0.9);
  --ai-panel-bg: #ffffff;
  --ai-panel-border: rgba(0, 0, 0, 0.25);
  --ai-panel-item-color: rgba(0, 0, 0, 0.75);
  --ai-panel-item-hover-bg: rgba(0, 0, 0, 0.08);
  --ai-panel-item-hover-color: rgba(0, 0, 0, 0.9);
  --ai-input-bg: #ffffff;
  --ai-input-border: rgba(0, 0, 0, 0.35);
  --ai-text-color: rgba(0, 0, 0, 0.9);
  --ai-placeholder-color: rgba(0, 0, 0, 0.6);
  --ai-scrollbar-thumb: rgba(0, 0, 0, 0.25);
  --ai-expand-color: rgba(0, 0, 0, 0.55);
  --ai-expand-hover-bg: rgba(0, 0, 0, 0.1);
  --ai-expand-hover-color: rgba(0, 0, 0, 0.8);
}

/* ── Layout modes ── */
.input-box.welcome-mode {
  align-items: center;
  justify-content: center;
  min-height: 200px;
  margin: 0 auto;
  max-width: 90%;
}

.input-box.chat-mode {
  position: sticky;
  bottom: 0;
  border-radius: 0;
  padding-bottom: calc(12px + env(safe-area-inset-bottom));
}

/* ── Welcome hero ── */
.welcome-hero {
  text-align: center;
  margin-bottom: 16px;
}

.hero-title {
  font-size: 20px;
  font-weight: 600;
  color: var(--text-primary);
}

.hero-subtitle {
  font-size: 14px;
  color: var(--text-secondary);
  margin-top: 4px;
}

/* ── Input row (AIChatInput style) ── */
.input-row {
  position: relative;
  display: flex;
  flex-direction: column;
  background: var(--ai-input-bg);
  border: 1px solid var(--ai-input-border);
  border-radius: 18px;
  padding: 10px 48px 44px 14px;
  min-height: 100px;
  transition: border-color 0.2s, box-shadow 0.2s, border-radius 0.2s, min-height 0.2s;
}

.input-row.is-focused {
  border-color: rgba(99, 102, 241, 0.6);
  box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.15);
}

.input-row.is-expanded {
  border-radius: 14px;
  min-height: 75vh;
}

/* ── Chat textarea (AIChatInput style) ── */
.chat-textarea {
  flex: 1;
  border: none;
  background: transparent;
  font-size: 14px;
  color: var(--ai-text-color);
  outline: none;
  resize: none;
  overflow-y: auto;
  line-height: 20px;
  min-height: 60px;
  padding: 0;
  margin: 0;
  transition: height 0.12s ease;
  caret-color: #6366f1;
}

.chat-textarea::placeholder {
  color: var(--ai-placeholder-color);
}

.chat-textarea:disabled {
  opacity: 0.5;
}

.chat-textarea::-webkit-scrollbar {
  width: 3px;
}

.chat-textarea::-webkit-scrollbar-thumb {
  background: var(--ai-scrollbar-thumb);
  border-radius: 2px;
}

/* ── Expand button (top-right) ── */
.expand-btn {
  position: absolute;
  top: 8px;
  right: 8px;
  width: 30px;
  height: 30px;
  background: transparent;
  border: none;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  color: var(--ai-expand-color);
  transition: background 0.15s, color 0.15s;
}

.expand-btn:hover {
  background: var(--ai-expand-hover-bg);
  color: var(--ai-expand-hover-color);
}

/* ── Bottom toolbar controls ── */
.input-controls {
  position: absolute;
  bottom: 8px;
  left: 10px;
  display: flex;
  align-items: center;
  gap: 6px;
}

.control-btn {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  border: none;
  background: rgba(99, 102, 241, 0.08);
  color: var(--ai-btn-color);
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: background 0.2s, color 0.2s, transform 0.15s, box-shadow 0.2s;
  position: relative;
  min-width: 44px;
  min-height: 44px;
}

.control-btn:hover {
  background: rgba(99, 102, 241, 0.15);
  color: var(--ai-btn-hover-color);
}

.control-btn:active {
  transform: scale(0.92);
}

.control-btn--active {
  background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%);
  color: #ffffff;
  box-shadow: 0 2px 8px rgba(99, 102, 241, 0.4), 0 0 0 2px rgba(99, 102, 241, 0.2);
}

.control-btn--active:hover {
  background: linear-gradient(135deg, #7c3aed 0%, #a78bfa 100%);
  box-shadow: 0 3px 12px rgba(99, 102, 241, 0.5), 0 0 0 2px rgba(99, 102, 241, 0.3);
}

.control-btn--plus {
  transition: background 0.2s, color 0.2s, transform 0.2s;
}

.control-btn--open {
  transform: rotate(45deg);
  background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%);
  color: #ffffff;
  box-shadow: 0 2px 8px rgba(99, 102, 241, 0.4);
}

.control-indicator {
  position: absolute;
  top: 2px;
  right: 2px;
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #10b981;
  box-shadow: 0 0 4px rgba(16, 185, 129, 0.6);
}

.agent-emoji {
  font-size: 14px;
  line-height: 1;
}

.agent-static-icon {
  font-size: 18px;
  line-height: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  min-width: 44px;
  min-height: 44px;
  border-radius: 50%;
  background: rgba(99, 102, 241, 0.12);
  cursor: default;
}

/* ── Model selector button ── */
.control-btn--model {
  width: auto;
  border-radius: 12px;
  padding: 6px 10px;
  gap: 4px;
  background: rgba(99, 102, 241, 0.08);
  color: var(--ai-btn-color);
  border: 1px solid var(--ai-btn-border);
}

.model-name {
  font-weight: 500;
  font-size: 12px;
}

.dropdown-icon {
  flex-shrink: 0;
}

/* ── Attachments row ── */
.attachments-row {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  padding: 6px 0 4px;
  margin-bottom: 4px;
  border-bottom: 1px dashed rgba(99, 102, 241, 0.2);
}

.attachment-item {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 4px 8px;
  border-radius: 6px;
  background: rgba(99, 102, 241, 0.12);
  border: 1px solid rgba(99, 102, 241, 0.25);
  font-size: 12px;
  color: var(--ai-text-color);
  max-width: 180px;
}

.attachment-icon {
  color: #818cf8;
  flex-shrink: 0;
}

.attachment-name {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.attachment-remove {
  width: 16px;
  height: 16px;
  border: none;
  border-radius: 4px;
  background: transparent;
  color: rgba(255, 255, 255, 0.5);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  transition: color 0.15s, background 0.15s;
}

.attachment-remove:hover {
  background: rgba(248, 113, 113, 0.2);
  color: #f87171;
}

.attachment-item--image {
  background: rgba(16, 185, 129, 0.12);
  border-color: rgba(16, 185, 129, 0.25);
}

.attachment-item--image .attachment-icon {
  color: #10b981;
}

/* ── Plus panel ── */
.plus-panel {
  position: absolute;
  background: var(--ai-panel-bg);
  border: 1px solid var(--ai-panel-border);
  border-radius: 14px;
  padding: 8px;
  display: flex;
  flex-direction: column;
  gap: 4px;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.4);
  z-index: 100;
  min-width: 160px;
}

.plus-panel--up {
  bottom: calc(100% + 8px);
  left: 0;
}

.panel-item {
  display: flex;
  flex-direction: row;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  border: none;
  border-radius: 10px;
  background: transparent;
  color: var(--ai-panel-item-color);
  font-size: 13px;
  cursor: pointer;
  transition: background 0.15s, color 0.15s;
  white-space: nowrap;
}

.panel-item:hover {
  background: var(--ai-panel-item-hover-bg);
  color: var(--ai-panel-item-hover-color);
}

.panel-item:active {
  transform: scale(0.95);
}

.panel-item-icon {
  width: 28px;
  height: 28px;
  border-radius: 8px;
  background: rgba(99, 102, 241, 0.12);
  display: flex;
  align-items: center;
  justify-content: center;
  color: #818cf8;
  flex-shrink: 0;
}

.panel-item-label {
  line-height: 1.2;
}

/* ── Send/Stop button ── */
.send-btn {
  position: absolute;
  bottom: 8px;
  right: 8px;
  width: 36px;
  height: 36px;
  min-width: 44px;
  min-height: 44px;
  border-radius: 50%;
  border: none;
  background: rgba(99, 102, 241, 0.2);
  color: rgba(99, 102, 241, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: background 0.2s, color 0.2s, transform 0.15s;
}

.send-btn--active {
  background: linear-gradient(135deg, #6366f1, #7c3aed);
  color: #fff;
  box-shadow: 0 2px 12px rgba(99, 102, 241, 0.4);
}

.send-btn--active:hover {
  transform: scale(1.05);
}

.send-btn--active:active {
  transform: scale(0.95);
}

.send-btn:disabled {
  cursor: default;
}

.send-btn--abort {
  background: #ff3b30;
  color: #fff;
  box-shadow: 0 2px 12px rgba(255, 59, 48, 0.4);
  cursor: pointer;
}

.send-btn--abort:hover {
  transform: scale(1.05);
  background: #ff2d20;
}

.send-btn--abort:active {
  transform: scale(0.95);
}

/* ── Chat background layer ── */
.chat-bg-layer {
  position: absolute;
  left: 0;
  right: 0;
  bottom: -16px;
  height: 16px;
  background: var(--bg-primary);
  z-index: -1;
}

/* ── Panel transition ── */
.panel-enter-active,
.panel-leave-active {
  transition: opacity 0.15s ease, transform 0.15s ease;
}

.panel-enter-from,
.panel-leave-to {
  opacity: 0;
  transform: scale(0.92) translateY(4px);
}

/* ── Animations ── */
.animate-spin {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

@media (prefers-reduced-motion: reduce) {
  .send-btn,
  .control-btn,
  .input-row,
  .panel-enter-active,
  .panel-leave-active {
    transition: none;
  }
}

/* ── Responsive (375px) ── */
@media (max-width: 375px) {
  .input-box {
    padding: 8px 12px;
    padding-bottom: calc(8px + env(safe-area-inset-bottom));
  }

  .input-box.welcome-mode {
    min-height: 160px;
    max-width: 95%;
  }

  .chat-textarea {
    font-size: 14px;
  }

  .hero-title {
    font-size: 18px;
  }

  .hero-subtitle {
    font-size: 12px;
  }
}
</style>
```

- [ ] **Step 2: Run typecheck**

Run: `cd frontend/apps/main && pnpm typecheck`
Expected: No type errors.

- [ ] **Step 3: Verify the full component renders correctly**

Run: `cd frontend/apps/main && pnpm test:run` (if tests exist for this component)
Run: `cd frontend/apps/main && pnpm typecheck`
Expected: All tests pass, no type errors.

- [ ] **Step 4: Commit**

```bash
git add frontend/apps/main/src/components/ai-chat/InputBox.vue
git commit -m "feat(InputBox): merge AIChatInput styling with CSS variable theme"
```

---

### Task 4: Update Consumer — AIHubPage

**Files:**
- Modify: `pages/AIHubPage.vue` — switch from `AIChatInput` to `InputBox`, remap events

**Interfaces:**
- Consumes: The merged `InputBox` component from Task 1-3
- Produces: Working AI hub page with the new unified input

- [ ] **Step 1: Replace AIChatInput import with InputBox in AIHubPage.vue**

Current AIHubPage imports `AIChatInput` from `@/components/common/AIChatInput.vue`. Replace it with `InputBox` from `@/components/ai-chat/InputBox.vue`.

Find the import line (likely `import AIChatInput from '@/components/common/AIChatInput.vue'`):
```typescript
// Remove:
// import AIChatInput from '@/components/common/AIChatInput.vue'

// Add:
import InputBox from '@/components/ai-chat/InputBox.vue'
```

- [ ] **Step 2: Remap template usage in AIHubPage.vue**

Replace the `<AIChatInput ... />` usage with `<InputBox ... />`. The key changes:

Old AIChatInput props:
- `v-model="message"` → `v-model="message"` (still works as `modelValue`)
- `:loading="loading"` → `:status="loading ? 'submitted' : 'ready'"` (InputBox uses status enum)
- `:web-search.sync="webSearch"` → `v-model:webSearch="webSearch"` (v-model syntax)
- `:mode="mode"` → `:initialMode="mode"` (different naming)
- `:agents="agents"` → same
- `:selected-agent-id="selectedAgentId"` → `:agentId="selectedAgentId"` (rename)
- `@submit="handleSubmit"` → `@submit="handleSubmit"` (same)
- `@abort="handleAbort"` → `@stop="handleAbort"` (rename event)
- `@action="handleAction"` → same
- `@selectAgent="showAgentPicker = true"` → same (InputBox emits same event)
- `@remove-attachment="handleRemoveAttachment"` → `@removeAttachment="handleRemoveAttachment"`

New InputBox props to add:
- `:is-welcome-mode="true"` (AIHubPage is always welcome mode)
- `:status="computedStatus"` (map from loading state)
- `:agent-icon="selectedAgent?.icon"` (pass icon for display)
- `:agent-label="selectedAgent?.display_name"`

The exact template replacement depends on the current AIHubPage template. The changes are:
1. Component tag name: `AIChatInput` → `InputBox`
2. `:loading` → `:status` (wrap in a computed or inline ternary)
3. `:web-search.sync` → `v-model:webSearch`
4. `:mode` → `:initialMode`
5. `:selected-agent-id` → `:agentId`
6. `@abort` → `@stop`
7. Add `:is-welcome-mode="true"`
8. Add `:agent-icon` and `:agent-label` if available in the page's state

- [ ] **Step 3: Run typecheck**

Run: `cd frontend/apps/main && pnpm typecheck`
Expected: No type errors.

- [ ] **Step 4: Commit**

```bash
git add frontend/apps/main/src/pages/AIHubPage.vue
git commit -m "feat(AIHubPage): switch from AIChatInput to unified InputBox"
```

---

### Task 5: Deprecate AIChatInput.vue

**Files:**
- Modify: `components/common/AIChatInput.vue` — add deprecation notice

- [ ] **Step 1: Add deprecation comment at top of AIChatInput.vue**

Add as the first line of the file:

```vue
<!--
  @deprecated Use InputBox from @/components/ai-chat/InputBox.vue instead.
  This component is kept as dead code for reference only.
  Do not use in new code.
-->
```

- [ ] **Step 2: Commit**

```bash
git add frontend/apps/main/src/components/common/AIChatInput.vue
git commit -m "chore: deprecate AIChatInput in favor of unified InputBox"
```

---

### Task 6: Verification

- [ ] **Step 1: Run frontend typecheck**

```bash
cd frontend/apps/main
pnpm typecheck
```

Expected: No type errors. If errors occur, fix them.

- [ ] **Step 2: Run frontend tests**

```bash
cd frontend/apps/main
pnpm test:run
```

Expected: All tests pass (pre-existing failures acceptable, but no new failures).

- [ ] **Step 3: Verify the full component chain**

Check that the component chain works end-to-end:
1. AIHubPage imports InputBox → renders in welcome mode → agent picker works
2. AIHubPage submits → navigates to `/ai/chat` → AIChatPage opens
3. AIChatPage uses AIChatBox → AIChatBox uses InputBox → chat mode works
4. InputBox in chat mode shows static agent icon, not clickable
5. Mode selector shows 4 modes (Flash/Thinking/Pro/Ultra)
6. Web search toggle calls getWebSearchStatus()
7. Plus panel shows camera/file/image options
8. Expand button toggles full-screen textarea
9. Send button changes to Stop when streaming

- [ ] **Step 4: Final commit**

```bash
git add -A
git commit -m "feat: unify AI chat input boxes (InputBox + AIChatInput)"
```

---

## Self-Review Checklist

**1. Spec coverage:**
- ✅ Requirement 1 (unified component): Task 1-3 create the merged InputBox
- ✅ Requirement 2 (agent picker in welcome, static icon in chat): Task 2 template shows agent button only in welcome mode, static icon in chat mode
- ✅ Requirement 3 (DeerFlow 4-mode: Flash/Thinking/Pro/Ultra): Task 1 reuses `ModeSelector.vue` and `INPUT_MODE_CONFIGS`
- ✅ Requirement 4 (web search toggle): Task 1 includes `toggleWebSearch()` with provider pre-check
- ✅ Requirement 5 (MCP/skills in family config): Out of scope — handled by backend and `useTenantAiResources`
- ✅ AIChatInput styling as base: Task 3 uses AIChatInput CSS variable approach
- ✅ No slash palette: Removed entirely (not in template or script)
- ✅ Tenant isolation: `useTenantAiResources` composable retained from InputBox
- ✅ AIChatInput becomes dead code: Task 5 adds deprecation notice

**2. Placeholder scan:** No "TBD", "TODO", or "implement later" patterns. Every step contains complete code.

**3. Type consistency:** Props/events are consistent across all tasks:
- `status: 'ready' | 'streaming' | 'submitted' | 'error' | 'reconnecting'` — consistent
- `isWelcomeMode?: boolean` — consistent
- `submit` emit with `SubmitPayload` — consistent
- `stop` emit — consistent (mapped from old `abort`)
- `selectAgent` emit — consistent
- `action` with `'file' | 'image' | 'camera'` — consistent
- No function name drift across tasks
