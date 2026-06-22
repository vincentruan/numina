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

<style scoped>
.input-box {
  position: relative;
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 12px 16px;
  background: var(--card-bg);
  border-radius: 16px;
  transition: all 0.2s ease;
}

/* 欢迎态: 居中布局 */
.input-box.welcome-mode {
  align-items: center;
  justify-content: center;
  min-height: 200px;
  margin: 0 auto;
  max-width: 90%;
}

/* 聊天态: 底部吸附 */
.input-box.chat-mode {
  position: sticky;
  bottom: 0;
  border-radius: 0;
  padding-bottom: calc(12px + env(safe-area-inset-bottom));
}

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

.input-row {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.input-textarea {
  flex: 1;
  min-height: 36px;
  max-height: 120px;
  padding: 8px 12px;
  background: var(--bg-primary);
  border: 1px solid var(--border-color);
  border-radius: 12px;
  font-size: 16px;
  color: var(--text-primary);
  resize: none;
  outline: none;
  transition: border-color 0.2s;
}

.input-textarea:focus {
  border-color: var(--van-primary-color);
}

.control-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 6px 10px;
  min-height: 44px; /* Touch target - DeerFlow pattern */
  background: var(--bg-primary);
  border: 1px solid var(--border-color);
  border-radius: 8px;
  font-size: 12px;
  color: var(--text-secondary);
  cursor: pointer;
}

.control-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.model-btn {
  min-width: 80px;
  min-height: 44px; /* Touch target - DeerFlow pattern */
}

.model-name {
  font-weight: 500;
}

.submit-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 36px;
  height: 36px;
  min-height: 44px; /* Touch target - DeerFlow pattern */
  min-width: 44px;
  border-radius: 50%;
  background: var(--van-primary-color);
  color: white;
  cursor: pointer;
  transition: all 0.2s;
}

/* 停止按钮: 红色方块 (DeerFlow pattern) */
.submit-btn.stop {
  background: #ef4444;
}

.submit-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.chat-bg-layer {
  position: absolute;
  left: 0;
  right: 0;
  bottom: -16px;
  height: 16px;
  background: var(--bg-primary);
  z-index: -1;
}

.animate-spin {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

/* 375px 响应式 */
@media (max-width: 375px) {
  .input-box {
    padding: 8px 12px;
    padding-bottom: calc(8px + env(safe-area-inset-bottom));
  }

  .input-box.welcome-mode {
    min-height: 160px;
    max-width: 95%;
  }

  .input-textarea {
    font-size: 14px;
    padding: 6px 10px;
  }

  .control-btn {
    padding: 4px 8px;
    font-size: 11px;
  }

  .model-btn {
    min-width: 60px;
  }

  .submit-btn {
    width: 32px;
    height: 32px;
  }

  .hero-title {
    font-size: 18px;
  }

  .hero-subtitle {
    font-size: 12px;
  }
}
</style>