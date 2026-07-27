<script setup lang="ts">
/**
 * TodoListPanel — Plan progress visualization following DeerFlow pattern
 *
 * DeerFlow reference: frontend/src/components/workspace/todo-list.tsx
 * DeerFlow reference: frontend/src/components/ai-elements/queue.tsx
 *
 * Key patterns (from DeerFlow):
 * - Collapsible header: ListTodoIcon + "To-dos" + ChevronUp (collapsed by default)
 * - QueueItemIndicator: small circle (10px rounded-full border)
 *   - pending: empty border
 *   - in_progress: filled with primary color bg
 *   - completed: filled with muted bg
 * - QueueItemContent: completed = line-through + faded, in_progress = primary text
 * - Panel: rounded-t-xl, border, backdrop-blur, slide-up animation
 * - Scrollable list with max-height
 */
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import type { PlanStep } from '@/types/agent-stream'

interface Props {
  steps: PlanStep[]
  source?: 'explicit' | 'inferred' | null
}

defineProps<Props>()

const { t } = useI18n()

// DeerFlow: collapsed by default
const isExpanded = ref(false)

function toggleExpanded() {
  isExpanded.value = !isExpanded.value
}
</script>

<template>
  <div class="todo-list-panel" :class="{ 'todo-list--inferred': source === 'inferred' }">
    <!-- Header: collapsible toggle (DeerFlow pattern) -->
    <button
      class="todo-header"
      :aria-expanded="isExpanded"
      @click="toggleExpanded"
    >
      <!-- Left: ListTodo icon + title -->
      <span class="header-left">
        <svg class="header-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
          <path d="M3 5h18M3 12h18M3 19h18"/>
          <circle cx="3" cy="5" r="1" fill="currentColor"/>
          <circle cx="3" cy="12" r="1" fill="currentColor"/>
          <circle cx="3" cy="19" r="1" fill="currentColor"/>
        </svg>
        <span class="header-title">{{ t('aiChat.planProgress') }}</span>
      </span>

      <!-- Right: chevron (DeerFlow: ChevronUpIcon, rotates when collapsed) -->
      <svg class="expand-indicator" :class="{ expanded: isExpanded }" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
        <polyline points="18 15 12 9 6 15"/>
      </svg>
    </button>

    <!-- Todo items (DeerFlow: scrollable list with max-h-40) -->
    <transition name="todo-content">
      <div v-if="isExpanded" class="todo-items-wrapper">
        <ul class="todo-items">
          <li
            v-for="step in steps"
            :key="step.id"
            class="todo-item"
            :class="`todo-item--${step.status}`"
          >
            <!-- QueueItemIndicator: small circle (DeerFlow: size-2.5 rounded-full border) -->
            <span class="item-indicator" />

            <!-- QueueItemContent: text with status-based styling -->
            <span class="item-label">{{ step.label }}</span>
          </li>
        </ul>
      </div>
    </transition>
  </div>
</template>

<style scoped>
.todo-list-panel {
  margin-bottom: 12px;
  border-radius: 12px 12px 0 0;
  border: 1px solid var(--border-color, rgba(0, 0, 0, 0.08));
  border-bottom: none;
  background: var(--bg-card, #fff);
  backdrop-filter: blur(8px);
  overflow: hidden;
  /* DeerFlow: slide-up entrance */
  transform: translateY(0);
  opacity: 1;
  transition: transform 0.2s ease-out, opacity 0.2s ease-out;
}

.todo-list--inferred {
  background: rgba(129, 140, 248, 0.04);
}

/* Header (DeerFlow: bg-accent, min-h-8, cursor-pointer) */
.todo-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
  padding: 8px 16px;
  min-height: 32px;
  background: var(--bg-secondary, rgba(0, 0, 0, 0.02));
  border: none;
  cursor: pointer;
  transition: background 0.15s;
}

.todo-header:hover {
  background: var(--bg-hover, rgba(0, 0, 0, 0.04));
}

.header-left {
  display: flex;
  align-items: center;
  gap: 8px;
}

.header-icon {
  color: var(--text-secondary);
  flex-shrink: 0;
}

.header-title {
  font-size: 13px;
  font-weight: 500;
  color: var(--text-secondary);
}

/* Chevron (DeerFlow: ChevronUpIcon, rotate-180 when expanded) */
.expand-indicator {
  color: var(--text-secondary);
  transition: transform 0.3s ease-out;
  /* Default: pointing up (collapsed) */
  transform: rotate(0deg);
}

.expand-indicator.expanded {
  transform: rotate(180deg);
}

/* Todo items wrapper (DeerFlow: scrollable, max-h-40 = 160px) */
.todo-items-wrapper {
  max-height: 160px;
  overflow-y: auto;
  padding: 4px 8px 12px;
}

.todo-items {
  list-style: none;
  margin: 0;
  padding: 0;
}

/* QueueItem (DeerFlow: flex flex-col gap-1 rounded-md px-3 py-1) */
.todo-item {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 4px 12px;
  border-radius: 6px;
  transition: background 0.15s;
}

.todo-item:hover {
  background: var(--bg-hover, rgba(0, 0, 0, 0.02));
}

/* QueueItemIndicator (DeerFlow: size-2.5 = 10px, rounded-full, border) */
.item-indicator {
  flex-shrink: 0;
  width: 10px;
  height: 10px;
  margin-top: 4px;
  border-radius: 50%;
  border: 1.5px solid var(--text-secondary);
  opacity: 0.5;
  transition: all 0.2s;
}

/* Pending: empty circle (DeerFlow: border-muted-foreground/50) */
.todo-item--pending .item-indicator {
  border-color: var(--text-secondary);
  opacity: 0.4;
  background: transparent;
}

.todo-item--pending .item-label {
  color: var(--text-secondary);
}

/* Active/in_progress: filled with primary color (DeerFlow: bg-primary/70) */
.todo-item--active .item-indicator {
  border-color: var(--color-primary, #818cf8);
  background: var(--color-primary, #818cf8);
  opacity: 0.7;
}

.todo-item--active .item-label {
  color: var(--color-primary, #818cf8);
  font-weight: 500;
}

/* Completed: filled with muted bg (DeerFlow: border-muted-foreground/20 bg-muted-foreground/10) */
.todo-item--done .item-indicator {
  border-color: var(--text-secondary);
  background: var(--text-secondary);
  opacity: 0.2;
}

/* QueueItemContent (DeerFlow: completed = line-through + faded) */
.todo-item--done .item-label {
  color: var(--text-secondary);
  opacity: 0.5;
  text-decoration: line-through;
}

.item-label {
  flex: 1;
  font-size: 13px;
  color: var(--text-primary);
  line-height: 1.4;
  word-break: break-word;
}

/* Transitions (DeerFlow: duration-300 ease-out) */
.todo-content-enter-active,
.todo-content-leave-active {
  transition: all 0.3s ease-out;
  overflow: hidden;
}

.todo-content-enter-from,
.todo-content-leave-to {
  opacity: 0;
  max-height: 0;
}

/* Dark theme overrides */
:global([data-theme='dark'] .todo-list-panel) {
  background: var(--bg-card, rgba(30, 30, 40, 0.9));
  border-color: var(--border-color, rgba(255, 255, 255, 0.08));
}

:global([data-theme='dark'] .todo-header) {
  background: var(--bg-secondary, rgba(255, 255, 255, 0.03));
}

:global([data-theme='dark'] .todo-header:hover) {
  background: var(--bg-hover, rgba(255, 255, 255, 0.06));
}

:global([data-theme='dark'] .todo-item:hover) {
  background: rgba(255, 255, 255, 0.03);
}
</style>