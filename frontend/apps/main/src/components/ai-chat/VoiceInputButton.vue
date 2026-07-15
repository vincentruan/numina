<script setup lang="ts">
/**
 * VoiceInputButton — mic button with pulse animation while listening
 *
 * Hidden when browser doesn't support Web Speech API.
 * Shows tooltip on first click explaining permission requirement.
 * Disabled state when permission denied.
 */
import { ref, computed, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useSpeechRecognition } from '@/composables/ai-chat/useSpeechRecognition'

const { t } = useI18n()

const emit = defineEmits<{
  result: [text: string]
  error: [message: string]
}>()

const { isSupported, isListening, transcript, error, start, stop } = useSpeechRecognition()

// Track first click for permission tooltip
const hasClickedOnce = ref(false)
const showTooltip = ref(false)

// Permission denied state
const isPermissionDenied = computed(() => error.value === 'permission-denied')

// Disabled when not supported or permission denied
const isDisabled = computed(() => !isSupported.value || isPermissionDenied.value)

// Button title/tooltip text
const buttonTitle = computed(() => {
  if (isPermissionDenied.value) return t('aiChat.voiceErrorPermission')
  if (!isSupported.value) return t('aiChat.voiceErrorNotSupported')
  if (isListening.value) return t('aiChat.voiceListening')
  return t('aiChat.voiceTooltip')
})

function handleClick() {
  if (isDisabled.value) return

  if (!hasClickedOnce.value) {
    hasClickedOnce.value = true
    showTooltip.value = true
    // Auto-hide tooltip after 3s
    setTimeout(() => { showTooltip.value = false }, 3000)
  }

  if (isListening.value) {
    stop()
  } else {
    start()
  }
}

// When transcript updates, emit it
watch(transcript, (val) => {
  if (val) emit('result', val)
})

// When error occurs, emit it
watch(error, (val) => {
  if (val && val !== 'permission-denied') {
    emit('error', val)
  }
})
</script>

<template>
  <div class="voice-input-wrapper">
    <!-- Tooltip -->
    <Transition name="tooltip-fade">
      <div v-if="showTooltip && !isListening" class="voice-tooltip">
        {{ t('aiChat.voiceTooltipFirst') }}
      </div>
    </Transition>

    <button
      class="voice-btn"
      :class="{
        'voice-btn--listening': isListening,
        'voice-btn--disabled': isDisabled,
      }"
      :disabled="isDisabled"
      :aria-label="buttonTitle"
      :title="buttonTitle"
      @click="handleClick"
    >
      <!-- Mic icon -->
      <svg
        width="20"
        height="20"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        stroke-width="2"
        stroke-linecap="round"
        stroke-linejoin="round"
        aria-hidden="true"
      >
        <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"/>
        <path d="M19 10v2a7 7 0 0 1-14 0v-2"/>
        <line x1="12" y1="19" x2="12" y2="23"/>
        <line x1="8" y1="23" x2="16" y2="23"/>
      </svg>

      <!-- Disabled overlay icon (ban/slash) — same size as the button -->
      <svg
        v-if="isDisabled"
        class="voice-disabled-icon"
        width="44"
        height="44"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        stroke-width="2"
        stroke-linecap="round"
        stroke-linejoin="round"
        aria-hidden="true"
      >
        <circle cx="12" cy="12" r="10"/>
        <line x1="4.93" y1="4.93" x2="19.07" y2="19.07"/>
      </svg>

      <!-- Pulse rings while listening -->
      <span v-if="isListening" class="pulse-ring pulse-ring--1" aria-hidden="true"></span>
      <span v-if="isListening" class="pulse-ring pulse-ring--2" aria-hidden="true"></span>
    </button>
  </div>
</template>

<style scoped>
.voice-input-wrapper {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
}

.voice-tooltip {
  position: absolute;
  bottom: calc(100% + 8px);
  left: 50%;
  transform: translateX(-50%);
  background: var(--bg-primary, #1a1a2e);
  color: var(--text-primary, #ffffff);
  font-size: 12px;
  padding: 6px 10px;
  border-radius: 6px;
  white-space: nowrap;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.2);
  z-index: 1000;
  pointer-events: none;
}

.voice-tooltip::after {
  content: '';
  position: absolute;
  top: 100%;
  left: 50%;
  transform: translateX(-50%);
  border: 4px solid transparent;
  border-top-color: var(--bg-primary, #1a1a2e);
}

.tooltip-fade-enter-active,
.tooltip-fade-leave-active {
  transition: opacity 0.2s ease;
}

.tooltip-fade-enter-from,
.tooltip-fade-leave-to {
  opacity: 0;
}

.voice-btn {
  width: 36px;
  height: 36px;
  min-width: 44px;
  min-height: 44px;
  border-radius: 50%;
  border: none;
  background: rgba(99, 102, 241, 0.08);
  color: var(--ai-btn-color, #666);
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: background 0.2s, color 0.2s, transform 0.15s;
  position: relative;
}

.voice-btn:hover {
  background: rgba(99, 102, 241, 0.15);
  color: var(--ai-btn-hover-color, #333);
}

.voice-btn:active {
  transform: scale(0.92);
}

.voice-btn--listening {
  background: rgba(239, 68, 68, 0.15);
  color: #ef4444;
}

.voice-btn--listening:hover {
  background: rgba(239, 68, 68, 0.25);
}

.voice-btn--disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.voice-btn--disabled:hover {
  background: rgba(99, 102, 241, 0.08);
  color: var(--ai-btn-color, #666);
}

.voice-disabled-icon {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  color: rgba(239, 68, 68, 0.6);
  pointer-events: none;
}

/* Pulse animation rings */
.pulse-ring {
  position: absolute;
  top: 50%;
  left: 50%;
  width: 100%;
  height: 100%;
  border-radius: 50%;
  border: 2px solid rgba(239, 68, 68, 0.4);
  transform: translate(-50%, -50%) scale(1);
  animation: pulse-expand 1.5s ease-out infinite;
  pointer-events: none;
}

.pulse-ring--2 {
  animation-delay: 0.5s;
}

@keyframes pulse-expand {
  0% {
    transform: translate(-50%, -50%) scale(1);
    opacity: 1;
  }
  100% {
    transform: translate(-50%, -50%) scale(1.8);
    opacity: 0;
  }
}

@media (prefers-reduced-motion: reduce) {
  .pulse-ring {
    animation: none;
  }
  .voice-btn {
    transition: none;
  }
}
</style>
