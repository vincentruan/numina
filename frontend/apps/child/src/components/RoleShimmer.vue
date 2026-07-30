<template>
  <div v-if="variant === 'clay-pulse'" class="role-shimmer clay-pulse-root" :class="{ 'reduced-motion': reducedMotion }">
    <div class="shimmer-bar bar-pink" />
    <div class="shimmer-bar bar-ochre" />
    <div class="shimmer-bar bar-teal" />
  </div>
  <van-skeleton v-else :row="3" row-width="100% 80% 60%" animate />
</template>

<script setup lang="ts">
import { useReducedMotion } from '@/composables/useReducedMotion'

defineOptions({ name: 'RoleShimmer' })

withDefaults(defineProps<{
  variant?: 'skeleton' | 'clay-pulse'
}>(), {
  variant: 'skeleton',
})

const reducedMotion = useReducedMotion()
</script>

<style scoped>
.role-shimmer {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: var(--space-md);
}

.shimmer-bar {
  height: 16px;
  border-radius: var(--radius-md);
}

/* -- Clay brand-color bars -- */
.bar-pink  { background: var(--color-brand-pink); }
.bar-ochre { background: var(--color-brand-ochre); }
.bar-teal  { background: var(--color-brand-teal); }

/* -- Pulse animation (optimal motion) -- */
.clay-pulse-root:not(.reduced-motion) .shimmer-bar {
  animation: clay-pulse 1200ms ease-in-out infinite;
}

@keyframes clay-pulse {
  0%, 100% { transform: scale(0.98); }
  50%      { transform: scale(1.0); }
}

/* -- Reduced motion: gentle fade -- */
.clay-pulse-root.reduced-motion .shimmer-bar {
  animation: clay-fade 200ms ease-in-out infinite alternate;
}

@keyframes clay-fade {
  from { opacity: 0.6; }
  to   { opacity: 1.0; }
}
</style>
