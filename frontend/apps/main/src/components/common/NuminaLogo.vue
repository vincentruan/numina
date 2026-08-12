<script setup lang="ts">
/**
 * Numina cursive wordmark logo.
 *
 * Extracted from LoginPage.vue per plan U7. The SVG was originally inlined in
 * LoginPage with hardcoded gradient/filter IDs. This component scopes those IDs
 * via `useId()` so multiple instances can render on the same page (e.g., the
 * login screen plus the AI hub agent grid plus an in-chat agent picker) without
 * SVG `url(#...)` reference collisions.
 *
 * Usage:
 *   <NuminaLogo />                  -- default 220px wide (login screen)
 *   <NuminaLogo :width="80" />      -- compact agent-card icon variant
 */
import { computed, useId } from 'vue'

withDefaults(
  defineProps<{
    width?: number
  }>(),
  { width: 220 },
)

// Scope all SVG def IDs per instance so multiple <NuminaLogo /> renders coexist.
const uid = useId()
const ids = computed(() => ({
  flourishGrad: `numina-${uid}-flourishGrad`,
  textGrad: `numina-${uid}-textGrad`,
  logoGlow: `numina-${uid}-logoGlow`,
  logoSoftglow: `numina-${uid}-logoSoftglow`,
  shimmerGrad: `numina-${uid}-shimmerGrad`,
  shimmerMask: `numina-${uid}-shimmerMask`,
}))
</script>

<template>
  <svg
    :class="['numina-logo']"
    :style="{ width: `${width}px` }"
    viewBox="-10 -15 300 95"
    xmlns="http://www.w3.org/2000/svg"
    aria-label="Numina"
    role="img"
  >
    <defs>
      <linearGradient :id="ids.flourishGrad" x1="0%" y1="0%" x2="100%" y2="0%">
        <stop offset="0%" stop-color="#bdbbff" stop-opacity="0.7" />
        <stop offset="45%" stop-color="#e8e4ff" stop-opacity="1" />
        <stop offset="100%" stop-color="#ffd6a5" stop-opacity="0.8" />
      </linearGradient>
      <linearGradient :id="ids.textGrad" x1="0%" y1="0%" x2="0%" y2="100%">
        <stop offset="0%" stop-color="#ffffff" />
        <stop offset="100%" stop-color="rgba(255,255,255,0.85)" />
      </linearGradient>
      <filter :id="ids.logoGlow" x="-30%" y="-30%" width="160%" height="160%">
        <feGaussianBlur stdDeviation="2" result="b" />
        <feMerge><feMergeNode in="b" /><feMergeNode in="SourceGraphic" /></feMerge>
      </filter>
      <filter :id="ids.logoSoftglow" x="-15%" y="-15%" width="130%" height="130%">
        <feGaussianBlur stdDeviation="1" result="b" />
        <feMerge><feMergeNode in="b" /><feMergeNode in="SourceGraphic" /></feMerge>
      </filter>

      <!-- Shimmer sweep gradient: white band with soft edges -->
      <linearGradient :id="ids.shimmerGrad" x1="0" y1="0" x2="1" y2="0">
        <stop offset="0%" stop-color="#ffffff" stop-opacity="0" />
        <stop offset="35%" stop-color="#ffffff" stop-opacity="0" />
        <stop offset="50%" stop-color="#ffffff" stop-opacity="0.9" />
        <stop offset="65%" stop-color="#ffffff" stop-opacity="0" />
        <stop offset="100%" stop-color="#ffffff" stop-opacity="0" />
      </linearGradient>

      <!-- Shimmer mask: re-renders the logo paths as opaque white shapes so the
           shimmer rect is visible only on the strokes / flourish. -->
      <mask :id="ids.shimmerMask" maskContentUnits="objectBoundingBox">
        <!-- N stem + diagonal -->
        <path d="M 4,56 C 4,50 4,30 5,18 C 5.5,14 7,12 9,13 C 11,14 13,17 15,22 C 22,36 28,48 31,54 C 32,57 33,58 34,57 C 35,56 36,40 36,18 C 36,14 37,12 39,12 M 39,12 C 41,11 44,14 45,20" fill="none" stroke="white" stroke-width="4" stroke-linecap="round" stroke-linejoin="round" />
        <!-- u -->
        <path d="M 45,20 C 45,20 44,46 44,52 C 44,57 46,60 49,59 C 52,58 55,54 57,49 C 58,46 58,20 58,20 M 58,20 C 60,19 63,20 64,22" fill="none" stroke="white" stroke-width="4" stroke-linecap="round" />
        <!-- m -->
        <path d="M 64,22 C 64,22 63,56 63,58 M 63,30 C 65,23 69,19 73,20 C 77,21 79,25 79,30 C 79,30 79,58 79,58 M 79,30 C 81,23 85,19 89,20 C 93,21 95,25 95,30 C 95,30 95,58 95,58 M 95,58 C 97,59 100,58 101,56 C 102,54 102,40 102,30" fill="none" stroke="white" stroke-width="4" stroke-linecap="round" />
        <!-- i -->
        <path d="M 102,30 C 102,30 102,56 102,58 M 102,58 C 104,59 107,58 108,56 C 109,54 109,40 109,30" fill="none" stroke="white" stroke-width="4" stroke-linecap="round" />
        <!-- i house icon -->
        <g transform="translate(96.5, 14)">
          <polyline points="5.5,8 0,4 5.5,0 11,4 5.5,8" fill="none" stroke="white" stroke-width="3" stroke-linejoin="round" />
          <rect x="1.5" y="8" width="8" height="6" fill="none" stroke="white" stroke-width="3" />
          <rect x="3.5" y="10.5" width="4" height="3.5" fill="none" stroke="white" stroke-width="2" />
        </g>
        <!-- n -->
        <path d="M 109,30 C 109,30 108,56 108,58 M 108,38 C 110,31 114,27 118,28 C 122,29 124,33 124,38 C 124,38 124,58 124,58 M 124,58 C 126,59 129,58 130,56 C 131,54 131,44 131,38" fill="none" stroke="white" stroke-width="4" stroke-linecap="round" />
        <!-- a -->
        <path d="M 148,32 C 146,26 142,23 138,24 C 134,25 131,29 131,36 C 131,44 134,56 140,58 C 144,59 148,56 148,52 C 148,48 148,32 148,32 M 148,32 C 148,32 148,58 149,60 C 150,62 153,63 156,61" fill="none" stroke="white" stroke-width="4" stroke-linecap="round" stroke-linejoin="round" />
        <!-- Decorative flourish arc -->
        <path d="M 39,12 C 55,0 90,-4 130,-1 C 170,2 205,-2 225,10 C 240,18 244,34 238,46 C 232,56 220,62 208,58 C 196,54 193,44 198,36 C 201,30 208,27 214,30" fill="none" stroke="white" stroke-width="3" stroke-linecap="round" />
        <!-- Trend line -->
        <path d="M 156,61 C 170,64 190,58 205,50" fill="none" stroke="white" stroke-width="3" stroke-linecap="round" />
        <!-- Growth arrow -->
        <g transform="translate(208, 22)">
          <polyline points="0,14 5,6 10,14" fill="none" stroke="white" stroke-width="3" stroke-linejoin="round" />
          <line x1="5" y1="6" x2="5" y2="20" stroke="white" stroke-width="3" />
        </g>
        <!-- Three flourish dots -->
        <circle cx="80" cy="-2" r="3" fill="white" />
        <circle cx="130" cy="-1" r="3" fill="white" />
        <circle cx="178" cy="2" r="3" fill="white" />
      </mask>
    </defs>

    <!-- N: left stem + diagonal + right stem -->
    <path
      d="M 4,56 C 4,50 4,30 5,18 C 5.5,14 7,12 9,13 C 11,14 13,17 15,22 C 22,36 28,48 31,54 C 32,57 33,58 34,57 C 35,56 36,40 36,18 C 36,14 37,12 39,12"
      fill="none" :stroke="`url(#${ids.textGrad})`" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round" :filter="`url(#${ids.logoSoftglow})`"
    />
    <path d="M 39,12 C 41,11 44,14 45,20" fill="none" :stroke="`url(#${ids.textGrad})`" stroke-width="1.6" stroke-linecap="round" opacity="0.7" />

    <!-- u -->
    <path
      d="M 45,20 C 45,20 44,46 44,52 C 44,57 46,60 49,59 C 52,58 55,54 57,49 C 58,46 58,20 58,20"
      fill="none" :stroke="`url(#${ids.textGrad})`" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round" :filter="`url(#${ids.logoSoftglow})`"
    />
    <path d="M 58,20 C 60,19 63,20 64,22" fill="none" :stroke="`url(#${ids.textGrad})`" stroke-width="1.6" stroke-linecap="round" opacity="0.7" />

    <!-- m: left stem + two arches -->
    <path d="M 64,22 C 64,22 63,56 63,58" fill="none" :stroke="`url(#${ids.textGrad})`" stroke-width="2.4" stroke-linecap="round" :filter="`url(#${ids.logoSoftglow})`" />
    <path d="M 63,30 C 65,23 69,19 73,20 C 77,21 79,25 79,30 C 79,30 79,58 79,58" fill="none" :stroke="`url(#${ids.textGrad})`" stroke-width="2.4" stroke-linecap="round" :filter="`url(#${ids.logoSoftglow})`" />
    <path d="M 79,30 C 81,23 85,19 89,20 C 93,21 95,25 95,30 C 95,30 95,58 95,58" fill="none" :stroke="`url(#${ids.textGrad})`" stroke-width="2.4" stroke-linecap="round" :filter="`url(#${ids.logoSoftglow})`" />
    <path d="M 95,58 C 97,59 100,58 101,56 C 102,54 102,40 102,30" fill="none" :stroke="`url(#${ids.textGrad})`" stroke-width="1.6" stroke-linecap="round" opacity="0.7" />

    <!-- i: stem -->
    <path d="M 102,30 C 102,30 102,56 102,58" fill="none" :stroke="`url(#${ids.textGrad})`" stroke-width="2.4" stroke-linecap="round" :filter="`url(#${ids.logoSoftglow})`" />
    <!-- i dot → house icon -->
    <g transform="translate(96.5, 14)" :filter="`url(#${ids.logoGlow})`">
      <polyline points="5.5,8 0,4 5.5,0 11,4 5.5,8" fill="none" :stroke="`url(#${ids.flourishGrad})`" stroke-width="1.5" stroke-linejoin="round" />
      <rect x="1.5" y="8" width="8" height="6" fill="none" :stroke="`url(#${ids.flourishGrad})`" stroke-width="1.5" />
      <rect x="3.5" y="10.5" width="4" height="3.5" fill="none" :stroke="`url(#${ids.flourishGrad})`" stroke-width="1.2" />
    </g>
    <path d="M 102,58 C 104,59 107,58 108,56 C 109,54 109,40 109,30" fill="none" :stroke="`url(#${ids.textGrad})`" stroke-width="1.6" stroke-linecap="round" opacity="0.7" />

    <!-- n: stem + arch -->
    <path d="M 109,30 C 109,30 108,56 108,58" fill="none" :stroke="`url(#${ids.textGrad})`" stroke-width="2.4" stroke-linecap="round" :filter="`url(#${ids.logoSoftglow})`" />
    <path d="M 108,38 C 110,31 114,27 118,28 C 122,29 124,33 124,38 C 124,38 124,58 124,58" fill="none" :stroke="`url(#${ids.textGrad})`" stroke-width="2.4" stroke-linecap="round" :filter="`url(#${ids.logoSoftglow})`" />
    <path d="M 124,58 C 126,59 129,58 130,56 C 131,54 131,44 131,38" fill="none" :stroke="`url(#${ids.textGrad})`" stroke-width="1.6" stroke-linecap="round" opacity="0.7" />

    <!-- a: bowl + right stem + exit -->
    <path
      d="M 148,32 C 146,26 142,23 138,24 C 134,25 131,29 131,36 C 131,44 134,56 140,58 C 144,59 148,56 148,52 C 148,48 148,32 148,32"
      fill="none" :stroke="`url(#${ids.textGrad})`" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round" :filter="`url(#${ids.logoSoftglow})`"
    />
    <path d="M 148,32 C 148,32 148,58 149,60 C 150,62 153,63 156,61" fill="none" :stroke="`url(#${ids.textGrad})`" stroke-width="2.4" stroke-linecap="round" :filter="`url(#${ids.logoSoftglow})`" />

    <!-- Decorative flourish: sweeping arc from N top, over word, curling back -->
    <path
      d="M 39,12 C 55,0 90,-4 130,-1 C 170,2 205,-2 225,10 C 240,18 244,34 238,46 C 232,56 220,62 208,58 C 196,54 193,44 198,36 C 201,30 208,27 214,30"
      fill="none" :stroke="`url(#${ids.flourishGrad})`" stroke-width="1.6" stroke-linecap="round" opacity="0.85" :filter="`url(#${ids.logoGlow})`"
    />

    <!-- Trend line from a's exit -->
    <path d="M 156,61 C 170,64 190,58 205,50" fill="none" :stroke="`url(#${ids.flourishGrad})`" stroke-width="1.3" stroke-linecap="round" opacity="0.65" />

    <!-- Growth arrow at flourish end -->
    <g transform="translate(208, 22)" :filter="`url(#${ids.logoGlow})`">
      <polyline points="0,14 5,6 10,14" fill="none" :stroke="`url(#${ids.flourishGrad})`" stroke-width="1.5" stroke-linejoin="round" opacity="0.95" />
      <line x1="5" y1="6" x2="5" y2="20" :stroke="`url(#${ids.flourishGrad})`" stroke-width="1.5" opacity="0.95" />
    </g>

    <!-- Three dots on flourish arc — family members connected -->
    <circle cx="80" cy="-2" r="2" :fill="`url(#${ids.flourishGrad})`" opacity="0.6" :filter="`url(#${ids.logoGlow})`" />
    <circle cx="130" cy="-1" r="2" :fill="`url(#${ids.flourishGrad})`" opacity="0.6" :filter="`url(#${ids.logoGlow})`" />
    <circle cx="178" cy="2" r="2" :fill="`url(#${ids.flourishGrad})`" opacity="0.6" :filter="`url(#${ids.logoGlow})`" />

    <!-- Shimmer overlay: animated gradient that sweeps left→right across the logo,
         clipped by the SVG mask so only strokes/flourish glow. -->
    <rect :mask="`url(#${ids.shimmerMask})`" x="-60" y="-20" width="50" height="100" :fill="`url(#${ids.shimmerGrad})`" class="numina-logo__shimmer" />
  </svg>
</template>

<style scoped>
.numina-logo {
  height: auto;
  display: block;
  margin: 0 auto;
}

/* Dark-mode visibility: the SVG strokes use white/light gradients (intended for
 * dark backgrounds like the login canvas). When rendered against a light
 * background (e.g., AgentCard light-mode), bump contrast by switching to a
 * subtle drop shadow rather than relying on stroke color. */
[data-theme='light'] .numina-logo {
  filter: drop-shadow(0 0 1px rgba(1, 1, 32, 0.35));
}

/* Shimmer sweep animation — light band glides left → right across the logo. */
.numina-logo__shimmer {
  animation: numina-shimmer 3s ease-in-out infinite;
}

@keyframes numina-shimmer {
  0% {
    transform: translateX(-10px);
  }
  100% {
    transform: translateX(360px);
  }
}

@media (prefers-reduced-motion: reduce) {
  .numina-logo__shimmer {
    animation: none;
    display: none;
  }
}
</style>
