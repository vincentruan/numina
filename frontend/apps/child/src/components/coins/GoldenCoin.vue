<template>
  <svg :width="size" :height="size" viewBox="0 0 48 48" xmlns="http://www.w3.org/2000/svg" class="golden-coin">
    <defs>
      <radialGradient id="gold-face-grad" cx="35%" cy="32%" r="70%">
        <stop class="stop-glow" offset="0%" />
        <stop class="stop-hi" offset="35%" />
        <stop class="stop-mid" offset="70%" />
        <stop class="stop-deep" offset="100%" />
      </radialGradient>
      <radialGradient id="gold-rim-grad" cx="50%" cy="50%" r="50%">
        <stop class="stop-rim-clear" offset="85%" stop-opacity="0" />
        <stop class="stop-rim-bright" offset="92%" stop-opacity="0.9" />
        <stop class="stop-rim-deep" offset="100%" stop-opacity="1" />
      </radialGradient>
      <linearGradient id="gold-sheen-grad" x1="0%" y1="0%" x2="100%" y2="100%">
        <stop offset="0%" stop-color="#FFFFFF" stop-opacity="0" />
        <stop offset="45%" stop-color="#FFFFFF" stop-opacity="0.75" />
        <stop offset="55%" stop-color="#FFFFFF" stop-opacity="0.75" />
        <stop offset="100%" stop-color="#FFFFFF" stop-opacity="0" />
      </linearGradient>
      <clipPath id="gold-face-clip">
        <circle cx="24" cy="23" r="20" />
      </clipPath>
    </defs>

    <ellipse cx="24" cy="40" rx="18" ry="3" class="coin-shadow" opacity="0.18" />

    <circle cx="24" cy="23" r="22" fill="none" stroke="url(#gold-rim-grad)" stroke-width="2" />

    <circle cx="24" cy="23" r="20" fill="url(#gold-face-grad)" />

    <g class="rim-dots" opacity="0.55">
      <circle cx="24" cy="6" r="0.7" />
      <circle cx="36.7" cy="10.3" r="0.7" />
      <circle cx="41" cy="23" r="0.7" />
      <circle cx="36.7" cy="35.7" r="0.7" />
      <circle cx="24" cy="40" r="0.7" />
      <circle cx="11.3" cy="35.7" r="0.7" />
      <circle cx="7" cy="23" r="0.7" />
      <circle cx="11.3" cy="10.3" r="0.7" />
    </g>

    <circle cx="24" cy="23" r="16" fill="none" class="inner-ring" stroke-width="0.6" opacity="0.55" />

    <ellipse cx="17" cy="15" rx="6" ry="3" class="highlight-blob" opacity="0.55" />

    <g v-if="!reducedMotion" clip-path="url(#gold-face-clip)" data-test="gold-sheen">
      <rect x="-30" y="0" width="14" height="48" fill="url(#gold-sheen-grad)" transform="rotate(20 24 23)">
        <animate attributeName="x" values="-30;55;55" dur="3.2s" keyTimes="0;0.55;1" repeatCount="indefinite" />
      </rect>
    </g>

    <text x="24" y="29.5" text-anchor="middle" font-size="20" font-weight="900" class="gold-star" stroke-width="0.5" paint-order="stroke">★</text>

    <g v-if="!reducedMotion" class="sparkles" data-test="gold-sparkles">
      <circle cx="11" cy="13" r="1.1">
        <animate attributeName="opacity" values="0;1;0" dur="2.4s" begin="0s" repeatCount="indefinite" />
      </circle>
      <circle cx="38" cy="14" r="0.9">
        <animate attributeName="opacity" values="0;1;0" dur="2.4s" begin="0.8s" repeatCount="indefinite" />
      </circle>
      <circle cx="36" cy="34" r="0.8">
        <animate attributeName="opacity" values="0;1;0" dur="2.4s" begin="1.6s" repeatCount="indefinite" />
      </circle>
    </g>
  </svg>
</template>

<script setup lang="ts">
import { useReducedMotion } from '@/composables/useReducedMotion'

withDefaults(defineProps<{ size?: number }>(), { size: 24 })

const reducedMotion = useReducedMotion()
</script>

<style scoped>
.golden-coin .stop-glow { stop-color: var(--color-coin-gold-glow); }
.golden-coin .stop-hi   { stop-color: var(--color-coin-gold-hi); }
.golden-coin .stop-mid  { stop-color: var(--color-coin-gold-mid); }
.golden-coin .stop-deep { stop-color: var(--color-coin-gold-deep); }
.golden-coin .stop-rim-clear  { stop-color: var(--color-coin-gold-mid); }
.golden-coin .stop-rim-bright { stop-color: var(--color-coin-gold-hi); }
.golden-coin .stop-rim-deep   { stop-color: var(--color-coin-gold-deep); }
.golden-coin .coin-shadow { fill: var(--color-coin-gold-deep); }
.golden-coin .rim-dots circle { fill: var(--color-coin-gold-deep); }
.golden-coin .inner-ring { stroke: var(--color-coin-gold-deep); }
.golden-coin .highlight-blob { fill: var(--color-coin-gold-glow); }
.golden-coin .gold-star { fill: var(--color-coin-gold-glow); stroke: var(--color-coin-gold-deep); }
.golden-coin .sparkles circle { fill: var(--color-coin-gold-glow); }
</style>
