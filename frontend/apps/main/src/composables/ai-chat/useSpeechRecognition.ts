/**
 * useSpeechRecognition — Web Speech API wrapper for voice input
 *
 * Feature detection, silence timeout restart, max duration auto-stop.
 */
import { ref, onUnmounted } from 'vue'

interface SpeechRecognitionEvent extends Event {
  results: SpeechRecognitionResultList
  resultIndex: number
}

interface SpeechRecognitionErrorEvent extends Event {
  error: string
  message: string
}

interface SpeechRecognitionInstance extends EventTarget {
  continuous: boolean
  interimResults: boolean
  lang: string
  start(): void
  stop(): void
  abort(): void
  onresult: ((event: SpeechRecognitionEvent) => void) | null
  onerror: ((event: SpeechRecognitionErrorEvent) => void) | null
  onend: (() => void) | null
}

type SpeechRecognitionCtor = new () => SpeechRecognitionInstance

const isSupported = ref(
  typeof window !== 'undefined' &&
    ('SpeechRecognition' in window || 'webkitSpeechRecognition' in window),
)

export function useSpeechRecognition(options?: {
  silenceTimeout?: number
  maxDuration?: number
  lang?: string
}) {
  const silenceTimeout = options?.silenceTimeout ?? 1500
  const maxDuration = options?.maxDuration ?? 60000
  const lang = options?.lang ?? navigator.language ?? 'zh-CN'

  const isListening = ref(false)
  const transcript = ref('')
  const error = ref('')

  let recognition: SpeechRecognitionInstance | null = null
  let silenceTimer: ReturnType<typeof setTimeout> | null = null
  let maxDurationTimer: ReturnType<typeof setTimeout> | null = null
  let shouldRestart = false

  function getRecognition(): SpeechRecognitionInstance | null {
    if (!isSupported.value) return null
    const Ctor = (window as unknown as Record<string, SpeechRecognitionCtor>).SpeechRecognition
      ?? (window as unknown as Record<string, SpeechRecognitionCtor>).webkitSpeechRecognition
    return new Ctor()
  }

  function resetSilenceTimer() {
    if (silenceTimer) clearTimeout(silenceTimer)
    silenceTimer = setTimeout(() => {
      // No new results for silenceTimeout — stop and emit what we have
      if (recognition && isListening.value) {
        shouldRestart = false
        recognition.stop()
      }
    }, silenceTimeout)
  }

  function start() {
    if (!isSupported.value) {
      error.value = 'not-supported'
      return
    }
    if (isListening.value) return

    error.value = ''
    transcript.value = ''
    shouldRestart = true

    recognition = getRecognition()
    if (!recognition) return

    recognition.continuous = true
    recognition.interimResults = false
    recognition.lang = lang

    recognition.onresult = (event: SpeechRecognitionEvent) => {
      resetSilenceTimer()
      for (let i = event.resultIndex; i < event.results.length; i++) {
        const result = event.results[i]
        if (result.isFinal) {
          transcript.value += result[0].transcript
        }
      }
    }

    recognition.onerror = (event: SpeechRecognitionErrorEvent) => {
      // 'no-speech' and 'aborted' are expected — don't surface as errors
      if (event.error === 'no-speech' || event.error === 'aborted') return
      error.value = event.error === 'not-allowed' ? 'permission-denied' : event.error
      isListening.value = false
      shouldRestart = false
    }

    recognition.onend = () => {
      if (shouldRestart && isListening.value) {
        // Restart for silence-timeout continuation
        try {
          recognition?.start()
          resetSilenceTimer()
        } catch {
          isListening.value = false
        }
      } else {
        isListening.value = false
      }
    }

    try {
      recognition.start()
      isListening.value = true
      resetSilenceTimer()
    } catch {
      error.value = 'start-failed'
      isListening.value = false
    }

    // Max duration auto-stop
    maxDurationTimer = setTimeout(() => {
      if (recognition && isListening.value) {
        shouldRestart = false
        recognition.stop()
      }
    }, maxDuration)
  }

  function stop() {
    shouldRestart = false
    if (silenceTimer) {
      clearTimeout(silenceTimer)
      silenceTimer = null
    }
    if (maxDurationTimer) {
      clearTimeout(maxDurationTimer)
      maxDurationTimer = null
    }
    if (recognition) {
      recognition.stop()
      recognition = null
    }
    isListening.value = false
  }

  onUnmounted(() => {
    stop()
  })

  return {
    isSupported,
    isListening,
    transcript,
    error,
    start,
    stop,
  }
}
