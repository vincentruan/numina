<template>
  <div class="agent-run-canvas" :class="canvasClasses" role="region" :aria-label="t('aiCanvas.canvasAriaLabel')">
    <!-- Header with status badge, elapsed time, model info, collapse toggle -->
    <AgentRunHeader
      v-if="showHeader"
      :status="status"
      :elapsed-ms="elapsedMs"
      :model-name="modelName"
      :is-collapsed="isCollapsed"
      :progress-summary="progressSummaryText"
      @toggle-collapse="toggleCollapse"
    />

    <!-- Canvas body - wraps content (AiProcessBlock) -->
    <Transition name="canvas-body">
      <div v-show="!isCollapsed" class="canvas-body">
        <!-- Slot for content (AiProcessBlock or other components) -->
        <slot />
      </div>
    </Transition>

    <!-- Collapsed hint: "正在后台运行..." -->
    <div v-if="isCollapsed && status === 'running'" class="canvas-collapsed-hint" aria-live="polite">
      <span class="hint-dot" aria-hidden="true" />
      <span>{{ t('aiCanvas.runningInBackground') }}</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import AgentRunHeader from './AgentRunHeader.vue'
import { useCanvasPreference } from '@/utils/canvasPreference'

const props = withDefaults(defineProps<{
  status: 'running' | 'done' | 'error' | 'interrupted'
  elapsedMs: number
  modelName?: string
  showHeader?: boolean
  // U10: Step counts for progress summary in interrupted sessions
  doneStepCount?: number
  totalStepCount?: number
}>(), {
  showHeader: true,
  modelName: '',
  doneStepCount: 0,
  totalStepCount: 0,
})

const { t } = useI18n()

// Collapse state - persisted in localStorage via module-level singleton
const { isCollapsed, toggleCollapse } = useCanvasPreference()

// U10: Progress summary text for interrupted sessions
const progressSummaryText = computed(() => {
  if (props.status !== 'interrupted' || props.totalStepCount === 0) return undefined
  return t('aiCanvas.progressSummary', { done: props.doneStepCount, total: props.totalStepCount })
})

// Computed classes for canvas styling
const canvasClasses = computed(() => ({
  'is-collapsed': isCollapsed.value,
  'is-running': props.status === 'running',
  'is-done': props.status === 'done',
  'is-error': props.status === 'error',
  'is-interrupted': props.status === 'interrupted',
  'is-full-width': true, // Always full-width when canvas is active
}))

// Expose collapse state for parent components
defineExpose({ isCollapsed, toggleCollapse })
</script>

<style scoped>
.agent-run-canvas {
  --canvas-bg: rgba(189, 187, 255, 0.08);
  --canvas-border: rgba(189, 187, 255, 0.18);
  --canvas-text: rgba(255, 255, 255, 0.85);
  --canvas-text-muted: rgba(255, 255, 255, 0.55);
  --canvas-radius: 12px;

  /* Full-width styling */
  width: 100%;
  max-width: 100%;
  background: var(--canvas-bg);
  border: 1px solid var(--canvas-border);
  border-radius: var(--canvas-radius);
  overflow: hidden;
  transition: max-width 0.3s ease, opacity 0.3s ease;
}

/* Light theme */
[data-theme="light"] .agent-run-canvas {
  --canvas-bg: rgba(189, 187, 255, 0.12);
  --canvas-border: rgba(0, 0, 0, 0.15);
  --canvas-text: rgba(0, 0, 0, 0.9);
  --canvas-text-muted: rgba(0, 0, 0, 0.6);
}

/* Collapsed state */
.agent-run-canvas.is-collapsed {
  opacity: 0.7;
}

/* U10: Interrupted state - subtle gray tint to indicate incomplete session */
.agent-run-canvas.is-interrupted {
  --canvas-bg: rgba(255, 255, 255, 0.05);
  --canvas-border: rgba(255, 255, 255, 0.12);
}

[data-theme="light"] .agent-run-canvas.is-interrupted {
  --canvas-bg: rgba(0, 0, 0, 0.05);
  --canvas-border: rgba(0, 0, 0, 0.12);
}

/* Canvas body */
.canvas-body {
  padding: 12px;
  max-height: 1000px;
  overflow: visible;
}

/* Canvas body transition */
.canvas-body-enter-active,
.canvas-body-leave-active {
  transition: max-height 0.3s ease, opacity 0.3s ease;
}

.canvas-body-enter-from,
.canvas-body-leave-to {
  max-height: 0;
  opacity: 0;
}

/* Collapsed hint */
.canvas-collapsed-hint {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  color: var(--canvas-text-muted);
  font-size: 12px;
}

.hint-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #818cf8;
  animation: hint-pulse 1.4s ease-out infinite;
}

@keyframes hint-pulse {
  0% { opacity: 1; transform: scale(1); }
  50% { opacity: 0.6; transform: scale(1.2); }
  100% { opacity: 1; transform: scale(1); }
}

/* U12: Reduced motion - disable animations */
@media (prefers-reduced-motion: reduce) {
  .hint-dot {
    animation: none;
  }

  .canvas-body-enter-active,
  .canvas-body-leave-active {
    transition: opacity 0.15s ease;
  }
}

/* Mobile responsive */
@media (max-width: 428px) {
  .agent-run-canvas {
    --canvas-radius: 0;
    border-radius: 0;
    border-left: none;
    border-right: none;
  }

  .canvas-body {
    padding: 8px;
  }
}
</style>