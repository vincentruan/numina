<script setup lang="ts">
import { ref, watch, onMounted, onUnmounted, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { getTokenUsage } from '@/api/ai-chat'
import type { UsageMetadata } from '@/types/ai-chat/message-group'

const props = defineProps<{
  threadId: string | null
  // When true, signals to the component to refresh the data (e.g. after a stream ends)
  refreshTrigger?: number
  /** 'popover' for header usage, 'inline' for per-message display */
  mode?: 'popover' | 'inline'
  /** Per-message usage data from SSE values events (primary source for inline mode) */
  usageMetadata?: UsageMetadata | null
  /** Whether streaming is in progress (enables polling fallback) */
  isStreaming?: boolean
}>()

const { t } = useI18n()

const usage = ref({
  prompt_tokens: 0,
  completion_tokens: 0,
  total_tokens: 0
})

const loading = ref(false)
const showPopover = ref(false)
let debounceTimer: ReturnType<typeof setTimeout> | null = null
let pollTimer: ReturnType<typeof setInterval> | null = null

/** Effective usage: prefer per-message usageMetadata, fall back to polled thread totals */
const effectiveUsage = computed(() => {
  if (props.mode === 'inline' && props.usageMetadata) {
    return {
      prompt_tokens: props.usageMetadata.inputTokens,
      completion_tokens: props.usageMetadata.outputTokens,
      total_tokens: props.usageMetadata.inputTokens + props.usageMetadata.outputTokens,
    }
  }
  return usage.value
})

const hasUsage = computed(() => effectiveUsage.value.total_tokens > 0)

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
// stream ends — otherwise requests fire for the whole stream after data is in.
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

onMounted(debouncedFetch)
onUnmounted(() => {
  if (debounceTimer) clearTimeout(debounceTimer)
  if (pollTimer !== null) clearInterval(pollTimer)
})

function formatTokenCount(n: number): string {
  if (n >= 1000) return (n / 1000).toFixed(1).replace(/\.0$/, '') + 'K'
  return n.toLocaleString()
}
</script>

<template>
  <!-- Popover mode (existing header behavior) -->
  <van-popover v-if="mode !== 'inline'" v-model:show="showPopover" placement="bottom-end">
    <div class="token-usage-popover">
      <div class="token-usage-row">
        <span>{{ t('aiChat.promptTokens', 'Prompt:') }}</span>
        <strong>{{ usage.prompt_tokens.toLocaleString() }}</strong>
      </div>
      <div class="token-usage-row">
        <span>{{ t('aiChat.completionTokens', 'Completion:') }}</span>
        <strong>{{ usage.completion_tokens.toLocaleString() }}</strong>
      </div>
      <div class="token-usage-row token-usage-total">
        <span>{{ t('aiChat.totalTokens', 'Total:') }}</span>
        <strong>{{ usage.total_tokens.toLocaleString() }}</strong>
      </div>
    </div>
    <template #reference>
      <button
        v-show="usage.total_tokens > 0"
        class="header-btn token-usage-btn"
        :class="{ 'has-tokens': usage.total_tokens > 0 }"
        :title="t('aiChat.tokenUsage', 'Token Usage')"
      >
        <van-loading v-if="loading" type="spinner" size="14" />
        <template v-else>
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <polyline points="22 12 18 12 15 21 9 3 6 12 2 12"></polyline>
          </svg>
          <span class="token-count">{{ usage.total_tokens > 999 ? (usage.total_tokens/1000).toFixed(1) + 'k' : usage.total_tokens }}</span>
        </template>
      </button>
    </template>
  </van-popover>

  <!-- Inline mode (per-message display) -->
  <span v-else-if="hasUsage" class="token-usage-inline">
    <svg class="token-icon" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
      <polyline points="22 12 18 12 15 21 9 3 6 12 2 12"></polyline>
    </svg>
    <span class="token-label">{{ t('aiChat.usageToken', 'Token') }}</span>
    <span class="token-sep">·</span>
    <span class="token-item">
      <span class="token-item-label">{{ t('aiChat.tokensInput') }}</span>
      <strong>{{ formatTokenCount(effectiveUsage.prompt_tokens) }}</strong>
    </span>
    <span class="token-sep">·</span>
    <span class="token-item">
      <span class="token-item-label">{{ t('aiChat.tokensOutput') }}</span>
      <strong>{{ formatTokenCount(effectiveUsage.completion_tokens) }}</strong>
    </span>
    <span class="token-sep">·</span>
    <span class="token-item token-item-total">
      <span class="token-item-label">{{ t('aiChat.tokensTotal') }}</span>
      <strong>{{ formatTokenCount(effectiveUsage.total_tokens) }}</strong>
    </span>
  </span>
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

.token-usage-popover {
  padding: 12px;
  min-width: 150px;
  font-size: 13px;
}

.token-usage-row {
  display: flex;
  justify-content: space-between;
  margin-bottom: 6px;
  color: var(--van-text-color-2);
}

.token-usage-row:last-child {
  margin-bottom: 0;
}

.token-usage-total {
  margin-top: 8px;
  padding-top: 8px;
  border-top: 1px dashed var(--van-border-color);
  color: var(--van-text-color);
}

/* Inline mode */
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
</style>
