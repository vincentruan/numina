import { ref, onUnmounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { refreshTokenIfNeeded } from '@numina/auth'

export type StreamStatus = 'idle' | 'connecting' | 'analyzing' | 'completed' | 'error'

export function useAIReportStream() {
  const { t } = useI18n()
  const status = ref<StreamStatus>('idle')
  const progressMessage = ref('')
  const report = ref<Record<string, unknown> | null>(null)
  const generatedAt = ref<string | null>(null)
  const errorMessage = ref('')

  let abortController: AbortController | null = null

  async function connect(): Promise<void> {
    abortController = new AbortController()
    const signal = abortController.signal

    status.value = 'connecting'
    progressMessage.value = t('wsErrors.connecting')

    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      Accept: 'application/x-ndjson',
    }

    let res = await fetch('/api/v1/ai/report/generate/events', {
      method: 'POST',
      headers,
      credentials: 'include',
      signal,
    })

    if (res.status === 401) {
      try {
        await refreshTokenIfNeeded()
      } catch {
        status.value = 'error'
        errorMessage.value = t('wsErrors.authFailed')
        throw new Error('401')
      }
      res = await fetch('/api/v1/ai/report/generate/events', {
        method: 'POST',
        headers,
        credentials: 'include',
        signal,
      })
    }

    if (!res.ok) {
      status.value = 'error'
      const detail = res.headers.get('Content-Type')?.includes('application/json')
        ? (await res.json()).detail
        : res.statusText
      errorMessage.value = detail || t('wsErrors.connectionFailed')
      throw new Error(`${res.status}`)
    }

    if (!res.body) {
      status.value = 'error'
      errorMessage.value = t('wsErrors.connectionFailed')
      throw new Error('streaming_not_supported')
    }

    status.value = 'analyzing'
    progressMessage.value = t('aiHub.reportGenerating')

    const reader = res.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''

    try {
      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() || ''

        for (const line of lines) {
          if (!line.trim()) continue
          try {
            const event = JSON.parse(line)
            if (event.type === 'capability.progress') {
              progressMessage.value = event.message || t('aiHub.reportGenerating')
            } else if (event.type === 'capability.end') {
              const result = event.result
              if (result?.structured_data) {
                report.value = result.structured_data
                generatedAt.value = new Date().toISOString()
                status.value = 'completed'
              } else if (result?.summary) {
                // Parse structured data from summary if embedded
                const match = result.summary.match(/<!-- STRUCTURED_DATA (.+?) -->/)
                if (match) {
                  report.value = JSON.parse(match[1])
                  generatedAt.value = new Date().toISOString()
                  status.value = 'completed'
                }
              }
            } else if (event.type === 'capability.error') {
              status.value = 'error'
              errorMessage.value = event.message || t('toast.aiGenerateFailed')
              throw new Error(event.message || 'AI error')
            }
          } catch (parseErr) {
            // Only ignore JSON parse errors (partial lines), log other errors
            if (!(parseErr instanceof SyntaxError)) {
              console.warn('[useAIReportStream] Unexpected error parsing event:', parseErr)
            }
          }
        }
      }
    } catch (err) {
      status.value = 'error'
      if (err instanceof Error && err.name === 'AbortError') {
        errorMessage.value = t('wsErrors.connectionInterrupted')
      } else if (err instanceof Error) {
        errorMessage.value = err.message || t('toast.aiGenerateFailed')
      } else {
        errorMessage.value = t('toast.aiGenerateFailed')
      }
      throw err
    }
  }

  function disconnect() {
    abortController?.abort()
    abortController = null
  }

  function reset() {
    disconnect()
    status.value = 'idle'
    progressMessage.value = ''
    errorMessage.value = ''
    report.value = null
    generatedAt.value = null
  }

  onUnmounted(() => disconnect())

  return { status, progressMessage, report, generatedAt, errorMessage, connect, disconnect, reset }
}