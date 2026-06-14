<script setup lang="ts">
/**
 * DeerFlow ShimmerText 组件
 *
 * 参考: frontend/src/components/ai-elements/shimmer.tsx
 *
 * 功能: 文字闪烁效果，用于 in_progress 状态的任务描述
 */
import { computed } from 'vue'

const props = defineProps<{
  text: string
  duration?: number // 动画周期（秒）
}>()

const shimmerStyle = computed(() => ({
  '--shimmer-duration': `${props.duration || 3}s`,
}))
</script>

<template>
  <span class="shimmer-text" :style="shimmerStyle">
    {{ text }}
  </span>
</template>

<style scoped>
.shimmer-text {
  position: relative;
  display: inline-block;
  font-weight: 500;
  color: var(--text-primary);
  background: linear-gradient(
    90deg,
    var(--text-primary) 0%,
    var(--van-primary-color) 50%,
    var(--text-primary) 100%
  );
  background-size: 200% 100%;
  background-clip: text;
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  animation: shimmer var(--shimmer-duration) ease-in-out infinite;
}

@keyframes shimmer {
  0% {
    background-position: -100% 0;
  }
  50% {
    background-position: 0% 0;
  }
  100% {
    background-position: 100% 0;
  }
}
</style>