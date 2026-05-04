<template>
  <Transition name="overlay" @after-leave="onAfterLeave">
    <div v-if="isLoading" class="loading-overlay" aria-live="polite" aria-label="加载中">
      <div class="loading-rings" :class="{ 'is-leaving': isLeaving }">
        <svg viewBox="0 0 120 120" class="rings-svg" aria-hidden="true">
          <!-- 5 concentric arcs, each with independent animation phase -->
          <circle
            v-for="ring in rings"
            :key="ring.id"
            cx="60" cy="60"
            :r="ring.r"
            fill="none"
            :stroke="ring.color"
            :stroke-width="ring.width"
            stroke-linecap="round"
            :stroke-dasharray="ring.dash"
            :stroke-dashoffset="ring.offset"
            :class="['ring', isLeaving ? 'ring-burst' : 'ring-pulse']"
            :style="ring.style"
          />
        </svg>
      </div>
    </div>
  </Transition>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { useLoadingOverlay } from '../composables/useLoadingOverlay'

const { isLoading } = useLoadingOverlay()
const isLeaving = ref(false)

// Ring definitions — 5 arcs at increasing radii with offset phases
const rings = [
  { id: 1, r: 14, color: '#bdbbff', width: 3,   dash: '22 66',  offset: 0,  style: { animationDelay: '0s',    animationDuration: '1.4s' } },
  { id: 2, r: 24, color: '#a78bfa', width: 2.5, dash: '38 112', offset: 20, style: { animationDelay: '0.15s', animationDuration: '1.6s' } },
  { id: 3, r: 34, color: '#818cf8', width: 2.5, dash: '54 160', offset: 40, style: { animationDelay: '0.05s', animationDuration: '1.3s' } },
  { id: 4, r: 44, color: '#c084fc', width: 2,   dash: '70 207', offset: 60, style: { animationDelay: '0.25s', animationDuration: '1.7s' } },
  { id: 5, r: 54, color: '#fbbf24', width: 2,   dash: '85 254', offset: 10, style: { animationDelay: '0.1s',  animationDuration: '1.5s' } },
]

// Trigger burst animation before the overlay hides
watch(isLoading, (val) => {
  if (!val) {
    isLeaving.value = true
    // Reset after burst animation completes (matches CSS duration)
    setTimeout(() => { isLeaving.value = false }, 500)
  }
})

function onAfterLeave() {
  isLeaving.value = false
}
</script>

<style scoped>
.loading-overlay {
  position: fixed;
  inset: 0;
  z-index: 9999;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(1, 1, 32, 0.55);
  backdrop-filter: blur(3px);
  -webkit-backdrop-filter: blur(3px);
}

.loading-rings {
  display: flex;
  align-items: center;
  justify-content: center;
}

.rings-svg {
  width: 120px;
  height: 120px;
  overflow: visible;
}

/* ── Pulse animation: each arc rotates + oscillates dashoffset ── */
@keyframes ring-pulse {
  0%   { stroke-dashoffset: var(--dash-start); opacity: 0.9; }
  50%  { stroke-dashoffset: var(--dash-mid);   opacity: 1;   }
  100% { stroke-dashoffset: var(--dash-start); opacity: 0.9; }
}

/* ── Burst animation: scale up + fade out on exit ── */
@keyframes ring-burst {
  0%   { transform: scale(1);   opacity: 1;   }
  60%  { transform: scale(1.6); opacity: 0.6; }
  100% { transform: scale(2.2); opacity: 0;   }
}

.ring-pulse {
  transform-origin: 60px 60px;
  animation: ring-pulse var(--dur, 1.5s) ease-in-out infinite;
  --dash-start: 0;
  --dash-mid: 40;
}

/* Stagger dash-mid per ring for independent wave feel */
.ring:nth-child(1) { --dash-mid: 30; }
.ring:nth-child(2) { --dash-mid: 55; }
.ring:nth-child(3) { --dash-mid: 75; }
.ring:nth-child(4) { --dash-mid: 95; }
.ring:nth-child(5) { --dash-mid: 115; }

.ring-burst {
  transform-origin: 60px 60px;
  animation: ring-burst 0.5s ease-out forwards;
}

/* Stagger burst delay so rings expand outward sequentially */
.ring-burst:nth-child(1) { animation-delay: 0s;    }
.ring-burst:nth-child(2) { animation-delay: 0.04s; }
.ring-burst:nth-child(3) { animation-delay: 0.08s; }
.ring-burst:nth-child(4) { animation-delay: 0.12s; }
.ring-burst:nth-child(5) { animation-delay: 0.16s; }

/* ── Overlay fade transition ── */
.overlay-enter-active {
  transition: opacity 0.25s ease;
}
.overlay-leave-active {
  transition: opacity 0.5s ease 0.3s; /* delay so burst plays first */
}
.overlay-enter-from,
.overlay-leave-to {
  opacity: 0;
}
</style>
