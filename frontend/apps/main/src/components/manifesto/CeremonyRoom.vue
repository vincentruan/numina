<template>
  <div class="ceremony-room">
    <!-- Close button: replaces nav-bar back arrow -->
    <button
      type="button"
      class="ceremony-close"
      aria-label="Close"
      @click="emit('close')"
    >
      <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round">
        <line x1="18" y1="6" x2="6" y2="18" />
        <line x1="6" y1="6" x2="18" y2="18" />
      </svg>
    </button>

    <!-- Document container: elevated card with scale-up entrance -->
    <div
      ref="docRef"
      class="ceremony-document"
      :class="animClass"
    >
      <slot />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'

const emit = defineEmits<{
  close: []
}>()

const docRef = ref<HTMLElement | null>(null)
const reducedMotion = ref(false)

/** True once the entrance animation has played (or was skipped). */
const entered = ref(false)

/** Animation class: starts at .ceremony-enter, transitions to .ceremony-active. */
const animClass = computed(() => {
  if (reducedMotion.value || entered.value) return 'ceremony-active'
  return 'ceremony-enter'
})

onMounted(() => {
  // Check prefers-reduced-motion before triggering animation
  const mql = window.matchMedia('(prefers-reduced-motion: reduce)')
  reducedMotion.value = mql.matches

  if (!reducedMotion.value) {
    // Trigger reflow to ensure the initial state is painted before transitioning
    void docRef.value?.offsetHeight
    // Use rAF so the browser paints .ceremony-enter first, then transitions
    requestAnimationFrame(() => {
      entered.value = true
    })
  } else {
    entered.value = true
  }
})
</script>

<style scoped>
/* ── Room: full-height parchment surface ── */
.ceremony-room {
  position: relative;
  min-height: calc(100vh - 50px); /* account for tab bar height */
  padding-bottom: env(safe-area-inset-bottom);
  background-color: var(--ceremony-bg, #FAF7F0);
}

/* Parchment texture: subtle grain via SVG feTurbulence data URI */
.ceremony-room::before {
  content: '';
  position: absolute;
  inset: 0;
  pointer-events: none;
  opacity: 0.04;
  background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='200' height='200'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.75' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)'/%3E%3C/svg%3E");
  background-repeat: repeat;
}

/* ── Close button: minimal × top-left ── */
.ceremony-close {
  position: fixed;
  top: 8px;
  left: 8px;
  z-index: 1001; /* above tab bar (z-index: 1000) */
  display: flex;
  align-items: center;
  justify-content: center;
  width: 44px;
  height: 44px;
  padding: 0;
  border: none;
  border-radius: 50%;
  background: rgba(26, 26, 46, 0.08);
  color: var(--ceremony-ink, #1a1a2e);
  cursor: pointer;
  transition: background 0.15s ease;
  -webkit-tap-highlight-color: transparent;
}

.ceremony-close:active {
  background: rgba(26, 26, 46, 0.16);
}

[data-theme='dark'] .ceremony-close {
  background: rgba(240, 236, 228, 0.12);
  color: var(--ceremony-ink, #f0ece4);
}

[data-theme='dark'] .ceremony-close:active {
  background: rgba(240, 236, 228, 0.24);
}

/* ─ Document card: elevated on parchment ─ */
.ceremony-document {
  position: relative;
  z-index: 1; /* above texture overlay */
  max-width: 100%;
  margin: 0;
  padding: 16px;
  background: var(--ceremony-doc-bg, #fffef9);
  box-shadow: 0 4px 24px var(--ceremony-shadow, rgba(26, 26, 46, 0.12));
  border-radius: 4px;
}

/* ── Entrance animation ── */
.ceremony-enter {
  transform: scale(0.92);
  opacity: 0;
  transition: transform 0.6s ease-out, opacity 0.6s ease-out;
}

.ceremony-active {
  transform: scale(1);
  opacity: 1;
}

/* ── Reduced motion: skip animation entirely ── */
@media (prefers-reduced-motion: reduce) {
  .ceremony-enter,
  .ceremony-active {
    transform: none;
    opacity: 1;
    transition: none;
  }
}
</style>
