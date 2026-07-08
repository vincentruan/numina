<script setup lang="ts">
/**
 * TodoListPanel — Plan progress visualization following DeerFlow pattern
 *
 * DeerFlow reference: frontend/src/components/workspace/todo-list.tsx
 *
 * Key patterns:
 * - Collapsible header with ListTodoIcon
 * - QueueItem pattern for each todo
 * - Status-based styling: pending (muted), active (highlighted), completed (check)
 * - Progress indicator
 */
import { ref, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import type { PlanStep } from '@/types/agent-stream'

interface Props {
  steps: PlanStep[]
  source?: 'explicit' | 'inferred' | null
}

const props = defineProps<Props>()

const { t } = useI18n()

const isExpanded = ref(true)

// Count completed/active steps
const completedCount = computed(() =>
  props.steps.filter((s) => s.status === 'done').length
)

// Active count (for future use)
const _activeCount = computed(() =>
  props.steps.filter((s) => s.status === 'active').length
)

const progressPercent = computed(() =>
  props.steps.length > 0
    ? Math.round((completedCount.value / props.steps.length) * 100)
    : 0
)

function toggleExpanded() {
  isExpanded.value = !isExpanded.value
}

// Status icon
function getStatusIcon(status: string) {
  switch (status) {
    case 'completed':
      return { icon: '✓', color: '#22c55e' }
    case 'active':
      return { icon: '●', color: '#818cf8' }
    default:
      return { icon: '○', color: '#6b7280' }
  }
}
</script>

<template>
  <div class="todo-list-panel" :class="{ 'todo-list--inferred': source === 'inferred' }">
    <!-- Header: collapsible toggle with progress -->
    <button
      class="todo-header"
      :aria-expanded="isExpanded"
      @click="toggleExpanded"
    >
      <!-- ListTodo icon -->
      <span class="header-icon">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
          <path d="M3 5h18M3 12h18M3 19h18"/>
          <circle cx="3" cy="5" r="1" fill="currentColor"/>
          <circle cx="3" cy="12" r="1" fill="currentColor"/>
          <circle cx="3" cy="19" r="1" fill="currentColor"/>
        </svg>
      </span>

      <!-- Title -->
      <span class="header-title">{{ t('aiChat.planProgress') }}</span>

      <!-- Progress badge -->
      <span class="progress-badge">
        {{ completedCount }}/{{ steps.length }}
      </span>

      <!-- Progress bar -->
      <div class="progress-bar">
        <div class="progress-fill" :style="{ width: `${progressPercent}%` }" />
      </div>

      <!-- Expand indicator -->
      <span class="expand-indicator" :class="{ expanded: isExpanded }">
        <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" aria-hidden="true">
          <polyline points="6 9 12 15 18 9"/>
        </svg>
      </span>
    </button>

    <!-- Todo items -->
    <transition name="todo-content">
      <div v-if="isExpanded" class="todo-items">
        <div
          v-for="step in steps"
          :key="step.id"
          class="todo-item"
          :class="`todo-item--${step.status}`"
        >
          <!-- Status indicator -->
          <span class="item-status" :style="{ color: getStatusIcon(step.status).color }">
            {{ getStatusIcon(step.status).icon }}
          </span>

          <!-- Content -->
          <span class="item-label">{{ step.label }}</span>

          <!-- Active shimmer -->
          <div v-if="step.status === 'active'" class="active-shimmer" aria-hidden="true" />
        </div>
      </div>
    </transition>

    <!-- Inferred mode hint -->
    <div v-if="source === 'inferred'" class="inferred-hint">
      {{ t('aiChat.planInferred') }}
    </div>
  </div>
</template>

<style scoped>
.todo-list-panel {
  margin-bottom: 12px;
  background: rgba(0, 0, 0, 0.04);
  border-radius: 8px;
  overflow: hidden;
}

.todo-list--inferred {
  background: rgba(129, 140, 248, 0.04);
}

/* Header */
.todo-header {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  padding: 10px 12px;
  background: transparent;
  border: none;
  cursor: pointer;
  transition: background 0.15s;
}

.todo-header:hover {
  background: rgba(0, 0, 0, 0.02);
}

.header-icon {
  color: var(--text-secondary);
}

.header-title {
  flex: 1;
  font-size: 13px;
  font-weight: 500;
  color: var(--text-primary);
}

.progress-badge {
  font-size: 11px;
  color: var(--text-secondary);
  font-variant-numeric: tabular-nums;
}

.progress-bar {
  width: 60px;
  height: 4px;
  background: rgba(0, 0, 0, 0.1);
  border-radius: 2px;
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  background: #22c55e;
  border-radius: 2px;
  transition: width 0.3s ease;
}

.expand-indicator {
  color: var(--text-secondary);
  transition: transform 0.2s;
}

.expand-indicator.expanded {
  transform: rotate(180deg);
}

/* Todo items */
.todo-items {
  padding: 8px 12px;
}

.todo-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 0;
  position: relative;
}

.todo-item--pending {
  opacity: 0.6;
}

.todo-item--active {
  background: rgba(129, 140, 248, 0.08);
  margin: 0 -12px;
  padding: 6px 12px;
  border-radius: 4px;
}

.todo-item--completed {
  opacity: 0.85;
}

.item-status {
  font-size: 12px;
}

.item-label {
  flex: 1;
  font-size: 13px;
  color: var(--text-primary);
}

/* Active shimmer */
.active-shimmer {
  position: absolute;
  inset: 0;
  background: linear-gradient(
    90deg,
    transparent 0%,
    rgba(129, 140, 248, 0.1) 50%,
    transparent 100%
  );
  animation: shimmer 2s infinite linear;
  pointer-events: none;
  border-radius: 4px;
}

/* Inferred hint */
.inferred-hint {
  padding: 8px 12px;
  font-size: 11px;
  color: var(--text-secondary);
  opacity: 0.7;
  border-top: 1px solid rgba(0, 0, 0, 0.06);
}

/* Transitions */
.todo-content-enter-active,
.todo-content-leave-active {
  transition: all 0.2s ease;
}

.todo-content-enter-from,
.todo-content-leave-to {
  opacity: 0;
  max-height: 0;
}

@keyframes shimmer {
  0% { transform: translateX(-100%); }
  100% { transform: translateX(100%); }
}

/* Light theme - wrap FULL selector in :global() so it matches the scoped
 * element; data-theme attr (not OS preference) is the source of truth. */
:global([data-theme='light'] .todo-list-panel) {
  background: rgba(0, 0, 0, 0.02);
}
</style>