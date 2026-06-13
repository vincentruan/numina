<script setup lang="ts">
/**
 * ToolCallList — Flat tool call visualization following DeerFlow ChainOfThought pattern
 *
 * DeerFlow reference: frontend/src/components/workspace/messages/ChainOfThought.tsx
 *
 * Key patterns:
 * - Flat list of tool calls (NO nesting)
 * - Each tool call shown as a card with: icon, name, status, result summary
 * - Collapsible result preview (click to expand)
 * - Status indicators: running (shimmer), done (check), error (x)
 */
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import type { ProcessStep } from '@/types/agent-stream'

interface Props {
  steps: ProcessStep[]
  status?: 'running' | 'done' | 'error' | 'interrupted'
}

const _props = defineProps<Props>()

const { t } = useI18n()

// Track expanded state for each tool call
const expandedSteps = ref<Set<string>>(new Set())

function toggleExpanded(stepId: string) {
  if (expandedSteps.value.has(stepId)) {
    expandedSteps.value.delete(stepId)
  } else {
    expandedSteps.value.add(stepId)
  }
}

// Tool icon mapping
const toolIconMap: Record<string, { icon: string; color: string }> = {
  search: { icon: '🔍', color: '#22c55e' },
  read_file: { icon: '📄', color: '#818cf8' },
  write_file: { icon: '✏️', color: '#f59e0b' },
  bash: { icon: '⚡', color: '#6366f1' },
  list_directory: { icon: '📁', color: '#3b82f6' },
  web_search: { icon: '🌐', color: '#06b6d4' },
  mcp: { icon: '🔌', color: '#a855f7' },
  default: { icon: '⚙️', color: '#6b7280' },
}

function getToolDisplay(step: ProcessStep): { icon: string; color: string; name: string } {
  const name = step.displayName ?? step.name ?? 'Tool'
  const key = step.name?.toLowerCase() ?? 'default'
  const mapping = toolIconMap[key] ?? toolIconMap.default
  return {
    icon: step.icon ?? mapping.icon,
    color: mapping.color,
    name,
  }
}

// Status icon helper (for future use)
function _getStatusIcon(status: string) {
  switch (status) {
    case 'done':
      return { svg: '<polyline points="20 6 9 17 4 12"/>', color: '#22c55e' }
    case 'error':
      return { svg: '<circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/>', color: '#f87171' }
    case 'running':
      return { svg: '<circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/>', color: '#818cf8' }
    default:
      return { svg: '', color: '#6b7280' }
  }
}

// Format execution time
function formatTime(ms?: number): string {
  if (!ms) return ''
  if (ms < 1000) return `${ms}ms`
  const seconds = Math.floor(ms / 1000)
  return `${seconds}s`
}
</script>

<template>
  <div class="tool-call-list">
    <div
      v-for="step in steps"
      :key="step.id"
      class="tool-card"
      :class="`tool-card--${step.status ?? 'running'}`"
    >
      <!-- Header: icon, name, status -->
      <div class="tool-header" @click="toggleExpanded(step.id)">
        <!-- Tool icon -->
        <span class="tool-icon" :style="{ color: getToolDisplay(step).color }">
          {{ getToolDisplay(step).icon }}
        </span>

        <!-- Tool name -->
        <span class="tool-name">{{ getToolDisplay(step).name }}</span>

        <!-- Status indicator -->
        <span class="tool-status" :class="`status--${step.status ?? 'running'}`">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" aria-hidden="true">
            <polyline v-if="step.status === 'done'" points="20 6 9 17 4 12"/>
            <template v-else-if="step.status === 'error'">
              <circle cx="12" cy="12" r="10"/>
              <line x1="15" y1="9" x2="9" y2="15"/>
              <line x1="9" y1="9" x2="15" y2="15"/>
            </template>
            <template v-else>
              <circle cx="12" cy="12" r="10"/>
              <path d="M12 6v6l4 2"/>
            </template>
          </svg>
        </span>

        <!-- Execution time -->
        <span v-if="step.elapsedMs" class="tool-time">{{ formatTime(step.elapsedMs) }}</span>

        <!-- Expand indicator -->
        <span class="expand-indicator" :class="{ expanded: expandedSteps.has(step.id) }">
          <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" aria-hidden="true">
            <polyline points="6 9 12 15 18 9"/>
          </svg>
        </span>
      </div>

      <!-- Result summary (collapsed view) -->
      <div v-if="!expandedSteps.has(step.id) && step.resultSummary" class="tool-summary">
        {{ step.resultSummary }}
      </div>

      <!-- Expanded result preview -->
      <transition name="tool-result">
        <div v-if="expandedSteps.has(step.id)" class="tool-result">
          <!-- Arguments -->
          <div v-if="step.args && Object.keys(step.args).length > 0" class="result-section">
            <span class="result-label">{{ t('aiChat.toolArgs') }}</span>
            <pre class="result-value">{{ JSON.stringify(step.args, null, 2) }}</pre>
          </div>

          <!-- Result data -->
          <div v-if="step.resultSummary || step.data" class="result-section">
            <span class="result-label">{{ t('aiChat.toolResult') }}</span>
            <pre class="result-value">{{ step.resultSummary ?? JSON.stringify(step.data, null, 2) }}</pre>
          </div>

          <!-- Error message -->
          <div v-if="step.error" class="result-section result-section--error">
            <span class="result-label">{{ t('aiChat.toolError') }}</span>
            <pre class="result-value">{{ step.error }}</pre>
          </div>
        </div>
      </transition>

      <!-- Running shimmer -->
      <div v-if="step.status === 'running'" class="running-shimmer" aria-hidden="true" />
    </div>
  </div>
</template>

<style scoped>
.tool-call-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-bottom: 12px;
}

/* Tool card */
.tool-card {
  background: rgba(0, 0, 0, 0.04);
  border: 1px solid rgba(0, 0, 0, 0.08);
  border-radius: 8px;
  overflow: hidden;
  position: relative;
}

.tool-card--running {
  border-color: rgba(129, 140, 248, 0.2);
}

.tool-card--done {
  border-color: rgba(34, 197, 94, 0.2);
}

.tool-card--error {
  border-color: rgba(248, 113, 113, 0.2);
}

/* Header */
.tool-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 12px;
  cursor: pointer;
  transition: background 0.15s;
}

.tool-header:hover {
  background: rgba(0, 0, 0, 0.02);
}

/* Tool icon */
.tool-icon {
  font-size: 16px;
}

/* Tool name */
.tool-name {
  flex: 1;
  font-size: 13px;
  font-weight: 500;
  color: var(--text-primary);
}

/* Status */
.tool-status {
  display: flex;
  align-items: center;
}

.status--running {
  color: #818cf8;
  animation: spin 2s linear infinite;
}

.status--done {
  color: #22c55e;
}

.status--error {
  color: #f87171;
}

/* Time */
.tool-time {
  font-size: 11px;
  color: var(--text-secondary);
  font-variant-numeric: tabular-nums;
}

/* Expand indicator */
.expand-indicator {
  color: var(--text-secondary);
  transition: transform 0.2s;
}

.expand-indicator.expanded {
  transform: rotate(180deg);
}

/* Summary */
.tool-summary {
  padding: 8px 12px 10px;
  font-size: 12px;
  color: var(--text-secondary);
  line-height: 1.5;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* Result preview */
.tool-result {
  padding: 12px;
  background: rgba(0, 0, 0, 0.02);
  border-top: 1px solid rgba(0, 0, 0, 0.06);
}

.result-section {
  margin-bottom: 8px;
}

.result-section:last-child {
  margin-bottom: 0;
}

.result-section--error {
  color: #f87171;
}

.result-label {
  display: block;
  font-size: 11px;
  font-weight: 500;
  color: var(--text-secondary);
  margin-bottom: 4px;
}

.result-value {
  font-family: 'SF Mono', Monaco, 'Cascadia Code', monospace;
  font-size: 12px;
  line-height: 1.5;
  color: var(--text-primary);
  white-space: pre-wrap;
  word-break: break-word;
  margin: 0;
  background: transparent;
}

/* Running shimmer */
.running-shimmer {
  position: absolute;
  inset: 0;
  background: linear-gradient(
    90deg,
    transparent 0%,
    rgba(129, 140, 248, 0.08) 50%,
    transparent 100%
  );
  animation: shimmer 2s infinite linear;
  pointer-events: none;
}

/* Transitions */
.tool-result-enter-active,
.tool-result-leave-active {
  transition: all 0.2s ease;
}

.tool-result-enter-from,
.tool-result-leave-to {
  opacity: 0;
  max-height: 0;
}

@keyframes shimmer {
  0% { transform: translateX(-100%); }
  100% { transform: translateX(100%); }
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

/* Light theme */
@media (prefers-color-scheme: light) {
  :global(.theme-light) .tool-card {
    background: rgba(0, 0, 0, 0.02);
    border-color: rgba(0, 0, 0, 0.06);
  }

  :global(.theme-light) .tool-result {
    background: rgba(0, 0, 0, 0.02);
  }
}
</style>