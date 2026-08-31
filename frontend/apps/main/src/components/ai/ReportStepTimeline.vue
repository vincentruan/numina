<template>
  <div class="report-step-timeline" role="region" :aria-label="t('aiReport.title')">
    <!-- Cache banner (互斥 with step3 失败 banner — cache only returns completed) -->
    <div v-if="cached" class="cache-banner" role="status">
      <van-icon name="clock-o" />
      <span>{{ t('aiReport.cacheFresh') }}</span>
      <van-button size="mini" plain type="primary" :loading="streaming" @click="$emit('force')">
        {{ t('aiReport.forceRegenerate') }}
      </van-button>
    </div>

    <!-- Step3 失败 banner (only when step3 errored, no cache) -->
    <div v-else-if="step3Status === 'error'" class="fail-banner" role="alert">
      <van-icon name="warning-o" />
      <span>{{ t('aiReport.step3Failed') }}</span>
      <van-button v-if="hasMarkdownFallback" size="mini" plain @click="$emit('view-markdown')">
        {{ t('aiReport.viewMarkdownFallback') }}
      </van-button>
    </div>

    <van-steps :active="activeStep" :status="vanStepsStatus" direction="vertical" active-color="var(--van-primary-color)">
      <!-- Step 1: markdown 落盘 -->
      <van-step :status="toVanStepStatus(step1Status)">
        <template #active-icon>
          <van-loading size="14px" type="spinner" color="var(--van-primary-color)" />
        </template>
        <template #title>
          <div class="step-title-row" role="button" tabindex="0" :aria-expanded="expandedStep === 1" @click="toggleStep(1)" @keydown.enter="toggleStep(1)">
            <span>{{ t('aiReport.step1') }}</span>
            <van-icon :name="expandedStep === 1 ? 'arrow-up' : 'arrow-down'" class="step-toggle" />
          </div>
        </template>
        <div class="step-desc" :class="{ 'step-desc--shimmer': isStep1Active }">{{ t('aiReport.step1Desc') }}</div>
        <div v-if="expandedStep === 1" class="step-panel">
          <!-- Thinking accumulation (rendered as markdown) -->
          <!-- eslint-disable vue/no-v-html -->
          <div v-if="step1Thinking" class="thinking-text thinking-markdown" aria-live="polite" v-html="renderedThinking" />
          <!-- Tool calls (write_file etc.) -->
          <div v-for="tc in writeToolCalls" :key="tc.id || tc.name" class="tool-call-card">
            <div class="tool-call-name">
              <van-icon :name="resolveToolIcon(tc.name)" />
              {{ resolveToolLabel(tc.name) }}
            </div>
            <div v-if="getToolResult(tc.id)" class="tool-result-done">
              <van-icon name="success" /> {{ t('aiReport.done') }}
            </div>
            <van-loading v-else-if="isStep1Active" size="12" type="spinner" />
          </div>
          <div v-if="!step1Thinking && !writeToolCalls.length && isStep1Active" class="panel-hint">
            {{ progressMessage || t('aiHub.reportGenerating') }}
          </div>
        </div>
      </van-step>

      <!-- Step 2: JSON 输出 -->
      <van-step :status="toVanStepStatus(step2Status)">
        <template #active-icon>
          <van-loading size="14px" type="spinner" color="var(--van-primary-color)" />
        </template>
        <template #title>
          <div class="step-title-row" role="button" tabindex="0" :aria-expanded="expandedStep === 2" @click="toggleStep(2)" @keydown.enter="toggleStep(2)">
            <span>{{ t('aiReport.step2') }}</span>
            <van-icon :name="expandedStep === 2 ? 'arrow-up' : 'arrow-down'" class="step-toggle" />
          </div>
        </template>
        <div class="step-desc" :class="{ 'step-desc--shimmer': isStep2Active }">{{ t('aiReport.step2Desc') }}</div>
        <div v-if="expandedStep === 2" class="step-panel">
          <div v-if="step2Status === 'error'" class="step-error">{{ t('aiReport.step2JsonFailed') }}</div>
          <div v-else-if="step2Json" class="json-panel">
            <van-button class="json-copy" size="mini" plain icon="description" @click="copyJson">{{ t('aiReport.copy') }}</van-button>
            <pre class="json-pre">{{ formattedJson }}</pre>
          </div>
          <div v-else-if="isStep2Active" class="panel-hint">
            <van-loading size="12" type="spinner" /> {{ t('aiHub.reportGenerating') }}
          </div>
        </div>
      </van-step>

      <!-- Step 3: 落库 (no expand) -->
      <van-step :status="toVanStepStatus(step3Status)">
        <template #active-icon>
          <van-loading size="14px" type="spinner" color="var(--van-primary-color)" />
        </template>
        <template #title>
          <span>{{ t('aiReport.step3') }}</span>
        </template>
        <div class="step-desc" :class="{ 'step-desc--shimmer': isStep3Active }">{{ t('aiReport.step3Desc') }}</div>
      </van-step>
    </van-steps>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { showSuccessToast, showFailToast } from 'vant'
import { marked } from 'marked'
import DOMPurify from 'dompurify'
import type { StepStatus, ToolCallInfo, ToolResultInfo } from '@/composables/useReportStream'

const props = defineProps<{
  step1Status: StepStatus
  step2Status: StepStatus
  step3Status: StepStatus
  step1Thinking: string
  toolCalls: ToolCallInfo[]
  toolResults: ToolResultInfo[]
  step2Json: Record<string, unknown> | null
  streaming: boolean
  cached: boolean
  progressMessage: string
  hasMarkdownFallback?: boolean
}>()

defineEmits<{
  (e: 'force'): void
  (e: 'view-markdown'): void
}>()

const { t } = useI18n()

const THINKING_PURIFY_CONFIG = {
  USE_PROFILES: { html: true },
  ALLOW_DATA_ATTR: false,
} as const

const renderedThinking = computed(() => {
  if (!props.step1Thinking) return ''
  const raw = marked.parse(props.step1Thinking, { async: false }) as string
  return DOMPurify.sanitize(raw, THINKING_PURIFY_CONFIG)
})

const expandedStep = ref<number | null>(1)

function toggleStep(step: number): void {
  expandedStep.value = expandedStep.value === step ? null : step
}

const activeStep = computed(() => {
  // van-steps `active` = index of the current step (0-based).
  if (props.step1Status === 'waiting' || props.step1Status === 'process') return 0
  if (props.step2Status === 'waiting' || props.step2Status === 'process') return 1
  if (props.step3Status === 'waiting' || props.step3Status === 'process') return 2
  // all finish → active past last
  return 3
})

const vanStepsStatus = computed<'process' | 'finish' | 'error'>(() => {
  if (props.step3Status === 'error') return 'error'
  if (props.step2Status === 'error') return 'error'
  if (props.step1Status === 'error') return 'error'
  if (props.step3Status === 'finish') return 'finish'
  return 'process'
})

function toVanStepStatus(s: StepStatus): 'wait' | 'process' | 'finish' | 'error' {
  switch (s) {
    case 'waiting': return 'wait'
    case 'process': return 'process'
    case 'finish': return 'finish'
    case 'error': return 'error'
  }
}

const isStep1Active = computed(() =>
  props.step1Status === 'process' || (props.step1Status === 'waiting' && props.streaming),
)
const isStep2Active = computed(() => props.step2Status === 'process')
const isStep3Active = computed(() => props.step3Status === 'process')

const writeToolCalls = computed(() =>
  props.toolCalls.filter((tc) => tc.name.includes('write_file') || tc.name.includes('read_file')),
)

function getToolResult(toolCallId: string): ToolResultInfo | undefined {
  if (!toolCallId) return undefined
  return props.toolResults.find((r) => r.tool_call_id === toolCallId)
}

function resolveToolIcon(name: string): string {
  if (name.includes('write_file')) return 'edit'
  if (name.includes('read_file')) return 'eye-o'
  if (name.includes('get_assets') || name.includes('get_family')) return 'balance-o'
  return 'orders-o'
}

function resolveToolLabel(name: string): string {
  const map: Record<string, string> = {
    write_file: t('aiReport.step1'),
    read_file: t('aiReport.step2'),
  }
  return map[name] || name
}

const formattedJson = computed(() => {
  if (!props.step2Json) return ''
  try {
    return JSON.stringify(props.step2Json, null, 2)
  } catch {
    return String(props.step2Json)
  }
})

async function copyJson(): Promise<void> {
  try {
    await navigator.clipboard.writeText(formattedJson.value)
    showSuccessToast(t('aiReport.copied'))
  } catch {
    // Fallback for non-secure contexts (LAN-IP HTTP dev)
    const ta = document.createElement('textarea')
    ta.value = formattedJson.value
    document.body.appendChild(ta)
    ta.select()
    try {
      document.execCommand('copy')
      showSuccessToast(t('aiReport.copied'))
    } catch {
      showFailToast(t('toast.operationFailed'))
    }
    document.body.removeChild(ta)
  }
}
</script>

<style scoped>
.report-step-timeline {
  margin: 12px 16px;
  padding: 16px;
  background: var(--bg-primary);
  border-radius: 16px;
}
.cache-banner,
.fail-banner {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 12px;
  border-radius: 8px;
  margin-bottom: 12px;
  font-size: 13px;
}
.cache-banner {
  background: rgba(25, 137, 250, 0.08);
  color: var(--van-primary-color);
}
.fail-banner {
  background: rgba(220, 38, 38, 0.08);
  color: #dc2626;
}
[data-theme='dark'] .fail-banner {
  color: #f87171;
}
.cache-banner :deep(.van-button),
.fail-banner :deep(.van-button) {
  margin-left: auto;
  flex-shrink: 0;
}
.step-title-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  cursor: pointer;
}
.step-toggle {
  font-size: 12px;
  color: var(--text-secondary);
}
.step-desc {
  font-size: 12px;
  color: var(--text-secondary);
  margin-top: 2px;
}
.step-desc--shimmer {
  background: linear-gradient(
    90deg,
    var(--text-secondary) 0%,
    color-mix(in srgb, var(--van-primary-color) 50%, var(--text-secondary)) 50%,
    var(--text-secondary) 100%
  );
  background-size: 200% 100%;
  background-clip: text;
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  animation: step-shimmer 1.8s ease-in-out infinite;
}
@keyframes step-shimmer {
  0% { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}
.step-panel {
  margin-top: 10px;
  font-size: 13px;
  color: var(--text-primary);
}
.thinking-text {
  white-space: pre-wrap;
  line-height: 1.6;
  margin-bottom: 8px;
  max-height: 40vh;
  overflow-y: auto;
}
.thinking-markdown {
  white-space: normal;
  :deep(p) {
    margin: 0 0 6px;
    &:last-child { margin-bottom: 0; }
  }
  :deep(strong) {
    font-weight: 600;
    color: var(--text-primary);
  }
  :deep(ul), :deep(ol) {
    margin: 4px 0;
    padding-left: 18px;
  }
  :deep(li) {
    margin: 2px 0;
  }
  :deep(h1), :deep(h2), :deep(h3) {
    margin: 10px 0 4px;
    font-weight: 600;
    font-size: 13px;
    color: var(--text-primary);
  }
  :deep(code) {
    background: var(--bg-secondary);
    padding: 1px 4px;
    border-radius: 3px;
    font-size: 12px;
  }
}
.tool-call-card {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 8px;
  background: var(--bg-secondary);
  border-radius: 6px;
  margin-bottom: 4px;
  font-size: 12px;
}
.tool-call-name {
  display: flex;
  align-items: center;
  gap: 4px;
  flex: 1;
}
.tool-result-done {
  color: #4caf50;
  font-size: 11px;
}
.panel-hint {
  display: flex;
  align-items: center;
  gap: 6px;
  color: var(--text-secondary);
  font-size: 12px;
}
.step-error {
  color: #dc2626;
  font-size: 12px;
}
.json-panel {
  position: relative;
  margin-top: 4px;
}
.json-copy {
  position: absolute;
  top: 4px;
  right: 4px;
  z-index: 1;
}
.json-pre {
  background: var(--bg-secondary);
  border-radius: 6px;
  padding: 10px;
  font-size: 11px;
  line-height: 1.5;
  overflow-x: auto;
  white-space: pre;
  word-break: normal;
  max-height: 50vh;
  overflow-y: auto;
  margin: 0;
}
/* 移动端竖屏: JSON 面板 50vh + sticky 复制按钮 */
@media (max-width: 767px) {
  .json-pre {
    max-height: 50vh;
  }
  .json-copy {
    position: sticky;
    bottom: 8px;
    right: auto;
    top: auto;
    align-self: flex-end;
  }
}
</style>
