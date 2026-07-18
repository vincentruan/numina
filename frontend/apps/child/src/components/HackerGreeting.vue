<template>
  <p class="hacker-greeting" :class="{ 'is-scrambling': !settled }">
    <span class="hg-prompt">&gt;&nbsp;</span>
    <span class="hg-text">{{ display }}</span>
    <span class="hg-cursor" :class="{ blink: settled }">▮</span>
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

const HOLD_MS = 4000

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
  holdTimer = setTimeout(advance, HOLD_MS)
})

// Reduced-motion rotation: interval-based, decoupled from settled transitions.
let reducedInterval: ReturnType<typeof setInterval> | null = null
function startReducedRotation() {
  if (reducedInterval) return
  reducedInterval = setInterval(advance, HOLD_MS)
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
  align-items: center;
  gap: 2px;
  font-family: 'JetBrains Mono', 'SFMono-Regular', Menlo, Consolas, Inter, monospace;
  font-size: 13px;
  font-weight: 500;
  margin: 0 0 6px;
  min-height: 18px;
  letter-spacing: 0.2px;
  opacity: 0.9;
  /* Truncate very long greetings gracefully on narrow screens */
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.hg-prompt {
  opacity: 0.6;
  flex-shrink: 0;
}
.hg-text {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
}
.hg-cursor {
  flex-shrink: 0;
  opacity: 0.85;
  font-weight: 700;
}
.hg-cursor.blink {
  animation: hg-blink 1s steps(2, start) infinite;
}
.hacker-greeting.is-scrambling .hg-cursor {
  animation: none;
  opacity: 0.95;
}
@media (prefers-reduced-motion: reduce) {
  .hg-cursor.blink { animation: none; }
  .hacker-greeting.is-scrambling .hg-cursor { animation: none; }
}
@keyframes hg-blink {
  0%, 50% { opacity: 0.95; }
  50.01%, 100% { opacity: 0; }
}
</style>
