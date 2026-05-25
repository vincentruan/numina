<template>
  <span class="ai-logo" :class="stateClass" :aria-label="ariaLabel" role="img">
    <svg
      class="ai-logo-svg"
      viewBox="0 0 24 24"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      aria-hidden="true"
    >
      <!-- idle / thinking shape: 4-point sparkle, animates via CSS -->
      <g class="logo-sparkle">
        <path
          d="M12 2 L13.5 10.5 L22 12 L13.5 13.5 L12 22 L10.5 13.5 L2 12 L10.5 10.5 Z"
          fill="currentColor"
        />
      </g>
      <!-- done shape: checkmark, shown when state=done -->
      <g class="logo-check">
        <path
          d="M5 12 L10 17 L19 7"
          stroke="currentColor"
          stroke-width="2.5"
          stroke-linecap="round"
          stroke-linejoin="round"
          fill="none"
        />
      </g>
      <!-- error shape: cross, shown when state=error -->
      <g class="logo-cross">
        <path
          d="M7 7 L17 17 M17 7 L7 17"
          stroke="currentColor"
          stroke-width="2.5"
          stroke-linecap="round"
          fill="none"
        />
      </g>
    </svg>
  </span>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

const props = defineProps<{
  state: 'idle' | 'thinking' | 'done' | 'error'
}>()

const { t } = useI18n()

const stateClass = computed(() => `state-${props.state}`)

const ariaLabel = computed(() => {
  switch (props.state) {
    case 'thinking':
      return t('aiProcess.statusRunning')
    case 'done':
      return t('aiProcess.statusDone')
    case 'error':
      return t('aiProcess.statusError')
    default:
      return t('aiProcess.title')
  }
})
</script>

<style scoped>
.ai-logo {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 100%;
  height: 100%;
  color: #ffffff;
}

.ai-logo-svg {
  width: 70%;
  height: 70%;
  transition: opacity 200ms ease-in-out;
}

.logo-sparkle,
.logo-check,
.logo-cross {
  opacity: 0;
  transition: opacity 200ms ease-in-out;
  transform-origin: center;
}

.state-idle .logo-sparkle,
.state-thinking .logo-sparkle {
  opacity: 1;
}

.state-thinking .logo-sparkle {
  animation: logo-spin 2.4s linear infinite;
}

.state-done .logo-check {
  opacity: 1;
}

.state-error .logo-cross {
  opacity: 1;
}

@keyframes logo-spin {
  0% {
    transform: rotate(0deg) scale(1);
  }
  50% {
    transform: rotate(180deg) scale(1.08);
  }
  100% {
    transform: rotate(360deg) scale(1);
  }
}

@media (prefers-reduced-motion: reduce) {
  .state-thinking .logo-sparkle {
    animation: none;
  }

  .ai-logo-svg,
  .logo-sparkle,
  .logo-check,
  .logo-cross {
    transition: none;
  }
}
</style>
