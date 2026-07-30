<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { streamNarrative, type NarrativeStreamHandle } from '@/api/dashboard'
import { useI18n } from 'vue-i18n'
import { showFailToast } from 'vant'
import { marked } from 'marked'
import DOMPurify from 'dompurify'
import IIcon from '@/components/IIcon.vue'

const { t } = useI18n()

type Phase = 'idle' | 'streaming' | 'complete' | 'cached'

const phase = ref<Phase>('idle')
const streamingThinking = ref('')
const streamingNarrative = ref('')
const cachedNarrative = ref('')
const cachedThinking = ref('')
const thinkingExpanded = ref(false)
const expanded = ref<string[]>(['narrative'])
const thinkingElapsed = ref(0)

let streamHandle: NarrativeStreamHandle | null = null
let elapsedTimer: ReturnType<typeof setInterval> | null = null
let thinkingStartMs = 0
let autoCollapseTimer: ReturnType<typeof setTimeout> | null = null

const hasThinking = computed(() => {
  if (phase.value === 'cached') return cachedThinking.value.length > 0
  return streamingThinking.value.length > 0
})

const displayNarrative = computed(() => {
  if (phase.value === 'cached') return cachedNarrative.value
  return streamingNarrative.value
})

const displayThinking = computed(() => {
  if (phase.value === 'cached') return cachedThinking.value
  return streamingThinking.value
})

/** Whether narrative should be clamped to 2 lines (cached phase only) */
const narrativeClamped = computed(() => {
  return phase.value === 'cached' && !thinkingExpanded.value
})

/** DOMPurify config for thinking content — allow basic formatting elements */
const THINKING_PURIFY_CONFIG = {
  USE_PROFILES: { html: true },
  ALLOW_DATA_ATTR: false,
} as const

/** Render thinking content as sanitized markdown HTML */
const renderedThinking = computed(() => {
  const raw = displayThinking.value
  if (!raw) return ''
  const html = marked.parse(raw, { async: false }) as string
  return DOMPurify.sanitize(html, THINKING_PURIFY_CONFIG)
})

function startElapsedTimer() {
  thinkingStartMs = Date.now()
  thinkingElapsed.value = 0
  elapsedTimer = setInterval(() => {
    thinkingElapsed.value = Math.round((Date.now() - thinkingStartMs) / 1000)
  }, 1000)
}

function stopElapsedTimer() {
  if (elapsedTimer) {
    clearInterval(elapsedTimer)
    elapsedTimer = null
  }
}

function toggleThinking() {
  thinkingExpanded.value = !thinkingExpanded.value
}

function toggleCachedNarrative() {
  if (phase.value === 'cached' && !thinkingExpanded.value) {
    thinkingExpanded.value = true
  }
}

async function load() {
  phase.value = 'idle'

  streamHandle = await streamNarrative({
    onReasoningDelta: (content) => {
      if (phase.value === 'idle') {
        phase.value = 'streaming'
        expanded.value = ['narrative']
        thinkingExpanded.value = true
        startElapsedTimer()
      }
      streamingThinking.value += content
    },
    onNarrativeDelta: (content) => {
      if (phase.value === 'idle') {
        // Narrative without prior reasoning → streaming without thinking
        phase.value = 'streaming'
        expanded.value = ['narrative']
        thinkingExpanded.value = false
      }
      streamingNarrative.value += content
    },
    onDone: (result) => {
      stopElapsedTimer()
      streamHandle = null

      if (phase.value === 'idle') {
        // JSON response (cached or threshold-miss)
        if (result.narrative) {
          cachedNarrative.value = result.narrative
          cachedThinking.value = result.thinking || ''
          thinkingExpanded.value = false
          phase.value = 'cached'
          expanded.value = ['narrative']
        }
        return
      }

      // Streaming complete → finalize
      if (result.narrative) streamingNarrative.value = result.narrative
      if (result.thinking) streamingThinking.value = result.thinking

      phase.value = 'complete'
      // Auto-collapse thinking after a brief moment
      autoCollapseTimer = setTimeout(() => {
        thinkingExpanded.value = false
      }, 1500)
    },
    onError: (msg) => {
      stopElapsedTimer()
      streamHandle = null
      showFailToast(t(msg))
    },
  })
}

onMounted(() => {
  void load()
})

onUnmounted(() => {
  streamHandle?.abort()
  stopElapsedTimer()
  if (autoCollapseTimer) clearTimeout(autoCollapseTimer)
})
</script>

<template>
  <van-cell-group
    v-if="phase !== 'idle'"
    inset
    class="narrative-card"
    data-test="narrative-card"
  >
    <van-collapse v-model="expanded" class="narrative-collapse">
      <van-collapse-item name="narrative">
        <template #title>
          <div class="narrative-card__header">
            <span class="narrative-card__title">
              <span class="narrative-card__icon">
                <van-loading
                  v-if="phase === 'streaming'"
                  size="16px"
                  type="spinner"
                  color="var(--van-primary-color, #1989fa)"
                />
                <IIcon v-else :icon="'lucide:sparkles'" size="18" class="narrative-card__icon-svg" />
              </span>
              <span class="narrative-card__title-text">{{ t('dashboard.narrative.title') }}</span>
            </span>
          </div>
        </template>

        <!-- ── Streaming layout: thinking first, then narrative ── -->
        <template v-if="phase === 'streaming'">
          <!-- Thinking indicator -->
          <button
            v-if="hasThinking"
            class="narrative-card__thinking-toggle"
            @click.stop="toggleThinking"
          >
            <IIcon :icon="'lucide:lightbulb'" size="14" class="narrative-card__thinking-icon" />
            <span class="narrative-card__thinking-status">
              {{ t('dashboard.narrative.thinkingElapsed', { seconds: thinkingElapsed }) }}
            </span>
            <van-icon :name="thinkingExpanded ? 'arrow-up' : 'arrow-down'" size="10" />
          </button>

          <!-- Thinking content -->
          <transition name="thinking-fade">
            <div v-if="thinkingExpanded && displayThinking" class="narrative-card__thinking-content">
              <!-- eslint-disable-next-line vue/no-v-html -- sanitized via DOMPurify -->
              <div class="narrative-card__thinking-md" v-html="renderedThinking" />
            </div>
          </transition>

          <!-- Narrative text (grows as it streams) -->
          <p class="narrative-card__text">
            {{ displayNarrative }}<span v-if="displayNarrative" class="narrative-card__cursor" />
          </p>
        </template>

        <!-- ── Complete layout: thinking first, then narrative ── -->
        <template v-else-if="phase === 'complete'">
          <!-- Thinking indicator (collapsed by default after streaming) -->
          <button
            v-if="hasThinking"
            class="narrative-card__thinking-toggle"
            @click.stop="toggleThinking"
          >
            <IIcon :icon="'lucide:lightbulb'" size="14" class="narrative-card__thinking-icon" />
            <span class="narrative-card__thinking-status">
              {{ t('dashboard.narrative.thinkingDone', { seconds: thinkingElapsed }) }}
            </span>
            <van-icon :name="thinkingExpanded ? 'arrow-up' : 'arrow-down'" size="10" />
          </button>

          <!-- Thinking content (expandable) -->
          <transition name="thinking-fade">
            <div v-if="thinkingExpanded && displayThinking" class="narrative-card__thinking-content">
              <!-- eslint-disable-next-line vue/no-v-html -- sanitized via DOMPurify -->
              <div class="narrative-card__thinking-md" v-html="renderedThinking" />
            </div>
          </transition>

          <!-- Narrative text (full, not clamped) -->
          <p class="narrative-card__text">
            {{ displayNarrative }}
          </p>
        </template>

        <!-- ── Cached layout: clamped narrative, click to expand ── -->
        <template v-else>
          <!-- Narrative text (clamped to 2 lines, clickable to expand) -->
          <p
            :class="['narrative-card__text', { 'narrative-card__text--clamp': narrativeClamped }]"
            @click="toggleCachedNarrative"
          >
            {{ displayNarrative }}
          </p>

          <!-- Thinking indicator + content (hidden when collapsed in cached mode) -->
          <template v-if="thinkingExpanded">
            <button
              v-if="hasThinking"
              class="narrative-card__thinking-toggle"
              @click.stop="toggleThinking"
            >
              <IIcon :icon="'lucide:lightbulb'" size="14" class="narrative-card__thinking-icon" />
              <span class="narrative-card__thinking-status">
                {{ t('dashboard.narrative.thinkingDone', { seconds: thinkingElapsed }) }}
              </span>
              <van-icon :name="thinkingExpanded ? 'arrow-up' : 'arrow-down'" size="10" />
            </button>

            <transition name="thinking-fade">
              <div v-if="displayThinking" class="narrative-card__thinking-content">
                <!-- eslint-disable-next-line vue/no-v-html -- sanitized via DOMPurify -->
                <div class="narrative-card__thinking-md" v-html="renderedThinking" />
              </div>
            </transition>
          </template>
        </template>
      </van-collapse-item>
    </van-collapse>
  </van-cell-group>
</template>

<style scoped>
.narrative-card {
  margin: 8px 0;
}

.narrative-card :deep(.van-cell) {
  background: var(--card-bg);
}

.narrative-collapse :deep(.van-collapse-item__title) {
  justify-content: flex-start;
}

.narrative-collapse :deep(.van-cell__title) {
  flex: 1;
  display: flex;
  min-width: 0;
}

.narrative-collapse :deep(.van-cell__value) {
  flex: none;
  width: 0;
}

/* Header row */
.narrative-card__header {
  display: flex;
  align-items: center;
  width: 100%;
  min-width: 0;
  gap: 8px;
}

.narrative-card__title {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  flex: 1;
  min-width: 0;
}

.narrative-card__icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 1.4em;
  height: 1.4em;
  flex-shrink: 0;
}

.narrative-card__icon-svg {
  color: #1989fa;
}

.narrative-card__title-text {
  font-weight: 600;
}

/* Narrative text */
.narrative-card__text {
  font-size: 14px;
  line-height: 1.6;
  color: var(--text-primary, #323233);
  margin: 0 0 8px;
  word-break: break-word;
  white-space: pre-wrap;
}

.narrative-card__text--clamp {
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  margin: 0;
  cursor: pointer;
}

/* Streaming cursor */
.narrative-card__cursor {
  display: inline-block;
  width: 2px;
  height: 1em;
  background: var(--van-primary-color, #1989fa);
  margin-left: 2px;
  vertical-align: text-bottom;
  animation: blink 1s step-end infinite;
}

@keyframes blink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0; }
}

/* Thinking indicator */
.narrative-card__thinking-toggle {
  display: flex;
  align-items: center;
  justify-content: flex-start;
  gap: 4px;
  font-size: 12px;
  color: var(--text-secondary, #969799);
  background: none;
  border: none;
  cursor: pointer;
  padding: 6px 0;
}

.narrative-card__thinking-icon {
  color: var(--van-primary-color, #1989fa);
}

.narrative-card__thinking-content {
  margin-top: 0;
  padding: 8px 12px;
  background: var(--van-background-2, #f7f8fa);
  border-radius: 8px;
}

[data-theme='dark'] .narrative-card__thinking-content {
  background: rgba(255, 255, 255, 0.04);
}

/* Thinking content — rendered markdown */
.narrative-card__thinking-md {
  font-size: 12px;
  line-height: 1.6;
  color: var(--text-secondary, #969799);
  word-break: break-word;
  white-space: pre-wrap;
}

.narrative-card__thinking-md :deep(p) {
  margin: 0 0 6px;
}

.narrative-card__thinking-md :deep(p:last-child) {
  margin-bottom: 0;
}

.narrative-card__thinking-md :deep(strong) {
  color: var(--text-primary, #323233);
  font-weight: 600;
}

.narrative-card__thinking-md :deep(em) {
  font-style: italic;
}

.narrative-card__thinking-md :deep(code) {
  font-family: 'SF Mono', 'Menlo', 'Monaco', 'Consolas', monospace;
  font-size: 11px;
  padding: 2px 6px;
  background: rgba(0, 0, 0, 0.06);
  border-radius: 4px;
}

[data-theme='dark'] .narrative-card__thinking-md :deep(code) {
  background: rgba(255, 255, 255, 0.08);
}

.narrative-card__thinking-md :deep(pre) {
  margin: 6px 0;
  padding: 8px 12px;
  border-radius: 6px;
  overflow-x: auto;
  background: rgba(0, 0, 0, 0.04);
}

[data-theme='dark'] .narrative-card__thinking-md :deep(pre) {
  background: rgba(255, 255, 255, 0.06);
}

.narrative-card__thinking-md :deep(pre code) {
  padding: 0;
  background: none;
  font-size: 11px;
}

.narrative-card__thinking-md :deep(ul),
.narrative-card__thinking-md :deep(ol) {
  margin: 4px 0;
  padding-left: 20px;
}

.narrative-card__thinking-md :deep(li) {
  margin: 2px 0;
}

.narrative-card__thinking-md :deep(h1),
.narrative-card__thinking-md :deep(h2),
.narrative-card__thinking-md :deep(h3),
.narrative-card__thinking-md :deep(h4) {
  margin: 8px 0 4px;
  font-size: 12px;
  font-weight: 600;
  color: var(--text-primary, #323233);
}

.narrative-card__thinking-md :deep(blockquote) {
  margin: 6px 0;
  padding-left: 12px;
  border-left: 3px solid var(--van-primary-color, #1989fa);
  opacity: 0.85;
}

.narrative-card__thinking-md :deep(a) {
  color: var(--van-primary-color, #1989fa);
  text-decoration: none;
}

.narrative-card__thinking-md :deep(a:hover) {
  text-decoration: underline;
}

.narrative-card__thinking-md :deep(hr) {
  margin: 8px 0;
  border: none;
  border-top: 1px solid rgba(0, 0, 0, 0.1);
}

[data-theme='dark'] .narrative-card__thinking-md :deep(hr) {
  border-top-color: rgba(255, 255, 255, 0.1);
}

/* Thinking expand/collapse transition */
.thinking-fade-enter-active,
.thinking-fade-leave-active {
  transition: opacity 0.25s ease, max-height 0.3s ease;
  overflow: hidden;
}

.thinking-fade-enter-from,
.thinking-fade-leave-to {
  opacity: 0;
  max-height: 0;
}

.thinking-fade-enter-to,
.thinking-fade-leave-from {
  opacity: 1;
  max-height: 500px;
}
</style>
