<template>
  <Teleport to="body">
    <div v-if="active && tier >= 30" class="streak-edge-glow" aria-hidden="true" />
    <FlyToTarget
      v-if="active && tier >= 7 && origin && target"
      :active="active"
      :origin="origin"
      :target="target"
      :particle-count="4"
      particle-type="sparkle"
      :duration="500"
      :stagger-ms="80"
      :control-point-offset="160"
      :rotation-deg="360"
      :scale-curve="[0.2, 0.6, 0.3]"
      :css-filter="tier >= 14 ? 'drop-shadow(0 0 4px var(--color-brand-ochre)) hue-rotate(15deg)' : undefined"
    />
  </Teleport>
</template>

<script setup lang="ts">
import FlyToTarget from './FlyToTarget.vue'

defineProps<{
  active: boolean
  tier: number
  origin: HTMLElement | { x: number; y: number } | null
  target: HTMLElement | { x: number; y: number } | null
}>()
</script>

<style scoped>
.streak-edge-glow {
  position: fixed;
  inset: 0;
  pointer-events: none;
  z-index: 1;
  box-shadow: inset 0 0 40px var(--color-brand-ochre);
  animation: streak-edge-pulse 1500ms ease-out forwards;
  opacity: 0;
}

@keyframes streak-edge-pulse {
  0% { opacity: 0; }
  30% { opacity: 0.8; }
  100% { opacity: 0; }
}
</style>
