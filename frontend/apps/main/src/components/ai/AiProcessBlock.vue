<template>
  <div class="ai-process-block" :class="{ 'is-collapsed': !isExpanded }">
    <!-- Header -->
    <div class="process-header" @click="toggleExpand">
      <div class="process-icon" :class="statusClass">
        <AiLogo :state="logoState" />
      </div>
      <div class="process-info">
        <span class="process-title" :class="{ 'is-thinking': isShimmerActive }">{{ titleLabel }}</span>
        <span class="process-status">{{ subtitleLabel }}</span>
      </div>
      <span class="process-elapsed">{{ formattedElapsed }}</span>
      <van-icon :name="isExpanded ? 'arrow-down' : 'arrow-up'" class="process-toggle" />
    </div>

    <!-- Plan progress bar — rendered between header and body, outside the body transition.
         Conditionally shown when planSteps are available. Smooth max-height appearance. -->
    <Transition name="plan-bar">
      <AiPlanProgressBar
        v-if="displayPlanSteps.length > 0"
        :steps="displayPlanSteps"
        :active-step-index="activeStepIndex"
        class="process-plan-bar"
        @step-tap="onStepTap"
      />
    </Transition>

    <!-- Body (collapsible) — unified steps rendering preserves arrival order between reasoning and tool calls (spec §3.3). U3: fade+slide collapse transition. -->
    <Transition name="process-body">
      <div v-show="isExpanded" class="process-body" role="list">
      <AiStepBlock
        v-for="(step, index) in steps"
        :id="stepProps(step).id"
        :key="step.id"
        :ref="(el) => registerStepRef(step.id, el)"
        :is-last="index === steps.length - 1"
        :type="stepProps(step).type"
        :status="stepProps(step).status"
        :content="stepProps(step).content"
        :name="stepProps(step).name"
        :display-name="stepProps(step).displayName"
        :icon="stepProps(step).icon"
        :tool-type="stepProps(step).toolType"
        :args="stepProps(step).args"
        :result-summary="stepProps(step).resultSummary"
        :error="stepProps(step).error"
        :result="stepProps(step).result"
        :elapsed-ms="stepProps(step).elapsedMs"
        :default-expanded="stepProps(step).defaultExpanded"
        :compressed="stepProps(step).compressed"
        :progress-message="stepProps(step).progressMessage"
        :title="stepProps(step).title"
        :description="stepProps(step).description"
        :task-id="stepProps(step).taskId"
        :url="stepProps(step).url"
        :path="stepProps(step).path"
        :kind="stepProps(step).kind"
        :auto-collapse-signal="reasoningAutoCollapse"
      />

      <!-- Empty running state -->
      <div v-if="status === 'running' && steps.length === 0" class="process-empty">
        <van-loading size="14" type="spinner" />
        <span>{{ t('aiProcess.connecting') }}</span>
      </div>

      <!-- Error state (spec §5.4): error message + retry button -->
      <div v-if="status === 'error'" class="process-error">
        <p class="process-error-msg">{{ errorMessage || t('aiProcess.errorMessage') }}</p>
        <button class="process-retry-btn" @click="onRetry">
          <van-icon name="replay" />
          <span>{{ t('aiProcess.retry') }}</span>
        </button>
      </div>
    </div>
    </Transition>
  </div>
</template>

<script setup lang="ts">
import { computed, onUnmounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import AiStepBlock from './AiStepBlock.vue'
import AiLogo from './AiLogo.vue'
import AiPlanProgressBar from './AiPlanProgressBar.vue'
import { usePlanInference } from '@/composables/usePlanInference'
import type { ProcessStep, PlanStep } from '@/types/agent-stream'

const props = defineProps<{
  status: 'running' | 'done' | 'error' | 'interrupted'
  elapsedMs: number
  steps: ProcessStep[]
  defaultExpanded?: boolean
  errorMessage?: string
  phase?: 'connecting' | 'thinking' | 'answering' | 'done' | 'error'
  reasoningStartTime?: number | null
  planSteps?: PlanStep[]
  planSource?: 'explicit' | 'inferred' | null
}>()

const emit = defineEmits<{
  (e: 'toggle-expand', expanded: boolean): void
  (e: 'retry'): void
}>()

const { t } = useI18n()
const isExpanded = ref(props.defaultExpanded ?? props.status === 'running')

function toggleExpand() {
  isExpanded.value = !isExpanded.value
  emit('toggle-expand', isExpanded.value)
}

function onRetry() {
  emit('retry')
}

// Auto-expand when status goes to running, collapse when done
watch(
  () => props.status,
  (val, prev) => {
    if (val === 'running' && prev !== 'running') {
      isExpanded.value = true
      return
    }
    if (val === 'done' && prev === 'running') {
      isExpanded.value = false
      return
    }
    if (val === 'error') {
      isExpanded.value = true
    }
  },
)

// Per-reasoning-step auto-collapse signal (replaces block-level auto-collapse)
const reasoningAutoCollapse = computed(
  () => props.phase === 'answering' || props.phase === 'done',
)

// ---------- Plan inference wiring ----------
// When planSource is 'inferred', derive plan steps from process steps.
// When planSource is 'explicit', the caller has passed explicit planSteps — use those directly.

const stepsRef = computed(() => props.steps)
const planSourceRef = computed(() => props.planSource ?? null)

const { inferredPlanSteps } = usePlanInference({
  steps: stepsRef,
  planSource: planSourceRef,
})

// The plan steps to display: explicit takes priority, inferred as fallback
const displayPlanSteps = computed<PlanStep[]>(() => {
  if (props.planSource === 'explicit' && props.planSteps && props.planSteps.length > 0) {
    return props.planSteps
  }
  if (props.planSource === 'inferred' || props.planSource == null) {
    return inferredPlanSteps.value
  }
  return []
})

// Active step index: first step with status 'active', or last done step index
const activeStepIndex = computed<number>(() => {
  const steps = displayPlanSteps.value
  const activeIdx = steps.findIndex((s) => s.status === 'active')
  if (activeIdx >= 0) return activeIdx
  // Fall back to last done step
  let lastDone = -1
  for (let i = 0; i < steps.length; i++) {
    if (steps[i].status === 'done') lastDone = i
  }
  return lastDone
})

// ---------- Step element registry for scroll-to-step ----------
// Maps stepId → the DOM element of the corresponding AiStepBlock
const stepElMap = new Map<string, Element>()

function registerStepRef(stepId: string, el: unknown) {
  if (el && typeof el === 'object' && '$el' in el) {
    stepElMap.set(stepId, (el as { $el: Element }).$el)
  } else if (el instanceof Element) {
    stepElMap.set(stepId, el)
  } else {
    stepElMap.delete(stepId)
  }
}

// Highlight class added briefly on scroll-to target
const highlightedStepId = ref<string | null>(null)
let highlightTimer: ReturnType<typeof setTimeout> | null = null

function onStepTap(stepId: string) {
  // Find the corresponding process step for this plan step.
  // Plan step IDs from plan.update are todo IDs — match by position when no direct match.
  // For inferred steps the id may be 'inferred-N'; for explicit steps id === todo.id.
  // Strategy: look for a step element already registered. If the plan step is explicit,
  // we look for a tool_call or progress step at the same index position in the steps array.
  const planIdx = displayPlanSteps.value.findIndex((s) => s.id === stepId)

  // Try direct id match first (inferred steps reuse process step ids indirectly)
  let targetEl: Element | undefined = stepElMap.get(stepId)

  // If not found by id, try by positional mapping to process steps
  if (!targetEl && planIdx >= 0) {
    // Map plan step index to the closest process step index
    const processSteps = props.steps
    const targetProcessIdx = Math.min(planIdx, processSteps.length - 1)
    if (targetProcessIdx >= 0) {
      const processStep = processSteps[targetProcessIdx]
      if (processStep) {
        targetEl = stepElMap.get(processStep.id)
      }
    }
  }

  if (!targetEl) return

  // Check if element is in viewport
  const rect = targetEl.getBoundingClientRect()
  const inViewport = rect.top >= 0 && rect.bottom <= window.innerHeight

  if (!inViewport) {
    targetEl.scrollIntoView({ behavior: 'smooth', block: 'center' })
  }

  // Add brief 200ms highlight flash
  if (highlightTimer) clearTimeout(highlightTimer)
  highlightedStepId.value = stepId
  highlightTimer = setTimeout(() => {
    highlightedStepId.value = null
    highlightTimer = null
  }, 200)
}

// Map ProcessStep union → AiStepBlock props
interface StepProps {
  type: 'reasoning' | 'tool_call' | 'subagent' | 'artifact' | 'progress'
  id: string
  status: 'pending' | 'streaming' | 'running' | 'done' | 'error' | 'failed'
  content?: string
  name?: string
  displayName?: string
  icon?: string
  toolType?: string
  args?: Record<string, unknown>
  resultSummary?: string
  error?: string
  result?: string
  elapsedMs?: number
  defaultExpanded?: boolean
  compressed?: boolean
  progressMessage?: string
  title?: string
  description?: string
  taskId?: string
  url?: string
  path?: string
  kind?: 'data' | 'link' | 'image' | 'file' | 'other' | 'report'
}

function stepProps(step: ProcessStep): StepProps {
  // Extract status with proper union type mapping for AiStepBlock
  const statusMap: Record<string, 'pending' | 'streaming' | 'running' | 'done' | 'error' | 'failed'> = {
    'streaming': 'streaming',
    'pending': 'pending',
    'running': 'running',
    'done': 'done',
    'error': 'error',
    'failed': 'failed',
  }

  // Artifact type doesn't have status - use 'done' as default
  const stepStatus = step.type === 'artifact' ? 'done' : step.status
  const base: StepProps = {
    type: step.type,
    id: step.id,
    status: statusMap[stepStatus] || stepStatus,
  }

  switch (step.type) {
    case 'reasoning':
      base.content = step.content
      base.elapsedMs = step.elapsedMs
      break
    case 'tool_call':
      base.name = step.name
      base.displayName = step.displayName
      base.icon = step.icon
      base.toolType = step.toolType
      base.args = step.args
      base.resultSummary = step.resultSummary
      base.error = step.error
      base.elapsedMs = step.elapsedMs
      base.compressed = step.status === 'done' || step.status === 'running'
      break
    case 'subagent':
      base.taskId = step.taskId
      base.title = step.title
      base.description = step.description
      base.result = step.result
      base.error = step.error
      break
    case 'artifact':
      base.title = step.title
      base.url = step.url
      base.path = step.path
      break
    case 'progress':
      base.title = step.title
      base.description = step.description
      break
  }
  return base
}

// Tick once per second while phase is thinking
const nowMs = ref(Date.now())
let tickInterval: ReturnType<typeof setInterval> | null = null

function startTick() {
  if (tickInterval) return
  tickInterval = setInterval(() => {
    nowMs.value = Date.now()
  }, 1000)
}

function stopTick() {
  if (tickInterval) {
    clearInterval(tickInterval)
    tickInterval = null
  }
}

watch(
  () => props.phase,
  (val) => {
    if (val === 'thinking') {
      nowMs.value = Date.now()
      startTick()
    } else {
      stopTick()
    }
  },
  { immediate: true },
)

onUnmounted(() => {
  stopTick()
  if (highlightTimer) clearTimeout(highlightTimer)
  stepElMap.clear()
})

const logoState = computed<'idle' | 'thinking' | 'done' | 'error'>(() => {
  if (props.status === 'error') return 'error'
  if (props.status === 'done') return 'done'
  if (props.phase === 'thinking' || props.phase === 'connecting') return 'thinking'
  return 'idle'
})

const isShimmerActive = computed(
  () => props.status === 'running' && (props.phase === 'thinking' || props.phase === 'connecting'),
)

const statusClass = computed(() => {
  switch (props.status) {
    case 'running': return 'status-running'
    case 'done': return 'status-done'
    case 'error': return 'status-error'
    case 'interrupted': return 'status-interrupted'
    default: return ''
  }
})

const titleLabel = computed(() => {
  if (props.status === 'error') return t('aiProcess.errorTitle')
  if (props.phase === 'thinking' || props.phase === 'connecting') return t('aiProcess.thinkingTitle')
  if (props.phase === 'answering') return t('aiProcess.answeringTitle')
  return t('aiProcess.title')
})

const subtitleLabel = computed(() => {
  if (props.phase === 'thinking' && props.reasoningStartTime != null) {
    const seconds = Math.max(0, Math.floor((nowMs.value - props.reasoningStartTime) / 1000))
    return t('aiProcess.elapsedSeconds', { seconds })
  }
  switch (props.status) {
    case 'running': return t('aiProcess.statusRunning')
    case 'done': return t('aiProcess.statusDone')
    case 'error': return t('aiProcess.statusError')
    default: return ''
  }
})

const formattedElapsed = computed(() => {
  const ms = props.elapsedMs
  if (ms < 1000) return `${ms}ms`
  const s = Math.floor(ms / 1000)
  if (s < 60) return `${s}s`
  return `${Math.floor(s / 60)}m${s % 60}s`
})
</script>

<style scoped>
.ai-process-block {
  margin: 12px 0;
  border-radius: 8px;
  background: var(--card-bg);
  border: 1px solid var(--color-card-border);
  overflow: hidden;
}

.is-collapsed {
  background: var(--bg-secondary);
  border-color: var(--color-card-border);
}

.process-header {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 14px;
  cursor: pointer;
  user-select: none;
}

.process-icon {
  width: 28px;
  height: 28px;
  border-radius: 4px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.status-running {
  background: var(--color-action-blue);
  animation: pulse 1.5s ease-in-out infinite;
}

.status-done {
  background: var(--color-success);
}

.status-error {
  background: var(--color-error);
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.6; }
}

.process-info {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.process-title {
  font-size: 13px;
  font-weight: 500;
  color: var(--text-primary);
}

.process-status {
  font-size: 12px;
  color: var(--text-secondary);
}

.process-elapsed {
  font-size: 12px;
  color: var(--text-tertiary);
  font-variant-numeric: tabular-nums;
}

.process-toggle {
  color: var(--text-secondary);
  font-size: 16px;
}

.process-body {
  padding: 10px 14px;
  border-top: 1px solid var(--separator);
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.process-empty {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  color: var(--text-secondary);
}

.process-error {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 10px 12px;
  border-radius: 4px;
  background: rgba(var(--color-error-rgb), 0.08);
  border: 1px solid var(--color-error);
}

.process-error-msg {
  margin: 0;
  font-size: 13px;
  color: var(--color-error);
  line-height: 1.5;
  word-break: break-word;
}

.process-retry-btn {
  align-self: flex-start;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 12px;
  font-size: 13px;
  color: var(--color-error);
  background: var(--card-bg);
  border: 1px solid var(--color-error);
  border-radius: 4px;
  cursor: pointer;
}

.process-retry-btn:hover {
  background: rgba(var(--color-error-rgb), 0.08);
}

/* U3: Shimmer animation on thinking title — CSS gradient sweep, 2s loop */
.process-title.is-thinking {
  background-image: linear-gradient(
    90deg,
    var(--text-primary) 0%,
    var(--text-primary) 40%,
    var(--color-action-blue) 50%,
    var(--text-primary) 60%,
    var(--text-primary) 100%
  );
  background-size: 200% 100%;
  background-clip: text;
  -webkit-background-clip: text;
  color: transparent;
  animation: shimmer-sweep 2s ease-in-out infinite;
}

@keyframes shimmer-sweep {
  from { background-position: 100% center; }
  to { background-position: 0% center; }
}

/* Reduced-motion: show static text, no animation */
@media (prefers-reduced-motion: reduce) {
  .process-title.is-thinking {
    background-image: none;
    background-clip: unset;
    -webkit-background-clip: unset;
    color: var(--text-primary);
    animation: none;
  }
}

/* Plan progress bar — sits between header and body */
.process-plan-bar {
  padding: 4px 14px;
  border-top: 1px solid var(--separator);
}

/* Smooth appearance transition for the plan bar */
.plan-bar-enter-active,
.plan-bar-leave-active {
  transition: max-height 0.3s ease, opacity 0.2s ease;
  overflow: hidden;
}

.plan-bar-enter-from,
.plan-bar-leave-to {
  max-height: 0;
  opacity: 0;
}

.plan-bar-enter-to,
.plan-bar-leave-from {
  max-height: 40px;
  opacity: 1;
}

/* U3: fade+slide transition for process-body collapse */
.process-body-enter-active,
.process-body-leave-active {
  transition: max-height 0.3s ease, opacity 0.2s ease;
  overflow: hidden;
}

.process-body-enter-from,
.process-body-leave-to {
  max-height: 0;
  opacity: 0;
}

.process-body-enter-to,
.process-body-leave-from {
  max-height: 800px;
  opacity: 1;
}

/* Mobile responsive (spec §8 mobile risk mitigation) */
@media (max-width: 768px) {
  .ai-process-block {
    margin: 8px 0;
  }

  .process-header {
    padding: 10px 12px;
    gap: 8px;
  }

  .process-icon {
    width: 24px;
    height: 24px;
  }

  .process-info {
    min-width: 0;
  }

  .process-title {
    font-size: 12px;
  }

  .process-status,
  .process-elapsed {
    font-size: 11px;
  }

  .process-body {
    padding: 8px 10px;
    gap: 8px;
  }

  .process-error {
    padding: 8px 10px;
  }

  .process-error-msg {
    font-size: 12px;
  }

  .process-retry-btn {
    font-size: 12px;
    padding: 6px 10px;
  }
}

/* U11: Mobile (≤428px) - tighter layout */
@media (max-width: 428px) {
  .ai-process-block {
    margin: 4px 0;
  }

  .process-header {
    padding: 8px;
    gap: 6px;
  }

  .process-body {
    padding: 6px 8px;
    gap: 6px;
  }

  .process-title {
    font-size: 11px;
  }

  .process-status,
  .process-elapsed {
    font-size: 10px;
  }
}
</style>