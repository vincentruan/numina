<template>
  <Teleport to="body">
    <Transition name="celebration-fade">
      <div
        v-if="visible"
        class="celebration-overlay"
        role="dialog"
        aria-modal="true"
        :aria-label="t('celebration.overlayLabel')"
        @click="dismiss"
      >
        <!-- Flying stars -->
        <div class="stars-container" aria-hidden="true">
          <span v-for="i in starCount" :key="i" class="star" :style="starStyle(i)" />
        </div>

        <!-- Encouraging phrase -->
        <Transition name="phrase-fade">
          <div v-if="showPhrase" class="phrase-container">
            <span class="phrase">{{ randomPhrase }}</span>
          </div>
        </Transition>

        <!-- Summary card -->
        <Transition name="card-pop">
          <div v-if="showSummary" class="summary-card" @click.stop>
            <template v-if="taskCount > 1">
              <span class="summary-text">{{ t('celebration.multipleTasks', { count: taskCount, stars: starsEarned }) }}</span>
            </template>
            <template v-else>
              <span class="summary-text">{{ t('celebration.singleTask', { stars: starsEarned }) }}</span>
            </template>
          </div>
        </Transition>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup lang="ts">
import { ref, computed, watch, onUnmounted } from 'vue'
import { useI18n } from 'vue-i18n'

const props = defineProps<{
  visible: boolean
  taskCount: number
  starsEarned: number
}>()

const emit = defineEmits<{
  dismiss: []
}>()

const { t } = useI18n()

// Animation state
const showPhrase = ref(false)
const showSummary = ref(false)
const animationPhase = ref(0)

// Random phrase selection
const randomPhrase = computed(() => {
  const phrases = t('celebration.phrases') as unknown as string[]
  if (Array.isArray(phrases) && phrases.length > 0) {
    return phrases[Math.floor(Math.random() * phrases.length)]
  }
  return '太棒了！'
})

// Star count: cap at 6-8 for visual
const starCount = computed(() => Math.min(props.taskCount + 2, 8))

// Star positioning: staggered launch positions and delays
function starStyle(i: number) {
  const startX = 10 + (i % 4) * 20 // 10%, 30%, 50%, 70%
  const startY = 70 + Math.floor(i / 4) * 15 // 70%, 85%
  const delay = 0.3 + i * 0.15 // staggered delays
  const rotation = -15 + Math.random() * 30 // varied rotation

  return {
    '--start-x': `${startX}%`,
    '--start-y': `${startY}%`,
    '--delay': `${delay}s`,
    '--rotation': `${rotation}deg`,
  }
}

// Animation choreography
let animationTimer: ReturnType<typeof setTimeout> | null = null

function startAnimation() {
  animationPhase.value = 1
  showPhrase.value = false
  showSummary.value = false

  // Phase 2: Phrase appear (0.2s)
  animationTimer = setTimeout(() => {
    showPhrase.value = true
    animationPhase.value = 2
  }, 200)

  // Phase 3-4: Stars launch + balance pulse (1.5s)
  animationTimer = setTimeout(() => {
    animationPhase.value = 3
  }, 1500)

  // Phase 5: Summary card (1.8s)
  animationTimer = setTimeout(() => {
    showSummary.value = true
    animationPhase.value = 4
  }, 1800)

  // Phase 6: Fade out + dismiss (2.5-3s)
  animationTimer = setTimeout(() => {
    animationPhase.value = 5
    dismiss()
  }, 2800)
}

function dismiss() {
  if (animationTimer) {
    clearTimeout(animationTimer)
    animationTimer = null
  }
  showPhrase.value = false
  showSummary.value = false
  animationPhase.value = 0
  emit('dismiss')
}

// Watch visibility to trigger animation
watch(() => props.visible, (newVal) => {
  if (newVal) {
    startAnimation()
  } else {
    if (animationTimer) {
      clearTimeout(animationTimer)
      animationTimer = null
    }
    showPhrase.value = false
    showSummary.value = false
    animationPhase.value = 0
  }
})

onUnmounted(() => {
  if (animationTimer) {
    clearTimeout(animationTimer)
  }
})
</script>

<style scoped>
/* ── Overlay ── */
.celebration-overlay {
  position: fixed;
  inset: 0;
  z-index: 1000;
  background: rgba(10, 10, 10, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
}

[data-theme="dark"] .celebration-overlay {
  background: rgba(10, 26, 26, 0.6);
}

/* ── Flying stars ── */
.stars-container {
  position: absolute;
  inset: 0;
  pointer-events: none;
}

.star {
  position: absolute;
  left: var(--start-x);
  top: var(--start-y);
  width: 28px;
  height: 28px;
  background: url('@/assets/icons/star-glow.svg') center/contain no-repeat;
  animation: star-fly 1.2s ease-out forwards;
  animation-delay: var(--delay);
  transform: rotate(var(--rotation));
  opacity: 0;
}

@keyframes star-fly {
  0% {
    opacity: 0;
    transform: translate(0, 0) rotate(var(--rotation)) scale(0.5);
  }
  20% {
    opacity: 1;
    transform: translate(20px, -30px) rotate(var(--rotation)) scale(1);
  }
  100% {
    opacity: 0.9;
    transform: translate(calc(50% - var(--start-x)), calc(-65vh)) rotate(calc(var(--rotation) + 180deg)) scale(0.8);
  }
}

/* ── Phrase ── */
.phrase-container {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  text-align: center;
  z-index: 10;
}

.phrase {
  font-family: Inter, sans-serif;
  font-size: 22px;
  font-weight: 600;
  color: var(--color-ink);
  background: var(--color-canvas);
  padding: 12px 28px;
  border-radius: var(--radius-lg);
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.15);
}

[data-theme="dark"] .phrase {
  background: var(--color-surface-dark-elevated);
  color: var(--color-on-dark);
}

/* ── Summary card ── */
.summary-card {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  background: var(--color-surface-card);
  border-radius: var(--radius-xl);
  padding: 24px 32px;
  text-align: center;
  z-index: 20;
  border: 1px solid var(--color-hairline);
  max-width: 280px;
  width: 90%;
}

[data-theme="dark"] .summary-card {
  background: var(--color-surface-dark-elevated);
  border-color: var(--color-hairline-soft);
}

.summary-text {
  font-family: Inter, sans-serif;
  font-size: 18px;
  font-weight: 600;
  color: var(--color-ink);
  line-height: 1.4;
}

[data-theme="dark"] .summary-text {
  color: var(--color-on-dark);
}

/* ── Transitions ── */
.celebration-fade-enter-active {
  animation: overlay-fade-in 0.2s ease-out;
}

.celebration-fade-leave-active {
  animation: overlay-fade-out 0.3s ease-in forwards;
}

@keyframes overlay-fade-in {
  from { opacity: 0; }
  to { opacity: 1; }
}

@keyframes overlay-fade-out {
  from { opacity: 1; }
  to { opacity: 0; }
}

.phrase-fade-enter-active {
  animation: phrase-pop 0.3s cubic-bezier(0.175, 0.885, 0.32, 1.275);
}

.phrase-fade-leave-active {
  animation: phrase-fade 0.2s ease-out forwards;
}

@keyframes phrase-pop {
  from {
    opacity: 0;
    transform: translate(-50%, -50%) scale(0.8);
  }
  to {
    opacity: 1;
    transform: translate(-50%, -50%) scale(1);
  }
}

@keyframes phrase-fade {
  from { opacity: 1; }
  to { opacity: 0; }
}

.card-pop-enter-active {
  animation: card-pop 0.4s cubic-bezier(0.175, 0.885, 0.32, 1.275);
}

.card-pop-leave-active {
  animation: card-fade 0.2s ease-out forwards;
}

@keyframes card-pop {
  from {
    opacity: 0;
    transform: translate(-50%, -50%) scale(0.6);
  }
  to {
    opacity: 1;
    transform: translate(-50%, -50%) scale(1);
  }
}

@keyframes card-fade {
  from { opacity: 1; }
  to { opacity: 0; }
}
</style>