<script setup lang="ts">
/**
 * ErrorMessage — 连接中断错误条（点击重试）
 *
 * 在 3 次 SSE 重试均失败后显示（U1 逻辑）。
 * 点击后触发 retry，重新发送当前问题。
 */
import { useI18n } from 'vue-i18n'

defineProps<{
  /** Error message to display */
  message?: string
  /** Whether to show the retry button */
  showRetry?: boolean
}>()

const emit = defineEmits<{
  retry: []
}>()

const { t } = useI18n()

function onRetry() {
  emit('retry')
}
</script>

<template>
  <div v-if="message" class="error-message-bar" role="alert">
    <svg class="error-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
      <circle cx="12" cy="12" r="10"/>
      <line x1="12" y1="8" x2="12" y2="12"/>
      <line x1="12" y1="16" x2="12.01" y2="16"/>
    </svg>
    <span class="error-text">{{ message }}</span>
    <button v-if="showRetry" class="error-retry-btn" type="button" @click="onRetry">
      <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
        <polyline points="1 4 1 10 7 10"/>
        <path d="M3.51 15a9 9 0 1 0 .49-3.5"/>
      </svg>
      <span>{{ t('aiChat.retry') }}</span>
    </button>
  </div>
</template>

<style scoped>
.error-message-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 16px;
  background: rgba(248, 113, 113, 0.12);
  border: 1px solid rgba(248, 113, 113, 0.3);
  border-radius: 8px;
  color: #f87171;
  font-size: 13px;
  margin: 8px 0;
}

.error-icon {
  flex-shrink: 0;
}

.error-text {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.error-retry-btn {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 4px 10px;
  font-size: 12px;
  background: rgba(248, 113, 113, 0.2);
  border: none;
  border-radius: 6px;
  color: inherit;
  cursor: pointer;
  flex-shrink: 0;
  transition: background 0.15s ease;
}

.error-retry-btn:hover {
  background: rgba(248, 113, 113, 0.3);
}

.error-retry-btn:active {
  transform: scale(0.96);
}
</style>
