<script setup lang="ts">
import { ref, watch, onMounted, onUnmounted, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { getTokenUsage } from '@/api/ai-chat'
import type { UsageMetadata, ChatMessage } from '@/types/ai-chat/message-group'
import {
  buildTokenDebugStep,
  formatTokenCount,
  type TokenDebugStep,
} from '@/utils/ai-chat/token-usage-steps'
import {
  useTokenUsagePrefs,
  type TokenUsageViewPreset,
} from '@/composables/ai-chat/useTokenUsagePrefs'

const props = defineProps<{
  threadId: string | null
  /** @deprecated Use realtimeUsage instead */
  refreshTrigger?: number
  /** 'popover' for header usage, 'inline' for per-message display */
  mode?: 'popover' | 'inline'
  /** Per-message usage data from SSE values events (primary source for inline mode) */
  usageMetadata?: UsageMetadata | null
  /** Whether streaming is in progress (enables polling fallback) */
  isStreaming?: boolean
  /**
   * The AI message this inline instance belongs to (inline debug mode only).
   * The message's own usageMetadata + tool_calls are used to build the
   * per-step debug card.
   */
  message?: ChatMessage
  /**
   * Realtime token usage from SSE values events (header mode only).
   * Computed by accumulateUsage(chat.messages) in AIChatBox.vue.
   * When available, popover mode uses this directly instead of calling
   * the backend /token-usage API (which has timing issues - checkpointer
   * write may not be complete when stream ends).
   */
  realtimeUsage?: { inputTokens: number; outputTokens: number; totalTokens: number } | null
}>()

const { t } = useI18n()
const { preset, preferences, setPreset } = useTokenUsagePrefs()

const usage = ref({
  prompt_tokens: 0,
  completion_tokens: 0,
  total_tokens: 0
})

const loading = ref(false)
const showPopover = ref(false)
let debounceTimer: ReturnType<typeof setTimeout> | null = null
let pollTimer: ReturnType<typeof setInterval> | null = null

/**
 * Effective usage for display.
 *
 * Priority (popover mode):
 * 1. realtimeUsage prop (from SSE values events, most realtime)
 * 2. usage.value (from backend API, may be stale due to checkpointer timing)
 *
 * For inline mode, usageMetadata prop is used (per-message data).
 */
const effectiveUsage = computed(() => {
  // Inline mode: use per-message usageMetadata
  if (props.mode === 'inline' && props.usageMetadata) {
    return {
      prompt_tokens: props.usageMetadata.inputTokens,
      completion_tokens: props.usageMetadata.outputTokens,
      total_tokens: props.usageMetadata.inputTokens + props.usageMetadata.outputTokens,
    }
  }
  // Popover mode: prefer realtimeUsage (from SSE) over API data
  if (props.mode !== 'inline' && props.realtimeUsage && props.realtimeUsage.totalTokens > 0) {
    return {
      prompt_tokens: props.realtimeUsage.inputTokens,
      completion_tokens: props.realtimeUsage.outputTokens,
      total_tokens: props.realtimeUsage.totalTokens,
    }
  }
  return usage.value
})

const hasUsage = computed(() => effectiveUsage.value.total_tokens > 0)

// Debug step for the current message (inline debug mode only).
// buildTokenDebugStep derives the per-step label + usage from the message's
// own usageMetadata and tool_calls.
const debugStep = computed<TokenDebugStep | null>(() => {
  if (props.mode !== 'inline') return null
  if (preferences.value.inlineMode !== 'step_debug') return null
  if (!props.message) return null
  return buildTokenDebugStep(props.message, t)
})

const shouldRenderInline = computed(() => {
  if (props.mode !== 'inline') return false
  if (preferences.value.inlineMode === 'off') return false
  // per_turn: show summary line when this message has usage
  if (preferences.value.inlineMode === 'per_turn') return hasUsage.value
  // step_debug: show debug card when this message has a debug step
  if (preferences.value.inlineMode === 'step_debug') return debugStep.value !== null
  return false
})

const fetchUsage = async () => {
  if (!props.threadId || props.threadId === 'new') {
    usage.value = { prompt_tokens: 0, completion_tokens: 0, total_tokens: 0 }
    return
  }

  try {
    loading.value = true
    usage.value = await getTokenUsage(props.threadId)
  } catch (err) {
    console.error('Failed to fetch token usage:', err)
  } finally {
    loading.value = false
  }
}

const debouncedFetch = () => {
  if (debounceTimer) clearTimeout(debounceTimer)
  debounceTimer = setTimeout(fetchUsage, 500)
}

// Polling during streaming (fallback when per-message data not yet available).
// Watch BOTH isStreaming and usageMetadata (#26): polling must stop the moment
// per-message data arrives via props (from a values event), not only when the
// stream ends - otherwise requests fire for the whole stream after data is in.
watch(
  () => [props.isStreaming, props.usageMetadata] as const,
  ([streaming, usageMetadata]) => {
    if (props.mode !== 'inline') return
    const shouldPoll = streaming && !usageMetadata
    if (shouldPoll) {
      if (pollTimer === null) {
        pollTimer = setInterval(fetchUsage, 1500)
      }
    } else if (pollTimer !== null) {
      clearInterval(pollTimer)
      pollTimer = null
    }
  },
)

watch(() => props.threadId, debouncedFetch)
watch(() => props.refreshTrigger, debouncedFetch)

// Popover mode (header): re-fetch when a stream ends so the button reflects the
// new totals. The `end` SSE frame from the worker carries only `{"status": ...}`
// (no `usage`), so `refreshTrigger` (derived from `chat.tokenUsage`) never updates
// and without this watch the header button stays at 0 after the first reply on a
// new thread. Inline mode already polls during streaming and prefers
// `usageMetadata`, so it is unaffected.
watch(
  () => props.isStreaming,
  (streaming, prev) => {
    if (props.mode === 'inline') return
    if (prev && !streaming) {
      debouncedFetch()
    }
  },
)

onMounted(debouncedFetch)
onUnmounted(() => {
  if (debounceTimer) clearTimeout(debounceTimer)
  if (pollTimer !== null) clearInterval(pollTimer)
})

function formatInlineTokenCount(n: number): string {
  if (n >= 1000) return (n / 1000).toFixed(1).replace(/\.0$/, '') + 'K'
  return n.toLocaleString()
}

const presetOptions: { value: TokenUsageViewPreset; labelKey: string; descKey: string }[] = [
  { value: 'off', labelKey: 'aiChat.tokenUsagePresetOff', descKey: 'aiChat.tokenUsagePresetOffDesc' },
  { value: 'summary', labelKey: 'aiChat.tokenUsagePresetSummary', descKey: 'aiChat.tokenUsagePresetSummaryDesc' },
  { value: 'per_turn', labelKey: 'aiChat.tokenUsagePresetPerTurn', descKey: 'aiChat.tokenUsagePresetPerTurnDesc' },
  { value: 'debug', labelKey: 'aiChat.tokenUsagePresetDebug', descKey: 'aiChat.tokenUsagePresetDebugDesc' },
]

function onSelectPreset(value: TokenUsageViewPreset) {
  setPreset(value)
  showPopover.value = false
}
</script>

<template>
  <!-- Popover mode (header dropdown - DeerFlow TokenUsageIndicator pattern) -->
  <van-popover
    v-if="mode !== 'inline'"
    v-model:show="showPopover"
    placement="bottom-end"
    :offset="[0, 8]"
  >
    <div class="token-usage-dropdown">
      <!-- Usage summary -->
      <div class="tud-section tud-summary">
        <div class="tud-header">{{ t('aiChat.tokenUsageTitle') }}</div>
        <template v-if="usage.total_tokens > 0">
          <div class="tud-row">
            <span>{{ t('aiChat.tokensInput') }}</span>
            <span class="tud-mono">{{ formatTokenCount(usage.prompt_tokens) }}</span>
          </div>
          <div class="tud-row">
            <span>{{ t('aiChat.tokensOutput') }}</span>
            <span class="tud-mono">{{ formatTokenCount(usage.completion_tokens) }}</span>
          </div>
          <div class="tud-row tud-total-row">
            <span>{{ t('aiChat.tokensTotal') }}</span>
            <span class="tud-mono tud-total-num">{{ formatTokenCount(usage.total_tokens) }}</span>
          </div>
        </template>
        <div v-else class="tud-unavailable">{{ t('aiChat.tokenUsageUnavailable') }}</div>
      </div>

      <!-- View preset selector -->
      <div class="tud-section tud-presets">
        <div class="tud-header">{{ t('aiChat.tokenUsageView') }}</div>
        <div
          v-for="opt in presetOptions"
          :key="opt.value"
          class="tud-preset"
          :class="{ active: preset === opt.value }"
          role="radio"
          :aria-checked="preset === opt.value"
          @click="onSelectPreset(opt.value)"
        >
          <div class="tud-preset-radio">
            <span v-if="preset === opt.value" class="tud-radio-dot"></span>
          </div>
          <div class="tud-preset-text">
            <div class="tud-preset-label">{{ t(opt.labelKey) }}</div>
            <div class="tud-preset-desc">{{ t(opt.descKey) }}</div>
          </div>
        </div>
      </div>

      <div class="tud-note">{{ t('aiChat.tokenUsageNote') }}</div>
    </div>
    <template #reference>
      <button
        v-show="preferences.headerTotal || usage.total_tokens > 0"
        class="header-btn token-usage-btn"
        :class="{ 'has-tokens': usage.total_tokens > 0, 'is-off': !preferences.headerTotal }"
        :title="t('aiChat.tokenUsage')"
      >
        <van-loading v-if="loading" type="spinner" size="14" />
        <template v-else>
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <polyline points="22 12 18 12 15 21 9 3 6 12 2 12"></polyline>
          </svg>
          <span v-if="usage.total_tokens > 0" class="token-count">{{ usage.total_tokens > 999 ? (usage.total_tokens/1000).toFixed(1) + 'k' : usage.total_tokens }}</span>
          <svg class="token-chevron" width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
            <polyline points="6 9 12 15 18 9"/>
          </svg>
        </template>
      </button>
    </template>
  </van-popover>

  <!-- Inline mode: per-turn summary (DeerFlow MessageTokenUsageList pattern) -->
  <span v-else-if="shouldRenderInline && preferences.inlineMode === 'per_turn'" class="token-usage-inline">
    <svg class="token-icon" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
      <polyline points="22 12 18 12 15 21 9 3 6 12 2 12"></polyline>
    </svg>
    <span class="token-label">{{ t('aiChat.usageToken') }}</span>
    <span class="token-sep">·</span>
    <span class="token-item">
      <span class="token-item-label">{{ t('aiChat.tokensInput') }}</span>
      <strong>{{ formatInlineTokenCount(effectiveUsage.prompt_tokens) }}</strong>
    </span>
    <span class="token-sep">·</span>
    <span class="token-item">
      <span class="token-item-label">{{ t('aiChat.tokensOutput') }}</span>
      <strong>{{ formatInlineTokenCount(effectiveUsage.completion_tokens) }}</strong>
    </span>
    <span class="token-sep">·</span>
    <span class="token-item token-item-total">
      <span class="token-item-label">{{ t('aiChat.tokensTotal') }}</span>
      <strong>{{ formatInlineTokenCount(effectiveUsage.total_tokens) }}</strong>
    </span>
  </span>

  <!-- Inline mode: debug step card (DeerFlow MessageTokenUsageDebugList pattern) -->
  <div v-else-if="shouldRenderInline && preferences.inlineMode === 'step_debug' && debugStep" class="token-debug-card">
    <div class="tdc-main">
      <div class="tdc-label-row">
        <svg class="tdc-coin" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
          <polyline points="22 12 18 12 15 21 9 3 6 12 2 12"></polyline>
        </svg>
        <span class="tdc-label">{{ debugStep.label }}</span>
      </div>
      <div v-if="debugStep.secondaryLabels.length > 0" class="tdc-badges">
        <span v-for="(label, i) in debugStep.secondaryLabels" :key="`${debugStep.id}-${i}-${label}`" class="tdc-badge">{{ label }}</span>
      </div>
      <div v-if="debugStep.sharedAttribution" class="tdc-shared">{{ t('aiChat.tokenUsageSharedAttribution') }}</div>
      <div class="tdc-usage-detail">
        <template v-if="debugStep.usage">
          {{ t('aiChat.tokensInput') }}: {{ formatTokenCount(debugStep.usage.inputTokens) }}
          · {{ t('aiChat.tokensOutput') }}: {{ formatTokenCount(debugStep.usage.outputTokens) }}
        </template>
        <template v-else>{{ t('aiChat.tokenUsageUnavailableShort') }}</template>
      </div>
    </div>
    <span class="tdc-total-badge">
      {{ debugStep.usage ? `${formatTokenCount(debugStep.usage.totalTokens)} ${t('aiChat.tokenUsageLabel')}` : t('aiChat.tokenUsageUnavailableShort') }}
    </span>
  </div>
</template>

<style scoped>
.token-usage-btn {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  padding: 0 8px;
  border-radius: 12px;
  background: var(--van-background-2);
  color: var(--van-text-color-2);
  border: 1px solid var(--van-border-color);
  height: 24px;
  transition: all 0.2s ease;
  margin-right: 4px; /* Space between token usage and + button */
}

.token-usage-btn.has-tokens {
  color: var(--van-primary-color);
  background: rgba(var(--van-primary-color-rgb), 0.1);
  border-color: rgba(var(--van-primary-color-rgb), 0.3);
}

/* When preset is 'off' (headerTotal=false), show a muted icon-only button so
 * the user can still open the dropdown to re-enable token display. */
.token-usage-btn.is-off {
  padding: 0 6px;
}

.token-usage-btn.is-off .token-chevron {
  display: none;
}

.token-chevron {
  opacity: 0.6;
  flex-shrink: 0;
}

/* Dropdown panel (DeerFlow DropdownMenuContent pattern) */
.token-usage-dropdown {
  padding: 4px 0;
  min-width: 260px;
  max-width: 320px;
  font-size: 13px;
}

.tud-section {
  padding: 8px 14px;
}

.tud-header {
  font-size: 12px;
  font-weight: 600;
  color: var(--van-text-color-2);
  text-transform: uppercase;
  letter-spacing: 0.04em;
  margin-bottom: 8px;
}

.tud-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 4px;
  color: var(--van-text-color-2);
}

.tud-mono {
  font-family: var(--van-font-mono, monospace);
  font-variant-numeric: tabular-nums;
}

.tud-total-row {
  margin-top: 6px;
  padding-top: 6px;
  border-top: 1px dashed var(--van-border-color);
  color: var(--van-text-color);
  font-weight: 500;
}

.tud-total-num {
  font-weight: 600;
}

.tud-unavailable {
  color: var(--van-text-color-3);
  font-size: 12px;
  line-height: 1.5;
}

.tud-presets {
  border-top: 1px solid var(--van-border-color);
}

.tud-preset {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 6px 4px;
  border-radius: 8px;
  cursor: pointer;
  transition: background 0.15s;
}

.tud-preset:hover {
  background: var(--van-background-2);
}

.tud-preset.active {
  background: rgba(var(--van-primary-color-rgb), 0.08);
}

.tud-preset-radio {
  width: 16px;
  height: 16px;
  border: 2px solid var(--van-border-color);
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  margin-top: 1px;
  transition: border-color 0.15s;
}

.tud-preset.active .tud-preset-radio {
  border-color: var(--van-primary-color);
}

.tud-radio-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--van-primary-color);
}

.tud-preset-text {
  min-width: 0;
  flex: 1;
}

.tud-preset-label {
  font-size: 13px;
  font-weight: 500;
  color: var(--van-text-color);
}

.tud-preset-desc {
  font-size: 11px;
  color: var(--van-text-color-3);
  line-height: 1.4;
  margin-top: 1px;
}

.tud-note {
  padding: 8px 14px 10px;
  font-size: 11px;
  color: var(--van-text-color-3);
  line-height: 1.5;
  border-top: 1px solid var(--van-border-color);
}

/* Inline per-turn mode */
.token-usage-inline {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  color: var(--text-secondary, #999);
  padding: 4px 0;
  flex-wrap: wrap;
}

.token-icon {
  flex-shrink: 0;
  opacity: 0.6;
}

.token-label {
  font-weight: 500;
  color: var(--text-secondary, #999);
}

.token-sep {
  opacity: 0.4;
}

.token-item {
  display: inline-flex;
  align-items: center;
  gap: 2px;
}

.token-item-label {
  color: var(--text-secondary, #999);
}

.token-item strong {
  color: var(--text-primary, #fff);
  font-weight: 600;
  font-variant-numeric: tabular-nums;
}

.token-item-total strong {
  color: var(--van-primary-color, #6366f1);
}

/* Inline debug mode (DeerFlow MessageTokenUsageDebugList card pattern) */
.token-debug-card {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 10px;
  margin-top: 6px;
  padding: 8px 10px;
  border: 1px solid var(--van-border-color);
  border-radius: 8px;
  background: var(--van-background-2);
}

.tdc-main {
  min-width: 0;
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.tdc-label-row {
  display: flex;
  align-items: center;
  gap: 6px;
}

.tdc-coin {
  flex-shrink: 0;
  opacity: 0.6;
  color: var(--van-text-color-2);
}

.tdc-label {
  font-size: 12px;
  font-weight: 500;
  color: var(--van-text-color);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.tdc-badges {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}

.tdc-badge {
  font-size: 10px;
  padding: 1px 6px;
  border-radius: 4px;
  background: var(--van-background-3, rgba(0,0,0,0.06));
  color: var(--van-text-color-2);
  font-weight: 400;
}

.tdc-shared {
  font-size: 11px;
  color: var(--van-text-color-3);
}

.tdc-usage-detail {
  font-size: 11px;
  color: var(--van-text-color-2);
  font-variant-numeric: tabular-nums;
}

.tdc-total-badge {
  flex-shrink: 0;
  font-size: 11px;
  font-weight: 600;
  font-family: var(--van-font-mono, monospace);
  font-variant-numeric: tabular-nums;
  padding: 2px 8px;
  border: 1px solid var(--van-border-color);
  border-radius: 6px;
  color: var(--van-text-color);
  white-space: nowrap;
}
</style>
