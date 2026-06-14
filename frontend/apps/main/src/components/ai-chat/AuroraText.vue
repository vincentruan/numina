<script setup lang="ts">
/**
 * DeerFlow AuroraText 组件
 *
 * 参考: frontend/src/components/ui/aurora-text.tsx
 *
 * 功能:
 * - 渐变文字动画
 * - 颜色可配置
 * - 动画速度可配置
 */
import { computed } from 'vue'

const props = withDefaults(
  defineProps<{
    colors?: string[]
    speed?: number
  }>(),
  {
    colors: () => ['#FF0080', '#7928CA', '#0070F3', '#38bdf8'],
    speed: 1,
  },
)

const gradientStyle = computed(() => ({
  backgroundImage: `linear-gradient(135deg, ${props.colors.join(', ')}, ${props.colors[0]})`,
  animationDuration: `${8 / props.speed}s`,
}))
</script>

<template>
  <span class="aurora-text-wrapper">
    <span class="sr-only"><slot /></span>
    <span class="aurora-text" :style="gradientStyle" aria-hidden="true">
      <slot />
    </span>
  </span>
</template>

<style scoped>
.aurora-text-wrapper {
  position: relative;
  display: inline-block;
}

.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border: 0;
}

.aurora-text {
  position: relative;
  background-size: 200% auto;
  background-clip: text;
  -webkit-background-clip: text;
  color: transparent;
  animation: aurora ease-in-out infinite alternate;
}

@keyframes aurora {
  0% {
    background-position: 0% 50%;
    transform: rotate(-5deg) scale(0.9);
  }
  25% {
    background-position: 50% 100%;
    transform: rotate(5deg) scale(1.1);
  }
  50% {
    background-position: 100% 50%;
    transform: rotate(-3deg) scale(0.95);
  }
  75% {
    background-position: 50% 0%;
    transform: rotate(3deg) scale(1.05);
  }
  100% {
    background-position: 0% 50%;
    transform: rotate(-5deg) scale(0.9);
  }
}
</style>