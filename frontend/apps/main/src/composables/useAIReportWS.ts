import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { createWsTicket } from '@/api/ai'

export type WSStatus = 'idle' | 'connecting' | 'analyzing' | 'completed' | 'error'

export function useAIReportWS() {
  const { t } = useI18n()
  const status = ref<WSStatus>('idle')
  const progressMessage = ref('')
  const report = ref<Record<string, unknown> | null>(null)
  const generatedAt = ref<string | null>(null)
  const errorMessage = ref('')

  let ws: WebSocket | null = null

  function connect(): Promise<void> {
    return new Promise((resolve, reject) => {
      let settled = false
      function settle(fn: () => void) {
        if (settled) return
        settled = true
        fn()
      }

      // Client-side timeout: 120s
      const timeoutId = setTimeout(() => {
        ws?.close()
        settle(() => {
          status.value = 'error'
          errorMessage.value = t('wsErrors.timeout')
          reject(new Error(t('wsErrors.timeoutShort')))
        })
      }, 120_000)

      status.value = 'connecting'
      progressMessage.value = t('wsErrors.connecting')

      // Exchange JWT for a one-time ticket, then open WS with ticket
      createWsTicket()
        .then((res) => {
          const ticket = res.data.ticket
          const protocol = location.protocol === 'https:' ? 'wss' : 'ws'
          const url = `${protocol}://${location.host}/api/v1/ai/report/ws?ticket=${encodeURIComponent(ticket)}`
          ws = new WebSocket(url)

          ws.onmessage = (event) => {
            try {
              const msg = JSON.parse(event.data)
              if (msg.type === 'progress') {
                status.value = 'analyzing'
                progressMessage.value = msg.message
              } else if (msg.type === 'completed') {
                clearTimeout(timeoutId)
                status.value = 'completed'
                report.value = msg.report
                generatedAt.value = msg.generated_at
                settle(resolve)
              } else if (msg.type === 'error') {
                clearTimeout(timeoutId)
                status.value = 'error'
                errorMessage.value = msg.message
                settle(() => reject(new Error(msg.message)))
              }
            } catch {
              // ignore parse errors
            }
          }

          ws.onerror = () => {
            clearTimeout(timeoutId)
            settle(() => {
              status.value = 'error'
              errorMessage.value = t('wsErrors.connectionFailed')
              reject(new Error(t('wsErrors.wsConnectionFailed')))
            })
          }

          ws.onclose = () => {
            clearTimeout(timeoutId)
            if (status.value === 'connecting' || status.value === 'analyzing') {
              settle(() => {
                status.value = 'error'
                errorMessage.value = t('wsErrors.connectionInterrupted')
                reject(new Error(t('wsErrors.connectionInterrupted')))
              })
            }
          }
        })
        .catch((err) => {
          clearTimeout(timeoutId)
          settle(() => {
            status.value = 'error'
            errorMessage.value = err?.response?.data?.detail || t('wsErrors.authFailed')
            reject(err)
          })
        })
    })
  }

  function disconnect() {
    ws?.close()
    ws = null
  }

  function reset() {
    disconnect()
    status.value = 'idle'
    progressMessage.value = ''
    errorMessage.value = ''
  }

  return { status, progressMessage, report, generatedAt, errorMessage, connect, disconnect, reset }
}
