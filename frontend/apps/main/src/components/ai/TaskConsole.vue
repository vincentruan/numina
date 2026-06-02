<template>
  <div v-if="status !== 'idle'" class="task-console">
    <!-- Header bar -->
    <div class="console-header" @click="toggleOpen">
      <span class="console-status-icon" :class="{ 'icon-spin': status === 'running' || status === 'post_processing' }" aria-hidden="true">
        {{ statusIcon }}
      </span>
      <span class="console-title">{{ title }}</span>
      <span v-if="status === 'queued' && queuePosition" class="console-queue-badge">
        {{ t('aiTask.queuePosition', { n: queuePosition }) }}
      </span>
      <span v-else class="console-elapsed">{{ formattedElapsed }}</span>
      <van-icon :name="isOpen ? 'arrow-up' : 'arrow-down'" class="console-toggle" />
    </div>

    <!-- Body (collapsible) -->
    <div v-show="isOpen" class="console-body">
      <!-- Failed warning bar (R6.4) -->
      <div v-if="status === 'failed'" class="console-error-bar" role="alert">
        <span class="error-bar-text">{{ failureMessage }}</span>
        <button class="error-bar-retry" @click.stop="$emit('retry')">
          {{ t('aiTask.retry') }}
        </button>
      </div>

      <!-- Queued state -->
      <div v-if="status === 'queued'" class="console-queued">
        <van-loading size="16" type="spinner" class="queue-spinner" />
        <span>{{ t('aiTask.queueWaiting') }}</span>
      </div>

      <!-- Phase indicator -->
      <div v-else-if="(status === 'running' || status === 'post_processing') && phase" class="console-phase">
        <span class="phase-dot" :class="`phase-dot--${phase}`" aria-hidden="true"></span>
        <span class="phase-label">{{ phaseLabel }}</span>
      </div>

      <!-- Thinking block (collapsible, auto-collapses when answering starts) -->
      <div v-if="thinkContent" class="console-think-block">
        <button
          class="think-toggle"
          :aria-expanded="thinkOpen"
          @click.stop="thinkOpen = !thinkOpen"
        >
          <span class="think-icon" aria-hidden="true">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <path d="M9.663 17h4.673M12 3a6 6 0 0 1 6 6c0 2.22-1.2 4.16-3 5.2V16a1 1 0 0 1-1 1H10a1 1 0 0 1-1-1v-1.8A6 6 0 0 1 12 3z"/>
              <path d="M9 21h6"/>
            </svg>
          </span>
          <span v-if="thinkDone" class="think-status">
            {{ t('aiChat.thinkDone') }}
            <span v-if="thinkSeconds" class="think-duration">{{ thinkSeconds }}s</span>
          </span>
          <span v-else class="think-status think-status--active">{{ t('aiTask.phase.thinking') }}</span>
          <svg class="think-chevron" :class="{ 'think-chevron--open': thinkOpen }" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
            <polyline points="6 9 12 15 18 9"/>
          </svg>
        </button>
        <div v-if="thinkOpen" class="think-content">{{ thinkContent }}</div>
      </div>

      <!-- Answer content (streaming) -->
      <div v-if="answerContent" ref="answerRef" class="console-answer">
        <!-- eslint-disable-next-line vue/no-v-html -- sanitized via DOMPurify before binding -->
        <div class="answer-text" v-html="renderedAnswer" />
        <span v-if="status === 'running' && phase === 'answering'" class="answer-cursor" aria-hidden="true">▋</span>
      </div>

      <!-- Empty running state (no content yet) -->
      <div v-else-if="(status === 'running' || status === 'post_processing') && !thinkContent" class="console-empty-running">
        <van-loading size="14" type="spinner" />
        <span>{{ status === 'post_processing' ? t('aiTask.phase.postProcessing') : t('aiTask.phase.connecting') }}</span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onUnmounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { marked } from 'marked'
import DOMPurify from 'dompurify'
import type { AITaskPhase } from '@/composables/useAITask'

const props = defineProps<{
  status: 'idle' | 'running' | 'post_processing' | 'queued' | 'completed' | 'failed' | 'timeout' | 'cancelled'
  phase?: AITaskPhase
  thinkContent?: string
  thinkDone?: boolean
  thinkSeconds?: number
  answerContent?: string
  elapsedSeconds: number
  queuePosition?: number | null
  errorCode?: string | null
  modelValue?: boolean // isOpen
}>()

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
  retry: []
}>()

const { t } = useI18n()
const answerRef = ref<HTMLElement | null>(null)
const thinkOpen = ref(false)
let scrollRAF: number | null = null

// v-model contract: honor modelValue when provided, fall back to internal state
const _internalOpen = ref(props.modelValue ?? (props.status === 'running' || props.status === 'queued'))
const isOpen = computed({
  get: () => (props.modelValue !== undefined ? props.modelValue : _internalOpen.value),
  set: (val: boolean) => {
    _internalOpen.value = val
    emit('update:modelValue', val)
  },
})

function toggleOpen() {
  isOpen.value = !isOpen.value
}

// Auto-open on running/queued edge, auto-close on completed.
// R6.4: failed status keeps console open so user can read the natural-language text
watch(
  () => props.status,
  (val, prev) => {
    if (val === 'completed' && prev !== 'completed') isOpen.value = false
    if ((val === 'running' || val === 'queued' || val === 'failed') && (prev === 'idle' || prev === 'queued')) isOpen.value = true
  },
)

// Auto-collapse thinking when answering starts
watch(
  () => props.phase,
  (val) => {
    if (val === 'answering') thinkOpen.value = false
    if (val === 'thinking') thinkOpen.value = true
  },
)

// Auto-scroll answer area when content streams in — coalesced via RAF to avoid
// thrashing on every token
watch(
  () => props.answerContent,
  () => {
    if (props.status !== 'running') return
    if (scrollRAF) return
    scrollRAF = requestAnimationFrame(() => {
      scrollRAF = null
      answerRef.value?.scrollIntoView({ behavior: 'smooth', block: 'end' })
    })
  },
)

onUnmounted(() => {
  if (scrollRAF) {
    cancelAnimationFrame(scrollRAF)
    scrollRAF = null
  }
})

const statusIcon = computed(() => {
  const icons: Partial<Record<typeof props.status, string>> = {
    running: '⏳',
    post_processing: '⏳',
    queued: '🕐',
    completed: '✅',
    failed: '❌',
    timeout: '⏱️',
    cancelled: '⏹️',
  }
  return icons[props.status] ?? '⏳'
})

const title = computed(() => {
  const key = `aiTask.status.${props.status}`
  return t(key)
})

const phaseLabel = computed(() => {
  if (!props.phase) return ''
  return t(`aiTask.phase.${props.phase}`)
})

const formattedElapsed = computed(() => {
  const s = props.elapsedSeconds
  if (s < 60) return `${s}s`
  return `${Math.floor(s / 60)}m${s % 60}s`
})

const renderedAnswer = computed(() => {
  if (!props.answerContent) return ''
  try {
    const html = marked.parse(props.answerContent, { async: false }) as string
    return DOMPurify.sanitize(html)
  } catch {
    return DOMPurify.sanitize(props.answerContent)
  }
})

const failureMessage = computed(() => {
  switch (props.errorCode) {
    case 'rate_limited':
      return t('aiTask.error.rateLimited')
    case 'circuit_open':
      return t('aiTask.error.circuitOpen')
    case 'extraction_failed':
    case 'structured_extraction_failed':
      return t('aiTask.error.extractionFailed')
    case 'agent_stream_error':
      return t('aiTask.error.streamError')
    case 'post_processing_timeout':
      return t('aiTask.error.postProcessingTimeout')
    default:
      return t('aiTask.error.generic')
  }
})
</script>

<style scoped>
.task-console {
  margin: 12px 0;
  border-radius: 12px;
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  overflow: hidden;
}

.console-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 14px;
  cursor: pointer;
  user-select: none;
}

.console-status-icon {
  font-size: 16px;
  flex-shrink: 0;
}

.icon-spin {
  display: inline-block;
  animation: spin 2s linear infinite;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.console-title {
  flex: 1;
  font-size: 13px;
  font-weight: 500;
  color: var(--text-primary);
}

.console-elapsed {
  font-size: 12px;
  color: var(--text-tertiary);
  font-variant-numeric: tabular-nums;
}

.console-queue-badge {
  font-size: 11px;
  color: var(--color-warning, #ff9500);
  background: rgba(255, 149, 0, 0.12);
  padding: 2px 7px;
  border-radius: 10px;
}

.console-toggle {
  color: var(--text-tertiary);
  font-size: 14px;
}

.console-body {
  padding: 0 14px 14px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

/* Queued */
.console-queued {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  color: var(--text-secondary);
  padding: 4px 0;
}

/* Phase indicator */
.console-phase {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: var(--text-secondary);
}

.phase-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  flex-shrink: 0;
}

.phase-dot--connecting { background: var(--text-tertiary); animation: pulse 1.5s ease-in-out infinite; }
.phase-dot--thinking   { background: #a78bfa; animation: pulse 1.2s ease-in-out infinite; }
.phase-dot--answering  { background: var(--color-primary); animation: pulse 1s ease-in-out infinite; }

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.4; }
}

/* Thinking block */
.console-think-block {
  border-radius: 8px;
  background: var(--bg-secondary);
  overflow: hidden;
}

.think-toggle {
  display: flex;
  align-items: center;
  gap: 6px;
  width: 100%;
  padding: 8px 10px;
  background: none;
  border: none;
  cursor: pointer;
  text-align: left;
  color: var(--text-secondary);
  font-size: 12px;
}

.think-icon {
  color: #a78bfa;
  flex-shrink: 0;
  display: flex;
}

.think-status {
  flex: 1;
  display: flex;
  align-items: center;
  gap: 6px;
}

.think-status--active {
  color: #a78bfa;
}

.think-duration {
  color: var(--text-tertiary);
  font-size: 11px;
}

.think-chevron {
  color: var(--text-tertiary);
  transition: transform 0.2s;
  flex-shrink: 0;
}

.think-chevron--open {
  transform: rotate(180deg);
}

.think-content {
  padding: 0 10px 10px;
  font-size: 12px;
  color: var(--text-secondary);
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-word;
}

/* Answer */
.console-answer {
  font-size: 14px;
  color: var(--text-primary);
  line-height: 1.7;
}

.answer-text :deep(p) { margin: 0 0 8px; }
.answer-text :deep(p:last-child) { margin-bottom: 0; }
.answer-text :deep(ul), .answer-text :deep(ol) { padding-left: 18px; margin: 4px 0 8px; }
.answer-text :deep(li) { margin-bottom: 4px; }
.answer-text :deep(strong) { color: var(--text-primary); }
.answer-text :deep(code) { background: var(--bg-secondary); padding: 1px 4px; border-radius: 3px; font-size: 12px; }

.answer-cursor {
  display: inline-block;
  animation: blink 1s step-end infinite;
  color: var(--color-primary);
  margin-left: 1px;
}

@keyframes blink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0; }
}

/* Empty running */
.console-empty-running {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  color: var(--text-secondary);
  padding: 4px 0;
}

/* Failure warning bar (R6.4) */
.console-error-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 12px;
  background: rgba(220, 38, 38, 0.08);
  border-left: 3px solid #dc2626;
  border-radius: 6px;
  font-size: 13px;
  color: var(--text-primary);
}

.error-bar-text {
  flex: 1;
  line-height: 1.5;
}

.error-bar-retry {
  flex-shrink: 0;
  padding: 6px 14px;
  border-radius: 6px;
  border: none;
  background: #dc2626;
  color: #fff;
  font-size: 12px;
  font-weight: 500;
  cursor: pointer;
  white-space: nowrap;
}

.error-bar-retry:hover {
  background: #b91c1c;
}
</style>
