<template>
  <div class="wax-seal" :class="{ 'wax-seal--stamped': hasStamped }" :title="sealTitle">
    <!-- Outer ring with subtle irregularity -->
    <svg class="wax-seal__border" viewBox="0 0 100 100" aria-hidden="true">
      <circle
        cx="50" cy="50" r="46"
        fill="none"
        stroke="var(--seal-color, #c41e3a)"
        stroke-width="3"
        stroke-dasharray="5.5 0.6"
        stroke-linecap="round"
      />
      <!-- Inner decorative ring — slightly rotated for hand-carved feel -->
      <circle
        cx="50" cy="50" r="41"
        fill="none"
        stroke="var(--seal-color, #c41e3a)"
        stroke-width="0.7"
        opacity="0.5"
        transform="rotate(12, 50, 50)"
      />
    </svg>
    <!-- Character -->
    <span class="wax-seal__char">{{ sealChar }}</span>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, onMounted } from 'vue'

const props = defineProps<{
  familyName: string
}>()

defineOptions({ name: 'WaxSeal' })

const sealChar = computed(() => {
  const name = props.familyName.trim()
  return name.length > 0 ? name.charAt(0) : '家'
})

const sealTitle = computed(() => props.familyName)

// Stamp animation: trigger after mount so the CSS transition plays
const hasStamped = ref(false)

onMounted(() => {
  // Double-rAF ensures the browser has painted the initial state
  requestAnimationFrame(() => {
    requestAnimationFrame(() => {
      hasStamped.value = true
    })
  })
})
</script>

<style scoped>
.wax-seal {
  position: relative;
  width: 72px;
  height: 72px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  --seal-color: #c41e3a;
  /* Initial state: slightly scaled up and rotated, invisible */
  opacity: 0;
  transform: scale(1.2) rotate(-12deg);
  transition:
    opacity 0.35s ease-out,
    transform 0.35s cubic-bezier(0.34, 1.56, 0.64, 1);
}

.wax-seal--stamped {
  /* Final state: normal size, slight tilt for realism */
  opacity: 0.85;
  transform: scale(1) rotate(-6deg);
}

.wax-seal__border {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  pointer-events: none;
}

.wax-seal__char {
  position: relative;
  z-index: 1;
  font-family: 'Noto Serif SC', 'STSong', 'SimSun', 'Songti SC', serif;
  font-size: 32px;
  font-weight: 900;
  color: var(--seal-color, #c41e3a);
  line-height: 1;
  user-select: none;
}

/* ── Dark mode: lighten seal for contrast on dark parchment ── */
:global([data-theme='dark']) .wax-seal {
  --seal-color: #e05263;
}

/* ── Reduced motion: skip animation, show at final state ── */
@media (prefers-reduced-motion: reduce) {
  .wax-seal {
    opacity: 0.85;
    transform: scale(1) rotate(-6deg);
    transition: none;
  }
}
</style>
