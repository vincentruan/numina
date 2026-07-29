<script setup lang="ts">
/**
 * VoiceInputButton — mic button with dual ASR strategy:
 * 1. Web Speech API (Chrome/Edge) — client-side, real-time
 * 2. Backend ASR via configured ASR provider (Safari/Firefox) — record audio, upload, transcribe
 *
 * Disabled when neither browser API nor backend ASR is available.
 */
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { showToast } from 'vant'
import { useSpeechRecognition } from '@/composables/ai-chat/useSpeechRecognition'
import { getASRStatus, transcribeAudio } from '@/api/asr'

const { t } = useI18n()

const emit = defineEmits<{
  result: [text: string]
  error: [message: string]
}>()

// ── Web Speech API mode ──
const { isSupported: speechApiSupported, isListening: speechListening, transcript, error: speechError, start: speechStart, stop: speechStop } = useSpeechRecognition()

// ── Backend ASR mode ──
const backendAsrAvailable = ref(false)
const asrStatusChecked = ref(false)
const isRecording = ref(false)
const isTranscribing = ref(false)
const micAvailable = ref(true)

let mediaRecorder: MediaRecorder | null = null
let audioChunks: Blob[] = []

// Use Web Speech API when available, otherwise fall back to backend ASR
const useSpeechApi = computed(() => speechApiSupported.value)
const isDisabled = computed(() => {
  if (useSpeechApi.value) return isPermissionDenied.value || !micAvailable.value
  return !backendAsrAvailable.value || !micAvailable.value
})
const isListening = computed(() => speechListening.value || isRecording.value)

// Permission denied state (only for Web Speech API)
const isPermissionDenied = computed(() => speechError.value === 'permission-denied')

// Compute disabled reason for tooltip
const disabledReason = computed(() => {
  if (isPermissionDenied.value) return t('aiChat.voiceErrorPermission')
  if (!micAvailable.value) return t('aiChat.voiceErrorMicUnavailable')
  if (!useSpeechApi.value && !backendAsrAvailable.value) return t('aiChat.voiceErrorASRUnavailable')
  return ''
})

// Button title/tooltip text
const buttonTitle = computed(() => {
  if (isDisabled.value) return disabledReason.value
  if (isTranscribing.value) return t('aiChat.voiceTranscribing')
  if (isListening.value) return t('aiChat.voiceListening')
  return t('aiChat.voiceTooltip')
})

// Track first click for permission tooltip
const hasClickedOnce = ref(false)
const showTooltip = ref(false)

// Check backend ASR availability + mic permission on mount
onMounted(async () => {
  // Check microphone availability
  try {
    const devices = await navigator.mediaDevices.enumerateDevices()
    micAvailable.value = devices.some(d => d.kind === 'audioinput')
  } catch {
    micAvailable.value = false
  }

  // Check backend ASR if Web Speech API not supported
  if (!speechApiSupported.value) {
    try {
      const result = await getASRStatus()
      backendAsrAvailable.value = result.data.available
    } catch {
      backendAsrAvailable.value = false
    } finally {
      asrStatusChecked.value = true
    }
  }
})

// ── Backend ASR: MediaRecorder flow ──
async function startRecording() {
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
    audioChunks = []
    mediaRecorder = new MediaRecorder(stream, { mimeType: getSupportedMimeType() })

    mediaRecorder.ondataavailable = (event) => {
      if (event.data.size > 0) audioChunks.push(event.data)
    }

    mediaRecorder.onstop = async () => {
      stream.getTracks().forEach(track => track.stop())
      const audioBlob = new Blob(audioChunks, { type: mediaRecorder!.mimeType })
      await uploadAndTranscribe(audioBlob)
    }

    mediaRecorder.start()
    isRecording.value = true

    // Auto-stop after 60 seconds
    setTimeout(() => {
      if (mediaRecorder && mediaRecorder.state === 'recording') {
        mediaRecorder.stop()
      }
    }, 60000)
  } catch {
    showToast(t('aiChat.voiceErrorPermission'))
    emit('error', 'permission-denied')
  }
}

function stopRecording() {
  if (mediaRecorder && mediaRecorder.state === 'recording') {
    mediaRecorder.stop()
    isRecording.value = false
  }
}

async function uploadAndTranscribe(audioBlob: Blob) {
  isTranscribing.value = true
  try {
    const file = new File([audioBlob], 'voice.webm', { type: audioBlob.type })
    const result = await transcribeAudio(file)
    if (result.text) {
      emit('result', result.text)
    }
  } catch {
    showToast(t('aiChat.voiceTranscribeFailed'))
    emit('error', 'transcribe-failed')
  } finally {
    isTranscribing.value = false
  }
}

function getSupportedMimeType(): string {
  const types = [
    'audio/webm;codecs=opus',
    'audio/webm',
    'audio/ogg;codecs=opus',
    'audio/mp4',
  ]
  for (const type of types) {
    if (MediaRecorder.isTypeSupported(type)) return type
  }
  return ''
}

// ── Unified click handler ──
function handleClick() {
  if (isDisabled.value || isTranscribing.value) return

  if (!hasClickedOnce.value) {
    hasClickedOnce.value = true
    showTooltip.value = true
    setTimeout(() => { showTooltip.value = false }, 3000)
  }

  if (useSpeechApi.value) {
    if (speechListening.value) {
      speechStop()
    } else {
      speechStart()
    }
  } else {
    if (isRecording.value) {
      stopRecording()
    } else {
      startRecording()
    }
  }
}

// When transcript updates (Web Speech API), emit it
watch(transcript, (val) => {
  if (val) emit('result', val)
})

// When Web Speech API error occurs, emit it
watch(speechError, (val) => {
  if (val && val !== 'permission-denied') {
    emit('error', val)
  }
})

onUnmounted(() => {
  if (mediaRecorder && mediaRecorder.state === 'recording') {
    mediaRecorder.stop()
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
        'voice-btn--transcribing': isTranscribing,
      }"
      :disabled="isDisabled || isTranscribing"
      :aria-label="buttonTitle"
      :title="buttonTitle"
      @click="handleClick"
    >
      <!-- Mic icon -->
      <svg
        v-if="!isTranscribing"
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

      <!-- Spinner while transcribing -->
      <svg v-else class="voice-spinner" width="20" height="20" viewBox="0 0 24 24" aria-hidden="true">
        <circle cx="12" cy="12" r="10" fill="none" stroke="currentColor" stroke-width="2" stroke-dasharray="31.4 31.4" stroke-linecap="round"/>
      </svg>

      <!-- Disabled overlay icon (ban/slash) -->
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

.voice-btn--transcribing {
  background: rgba(99, 102, 241, 0.15);
  color: #6366f1;
  cursor: wait;
}

.voice-disabled-icon {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  color: rgba(239, 68, 68, 0.6);
  pointer-events: none;
}

.voice-spinner {
  animation: voice-spin 1s linear infinite;
}

@keyframes voice-spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
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
  .voice-spinner {
    animation: none;
  }
}
</style>
