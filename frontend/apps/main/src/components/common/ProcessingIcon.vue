<template>
  <div class="processing-icon" :class="{ active: active }">
    <div class="icon-container">
      <!-- Simple geometric shape: circular progress ring -->
      <svg class="processing-svg" viewBox="0 0 24 24" aria-hidden="true">
        <!-- Background circle -->
        <circle cx="12" cy="12" r="10" fill="none" stroke="currentColor" stroke-width="2" opacity="0.15" />
        <!-- Sweep arc that rotates -->
        <circle
          cx="12"
          cy="12"
          r="10"
          fill="none"
          stroke="currentColor"
          stroke-width="2"
          stroke-linecap="round"
          stroke-dasharray="31.4 62.8"
          class="sweep-arc"
        />
        <!-- Center dot -->
        <circle cx="12" cy="12" r="2" fill="currentColor" opacity="0.6" />
      </svg>
      <!-- Light sweep overlay -->
      <div class="light-sweep" aria-hidden="true" />
    </div>
  </div>
</template>

<script setup lang="ts">
defineProps<{
  active?: boolean
}>()
</script>

<style scoped>
.processing-icon {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
}

.icon-container {
  position: relative;
  width: var(--icon-size, 28px);
  height: var(--icon-size, 28px);
  display: flex;
  align-items: center;
  justify-content: center;
}

.processing-svg {
  width: 100%;
  height: 100%;
  color: var(--text-secondary);
  transition: color 0.3s;
}

.processing-icon.active .processing-svg {
  color: var(--van-primary-color);
}

/* Rotating sweep arc animation */
.sweep-arc {
  transform-origin: center;
  opacity: 0;
  transition: opacity 0.3s;
}

.processing-icon.active .sweep-arc {
  opacity: 1;
  animation: rotate-sweep 1.5s linear infinite;
}

@keyframes rotate-sweep {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
}

/* Light sweep effect - horizontal gradient moving left to right */
.light-sweep {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  border-radius: 50%;
  overflow: hidden;
  opacity: 0;
  transition: opacity 0.3s;
}

.processing-icon.active .light-sweep {
  opacity: 1;
}

.light-sweep::before {
  content: '';
  position: absolute;
  top: 0;
  left: -100%;
  width: 50%;
  height: 100%;
  background: linear-gradient(
    90deg,
    transparent 0%,
    rgba(255, 255, 255, 0.3) 50%,
    transparent 100%
  );
  animation: sweep-across 2s ease-in-out infinite;
}

@keyframes sweep-across {
  0% {
    left: -100%;
  }
  50% {
    left: 100%;
  }
  100% {
    left: 100%;
  }
}

/* Dark mode adjustments */
[data-theme='dark'] .light-sweep::before {
  background: linear-gradient(
    90deg,
    transparent 0%,
    rgba(255, 255, 255, 0.15) 50%,
    transparent 100%
  );
}

/* Reduced motion */
@media (prefers-reduced-motion: reduce) {
  .sweep-arc,
  .light-sweep::before {
    animation: none;
  }
  .processing-icon.active .sweep-arc {
    opacity: 0.7;
  }
}
</style>