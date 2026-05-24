<template>
  <Teleport to="body">
    <Transition name="popup-fade">
      <div
        v-if="visible"
        class="popup-overlay"
        role="dialog"
        aria-modal="true"
        :aria-label="t('celebration.overlayLabel')"
      >
        <div class="popup-card">
          <div class="popup-emoji">🎁</div>
          <h2 class="popup-title">
            {{ taskCount > 1
              ? t('celebration.multipleTasks', { count: taskCount, stars: starsEarned })
              : t('celebration.treasureUnlocked') }}
          </h2>
          <p class="popup-phrase">{{ randomPhrase }}</p>
          <p v-if="taskCount === 1" class="popup-stars">
            {{ t('celebration.singleTask', { stars: starsEarned }) }}
          </p>
          <button
            type="button"
            class="popup-confirm"
            :class="{ 'fade-in': showConfirm }"
            @click="onConfirm"
          >
            {{ t('celebration.confirmButton') }}
          </button>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup lang="ts">
import { ref, computed, watch, onUnmounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { tryVibrate } from '@/composables/useHaptic'
import { MOTION } from '@/utils/motionTokens'

const props = defineProps<{
  visible: boolean
  taskCount: number
  starsEarned: number
}>()

const emit = defineEmits<{
  confirm: []
  'auto-dismiss': []
}>()

const { t } = useI18n()

const showConfirm = ref(false)
let confirmTimer: ReturnType<typeof setTimeout> | null = null
let autoDismissTimer: ReturnType<typeof setTimeout> | null = null

const randomPhrase = computed(() => {
  const phrases = t('celebration.phrases') as unknown as string[]
  if (Array.isArray(phrases) && phrases.length > 0) {
    return phrases[Math.floor(Math.random() * phrases.length)]
  }
  return ''
})

function clearTimers(): void {
  if (confirmTimer) {
    clearTimeout(confirmTimer)
    confirmTimer = null
  }
  if (autoDismissTimer) {
    clearTimeout(autoDismissTimer)
    autoDismissTimer = null
  }
}

function onConfirm(): void {
  clearTimers()
  emit('confirm')
}

watch(
  () => props.visible,
  (v) => {
    if (v) {
      showConfirm.value = false
      tryVibrate(MOTION.haptic.arrival)
      confirmTimer = setTimeout(() => {
        showConfirm.value = true
      }, MOTION.durations.medium)
      autoDismissTimer = setTimeout(() => {
        emit('auto-dismiss')
      }, 6000)
    } else {
      clearTimers()
    }
  },
  { immediate: true },
)

onUnmounted(clearTimers)
</script>

<style scoped>
.popup-overlay {
  position: fixed;
  inset: 0;
  z-index: 1000;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(10, 10, 10, 0.5);
}

[data-theme='dark'] .popup-overlay {
  background: rgba(10, 26, 26, 0.6);
}

.popup-card {
  position: relative;
  max-width: 320px;
  width: 86%;
  padding: 32px 28px 24px;
  text-align: center;
  border-radius: 24px;
  background:
    radial-gradient(
      ellipse at center,
      var(--color-brand-peach) 0%,
      var(--color-brand-ochre) 70%,
      var(--color-surface-card) 100%
    );
  box-shadow: 0 12px 40px rgba(0, 0, 0, 0.25);
  animation: card-pop 400ms cubic-bezier(0.175, 0.885, 0.32, 1.275);
}

[data-theme='dark'] .popup-card {
  background:
    radial-gradient(
      ellipse at center,
      var(--color-brand-peach) 0%,
      var(--color-brand-ochre) 70%,
      var(--color-surface-dark-elevated) 100%
    );
}

.popup-emoji {
  font-size: 56px;
  line-height: 1;
  margin-bottom: 12px;
  animation: emoji-pop 300ms cubic-bezier(0.175, 0.885, 0.32, 1.275) 100ms backwards;
}

.popup-title {
  font-family: Inter, sans-serif;
  font-size: 22px;
  font-weight: 700;
  color: var(--color-ink);
  margin: 0 0 8px;
}

.popup-phrase {
  font-family: Inter, sans-serif;
  font-size: 16px;
  font-weight: 600;
  color: var(--color-ink);
  margin: 0 0 8px;
  opacity: 0.9;
}

.popup-stars {
  font-family: Inter, sans-serif;
  font-size: 18px;
  font-weight: 700;
  color: var(--color-ink);
  margin: 0 0 20px;
}

.popup-confirm {
  margin-top: 8px;
  padding: 12px 32px;
  font-family: Inter, sans-serif;
  font-size: 16px;
  font-weight: 700;
  color: var(--color-ink);
  background: var(--color-canvas);
  border: 2px solid var(--color-ink);
  border-radius: 999px;
  cursor: pointer;
  opacity: 0;
  transition: opacity 200ms ease-out, transform 100ms ease-out;
}

.popup-confirm.fade-in {
  opacity: 1;
}

.popup-confirm:active {
  transform: scale(0.96);
}

[data-theme='dark'] .popup-confirm {
  background: var(--color-surface-dark-elevated);
  color: var(--color-on-dark);
  border-color: var(--color-brand-ochre);
}

@keyframes card-pop {
  0% {
    opacity: 0;
    transform: scale(0.6);
  }
  100% {
    opacity: 1;
    transform: scale(1);
  }
}

@keyframes emoji-pop {
  0% {
    opacity: 0;
    transform: scale(0.4);
  }
  100% {
    opacity: 1;
    transform: scale(1);
  }
}

.popup-fade-enter-active {
  animation: overlay-fade 200ms ease-out;
}

.popup-fade-leave-active {
  animation: overlay-fade 300ms ease-in reverse forwards;
}

@keyframes overlay-fade {
  from {
    opacity: 0;
  }
  to {
    opacity: 1;
  }
}
</style>
