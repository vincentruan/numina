<template>
  <div class="agent-run-header" role="banner">
    <!-- Status badge -->
    <span
      class="status-badge"
      :class="statusClass"
      role="status"
      aria-live="polite"
    >
      <span class="status-dot" aria-hidden="true" />
      <span class="status-label">{{ statusLabel }}</span>
      <!-- U10: Progress summary for interrupted sessions -->
      <span v-if="status === 'interrupted' && progressSummary" class="status-progress">{{ progressSummary }}</span>
    </span>

    <!-- Elapsed time -->
    <span class="elapsed-time" :aria-label="t('aiCanvas.elapsedTimeAriaLabel')">{{ formattedElapsed }}</span>

    <!-- Model info (optional) -->
    <span v-if="modelName" class="model-info">{{ modelName }}</span>

    <!-- Collapse toggle button -->
    <button
      class="collapse-toggle"
      type="button"
      :aria-expanded="!isCollapsed"
      :aria-controls="controlsId"
      :aria-label="isCollapsed ? t('aiCanvas.expand') : t('aiCanvas.collapse')"
      @click="onToggle"
    >
      <svg
        width="16"
        height="16"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        stroke-width="2"
        stroke-linecap="round"
        stroke-linejoin="round"
        aria-hidden="true"
      >
        <polyline :points="isCollapsed ? '6 9 12 15 18 9' : '18 15 12 9 6 15'" />
      </svg>
    </button>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

const props = defineProps<{
  status: 'running' | 'done' | 'error' | 'interrupted'
  elapsedMs: number
  modelName?: string
  isCollapsed: boolean
  // U10: Progress summary for interrupted sessions (e.g., "已完成 3/5 步骤")
  progressSummary?: string
}>()

const emit = defineEmits<{
  (e: 'toggle-collapse'): void
}>()

const { t } = useI18n()

// Unique ID for aria-controls - stable across re-renders
const controlsId = computed(() => `canvas-body-${props.status}-${props.elapsedMs}`)

// Status class for styling
const statusClass = computed(() => ({
  'is-running': props.status === 'running',
  'is-done': props.status === 'done',
  'is-error': props.status === 'error',
  'is-interrupted': props.status === 'interrupted',
}))

// Status label text
const statusLabel = computed(() => {
  switch (props.status) {
    case 'running':
      return t('aiCanvas.statusRunning')
    case 'done':
      return t('aiCanvas.statusDone')
    case 'error':
      return t('aiCanvas.statusError')
    case 'interrupted':
      return t('aiCanvas.statusInterrupted')
    default:
      return ''
  }
})

// Format elapsed time
const formattedElapsed = computed(() => {
  const seconds = Math.floor(props.elapsedMs / 1000)
  if (seconds < 60) {
    return `${seconds}s`
  }
  const minutes = Math.floor(seconds / 60)
  const remainingSeconds = seconds % 60
  return `${minutes}m ${remainingSeconds}s`
})

// Toggle handler
function onToggle() {
  emit('toggle-collapse')
}
</script>

<style scoped>
.agent-run-header {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  border-bottom: 1px solid var(--canvas-border, rgba(189, 187, 255, 0.18));
  user-select: none;
}

/* Status badge */
.status-badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 3px 8px;
  border-radius: 6px;
  font-size: 12px;
  font-weight: 500;
}

.status-badge.is-running {
  background: rgba(129, 140, 248, 0.15);
  color: #818cf8;
}

.status-badge.is-done {
  background: rgba(110, 231, 160, 0.15);
  color: #6ee7a0;
}

.status-badge.is-error {
  background: rgba(248, 113, 113, 0.15);
  color: #f87171;
}

.status-badge.is-interrupted {
  background: rgba(255, 255, 255, 0.08);
  color: rgba(255, 255, 255, 0.6);
}

[data-theme="light"] .status-badge.is-interrupted {
  background: rgba(0, 0, 0, 0.08);
  color: rgba(0, 0, 0, 0.6);
}

.status-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: currentColor;
}

.status-badge.is-running .status-dot {
  animation: status-pulse 1.4s ease-out infinite;
}

@keyframes status-pulse {
  0% { opacity: 1; transform: scale(1); }
  50% { opacity: 0.5; transform: scale(1.3); }
  100% { opacity: 1; transform: scale(1); }
}

/* U12: Reduced motion - disable pulse animation */
@media (prefers-reduced-motion: reduce) {
  .status-badge.is-running .status-dot {
    animation: none;
  }
}

.status-label {
  line-height: 1.2;
}

/* U10: Progress summary for interrupted sessions */
.status-progress {
  margin-left: 6px;
  font-size: 10px;
  opacity: 0.7;
}

/* Elapsed time */
.elapsed-time {
  font-size: 11px;
  color: var(--canvas-text-muted, rgba(255, 255, 255, 0.55));
  font-family: 'SF Mono', 'Menlo', monospace;
}

[data-theme="light"] .elapsed-time {
  color: rgba(0, 0, 0, 0.55);
}

/* Model info */
.model-info {
  font-size: 11px;
  color: var(--canvas-text-muted, rgba(255, 255, 255, 0.55));
  max-width: 100px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

[data-theme="light"] .model-info {
  color: rgba(0, 0, 0, 0.55);
}

/* Collapse toggle */
.collapse-toggle {
  margin-left: auto;
  width: 44px;
  height: 44px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: transparent;
  border: none;
  color: var(--canvas-text-muted, rgba(255, 255, 255, 0.7));
  cursor: pointer;
  border-radius: 8px;
  transition: background 0.15s, color 0.15s;
  /* Negative margin trick to preserve touch target while reducing visual footprint */
  margin-right: -8px;
}

[data-theme="light"] .collapse-toggle {
  color: rgba(0, 0, 0, 0.7);
}

.collapse-toggle:hover {
  background: rgba(255, 255, 255, 0.08);
  color: var(--canvas-text, rgba(255, 255, 255, 0.9));
}

[data-theme="light"] .collapse-toggle:hover {
  background: rgba(0, 0, 0, 0.08);
  color: rgba(0, 0, 0, 0.9);
}

.collapse-toggle:focus-visible {
  outline: 2px solid var(--van-primary-color, #818cf8);
  outline-offset: 2px;
}

/* Mobile responsive */
@media (max-width: 428px) {
  .agent-run-header {
    padding: 8px;
    gap: 8px;
  }

  .model-info {
    max-width: 60px;
  }
}
</style>