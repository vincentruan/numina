<script setup lang="ts">
/**
 * WelcomePage — empty chat state
 *
 * Two visual variants based on the active agent:
 *
 * ─ numina (built-in system agent):
 *   • Circular gradient logo disc with shimmer pulse ring (single continuous anim)
 *   • Gradient "Numina AI" title + subtitle
 *   • 3 randomly picked suggestion cards (summary shown, prompt sent on tap)
 *
 * ─ other agent (user-created / future):
 *   • Agent's own emoji icon on its brand-color disc (no shimmer)
 *   • Agent's display_name + description (no suggestion cards)
 *   • Rationale: custom agents have their own identity; the curated question
 *     pool is Numina-specific and would feel out of place.
 *
 * InputBox stays fixed-bottom in both variants.
 */
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import InputBox from '@/components/ai-chat/InputBox.vue'
import AiLogo from '@/components/ai/AiLogo.vue'
import { useWelcomeQuestions } from '@/utils/ai-chat/welcomeQuestions'
import type { ResolvedWelcomeQuestion } from '@/utils/ai-chat/welcomeQuestions'
import type { SubmitPayload } from '@/types/ai-chat/input-mode'

const NUMINA_AGENT_NAME = 'numina'

// Draft text to pre-fill the input with (e.g. recovered after a failed
// auto-send from the AI hub). Empty/undefined leaves the input blank.
const props = defineProps<{
  modelValue?: string
  agentId?: string
  agentName?: string
  agents?: Array<{ id: string; display_name: string; agent_name?: string; icon?: string; color?: string | null; description?: string | null }>
  agentIcon?: string
  agentLabel?: string
  /** When true, agent icon shows info popup instead of triggering selection */
  readonly?: boolean
}>()
const emit = defineEmits<{
  startChat: [payload: SubmitPayload]
  /** Suggestion card tapped — AIChatBox fills mode/model defaults. */
  selectSuggestion: [prompt: string]
}>()

const { t } = useI18n()

// Active agent record (first entry of the agents array)
const activeAgent = computed(() => props.agents?.[0])

// Is the active agent the built-in numina? Drives the whole layout branch.
const isNumina = computed(() => props.agentName === NUMINA_AGENT_NAME)

// Agent's display color (fallback to primary when unset)
const agentColor = computed(() =>
  activeAgent.value?.color && activeAgent.value.color.length > 0
    ? activeAgent.value.color
    : 'var(--van-primary-color)'
)

// Per-agent question pool. Only instantiated for numina — other agents skip
// the card section entirely, so we never call pickRandom for them.
const { pickRandom } = useWelcomeQuestions(props.agentName)

// Hold the 3 visible questions in a ref so they stay stable across re-renders
// but reshuffle when the agent switches.
const suggestions = ref<ResolvedWelcomeQuestion[]>(
  isNumina.value ? pickRandom(3) : []
)
// Key of the currently expanded card (shows full prompt text). Null = none.
// Only one card can be expanded at a time; expanding another collapses the previous.
const expandedKey = ref<string | null>(null)
watch(() => props.agentName, (newName) => {
  if (newName === NUMINA_AGENT_NAME) {
    suggestions.value = pickRandom(3)
  } else {
    suggestions.value = []
  }
  expandedKey.value = null
})

const subtitleKey = computed(() =>
  props.agentName === 'chat' ? 'aiChat.welcomeChatSubtitle' : 'aiChat.welcomeSubtitle'
)

function handleSuggestionTap(prompt: string) {
  emit('selectSuggestion', prompt)
}

/** Toggle the full-prompt expansion for a card. Only one card open at a time. */
function toggleExpanded(key: string) {
  expandedKey.value = expandedKey.value === key ? null : key
}

/** Build an accessible aria-label from title + summary for screen readers. */
function cardAriaLabel(q: ResolvedWelcomeQuestion): string {
  return `${q.title}：${q.summary}`
}
</script>

<template>
  <div class="welcome-page">
    <!-- ════════════════════════════════════════════════════════════════════
         Numina (built-in) hero: logo disc + shimmer + title + suggestions
         ════════════════════════════════════════════════════════════════════ -->
    <template v-if="isNumina">
      <div class="welcome-hero">
        <div class="logo-wrap">
          <span class="logo-shimmer-ring" aria-hidden="true" />
          <span class="logo-disc">
            <AiLogo state="idle" />
          </span>
        </div>
        <h1 class="welcome-title">{{ t('aiChat.welcomeTitle') }}</h1>
        <p class="welcome-subtitle">{{ t(subtitleKey) }}</p>
      </div>

      <!-- Suggestion cards: summary as main text, prompt sent on tap.
           Info button (ⓘ) on the right reveals the full prompt inline. -->
      <div class="welcome-suggestions" role="list">
        <div
          v-for="(q, idx) in suggestions"
          :key="q.key"
          class="suggestion-card"
          :class="{ 'is-expanded': expandedKey === q.key }"
          role="button"
          tabindex="0"
          :aria-label="cardAriaLabel(q)"
          :style="{ animationDelay: `${300 + idx * 80}ms` }"
          @click="handleSuggestionTap(q.prompt)"
          @keydown.enter.prevent="handleSuggestionTap(q.prompt)"
          @keydown.space.prevent="handleSuggestionTap(q.prompt)"
        >
          <span class="card-index" aria-hidden="true">{{ String(idx + 1).padStart(2, '0') }}</span>
          <div class="card-main">
            <span class="card-summary">{{ q.summary }}</span>
            <div v-if="expandedKey === q.key" class="card-prompt-detail">
              {{ q.prompt }}
            </div>
          </div>
          <button
            type="button"
            class="card-info-btn"
            :aria-label="expandedKey === q.key ? t('aiChat.welcomeQHideFull') : t('aiChat.welcomeQShowFull')"
            :aria-expanded="expandedKey === q.key"
            @click.stop="toggleExpanded(q.key)"
          >
            <!-- "!" in circle — the user-requested exclamation mark -->
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
              <circle cx="12" cy="12" r="10" />
              <line x1="12" y1="8" x2="12" y2="12" />
              <line x1="12" y1="16" x2="12.01" y2="16" />
            </svg>
          </button>
          <svg class="card-arrow" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
            <line x1="5" y1="12" x2="19" y2="12" />
            <polyline points="12 5 19 12 12 19" />
          </svg>
        </div>
      </div>
    </template>

    <!-- ════════════════════════════════════════════════════════════════════
         Other agent hero: agent's own icon + name + description
         No suggestion cards — the curated pool is Numina-specific.
         ════════════════════════════════════════════════════════════════════ -->
    <template v-else>
      <div class="welcome-hero welcome-hero--agent">
        <div
          class="agent-disc"
          :style="{ background: agentColor }"
          :aria-label="agentLabel"
          role="img"
        >
          <span v-if="agentIcon" class="agent-emoji" aria-hidden="true">{{ agentIcon }}</span>
        </div>
        <h1 class="welcome-title welcome-title--agent">{{ agentLabel }}</h1>
        <p v-if="activeAgent?.description" class="welcome-subtitle">
          {{ activeAgent.description }}
        </p>
      </div>
    </template>

    <!-- InputBox handles hero + examples + input in welcome mode (DeerFlow pattern) -->
    <InputBox
      status="ready"
      is-welcome-mode
      :model-value="modelValue"
      :agent-id="agentId"
      :agents="agents"
      :agent-icon="agentIcon"
      :agent-label="agentLabel"
      :readonly="readonly"
      @submit="emit('startChat', $event)"
    />
  </div>
</template>

<style scoped>
.welcome-page {
  display: flex;
  flex-direction: column;
  align-items: center;
  /* Leave room for the fixed-bottom InputBox (~160px) + safe area.
     Hero sits roughly in the upper-middle third of the viewport. */
  justify-content: flex-start;
  padding: max(48px, 10vh) 20px 180px;
  min-height: 100%;
  box-sizing: border-box;
  overflow-y: auto;
}

/* ── Hero (shared base) ── */
.welcome-hero {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  margin-bottom: 28px;
  opacity: 0;
  animation: hero-fade-in 0.4s ease-out 0.05s forwards;
}

/* ── Numina logo ── */
.logo-wrap {
  position: relative;
  width: 72px;
  height: 72px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.logo-disc {
  position: relative;
  width: 56px;
  height: 56px;
  border-radius: 50%;
  background: linear-gradient(135deg, #4040ff 0%, #a07cfe 50%, #ff49fd 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 8px 24px rgba(99, 102, 241, 0.35);
  z-index: 1;
}

/* Shimmer pulse ring — the single continuous animation per the
   "animate 1-2 key elements per view" rule. */
.logo-shimmer-ring {
  position: absolute;
  inset: -6px;
  border-radius: 50%;
  background: radial-gradient(
    circle,
    rgba(99, 102, 241, 0.35) 0%,
    rgba(160, 124, 254, 0.2) 40%,
    transparent 70%
  );
  animation: logo-pulse 2.8s ease-in-out infinite;
  z-index: 0;
}

@keyframes logo-pulse {
  0%, 100% {
    transform: scale(1);
    opacity: 0.6;
  }
  50% {
    transform: scale(1.18);
    opacity: 1;
  }
}

/* ── Other agent disc ──
 * No shimmer — respects the "single continuous anim" rule. The agent's
 * brand color fills the disc background (inline style from agentColor). */
.agent-disc {
  width: 64px;
  height: 64px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 8px 20px rgba(0, 0, 0, 0.15);
}

.agent-emoji {
  font-size: 32px;
  line-height: 1;
}

/* ── Hero fade-in (shared) ── */
@keyframes hero-fade-in {
  from {
    opacity: 0;
    transform: translateY(-6px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

/* ── Title ── */
.welcome-title {
  margin: 4px 0 0;
  font-size: 24px;
  font-weight: 700;
  letter-spacing: 0.5px;
  line-height: 1.2;
  color: var(--text-primary);
  /* Subtle gradient text (static — logo ring handles motion) */
  background: linear-gradient(135deg, var(--text-primary) 0%, var(--van-primary-color) 100%);
  background-clip: text;
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  text-align: center;
}

/* Agent-specific title: solid color, no gradient — keeps focus on the agent's
 * own brand identity rather than Numina's gradient palette. */
.welcome-title--agent {
  background: none;
  -webkit-text-fill-color: var(--text-primary);
  color: var(--text-primary);
}

.welcome-subtitle {
  margin: 0;
  font-size: 13px;
  color: var(--text-secondary);
  text-align: center;
  line-height: 1.5;
  max-width: 300px;
  /* 2-line clamp for long agent descriptions */
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

/* ── Suggestion cards ── */
.welcome-suggestions {
  display: flex;
  flex-direction: column;
  gap: 10px;
  width: 100%;
  max-width: 380px;
}

.suggestion-card {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 14px 16px;
  border-radius: 16px;
  border: 1px solid rgba(99, 102, 241, 0.18);
  background:
    linear-gradient(135deg,
      color-mix(in srgb, var(--van-primary-color) 6%, var(--card-bg, #fff)) 0%,
      color-mix(in srgb, var(--van-primary-color) 2%, var(--card-bg, #fff)) 100%);
  cursor: pointer;
  text-align: left;
  font-family: inherit;
  transition:
    transform 0.18s ease,
    box-shadow 0.18s ease,
    border-color 0.18s ease,
    background 0.2s ease;
  opacity: 0;
  animation: card-fade-in 0.35s ease-out forwards;
  min-height: 52px; /* > 44pt touch target */
  box-sizing: border-box;
  width: 100%;
  outline: none;
}

.suggestion-card:hover {
  transform: translateY(-2px);
  border-color: var(--van-primary-color);
  box-shadow: 0 8px 24px rgba(99, 102, 241, 0.15);
}

.suggestion-card:active {
  transform: translateY(0);
  box-shadow: 0 4px 12px rgba(99, 102, 241, 0.1);
}

/* Keyboard focus: visible outline per WCAG 2.4.7 */
.suggestion-card:focus-visible {
  outline: 2px solid var(--van-primary-color);
  outline-offset: 2px;
}

.card-index {
  font-size: 11px;
  font-weight: 600;
  color: var(--van-primary-color);
  min-width: 18px;
  font-variant-numeric: tabular-nums;
  flex-shrink: 0;
  /* Vertically center with the first line of the summary */
  line-height: 20px;
  padding-top: 1px;
}

/* Main column: summary + (optional) expanded prompt */
.card-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 6px;
  min-width: 0; /* allow children to truncate */
}

.card-summary {
  font-size: 14px;
  font-weight: 400;
  color: var(--text-primary);
  line-height: 1.45;
  /* 2 lines max, then ellipsis */
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  text-overflow: ellipsis;
  word-break: break-word;
}

/* When expanded: release the 2-line clamp so the summary shows fully too */
.is-expanded .card-summary {
  -webkit-line-clamp: unset;
  display: block;
}

/* Full prompt detail — shown below summary when expanded.
 * Subtle style: smaller, muted color, separated by a thin divider. */
.card-prompt-detail {
  font-size: 12.5px;
  color: var(--text-secondary);
  line-height: 1.55;
  padding-top: 8px;
  margin-top: 2px;
  border-top: 1px dashed color-mix(in srgb, var(--van-primary-color) 25%, transparent);
  word-break: break-word;
  animation: prompt-fade-in 0.2s ease-out;
}

@keyframes prompt-fade-in {
  from {
    opacity: 0;
    transform: translateY(-4px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

/* ── Info button (ⓘ) ──
 * Circular icon between card-main and the arrow. Tapping it reveals
 * the full prompt text. @click.stop prevents the card's send action.
 * 28×28 visual with ~32×32 padded hit area — acceptable because the
 * whole card is itself a 44pt+ tap target (a11y exception for secondary
 * controls inside larger tappable regions). */
.card-info-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  padding: 0;
  margin: 0;
  border: none;
  border-radius: 50%;
  background: transparent;
  color: var(--text-secondary);
  cursor: pointer;
  flex-shrink: 0;
  transition: background 0.15s ease, color 0.15s ease, transform 0.15s ease;
  /* Visually align with the first line of summary */
  margin-top: -2px;
}

.card-info-btn svg {
  width: 16px;
  height: 16px;
  display: block;
  transition: transform 0.2s ease;
}

.card-info-btn:hover {
  background: color-mix(in srgb, var(--van-primary-color) 14%, transparent);
  color: var(--van-primary-color);
}

.card-info-btn:active {
  transform: scale(0.92);
}

/* Expanded state: info button flips to hint it can be collapsed */
.is-expanded .card-info-btn {
  color: var(--van-primary-color);
}

.is-expanded .card-info-btn svg {
  transform: rotate(180deg);
}

.card-arrow {
  width: 14px;
  height: 14px;
  color: var(--text-secondary);
  opacity: 0.55;
  transition: transform 0.18s ease, opacity 0.18s ease, color 0.18s ease;
  flex-shrink: 0;
  /* Vertically center with the first line of summary */
  margin-top: 3px;
}

.suggestion-card:hover .card-arrow {
  opacity: 1;
  transform: translateX(3px);
  color: var(--van-primary-color);
}

@keyframes card-fade-in {
  from {
    opacity: 0;
    transform: translateY(10px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

/* ── Dark mode ──
 * Strengthen border/background contrast so cards remain legible on dark canvas.
 * --van-primary-color in dark is #bdbbff (lighter) — border opacity bumped. */
:global([data-theme='dark']) .logo-disc {
  box-shadow: 0 8px 24px rgba(99, 102, 241, 0.55);
}

:global([data-theme='dark']) .agent-disc {
  box-shadow: 0 8px 20px rgba(0, 0, 0, 0.4);
}

:global([data-theme='dark']) .suggestion-card {
  border-color: rgba(189, 187, 255, 0.22);
  background:
    linear-gradient(135deg,
      color-mix(in srgb, var(--van-primary-color) 12%, var(--card-bg, #12122a)) 0%,
      color-mix(in srgb, var(--van-primary-color) 5%, var(--card-bg, #12122a)) 100%);
}

:global([data-theme='dark']) .suggestion-card:hover {
  border-color: var(--van-primary-color);
  box-shadow: 0 8px 24px rgba(189, 187, 255, 0.18);
}

:global([data-theme='dark']) .card-index {
  /* #bdbdff on dark bg — full opacity for ≥3:1 UI contrast */
  opacity: 1;
}

/* ── Reduced motion ── */
@media (prefers-reduced-motion: reduce) {
  .logo-shimmer-ring { animation: none; }
  .welcome-hero { animation: none; opacity: 1; }
  .suggestion-card { animation: none; opacity: 1; }
}

/* ── Responsive (375px) ── */
@media (max-width: 375px) {
  .welcome-page {
    padding: 36px 16px 160px;
  }
  .logo-wrap {
    width: 60px;
    height: 60px;
  }
  .logo-disc {
    width: 48px;
    height: 48px;
  }
  .agent-disc {
    width: 56px;
    height: 56px;
  }
  .agent-emoji {
    font-size: 28px;
  }
  .welcome-title {
    font-size: 20px;
  }
  .suggestion-card {
    padding: 12px 14px;
    gap: 10px;
  }
  .card-summary {
    font-size: 13px;
  }
}
</style>
