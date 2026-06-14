<script setup lang="ts">
/**
 * DeerFlow FlipDisplay 组件
 *
 * 参考: frontend/src/components/workspace/flip-display.tsx
 *
 * 功能: 内容变化时的翻转动画，用于最后一个 tool call 高亮
 */
defineProps<{
  uniqueKey: string // 用于触发动画的唯一标识
}>()
</script>

<template>
  <div :key="uniqueKey" class="flip-display">
    <slot />
  </div>
</template>

<style scoped>
/* DeerFlow reference: flip-display.tsx motion.div transition */
.flip-display {
  animation: flip-in 0.25s cubic-bezier(0.4, 0, 0.2, 1);
}

@keyframes flip-in {
  0% {
    opacity: 0;
    transform: translateY(8px);
  }
  100% {
    opacity: 1;
    transform: translateY(2px);
  }
}
</style>