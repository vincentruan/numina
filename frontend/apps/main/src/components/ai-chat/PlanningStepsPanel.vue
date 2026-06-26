<script setup lang="ts">
/**
 * PlanningStepsPanel — Real-time planning steps from SSE custom events
 *
 * Displays tool call progress during streaming with:
 * - Emoji icons per tool type (R3)
 * - Step summary text (query for websearch, URL for page-fetch)
 * - Status indicators (spinner for running, ✓ for done, ✗ for error)
 * - Collapsible panel: default expanded (R4), toggle "隐藏步骤"/"查看其他 N 个步骤"
 */
import { ref, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import type { PlanningStep } from '@/types/ai-chat/message-group'
import { explainToolCallKey } from '@/utils/ai-chat/tool-icon-map'

const TOOL_EMOJI_MAP: Record<string, string> = {
  web_search: '🔍',
  web_fetch: '🌐',
  image_search: '🔍',
  read_file: '📄',
  write_file: '📝',
  str_replace: '📝',
  bash: '💻',
  present_files: '📎',
  task: '🤖',
  skill: '🧩',
  default: '🔧',
}

/** Map MCP/skill prefixed tool names to their emoji */
function getToolEmoji(toolName: string): string {
  const normalized = toolName.replace(/^(mcp|skill|builtin):\/\//, '')
  return TOOL_EMOJI_MAP[normalized] || TOOL_EMOJI_MAP['default']
}

const props = defineProps<{
  steps: PlanningStep[]
  isStreaming?: boolean
  defaultExpanded?: boolean
}>()

const { t } = useI18n()

const expanded = ref(props.defaultExpanded ?? true)

/** When collapsed, show only the last step */
const visibleSteps = computed(() => {
  if (expanded.value || props.steps.length <= 1) return props.steps
  return [props.steps[props.steps.length - 1]]
})

const hiddenCount = computed(() => {
  if (expanded.value || props.steps.length <= 1) return 0
  return props.steps.length - 1
})

function getStepSummary(step: PlanningStep): string {
  const result = explainToolCallKey(step.toolName, step.args)
  return t(result.key, result.params)
}

function getStepStatusLabel(step: PlanningStep): string {
  switch (step.status) {
    case 'running': return t('aiChat.toolRunning')
    case 'done': return ''
    case 'error': return t('aiChat.toolFailed')
    default: return ''
  }
}
</script>

<template>
  <div v-if="steps.length > 0" class="planning-steps-panel">
    <!-- Toggle button -->
    <button
      class="steps-toggle"
      type="button"
      @click="expanded = !expanded"
    >
      <span class="toggle-icon">{{ expanded ? '▾' : '▸' }}</span>
      <span v-if="expanded">{{ t('aiChat.collapse') }}</span>
      <span v-else>{{ t('aiChat.moreResults', { count: hiddenCount }) }}</span>
    </button>

    <!-- Steps list -->
    <div v-show="expanded" class="steps-list">
      <div
        v-for="step in visibleSteps"
        :key="step.id"
        class="step-item"
        :class="`step-item--${step.status}`"
      >
        <span class="step-emoji" aria-hidden="true">{{ getToolEmoji(step.toolName) }}</span>
        <span class="step-text">{{ getStepSummary(step) }}</span>
        <span v-if="getStepStatusLabel(step)" class="step-status">{{ getStepStatusLabel(step) }}</span>
        <span v-if="step.status === 'running'" class="step-spinner" aria-hidden="true" />
        <span v-if="step.status === 'done'" class="step-done-badge" aria-hidden="true">✓</span>
      </div>
    </div>

    <!-- Collapsed: show last step with "N more" hint -->
    <div v-if="!expanded && steps.length > 1" class="steps-collapsed-last">
      <div
        class="step-item"
        :class="`step-item--${steps[steps.length - 1].status}`"
      >
        <span class="step-emoji" aria-hidden="true">{{ getToolEmoji(steps[steps.length - 1].toolName) }}</span>
        <span class="step-text">{{ getStepSummary(steps[steps.length - 1]) }}</span>
        <span v-if="steps[steps.length - 1].status === 'running'" class="step-spinner" aria-hidden="true" />
        <span v-if="steps[steps.length - 1].status === 'done'" class="step-done-badge" aria-hidden="true">✓</span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.planning-steps-panel {
  margin: 8px 0;
  padding: 10px 12px;
  background: var(--card-bg, rgba(255, 255, 255, 0.04));
  border: 1px solid var(--border-color, rgba(255, 255, 255, 0.08));
  border-radius: 10px;
}

.steps-toggle {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 4px 0;
  background: transparent;
  border: none;
  color: var(--text-secondary, #999);
  font-size: 13px;
  cursor: pointer;
  width: 100%;
  text-align: left;
}

.steps-toggle:hover {
  color: var(--text-primary, #fff);
}

.toggle-icon {
  font-size: 10px;
  width: 12px;
  text-align: center;
}

.steps-list {
  margin-top: 6px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.step-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 4px 0;
  font-size: 13px;
  color: var(--text-primary, #fff);
  line-height: 1.4;
}

.step-emoji {
  flex-shrink: 0;
  font-size: 14px;
  width: 20px;
  text-align: center;
}

.step-text {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.step-status {
  flex-shrink: 0;
  font-size: 11px;
  color: var(--text-secondary, #999);
}

.step-spinner {
  flex-shrink: 0;
  width: 12px;
  height: 12px;
  border: 2px solid var(--van-primary-color, #6366f1);
  border-top-color: transparent;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

.step-done-badge {
  flex-shrink: 0;
  font-size: 12px;
  color: #22c55e;
  font-weight: 600;
}

.step-item--error .step-text {
  color: #f87171;
}

.steps-collapsed-last {
  margin-top: 4px;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

@media (prefers-reduced-motion: reduce) {
  .step-spinner {
    animation: none;
    border-top-color: var(--van-primary-color, #6366f1);
  }
}

/* 375px mobile */
@media (max-width: 375px) {
  .planning-steps-panel {
    padding: 8px 10px;
  }

  .step-item {
    font-size: 12px;
    gap: 6px;
  }

  .step-emoji {
    font-size: 13px;
    width: 18px;
  }
}
</style>
