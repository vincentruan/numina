<script setup lang="ts">
/**
 * AssistantMessage — AI message container following DeerFlow pattern
 *
 * DeerFlow reference: frontend/src/components/workspace/messages/message-list-item.tsx
 *
 * Key patterns:
 * - w-full (full width for better content display)
 * - Collapsible reasoning section (ReasoningTrigger + ReasoningContent)
 * - Flat tool call list (ChainOfThought pattern, no nesting)
 * - TodoList for plan progress
 * - Subagent cards for delegation
 * - Main content area with markdown rendering
 * - Actions: copy, regenerate, feedback (thumbs up/down)
 */
import { computed, ref, nextTick, onMounted, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import type { ProcessStep, PlanStep } from '@/types/agent-stream'
import type { CitationSource } from '@/utils/ai-chat/citations'
import ReasoningSection from './ReasoningSection.vue'
import ToolCallList from './ToolCallList.vue'
import TodoListPanel from './TodoListPanel.vue'
import MarkdownContent from '@/components/ai-chat/MarkdownContent.vue'
import CitationSourcesPanel from '@/components/ai-chat/CitationSourcesPanel.vue'
import StreamingIndicator from '@/components/ai-chat/StreamingIndicator.vue'

interface Props {
  id: string
  content: string
  phase?: 'connecting' | 'thinking' | 'answering' | 'done' | 'error' | 'interrupted'
  processSteps?: ProcessStep[]
  planSteps?: PlanStep[]
  planSource?: 'explicit' | 'inferred' | null
  processElapsedMs?: number
  reasoningStartTime?: number | null
  renderedContent?: string
  suggestions?: string[]
  feedback?: 1 | -1 | 0
  displayTime: string
  artifacts?: Array<{ id: string; title: string; kind: string; url?: string; path?: string }>
  canBranch?: boolean
  isBranching?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  phase: 'done',
  canBranch: false,
  isBranching: false,
})

const emit = defineEmits<{
  retry: []
  copy: [content: string]
  feedback: [value: 1 | -1]
  suggestionClick: [text: string]
  artifactTap: [artifact: { id: string; title: string; kind: string; url?: string; path?: string }]
  branch: []
}>()

const { t } = useI18n()

// Extract reasoning steps from processSteps
const reasoningSteps = computed(() =>
  props.processSteps?.filter((s) => s.type === 'reasoning') ?? []
)

// Extract tool call steps from processSteps
const toolCallSteps = computed(() =>
  props.processSteps?.filter((s) => s.type === 'tool_call') ?? []
)

// Extract subagent steps from processSteps (for future use)
const _subagentSteps = computed(() =>
  props.processSteps?.filter((s) => s.type === 'subagent') ?? []
)

// Determine if process visualization should show (for future use)
const _hasProcessContent = computed(() =>
  (props.processSteps?.length ?? 0) > 0 ||
  props.phase === 'error' ||
  props.phase === 'connecting'
)

// Determine process status
const processStatus = computed((): 'running' | 'done' | 'error' | 'interrupted' => {
  if (props.phase === 'interrupted') return 'interrupted'
  if (props.phase === 'error') return 'error'
  if (props.phase === 'done') return 'done'
  return 'running'
})

// Connecting timer display
const connectingSeconds = ref(0)
let _connectingTimer: ReturnType<typeof setInterval> | null = null

// Start connecting timer when phase is connecting
if (props.phase === 'connecting') {
  _connectingTimer = setInterval(() => {
    connectingSeconds.value++
  }, 1000)
}

// Phase label helper (for future use)
function _phaseLabel(phase: string): string {
  switch (phase) {
    case 'connecting': return t('aiChat.connectingAI')
    case 'thinking': return t('aiChat.thinking')
    case 'answering': return t('aiChat.generatingAnswer')
    default: return ''
  }
}

// Action handlers
function onCopy() {
  navigator.clipboard.writeText(props.content)
  emit('copy', props.content)
}

function onFeedback(value: 1 | -1) {
  emit('feedback', value)
}

// Citation sources extracted from markdown content
const citationSources = ref<CitationSource[]>([])

function onCitations(sources: CitationSource[]) {
  citationSources.value = sources
}

// Suggestion chips generation (placeholder - will be enhanced)
function suggestionChips(): string[] {
  return props.suggestions ?? []
}

// Marquee scrolling: detect overflow chips via canvas text measurement
// and apply CSS animation class + distance variable
const overflowIdxs = ref<number[]>([])
const chipsContainerRef = ref<HTMLDivElement | null>(null)

let _measureCanvas: HTMLCanvasElement | null = null
function measureTextPxWidth(text: string, font: string): number {
  if (!_measureCanvas) _measureCanvas = document.createElement('canvas')
  const ctx = _measureCanvas.getContext('2d')
  if (!ctx) return 0
  ctx.font = font
  return ctx.measureText(text).width
}

function measureChipOverflow() {
  const container = chipsContainerRef.value
  console.log('[SuggestionChip] container:', !!container)
  if (!container) return

  const chips = container.querySelectorAll<HTMLButtonElement>('.suggestion-chip')
  console.log('[SuggestionChip] chips count:', chips.length)
  const next: number[] = []

  chips.forEach((chip, idx) => {
    const textEl = chip.querySelector('.suggestion-chip__text') as HTMLElement | null
    if (!textEl) return
    const text = textEl.textContent ?? ''
    if (!text) return

    const cs = window.getComputedStyle(textEl)
    const font = `${cs.fontStyle} ${cs.fontWeight} ${cs.fontSize}/${cs.lineHeight} ${cs.fontFamily}`
    const textW = measureTextPxWidth(text, font)
    const availW = chip.clientWidth - parseFloat(cs.paddingLeft) - parseFloat(cs.paddingRight)

    console.log(`[SuggestionChip] chip ${idx}:`, {
      text: text.substring(0, 30),
      textW: Math.round(textW),
      availW: Math.round(availW),
      chipW: chip.clientWidth,
      padL: cs.paddingLeft,
      padR: cs.paddingRight,
      overflow: textW > availW + 2,
    })

    if (textW > availW + 2) {
      next.push(idx)
      chip.style.setProperty('--marquee-distance', `-${Math.round(textW - availW)}px`)
    } else {
      chip.style.removeProperty('--marquee-distance')
    }
  })
  overflowIdxs.value = next
  console.log('[SuggestionChip] overflowIdxs:', next)
}

function onChipClick(chip: string) {
  emit('suggestionClick', chip)
}

// Watch the actual render condition, not just the props
const shouldShowChips = computed(() =>
  props.phase === 'done' &&
  props.content &&
  props.content.length >= 30 &&
  suggestionChips().length > 0
)

// flush: 'post' ensures this runs AFTER DOM updates
watch(
  shouldShowChips,
  (show) => {
    if (show) {
      // Chips just became visible, measure them after DOM update
      // flush: 'post' already ensures DOM is updated, no need for nextTick
      measureChipOverflow()
    } else {
      // Chips hidden, reset
      overflowIdxs.value = []
    }
  },
  { immediate: true, flush: 'post' }
)
</script>

<template>
  <div class="assistant-message">
    <!-- Connecting state: shimmer animation -->
    <div v-if="phase === 'connecting'" class="connecting-region shimmer-active" aria-live="polite">
      <span class="connecting-dot" aria-hidden="true" />
      <span class="connecting-label">{{ t('aiChat.connectingAI') }}</span>
      <span class="connecting-sep" aria-hidden="true">·</span>
      <span class="connecting-time">{{ connectingSeconds }}s</span>
    </div>

    <!-- Reasoning section: collapsible thinking content -->
    <ReasoningSection
      v-if="reasoningSteps.length > 0 || phase === 'thinking'"
      :steps="reasoningSteps"
      :phase="phase"
      :elapsed-ms="processElapsedMs"
      :start-time="reasoningStartTime"
      :is-streaming="phase === 'thinking'"
    />

    <!-- TodoList: plan progress visualization -->
    <TodoListPanel
      v-if="planSteps && planSteps.length > 0"
      :steps="planSteps"
      :source="planSource"
    />

    <!-- Tool calls: flat list (ChainOfThought pattern) -->
    <ToolCallList
      v-if="toolCallSteps.length > 0"
      :steps="toolCallSteps"
      :status="processStatus"
    />

    <!-- Main content area -->
    <div
      v-if="phase !== 'error' && content"
      class="message-content"
      :class="{ 'content--appearing': phase === 'answering' && !renderedContent }"
    >
      <!-- Markdown rendered via MarkdownContent (markdown-it + shiki) -->
      <MarkdownContent :content="content" :is-loading="false" @citations="onCitations" />

      <!-- Citation sources panel (DeerFlow pattern) -->
      <CitationSourcesPanel
        v-if="citationSources.length > 0 && phase === 'done'"
        :sources="citationSources"
      />

      <!-- Streaming indicator (block-level bouncing dots, U6) -->
      <StreamingIndicator :visible="phase === 'answering'" />
    </div>

    <!-- Error state -->
    <div v-if="phase === 'error'" class="error-state">
      <p class="error-msg">{{ t('aiChat.errorRetry') }}</p>
      <button class="retry-btn" @click="emit('retry')">
        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
          <polyline points="1 4 1 10 7 10"/>
          <path d="M3.51 15a9 9 0 1 0 .49-3.5"/>
        </svg>
        <span>{{ t('aiChat.retry') }}</span>
      </button>
    </div>

    <!-- Interrupted hint -->
    <div v-if="phase === 'interrupted'" class="interrupted-hint" aria-live="polite">
      {{ t('aiChat.generationStopped') }}
    </div>

    <!-- Token usage slot: rendered between content and footer so the order is
         content -> token usage -> timestamp/actions -> suggestions.
         Slotted in by MessageGroup to keep this component data-agnostic. -->
    <slot name="token-usage" />

    <!-- Footer: timestamp and actions -->
    <div v-if="phase === 'done' || phase === 'interrupted' || phase === 'error'" class="message-footer">
      <span class="message-time">{{ displayTime }}</span>

      <!-- Actions -->
      <div class="message-actions">
        <button class="action-btn" :aria-label="t('aiChat.copyAria')" @click="onCopy">
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
            <rect x="9" y="9" width="13" height="13" rx="2" ry="2"/>
            <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>
          </svg>
        </button>
        <button class="action-btn" :aria-label="t('aiChat.regenerateAria')" @click="emit('retry')">
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
            <polyline points="1 4 1 10 7 10"/>
            <path d="M3.51 15a9 9 0 1 0 .49-3.5"/>
          </svg>
        </button>
        <button
          v-if="canBranch"
          class="action-btn"
          :class="{ 'action-btn--branching': isBranching }"
          :aria-label="t('aiChat.branchButton')"
          :disabled="isBranching"
          @click="emit('branch')"
        >
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
            <line x1="6" y1="3" x2="6" y2="15"/>
            <circle cx="18" cy="6" r="3"/>
            <circle cx="6" cy="18" r="3"/>
            <path d="M18 9a9 9 0 0 1-9 9"/>
          </svg>
        </button>
        <button
          class="action-btn"
          :class="{ 'action-btn--active': feedback === 1 }"
          :aria-label="t('aiChat.helpfulAria')"
          @click="onFeedback(1)"
        >
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
            <path d="M14 9V5a3 3 0 0 0-3-3l-4 9v11h11.28a2 2 0 0 0 2-1.7l1.38-9a2 2 0 0 0-2-2.3H14z"/>
            <path d="M7 22H4a2 2 0 0 1-2-2v-7a2 2 0 0 1 2-2h3"/>
          </svg>
        </button>
        <button
          class="action-btn"
          :class="{ 'action-btn--active': feedback === -1 }"
          :aria-label="t('aiChat.notHelpfulAria')"
          @click="onFeedback(-1)"
        >
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
            <path d="M10 15v4a3 3 0 0 0 3 3l4-9V2H5.72a2 2 0 0 0-2 1.7l-1.38 9a2 2 0 0 0 2 2.3H10z"/>
            <path d="M17 2h2.67A2.31 2.31 0 0 1 22 4v7a2.31 2.31 0 0 1-2.33 2H17"/>
          </svg>
        </button>
      </div>
    </div>

    <!-- Suggestion chips -->
    <div
      v-if="phase === 'done' && content && content.length >= 30 && suggestionChips().length > 0"
      ref="chipsContainerRef"
      class="suggestion-chips"
    >
      <button
        v-for="(chip, idx) in suggestionChips()"
        :key="chip"
        class="suggestion-chip"
        :class="{ 'suggestion-chip--scrolling': overflowIdxs.includes(idx) }"
        type="button"
        @click="onChipClick(chip)"
      >
        <span class="suggestion-chip__text">{{ chip }}</span>
      </button>
    </div>
  </div>
</template>

<style scoped>
/* DeerFlow pattern: full width for assistant messages */
.assistant-message {
  width: 100%;
  max-width: 100%;
}

/* Connecting state */
.connecting-region {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 16px;
  background: var(--bubble-ai-bg, rgba(189, 187, 255, 0.12));
  border-radius: 12px;
  font-size: 14px;
  color: var(--text-secondary);
}

.connecting-dot {
  width: 8px;
  height: 8px;
  background: var(--van-primary-color);
  border-radius: 50%;
  animation: pulse 1.5s ease-in-out infinite;
}

.connecting-sep {
  opacity: 0.5;
}

.connecting-time {
  font-variant-numeric: tabular-nums;
}

/* Shimmer animation */
.shimmer-active {
  animation: shimmer 2s infinite linear;
  background: linear-gradient(
    90deg,
    var(--bubble-ai-bg) 0%,
    rgba(189, 187, 255, 0.2) 50%,
    var(--bubble-ai-bg) 100%
  );
  background-size: 200% 100%;
}

@keyframes shimmer {
  0% { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}

/* Main content area */
.message-content {
  padding: 12px 0;
}

.content--appearing {
  animation: fadeIn 0.3s ease-out;
}

.markdown-body {
  font-size: 15px;
  line-height: 1.6;
  color: var(--text-primary);
}

.markdown-body :deep(p) {
  margin: 0 0 8px;
}

.markdown-body :deep(p:last-child) {
  margin-bottom: 0;
}

.markdown-body :deep(ul),
.markdown-body :deep(ol) {
  margin: 4px 0 8px 16px;
  padding: 0;
}

.markdown-body :deep(li) {
  margin-bottom: 2px;
}

.markdown-body :deep(code) {
  font-family: 'SF Mono', Monaco, 'Cascadia Code', monospace;
  font-size: 13px;
  background: rgba(0, 0, 0, 0.1);
  padding: 2px 4px;
  border-radius: 4px;
}

.markdown-body :deep(pre) {
  background: rgba(0, 0, 0, 0.08);
  padding: 12px;
  border-radius: 8px;
  overflow-x: auto;
  margin: 8px 0;
}

.markdown-body :deep(pre code) {
  background: transparent;
  padding: 0;
}

.markdown-body :deep(strong) {
  color: var(--text-primary);
  font-weight: 600;
}

.markdown-body :deep(a) {
  color: #818cf8;
  text-decoration: underline;
}

.markdown-body :deep(table) {
  width: 100%;
  border-collapse: collapse;
  margin: 8px 0;
}

.markdown-body :deep(th),
.markdown-body :deep(td) {
  padding: 8px;
  border: 1px solid var(--bubble-ai-border, rgba(0, 0, 0, 0.1));
}

.markdown-body :deep(img) {
  max-width: 100%;
  height: auto;
}

/* Error state */
.error-state {
  padding: 12px;
  background: rgba(248, 113, 113, 0.1);
  border-radius: 8px;
  color: #f87171;
}

.error-msg {
  margin: 0 0 8px;
  font-size: 14px;
}

.retry-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 12px;
  font-size: 13px;
  background: rgba(248, 113, 113, 0.2);
  border: none;
  border-radius: 6px;
  color: inherit;
  cursor: pointer;
}

/* Interrupted hint */
.interrupted-hint {
  padding: 8px 12px;
  font-size: 13px;
  color: var(--text-secondary);
  opacity: 0.8;
}

/* Footer */
.message-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 8px;
  padding-top: 8px;
}

.message-time {
  font-size: 11px;
  color: var(--text-secondary);
  opacity: 0.6;
}

.message-actions {
  display: flex;
  gap: 4px;
  opacity: 0;
  transition: opacity 0.2s;
}

.assistant-message:hover .message-actions,
.assistant-message:focus-within .message-actions {
  opacity: 1;
}

.action-btn {
  padding: 4px;
  background: transparent;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  color: var(--text-secondary);
  opacity: 0.7;
  transition: opacity 0.15s;
}

.action-btn:hover {
  opacity: 1;
}

.action-btn--active {
  color: var(--van-primary-color);
  opacity: 1;
}

.action-btn--branching {
  animation: branch-pulse 1.2s ease-in-out infinite;
}

@keyframes branch-pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.4; }
}

/* Suggestion chips */
.suggestion-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 12px;
}

.suggestion-chip {
  position: relative;
  max-width: min(100%, 320px);
  padding: 8px 14px;
  font-size: 13px;
  background: rgba(129, 140, 248, 0.1);
  border: 1px solid rgba(129, 140, 248, 0.2);
  border-radius: 20px;
  color: var(--text-primary);
  cursor: pointer;
  transition: background 0.2s, border-color 0.2s;
  overflow: hidden;
  text-align: left;
}

.suggestion-chip:hover {
  background: rgba(129, 140, 248, 0.2);
  border-color: rgba(129, 140, 248, 0.3);
}

.suggestion-chip__text {
  display: inline-block;
  white-space: nowrap;
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* Overflow chips: auto-scroll marquee (works on mobile without hover) */
.suggestion-chip--scrolling .suggestion-chip__text {
  /* Remove max-width constraint so text can be wider than container */
  max-width: none;
  /* Make overflow visible so parent's overflow:hidden can clip it */
  overflow: visible;
  text-overflow: clip;
  animation: suggestion-marquee 6s ease-in-out infinite;
}

@keyframes suggestion-marquee {
  0%, 20% {
    transform: translateX(0);
  }
  80%, 100% {
    transform: translateX(var(--marquee-distance, -50%));
  }
}

/* Respect reduced motion preference */
@media (prefers-reduced-motion: reduce) {
  .suggestion-chip--scrolling .suggestion-chip__text {
    animation: none;
  }
}

@keyframes pulse {
  0%, 100% { opacity: 0.4; transform: scale(0.95); }
  50% { opacity: 1; transform: scale(1); }
}

@keyframes fadeIn {
  from { opacity: 0; }
  to { opacity: 1; }
}
</style>