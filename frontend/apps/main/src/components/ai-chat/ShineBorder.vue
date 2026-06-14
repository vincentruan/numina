<script setup lang="ts">
/**
 * DeerFlow ShineBorder 组件
 *
 * 参考: frontend/src/components/ui/shine-border.tsx
 *
 * 功能: 发光边框动画，用于 in_progress 状态的卡片
 */
import { computed } from 'vue'

const props = defineProps<{
  borderWidth?: number
  colors?: string[]
}>()

const borderStyle = computed(() => ({
  '--shine-border-width': `${props.borderWidth || 1.5}px`,
  '--shine-color-1': props.colors?.[0] || '#A07CFE',
  '--shine-color-2': props.colors?.[1] || '#FE8FB5',
  '--shine-color-3': props.colors?.[2] || '#FFBE7B',
}))
</script>

<template>
  <div class="shine-border" :style="borderStyle" />
</template>

<style scoped>
.shine-border {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  border-radius: inherit;
  pointer-events: none;
  overflow: hidden;
  z-index: -1;
}

.shine-border::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  border: var(--shine-border-width) solid transparent;
  border-radius: inherit;
  background: linear-gradient(
    90deg,
    var(--shine-color-1),
    var(--shine-color-2),
    var(--shine-color-3),
    var(--shine-color-1)
  );
  background-size: 300% 100%;
  animation: shine-border-spin 3s linear infinite;
  mask: linear-gradient(#fff 0 0) content-box, linear-gradient(#fff 0 0);
  -webkit-mask: linear-gradient(#fff 0 0) content-box, linear-gradient(#fff 0 0);
  -webkit-mask-composite: xor;
  mask-composite: exclude;
  padding: var(--shine-border-width);
}

@keyframes shine-border-spin {
  0% {
    background-position: 0% 0;
  }
  100% {
    background-position: 300% 0;
  }
}
</style>