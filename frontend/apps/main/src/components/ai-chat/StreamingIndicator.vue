<script setup lang="ts">
/**
 * StreamingIndicator — 弹跳三点动画指示器
 *
 * 块级放置：作为独立 <div> 渲染在 markdown 内容下方（不注入 markdown HTML）
 * 配合 R5 自动滚动，始终可见在视口底部。
 */
import { useI18n } from 'vue-i18n'

defineProps<{
  visible: boolean
}>()

const { t } = useI18n()
</script>

<template>
  <div v-if="visible" class="streaming-indicator" :aria-label="t('aiChat.streaming')" role="status">
    <span class="stream-dot" />
    <span class="stream-dot" />
    <span class="stream-dot" />
  </div>
</template>

<style scoped>
.streaming-indicator {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 8px 0 4px;
  margin-left: 2px;
}

.stream-dot {
  width: 6px;
  height: 6px;
  background: var(--van-primary-color, #6366f1);
  border-radius: 50%;
  display: inline-block;
  animation: bounce 1.4s ease-in-out infinite both;
}

.stream-dot:nth-child(1) {
  animation-delay: 0s;
}

.stream-dot:nth-child(2) {
  animation-delay: 0.2s;
}

.stream-dot:nth-child(3) {
  animation-delay: 0.4s;
}

@keyframes bounce {
  0%, 80%, 100% {
    transform: scale(0.6);
    opacity: 0.5;
  }
  40% {
    transform: scale(1);
    opacity: 1;
  }
}

@media (prefers-reduced-motion: reduce) {
  .stream-dot {
    animation: none;
    opacity: 0.7;
  }
}
</style>
