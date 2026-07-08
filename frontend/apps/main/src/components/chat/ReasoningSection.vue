<script setup lang="ts">
/**
 * ReasoningSection — Collapsible thinking/reasoning section following DeerFlow pattern
 *
 * DeerFlow reference: frontend/src/components/workspace/messages/Reasoning.tsx
 *
 * Key patterns:
 * - ReasoningTrigger: toggle button with elapsed time display
 * - ReasoningContent: expandable content area with shimmer animation
 * - Collapsible by default (click to expand)
 * - Shows duration when reasoning completes
 */
import { ref, computed, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import type { ProcessStep } from '@/types/agent-stream'

interface Props {
  steps: ProcessStep[]
  phase?: string
  elapsedMs?: number
  startTime?: number | null
  isStreaming?: boolean
}

const props = defineProps<Props>()

const { t } = useI18n()

// Collapsible state: expanded during streaming, collapsed after done
const isExpanded = ref(props.isStreaming ?? false)

// Auto-collapse when phase changes to done
watch(
  () => props.phase,
  (newPhase) => {
    if (newPhase === 'done' || newPhase === 'answering') {
      // Keep expanded for 2 seconds then collapse
      setTimeout(() => {
        isExpanded.value = false
      }, 2000)
    }
  }
)

// Combine all reasoning content
const combinedContent = computed(() =>
  props.steps
    .filter((s) => s.type === 'reasoning')
    .map((s) => s.content ?? '')
    .join('\n')
)

// Calculate elapsed time
const displayElapsedMs = computed(() => {
  if (props.elapsedMs) return props.elapsedMs
  // Calculate from startTime if available
  if (props.startTime) {
    return Math.round((Date.now() - props.startTime) / 1000) * 1000
  }
  return 0
})

// Format elapsed time as human-readable string
function formatElapsed(ms: number): string {
  const seconds = Math.floor(ms / 1000)
  if (seconds < 60) {
    return t('aiChat.secondsCount', { count: seconds })
  }
  const minutes = Math.floor(seconds / 60)
  const remainingSeconds = seconds % 60
  return t('aiChat.minutesSeconds', { minutes, seconds: remainingSeconds })
}

function toggleExpanded() {
  isExpanded.value = !isExpanded.value
}
</script>

<template>
  <div class="reasoning-section" :class="{ 'reasoning--streaming': isStreaming }">
    <!-- Trigger: collapsible toggle with status indicator -->
    <button
      class="reasoning-trigger"
      :aria-expanded="isExpanded"
      :aria-label="isExpanded ? t('aiChat.collapseReasoning') : t('aiChat.expandReasoning')"
      @click="toggleExpanded"
    >
      <!-- Status indicator -->
      <span class="trigger-icon" :class="`trigger-icon--${phase ?? 'done'}`">
        <svg v-if="isStreaming" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
          <circle cx="12" cy="12" r="10"/>
          <path d="M12 6v6l4 2"/>
        </svg>
        <svg v-else width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
          <polyline points="9 11 12 14 22 4"/>
          <path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"/>
        </svg>
      </span>

      <!-- Label -->
      <span class="trigger-label">
        {{ isStreaming ? t('aiChat.thinking') : t('aiChat.reasoningComplete') }}
      </span>

      <!-- Duration -->
      <span v-if="displayElapsedMs > 0" class="trigger-duration">
        {{ formatElapsed(displayElapsedMs) }}
      </span>

      <!-- Expand/collapse indicator -->
      <span class="trigger-chevron" :class="{ 'trigger-chevron--expanded': isExpanded }">
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" aria-hidden="true">
          <polyline points="6 9 12 15 18 9"/>
        </svg>
      </span>
    </button>

    <!-- Content: expandable area -->
    <transition name="reasoning-content">
      <div v-if="isExpanded" class="reasoning-content">
        <!-- Streaming: shimmer background -->
        <div v-if="isStreaming" class="content-shimmer" />

        <!-- Reasoning text -->
        <div class="reasoning-text">
          {{ combinedContent }}
        </div>

        <!-- Streaming dots -->
        <span v-if="isStreaming" class="stream-indicator" aria-hidden="true">
          <span class="stream-dot" />
          <span class="stream-dot" />
          <span class="stream-dot" />
        </span>
      </div>
    </transition>
  </div>
</template>

<style scoped>
.reasoning-section {
  margin-bottom: 12px;
}

/* Trigger button */
.reasoning-trigger {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  padding: 10px 12px;
  background: rgba(129, 140, 248, 0.08);
  border: 1px solid rgba(129, 140, 248, 0.15);
  border-radius: 8px;
  cursor: pointer;
  transition: background 0.2s;
}

.reasoning-trigger:hover {
  background: rgba(129, 140, 248, 0.12);
}

/* Status icon */
.trigger-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 20px;
  height: 20px;
  border-radius: 50%;
  background: rgba(129, 140, 248, 0.15);
  color: #818cf8;
}

.trigger-icon--thinking,
.trigger-icon--streaming {
  animation: pulse 1.5s ease-in-out infinite;
}

.trigger-icon--done {
  background: rgba(34, 197, 94, 0.15);
  color: #22c55e;
}

.trigger-icon--error {
  background: rgba(248, 113, 113, 0.15);
  color: #f87171;
}

/* Label */
.trigger-label {
  flex: 1;
  font-size: 13px;
  font-weight: 500;
  color: var(--text-primary);
}

/* Duration */
.trigger-duration {
  font-size: 12px;
  color: var(--text-secondary);
  font-variant-numeric: tabular-nums;
}

/* Chevron */
.trigger-chevron {
  color: var(--text-secondary);
  transition: transform 0.2s;
}

.trigger-chevron--expanded {
  transform: rotate(180deg);
}

/* Content area */
.reasoning-content {
  position: relative;
  margin-top: 8px;
  padding: 12px;
  background: rgba(0, 0, 0, 0.04);
  border-radius: 8px;
  overflow: hidden;
}

/* Shimmer animation for streaming */
.content-shimmer {
  position: absolute;
  inset: 0;
  background: linear-gradient(
    90deg,
    transparent 0%,
    rgba(129, 140, 248, 0.05) 50%,
    transparent 100%
  );
  animation: shimmer 2s infinite linear;
}

@keyframes shimmer {
  0% { transform: translateX(-100%); }
  100% { transform: translateX(100%); }
}

/* Reasoning text */
.reasoning-text {
  font-size: 14px;
  line-height: 1.6;
  color: var(--text-secondary);
  white-space: pre-wrap;
  word-break: break-word;
}

/* Streaming indicator */
.stream-indicator {
  display: flex;
  gap: 3px;
  margin-top: 8px;
}

.stream-dot {
  width: 4px;
  height: 4px;
  background: #818cf8;
  border-radius: 50%;
  animation: bounce 1.4s ease-in-out infinite;
}

.stream-dot:nth-child(1) { animation-delay: 0s; }
.stream-dot:nth-child(2) { animation-delay: 0.2s; }
.stream-dot:nth-child(3) { animation-delay: 0.4s; }

/* Transition */
.reasoning-content-enter-active,
.reasoning-content-leave-active {
  transition: all 0.3s ease;
}

.reasoning-content-enter-from,
.reasoning-content-leave-to {
  opacity: 0;
  max-height: 0;
  padding-top: 0;
  padding-bottom: 0;
}

@keyframes pulse {
  0%, 100% { opacity: 0.6; }
  50% { opacity: 1; }
}

@keyframes bounce {
  0%, 80%, 100% { transform: translateY(0); }
  40% { transform: translateY(-4px); }
}

/* Light theme - wrap FULL selector in :global() so it matches the scoped
 * element; data-theme attr (not OS preference) is the source of truth. */
:global([data-theme='light'] .reasoning-content) {
  background: rgba(0, 0, 0, 0.02);
}
</style>