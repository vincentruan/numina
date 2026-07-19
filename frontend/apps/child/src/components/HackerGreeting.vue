<template>
  <p class="hacker-greeting" :class="{ 'is-scrambling': !settled }">
    <span class="hg-text">{{ display }}</span>
  </p>
</template>

<script setup lang="ts">
/**
 * Rotating "hacker terminal" greeting for the child home hero.
 *
 * Cycles through a list of greeting phrases (i18n-driven), each interpolated
 * with the child's display name and current star-coin balance. Each phrase is
 * revealed via a scramble-decode effect (see useScrambleText), held for a few
 * seconds, then advanced to the next phrase.
 *
 * Respects reduced-motion: phrases snap to their final text with no scramble.
 */
import { computed, onUnmounted, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useScrambleText } from '@/composables/useScrambleText'
import { useReducedMotion } from '@/composables/useReducedMotion'

const props = defineProps<{
  /** Child display name; falls back to a generic greeting when empty. */
  name: string
  /** Current star-coin balance, interpolated into phrases. */
  balance: number
}>()

const { tm, t } = useI18n()
const reducedMotion = useReducedMotion()

// Hold each phrase for a randomized 7–9s window. A fixed 4s cadence cut low-age
// readers off mid-sentence; the jitter also keeps the rotation from feeling
// mechanical. Deterministic pseudo-random (no Math.random) so tests stay
// reproducible — the per-advance index makes each window differ.
function holdMs(): number {
  const idx = phraseIndex
  const span = 9000 - 7000 // 2000ms window
  return 7000 + ((idx * 7 + 3) % span)
}

// Raw i18n phrase list (array of strings with {name}/{balance} placeholders).
// Using tm() so the list is reactive to locale switches.
const phrases = computed<string[]>(() => {
  const raw = tm('home.greetingPhrases') as unknown
  return Array.isArray(raw) ? (raw.filter((p) => typeof p === 'string') as string[]) : []
})

const displayName = computed(() => props.name?.trim() || t('home.greetingFallbackName'))

function buildPhrase(template: string): string {
  return template
    .replaceAll('{name}', displayName.value)
    .replaceAll('{balance}', String(props.balance ?? 0))
}

const { display, settled, setTarget } = useScrambleText({ framesPerLock: 3 })

let phraseIndex = 0
let holdTimer: ReturnType<typeof setTimeout> | null = null
let mounted = true

function clearHold() {
  if (holdTimer !== null) {
    clearTimeout(holdTimer)
    holdTimer = null
  }
}

function currentPhrase(): string {
  const list = phrases.value
  if (list.length === 0) return buildPhrase(t('home.greetingFallback'))
  return buildPhrase(list[phraseIndex % list.length])
}

function advance() {
  if (!mounted) return
  phraseIndex++
  setTarget(currentPhrase())
}

// In the animated (non-reduced-motion) path, `settled` flips false→true once
// each phrase finishes decoding, which we watch to schedule the next advance.
// In the reduced-motion path `settled` never leaves true, so that watch can't
// drive rotation — we fall back to a plain interval there.
watch(settled, (isSettled) => {
  if (!isSettled || reducedMotion.value) return
  holdTimer = setTimeout(advance, holdMs())
})

// Reduced-motion rotation: interval-based, decoupled from settled transitions.
// setInterval takes a fixed delay, so use the midpoint of the 7–9s window.
let reducedInterval: ReturnType<typeof setInterval> | null = null
function startReducedRotation() {
  if (reducedInterval) return
  reducedInterval = setInterval(advance, 8000)
}
function stopReducedRotation() {
  if (reducedInterval) {
    clearInterval(reducedInterval)
    reducedInterval = null
  }
}

// React to reduced-motion toggling at runtime: start/stop the interval path.
watch(reducedMotion, (isReduced) => {
  if (isReduced) {
    clearHold()
    stopReducedRotation()
    startReducedRotation()
    // Snap current phrase to its final form immediately.
    setTarget(currentPhrase())
  } else {
    stopReducedRotation()
    clearHold()
    setTarget(currentPhrase())
  }
})

function start() {
  clearHold()
  phraseIndex = 0
  setTarget(currentPhrase())
  if (reducedMotion.value) startReducedRotation()
}

// If name or balance changes while settled, re-decode the *current* phrase
// so the live number updates without waiting for the next rotation.
watch(
  () => [props.name, props.balance, phrases.value] as const,
  () => {
    if (settled.value) {
      setTarget(currentPhrase())
    }
  },
)

start()
onUnmounted(() => {
  mounted = false
  clearHold()
  stopReducedRotation()
})
</script>

<style scoped>
.hacker-greeting {
  display: flex;
  align-items: baseline;
  gap: 4px;
  font-family: 'JetBrains Mono', 'SFMono-Regular', Menlo, Consolas, Inter, monospace;
  font-size: clamp(15px, 4.5vw, 19px);
  font-weight: 600;
  margin: 0 0 10px;
  min-height: 22px;
  letter-spacing: 0.1px;
  /* Truncate very long greetings gracefully on narrow screens */
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.hg-text {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  /* Multi-color gradient sweep across the greeting text —
     mirrors the main app 数鸣智能体 shimmer effect (background-clip: text). */
  background: linear-gradient(
    90deg,
    var(--color-brand-pink) 0%,
    var(--color-brand-lavender) 25%,
    var(--color-brand-peach) 50%,
    var(--color-brand-mint) 75%,
    var(--color-brand-pink) 100%
  );
  background-size: 200% auto;
  background-clip: text;
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  color: transparent;
  animation: hg-shimmer 4s ease-in-out infinite;
}
/* While scrambling, freeze the gradient so the glyph noise reads cleanly. */
.hacker-greeting.is-scrambling .hg-text {
  animation: none;
}
@media (prefers-reduced-motion: reduce) {
  .hg-text { animation: none; }
  .hacker-greeting.is-scrambling .hg-text { animation: none; }
}
@keyframes hg-shimmer {
  0% { background-position: 0% 50%; }
  50% { background-position: 100% 50%; }
  100% { background-position: 0% 50%; }
}
</style>
