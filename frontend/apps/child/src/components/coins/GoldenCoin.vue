<template>
  <svg
    :width="size"
    :height="size"
    viewBox="0 0 1028 1024"
    xmlns="http://www.w3.org/2000/svg"
    class="golden-coin"
    data-test="golden-coin"
  >
    <defs>
      <!-- Metallic gold gradient for outer ring -->
      <linearGradient id="gold-ring-grad" x1="0%" y1="0%" x2="100%" y2="100%">
        <stop offset="0%" class="stop-ring-hi" />
        <stop offset="50%" class="stop-ring-mid" />
        <stop offset="100%" class="stop-ring-lo" />
      </linearGradient>
      <!-- Metallic gold radial gradient for coin face -->
      <radialGradient id="gold-face-grad" cx="35%" cy="30%" r="70%">
        <stop offset="0%" class="stop-glow" />
        <stop offset="40%" class="stop-hi" />
        <stop offset="70%" class="stop-mid" />
        <stop offset="100%" class="stop-deep" />
      </radialGradient>
      <!-- Specular highlight -->
      <linearGradient id="gold-specular" x1="0%" y1="0%" x2="100%" y2="100%">
        <stop offset="0%" stop-color="#FFFFFF" stop-opacity="0" />
        <stop offset="30%" stop-color="#FFFFFF" stop-opacity="0.6" />
        <stop offset="50%" stop-color="#FFFFFF" stop-opacity="0.8" />
        <stop offset="70%" stop-color="#FFFFFF" stop-opacity="0.6" />
        <stop offset="100%" stop-color="#FFFFFF" stop-opacity="0" />
      </linearGradient>
      <clipPath id="gold-coin-clip">
        <circle cx="512" cy="512" r="400" />
      </clipPath>
    </defs>

    <!-- Outer ring (shadow depth) -->
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

    <!-- Specular highlight sweep -->
    <g v-if="!reducedMotion" clip-path="url(#gold-coin-clip)" data-test="gold-specular">
      <rect x="-200" y="0" width="100" height="1024" fill="url(#gold-specular)">
        <animate
          attributeName="x"
          values="-200;900;900"
          dur="4s"
          keyTimes="0;0.6;1"
          repeatCount="indefinite"
        />
      </rect>
    </g>

    <!-- Star shadow (depth) -->
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

    <!-- Sparkle animations -->
    <g v-if="!reducedMotion" class="sparkles" data-test="gold-sparkles">
      <circle cx="180" cy="260" r="12">
        <animate attributeName="opacity" values="0;1;0" dur="2.5s" begin="0s" repeatCount="indefinite" />
        <animate attributeName="r" values="8;14;8" dur="2.5s" begin="0s" repeatCount="indefinite" />
      </circle>
      <circle cx="840" cy="280" r="10">
        <animate attributeName="opacity" values="0;1;0" dur="2.5s" begin="0.8s" repeatCount="indefinite" />
        <animate attributeName="r" values="6;12;6" dur="2.5s" begin="0.8s" repeatCount="indefinite" />
      </circle>
      <circle cx="720" cy="720" r="9">
        <animate attributeName="opacity" values="0;1;0" dur="2.5s" begin="1.6s" repeatCount="indefinite" />
      </circle>
    </g>
  </svg>
</template>

<script setup lang="ts">
import { useReducedMotion } from '@/composables/useReducedMotion'

withDefaults(defineProps<{ size?: number }>(), { size: 32 })

const reducedMotion = useReducedMotion()
</script>

<style scoped>
/* Metallic gold palette */
.golden-coin .stop-glow      { stop-color: var(--color-coin-gold-glow); }
.golden-coin .stop-hi        { stop-color: var(--color-coin-gold-hi); }
.golden-coin .stop-ring-hi   { stop-color: var(--color-coin-gold-hi); }
.golden-coin .stop-ring-mid  { stop-color: var(--color-coin-gold-mid); }
.golden-coin .stop-ring-lo   { stop-color: var(--color-coin-gold-lo); }
.golden-coin .stop-mid       { stop-color: var(--color-coin-gold-mid); }
.golden-coin .stop-deep      { stop-color: var(--color-coin-gold-deep); }

/* Ring shadow (edge depth) */
.golden-coin .coin-ring-shadow {
  fill: var(--color-coin-gold-deep);
}

/* Main face with metallic gradient */
.golden-coin .coin-face {
  fill: url(#gold-face-grad);
}

/* Outer ring stroke (bright edge) */
.golden-coin .coin-ring-stroke {
  fill: var(--color-coin-gold-hi);
}

/* Star shadow (depth) */
.golden-coin .star-shadow {
  fill: var(--color-coin-gold-deep);
}

/* Main star body */
.golden-coin .star-main {
  fill: var(--color-coin-gold-mid);
}

/* Star highlight (bright accents) */
.golden-coin .star-highlight {
  fill: var(--color-coin-gold-glow);
}

/* Arc decoration */
.golden-coin .coin-arc {
  fill: var(--color-coin-gold-mid);
}

/* Sparkles */
.golden-coin .sparkles circle {
  fill: var(--color-coin-gold-glow);
}
</style>