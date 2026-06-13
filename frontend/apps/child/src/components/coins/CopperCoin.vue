<template>
  <svg
    :width="size"
    :height="size"
    viewBox="0 0 1028 1024"
    xmlns="http://www.w3.org/2000/svg"
    class="copper-coin"
    data-test="copper-coin"
  >
    <defs>
      <!-- Metallic copper gradient for outer ring -->
      <linearGradient id="copper-ring-grad" x1="0%" y1="0%" x2="100%" y2="100%">
        <stop offset="0%" class="stop-ring-hi" />
        <stop offset="50%" class="stop-ring-mid" />
        <stop offset="100%" class="stop-ring-lo" />
      </linearGradient>
      <!-- Metallic copper radial gradient for coin face -->
      <radialGradient id="copper-face-grad" cx="35%" cy="30%" r="70%">
        <stop offset="0%" class="stop-hi" />
        <stop offset="45%" class="stop-mid" />
        <stop offset="85%" class="stop-lo" />
        <stop offset="100%" class="stop-deep" />
      </radialGradient>
      <!-- Warm specular highlight -->
      <linearGradient id="copper-specular" x1="0%" y1="0%" x2="100%" y2="100%">
        <stop offset="0%" stop-color="#FFE8D0" stop-opacity="0" />
        <stop offset="30%" stop-color="#FFE8D0" stop-opacity="0.5" />
        <stop offset="50%" stop-color="#FFF0E0" stop-opacity="0.7" />
        <stop offset="70%" stop-color="#FFE8D0" stop-opacity="0.5" />
        <stop offset="100%" stop-color="#FFE8D0" stop-opacity="0" />
      </linearGradient>
      <clipPath id="copper-coin-clip">
        <circle cx="512" cy="512" r="400" />
      </clipPath>
    </defs>

    <!-- Outer ring (shadow depth — deep焦褐色) -->
    <path
      d="M512 934.65a424.84 424.84 0 1 0 0-849.68 424.84 424.84 0 0 0 0 849.68z"
      class="coin-ring-shadow"
    />

    <!-- Main coin face -->
    <path
      d="M512 878a368.2 368.2 0 1 1 0-736.39 368.2 368.2 0 0 1 0 736.39z"
      class="coin-face"
    />

    <!-- Outer ring highlight stroke -->
    <path
      d="M512 1019.62a509.81 509.81 0 1 0 0-1019.62 509.81 509.81 0 0 0 0 1019.62z m0-113.29a396.52 396.52 0 1 1 0-793.04 396.52 396.52 0 0 1 0 793.04z"
      class="coin-ring-stroke"
    />

    <!-- Subtle specular highlight -->
    <g v-if="!reducedMotion" clip-path="url(#copper-coin-clip)" data-test="copper-specular">
      <rect x="-200" y="0" width="100" height="1024" fill="url(#copper-specular)">
        <animate
          attributeName="x"
          values="-200;900;900"
          dur="6s"
          keyTimes="0;0.4;1"
          repeatCount="indefinite"
        />
      </rect>
    </g>

    <!-- Star shadow (depth — deep red-brown) -->
    <path
      d="M512 679.75l-166.48 87.52 31.78-185.34-134.65-131.3 186.14-27.08L512 254.9l83.27 168.63 186.08 27.08-134.65 131.3 31.72 185.34z"
      class="star-shadow"
    />

    <!-- Main star -->
    <path
      d="M512 651.42l-166.48 87.52 31.78-185.34-134.65-131.3 186.14-27.08L512 226.58l83.27 168.63 186.08 27.08-134.65 131.3 31.72 185.34z"
      class="star-main"
    />

    <!-- Star highlight -->
    <path
      d="M348.65 736.17l-5.32 2.83 27.64-161.16 4.14 4.08-26.45 154.25zM265.72 446.93l-25.26-24.64 186.14-27.08L512 226.58l83.27 168.63 186.08 27.08-25.26 24.64-160.87-23.39L512 254.9l-85.46 168.65-160.82 23.39z m382.92 130.85l27.64 161.16-5.32-2.83-26.45-154.19 4.14-4.08z"
      class="star-highlight"
    />

    <!-- Arc decoration -->
    <path
      d="M149.32 870.3l72.11-72.11a407.85 407.85 0 1 0 576.71-576.71l72.11-72.11a509.81 509.81 0 1 1-721.03 721.03z"
      class="coin-arc"
    />
  </svg>
</template>

<script setup lang="ts">
import { useReducedMotion } from '@/composables/useReducedMotion'

withDefaults(defineProps<{ size?: number }>(), { size: 32 })

const reducedMotion = useReducedMotion()
</script>

<style scoped>
/* Metallic copper palette — warm red-brown tones */
.copper-coin .stop-hi        { stop-color: var(--color-coin-copper-hi); }
.copper-coin .stop-ring-hi   { stop-color: var(--color-coin-copper-hi); }
.copper-coin .stop-ring-mid  { stop-color: var(--color-coin-copper-mid); }
.copper-coin .stop-ring-lo   { stop-color: var(--color-coin-copper-lo); }
.copper-coin .stop-mid       { stop-color: var(--color-coin-copper-mid); }
.copper-coin .stop-lo        { stop-color: var(--color-coin-copper-lo); }
.copper-coin .stop-deep      { stop-color: var(--color-coin-copper-deep); }

/* Ring shadow (edge depth — 极暗的焦褐色) */
.copper-coin .coin-ring-shadow {
  fill: var(--color-coin-copper-deep);
}

/* Main face with metallic gradient */
.copper-coin .coin-face {
  fill: url(#copper-face-grad);
}

/* Outer ring stroke (bright sand orange edge) */
.copper-coin .coin-ring-stroke {
  fill: var(--color-coin-copper-hi);
}

/* Star shadow (depth — deep red-brown) */
.copper-coin .star-shadow {
  fill: var(--color-coin-copper-deep);
}

/* Main star body (classic red copper) */
.copper-coin .star-main {
  fill: var(--color-coin-copper-mid);
}

/* Star highlight (bright sand orange accents) */
.copper-coin .star-highlight {
  fill: var(--color-coin-copper-hi);
}

/* Arc decoration */
.copper-coin .coin-arc {
  fill: var(--color-coin-copper-mid);
}
</style>