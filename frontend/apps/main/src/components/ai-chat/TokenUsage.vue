<script setup lang="ts">
import { ref, watch, onMounted, onUnmounted } from 'vue'
import { useI18n } from 'vue-i18n'
import http from '@/api/index'

const props = defineProps<{
  threadId: string | null
  // When true, signals to the component to refresh the data (e.g. after a stream ends)
  refreshTrigger?: number
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

const fetchUsage = async () => {
  if (!props.threadId || props.threadId === 'new') {
    usage.value = { prompt_tokens: 0, completion_tokens: 0, total_tokens: 0 }
    return
  }
  
  try {
    loading.value = true
    const res = await http.get<{prompt_tokens: number, completion_tokens: number, total_tokens: number}>(`/threads/${encodeURIComponent(props.threadId)}/token-usage`)
    usage.value = res.data
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

watch(() => props.threadId, debouncedFetch)
watch(() => props.refreshTrigger, debouncedFetch)

onMounted(debouncedFetch)
onUnmounted(() => {
  if (debounceTimer) clearTimeout(debounceTimer)
})
</script>

<template>
  <van-popover v-model:show="showPopover" placement="bottom-end">
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
        class="header-btn token-usage-btn" 
        :class="{ 'has-tokens': usage.total_tokens > 0 }"
        :title="t('aiChat.tokenUsage', 'Token Usage')"
        v-show="usage.total_tokens > 0"
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
</style>
