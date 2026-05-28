<template>
  <svg :width="size" :height="size" viewBox="0 0 48 48" xmlns="http://www.w3.org/2000/svg" class="silver-coin">
    <defs>
      <radialGradient id="silver-grad" cx="35%" cy="32%" r="70%">
        <stop class="stop-hi" offset="0%" />
        <stop class="stop-mid" offset="50%" />
        <stop class="stop-lo" offset="100%" />
      </radialGradient>
    </defs>
    <ellipse cx="24" cy="40" rx="17" ry="2.5" class="coin-shadow" opacity="0.15" />
    <circle cx="24" cy="23" r="20" fill="url(#silver-grad)" />
    <circle cx="24" cy="23" r="20" fill="none" class="coin-edge" stroke-width="1" opacity="0.7" />
    <path
      d="M 12 16 A 16 16 0 0 1 32 12"
      class="silver-arc"
      stroke-width="1.6"
      fill="none"
      :opacity="reducedMotion ? 0.55 : undefined"
      stroke-linecap="round"
      data-test="silver-arc"
    >
      <animate
        v-if="!reducedMotion"
        attributeName="opacity"
        values="0.4;0.7;0.4"
        dur="5s"
        repeatCount="indefinite"
        data-test="silver-arc-animate"
      />
    </path>
    <text x="24" y="29.5" text-anchor="middle" font-size="20" font-weight="900" fill="#FFFFFF" opacity="0.92">★</text>
  </svg>
</template>

<script setup lang="ts">
import { useReducedMotion } from '@/composables/useReducedMotion'

withDefaults(defineProps<{ size?: number }>(), { size: 24 })

const reducedMotion = useReducedMotion()
</script>

<style scoped>
.silver-coin .stop-hi  { stop-color: var(--color-coin-silver-hi); }
.silver-coin .stop-mid { stop-color: var(--color-coin-silver-mid); }
.silver-coin .stop-lo  { stop-color: var(--color-coin-silver-lo); }
.silver-coin .coin-shadow { fill: var(--color-coin-silver-lo); }
.silver-coin .coin-edge   { stroke: var(--color-coin-silver-hi); }
.silver-coin .silver-arc  { stroke: #FFFFFF; }
</style>
