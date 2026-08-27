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
import { computed, nextTick, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import type { PlanStep } from '@/types/agent-stream'
import type { CitationSource } from '@/utils/ai-chat/citations'
import CopyButton from '@/components/ai-chat/CopyButton.vue'
import LiveTimer from '@/components/ai-chat/LiveTimer.vue'
import TodoListPanel from './TodoListPanel.vue'
import MarkdownContent from '@/components/ai-chat/MarkdownContent.vue'
import CitationSourcesPanel from '@/components/ai-chat/CitationSourcesPanel.vue'
import StreamingIndicator from '@/components/ai-chat/StreamingIndicator.vue'

interface Props {
  id: string
  content: string
  phase?: 'connecting' | 'thinking' | 'answering' | 'done' | 'error' | 'interrupted'
  /** DeerFlow: reasoning content extracted from message (think tags / reasoning_content) */
  reasoningContent?: string | null
  /** DeerFlow: reasoning start timestamp (from additional_kwargs) */
  reasoningStartTime?: number | null
  /** DeerFlow: reasoning end timestamp (from additional_kwargs) */
  reasoningEndTime?: number | null
  planSteps?: PlanStep[]
  planSource?: 'explicit' | 'inferred' | null
  renderedContent?: string
  suggestions?: string[]
  feedback?: 1 | -1 | 0
  displayTime: string
  artifacts?: Array<{ id: string; title: string; kind: string; url?: string; path?: string }>
  canBranch?: boolean
  isBranching?: boolean
  retrying?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  phase: 'done',
  reasoningContent: null,
  reasoningStartTime: null,
  reasoningEndTime: null,
  planSteps: undefined,
  planSource: undefined,
  renderedContent: undefined,
  suggestions: undefined,
  feedback: undefined,
  artifacts: undefined,
  canBranch: false,
  isBranching: false,
  retrying: false,
})

const emit = defineEmits<{
  retry: []
  copy: [content: string]
  feedback: [value: 1 | -1]
  suggestionClick: [text: string]
  artifactTap: [artifact: { id: string; title: string; kind: string; url?: string; path?: string }]
  sandboxFileClick: [filepath: string]
  branch: []
}>()

const { t } = useI18n()
const router = useRouter()

function onReportArtifactTap() {
  router.push('/ai/report')
}

function onSandboxFileClick(filepath: string) {
  emit('sandboxFileClick', filepath)
}

// Filter report-kind artifacts from the artifacts prop
const reportArtifacts = computed(() =>
  (props.artifacts ?? []).filter(a => a.kind === 'report')
)

// DeerFlow 模式：当 planSteps 存在且内容只是冗余的完成总结时，抑制内容渲染。
// Numina agent 在 write_todos 完成后会生成一条额外的 AI 总结消息
// （如"已完成！所有 5 个待办事项均已标记为完成。"），但 DeerFlow
// 不显示这种冗余消息——todo 列表本身就是最终输出。
const isRedundantCompletionSummary = computed(() => {
  if (!props.planSteps || props.planSteps.length === 0) return false
  const content = props.content.trim()
  if (content.length === 0 || content.length >= 100) return false
  return content.includes('完成') || content.includes('已完成') ||
    content.includes('标记为完成') || content.includes('全部完成')
})

// ── DeerFlow Reasoning pattern ──
// Collapsible reasoning section with LiveTimer + MarkdownContent.
// Default open; auto-close 1s after streaming ends (only once).
const isReasoningExpanded = ref(true)
let reasoningAutoCloseTimer: ReturnType<typeof setTimeout> | null = null

// Auto-close reasoning after streaming ends (DeerFlow AUTO_CLOSE_DELAY=1000)
watch(
  () => props.phase,
  (newPhase) => {
    if ((newPhase === 'done' || newPhase === 'answering') && props.reasoningContent) {
      if (reasoningAutoCloseTimer === null) {
        reasoningAutoCloseTimer = setTimeout(() => {
          isReasoningExpanded.value = false
          reasoningAutoCloseTimer = null
        }, 1000)
      }
    }
  },
)

function toggleReasoning() {
  isReasoningExpanded.value = !isReasoningExpanded.value
}

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

// Track dismissed chips by value so removals survive re-renders
const dismissedChips = ref(new Set<string>())

// Visible chips: filter out dismissed ones
const visibleChips = computed(() => {
  const all = suggestionChips()
  if (dismissedChips.value.size === 0) return all
  return all.filter((c) => !dismissedChips.value.has(c))
})

function dismissChip(chip: string) {
  dismissedChips.value.add(chip)
  // Re-measure overflow after a chip is removed
  nextTick(() => measureChipOverflow())
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
  if (!container) return

  const chips = container.querySelectorAll<HTMLButtonElement>('.suggestion-chip')
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

    if (textW > availW + 2) {
      next.push(idx)
      chip.style.setProperty('--marquee-distance', `-${Math.round(textW - availW)}px`)
    } else {
      chip.style.removeProperty('--marquee-distance')
    }
  })
  overflowIdxs.value = next
}

function onChipClick(chip: string) {
  emit('suggestionClick', chip)
}

// Watch the actual render condition, not just the props
const shouldShowChips = computed(() =>
  props.phase === 'done' &&
  props.content &&
  props.content.length >= 30 &&
  visibleChips.value.length > 0
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

    <!-- DeerFlow Reasoning pattern: collapsible thinking section with LiveTimer -->
    <div
      v-if="reasoningContent"
      class="reasoning-section"
    >
      <button class="reasoning-trigger" @click="toggleReasoning">
        <div class="reasoning-trigger-inner">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="reasoning-icon">
            <path d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.984 3.984 0 0014 21a3.984 3.984 0 00-2.612-1.267l-.548-.547z"/>
          </svg>
          <LiveTimer
            v-if="reasoningStartTime"
            :start-time="reasoningStartTime"
            :end-time="reasoningEndTime ?? undefined"
          />
          <span v-else class="reasoning-label">{{ t('aiChat.thinkingLabel') }}</span>
        </div>
        <svg
          width="12"
          height="12"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="2"
          :class="['reasoning-chevron', { rotated: !isReasoningExpanded }]"
        >
          <polyline points="6 9 12 15 18 9"/>
        </svg>
      </button>
      <Transition name="reasoning-fade">
        <div v-if="isReasoningExpanded" class="reasoning-content">
          <MarkdownContent :content="reasoningContent" @sandbox-file-click="onSandboxFileClick" />
        </div>
      </Transition>
    </div>

    <!-- TodoList: plan progress visualization -->
    <TodoListPanel
      v-if="planSteps && planSteps.length > 0"
      :steps="planSteps"
      :source="planSource"
    />

    <!-- Main content area (suppressed when planSteps exist and content is a redundant completion summary) -->
    <div
      v-if="phase !== 'error' && content && !isRedundantCompletionSummary"
      class="message-content"
      :class="{ 'content--appearing': phase === 'answering' && !renderedContent }"
    >
      <!-- Markdown rendered via MarkdownContent (markdown-it + shiki) -->
      <MarkdownContent :content="content" :is-loading="false" @citations="onCitations" @sandbox-file-click="onSandboxFileClick" />

      <!-- Citation sources panel (DeerFlow pattern) -->
      <CitationSourcesPanel
        v-if="citationSources.length > 0 && phase === 'done'"
        :sources="citationSources"
      />

      <!-- Streaming indicator (block-level bouncing dots, U6) -->
      <StreamingIndicator :visible="phase === 'answering'" />
    </div>

    <!-- Report artifact: "View full report" navigation button -->
    <div v-if="reportArtifacts.length > 0 && phase === 'done'" class="report-artifact-row">
      <button class="report-artifact-btn" @click="onReportArtifactTap">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
          <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
          <polyline points="14 2 14 8 20 8"/>
          <line x1="16" y1="13" x2="8" y2="13"/>
          <line x1="16" y1="17" x2="8" y2="17"/>
          <polyline points="10 9 9 9 8 9"/>
        </svg>
        <span>{{ t('aiChat.viewFullReport') }}</span>
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
          <polyline points="9 18 15 12 9 6"/>
        </svg>
      </button>
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

    <!-- Footer: timestamp + actions (DeerFlow: actions on hover toolbar).
         No border-top here — TokenUsage component above provides the separator. -->
    <div v-if="phase === 'done' || phase === 'interrupted' || phase === 'error'" class="message-footer">
      <span class="message-time">{{ displayTime }}</span>
      <div class="message-footer-spacer" />

      <!-- Actions: flat icon row (ChatGPT/Claude pattern — no container, no divider) -->
      <div class="message-action-bar">
        <CopyButton v-slot="{ copy }" :content="content">
          <button class="action-btn" :aria-label="t('aiChat.copyAria')" @click="copy(); emit('copy', content)">
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
              <rect x="9" y="9" width="13" height="13" rx="2" ry="2"/>
              <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>
            </svg>
          </button>
        </CopyButton>
        <button class="action-btn" :aria-label="t('aiChat.regenerateAria')" :disabled="retrying" @click="emit('retry')">
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true" :class="{ 'action-btn--spinning': retrying }">
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
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
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
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
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
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
            <path d="M10 15v4a3 3 0 0 0 3 3l4-9V2H5.72a2 2 0 0 0-2 1.7l-1.38 9a2 2 0 0 0 2 2.3H10z"/>
            <path d="M17 2h2.67A2.31 2.31 0 0 1 22 4v7a2.31 2.31 0 0 1-2.33 2H17"/>
          </svg>
        </button>
      </div>
    </div>

    <!-- Suggestion chips: DeerFlow-style outlined buttons with per-chip dismiss -->
    <div
      v-if="phase === 'done' && content && content.length >= 30 && visibleChips.length > 0"
      ref="chipsContainerRef"
      class="suggestion-chips"
      role="group"
      :aria-label="t('aiChat.suggestionsAria')"
    >
      <button
        v-for="(chip, idx) in visibleChips"
        :key="chip"
        class="suggestion-chip"
        :class="{ 'suggestion-chip--scrolling': overflowIdxs.includes(idx) }"
        type="button"
        @click="onChipClick(chip)"
      >
        <span class="suggestion-chip__text">{{ chip }}</span>
        <span
          class="suggestion-chip__dismiss"
          role="button"
          tabindex="0"
          :aria-label="t('aiChat.suggestionRemove')"
          @click.stop="dismissChip(chip)"
          @keydown.enter.prevent="dismissChip(chip)"
          @keydown.space.prevent="dismissChip(chip)"
        >
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" aria-hidden="true">
            <line x1="18" y1="6" x2="6" y2="18"/>
            <line x1="6" y1="6" x2="18" y2="18"/>
          </svg>
        </span>
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

/* ── DeerFlow Reasoning section ── */
.reasoning-section {
  margin-bottom: 8px;
}

.reasoning-trigger {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  width: 100%;
  padding: 8px 12px;
  background: transparent;
  border: none;
  cursor: pointer;
  text-align: left;
}

.reasoning-trigger-inner {
  display: flex;
  align-items: center;
  gap: 8px;
}

.reasoning-icon {
  width: 16px;
  height: 16px;
  color: var(--van-primary-color);
  flex-shrink: 0;
}

.reasoning-label {
  font-size: 13px;
  color: var(--text-secondary);
}

.reasoning-chevron {
  width: 12px;
  height: 12px;
  color: var(--text-secondary);
  transition: transform 0.2s ease;
  flex-shrink: 0;
}

.reasoning-chevron.rotated {
  transform: rotate(180deg);
}

.reasoning-content {
  padding: 8px 12px;
  font-size: 13px;
  color: var(--text-secondary);
  background: rgba(129, 140, 248, 0.06);
  border-radius: 6px;
  line-height: 1.5;
  margin-top: 4px;
}

/* Subdue MarkdownContent inside reasoning — cascade override */
.reasoning-content :deep(.markdown-content),
.reasoning-content :deep(.markdown-content *) {
  color: var(--text-secondary);
}

.reasoning-content :deep(a) {
  color: var(--van-primary-color);
  opacity: 0.7;
}

/* Fade + slide transition (DeerFlow slide-in-from-top-2 / fade-in) */
.reasoning-fade-enter-active,
.reasoning-fade-leave-active {
  transition: opacity 0.2s ease, transform 0.2s ease;
}
.reasoning-fade-enter-from {
  opacity: 0;
  transform: translateY(-8px);
}
.reasoning-fade-enter-to {
  opacity: 1;
  transform: translateY(0);
}
.reasoning-fade-leave-from {
  opacity: 1;
  transform: translateY(0);
}
.reasoning-fade-leave-to {
  opacity: 0;
  transform: translateY(-8px);
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

/* Footer — no border-top (TokenUsage above provides the separator) */
.message-footer {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 8px;
}

/* Spacer pushes actions to the right */
.message-footer-spacer {
  flex: 1;
}

.message-time {
  font-size: 11px;
  color: var(--text-secondary);
  opacity: 0.6;
  flex-shrink: 0;
}

/* Action bar: flat icon row (ChatGPT/Claude pattern) */
.message-action-bar {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  opacity: 0;
  transition: opacity 0.2s;
}

.assistant-message:hover .message-action-bar,
.assistant-message:focus-within .message-action-bar {
  opacity: 1;
}

.action-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  background: transparent;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  color: var(--text-secondary);
  opacity: 0.55;
  transition: opacity 0.15s, background-color 0.15s;
}

.action-btn:hover {
  opacity: 1;
  background-color: rgba(0, 0, 0, 0.06);
}

:global([data-theme='dark']) .action-btn:hover {
  background-color: rgba(255, 255, 255, 0.08);
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

/* Mobile touch: always visible + 48×48px tap targets (Apple HIG ≥ 44×44) */
@media (hover: none) {
  .message-action-bar {
    opacity: 1;
    gap: 4px;
    flex-shrink: 0;
  }

  .action-btn {
    width: 48px;
    height: 48px;
    border-radius: 10px;
    opacity: 0.65; /* override 0.55 — buttons must look tappable on touch */
  }

  .action-btn:active {
    background-color: rgba(0, 0, 0, 0.08);
    opacity: 1;
  }

  :global([data-theme='dark']) .action-btn:active {
    background-color: rgba(255, 255, 255, 0.1);
  }

  .action-btn svg {
    width: 20px;
    height: 20px;
  }

.action-btn--spinning {
    animation: spin-refresh 0.8s linear infinite;
  }

@keyframes spin-refresh {
    from { transform: rotate(0deg); }
    to { transform: rotate(360deg); }
  }

  /* Feedback active state: subtle tint */
  .action-btn--active {
    opacity: 1;
    background-color: rgba(99, 102, 241, 0.08);
  }

  /* Narrow screen: hide timestamp to prevent overflow (iPhone SE 375px) */
  @media (max-width: 400px) {
    .message-time {
      display: none;
    }

    .message-footer-spacer {
      display: none;
    }

    .message-footer {
      justify-content: flex-end;
    }
  }
}

/* Suggestion chips — DeerFlow style: outlined, no fill */
.suggestion-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 12px;
}

.suggestion-chip {
  position: relative;
  display: inline-flex;
  align-items: center;
  max-width: min(100%, 320px);
  padding: 6px 28px 6px 14px; /* extra right padding for dismiss button */
  font-size: 13px;
  background: transparent;
  border: 1px solid var(--suggestion-chip-border, rgba(129, 140, 248, 0.35));
  border-radius: 20px;
  color: var(--text-primary);
  cursor: pointer;
  transition: background 0.2s, border-color 0.2s;
  overflow: hidden;
  text-align: left;
  line-height: 1.4;
}

.suggestion-chip:hover {
  background: rgba(129, 140, 248, 0.06);
  border-color: rgba(129, 140, 248, 0.5);
}

/* Light mode: add subtle tinted background for visibility */
:global([data-theme='light']) .suggestion-chip {
  background: rgba(129, 140, 248, 0.08);
  border-color: rgba(129, 140, 248, 0.45);
}

:global([data-theme='light']) .suggestion-chip:hover {
  background: rgba(129, 140, 248, 0.14);
  border-color: rgba(129, 140, 248, 0.6);
}

:global([data-theme='dark']) .suggestion-chip {
  --suggestion-chip-border: rgba(160, 165, 255, 0.3);
}

:global([data-theme='dark']) .suggestion-chip:hover {
  background: rgba(160, 165, 255, 0.08);
  border-color: rgba(160, 165, 255, 0.45);
}

.suggestion-chip__text {
  display: inline-block;
  white-space: nowrap;
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  flex: 1;
}

/* Dismiss button: positioned top-right inside chip */
.suggestion-chip__dismiss {
  position: absolute;
  right: 4px;
  top: 50%;
  transform: translateY(-50%);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 20px;
  height: 20px;
  padding: 0;
  background: transparent;
  border: none;
  border-radius: 50%;
  color: var(--text-secondary);
  opacity: 0;
  cursor: pointer;
  transition: opacity 0.15s, background 0.15s;
}

.suggestion-chip:hover .suggestion-chip__dismiss {
  opacity: 0.7;
}

.suggestion-chip__dismiss:hover {
  opacity: 1 !important;
  background: rgba(128, 128, 128, 0.15);
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

/* Report artifact: "View full report" navigation button */
.report-artifact-row {
  margin-top: 12px;
}

.report-artifact-btn {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 10px 16px;
  font-size: 14px;
  font-weight: 500;
  color: var(--van-primary-color);
  background: rgba(129, 140, 248, 0.08);
  border: 1px solid rgba(129, 140, 248, 0.3);
  border-radius: 10px;
  cursor: pointer;
  transition: background 0.2s, border-color 0.2s;
}

.report-artifact-btn:hover {
  background: rgba(129, 140, 248, 0.14);
  border-color: rgba(129, 140, 248, 0.5);
}

.report-artifact-btn:active {
  background: rgba(129, 140, 248, 0.18);
}

:global([data-theme='dark']) .report-artifact-btn {
  background: rgba(160, 165, 255, 0.08);
  border-color: rgba(160, 165, 255, 0.25);
  color: #a0a5ff;
}

:global([data-theme='dark']) .report-artifact-btn:hover {
  background: rgba(160, 165, 255, 0.14);
  border-color: rgba(160, 165, 255, 0.4);
}
</style>