import { ref } from 'vue'
import { getToken } from '@/utils/storage'

export type WSStatus = 'idle' | 'connecting' | 'analyzing' | 'completed' | 'error'

export function useAIReportWS() {
  const status = ref<WSStatus>('idle')
  const progressMessage = ref('')
  const report = ref<Record<string, any> | null>(null)
  const generatedAt = ref<string | null>(null)
  const errorMessage = ref('')

  let ws: WebSocket | null = null

  function connect(): Promise<void> {
    return new Promise((resolve, reject) => {
      const token = getToken()
      if (!token) {
        reject(new Error('未登录'))
        return
      }

      const protocol = location.protocol === 'https:' ? 'wss' : 'ws'
      const url = `${protocol}://${location.host}/api/v1/ai/report/ws?token=${encodeURIComponent(token)}`

      status.value = 'connecting'
      progressMessage.value = '正在连接...'
      ws = new WebSocket(url)

      ws.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data)
          if (msg.type === 'progress') {
            status.value = 'analyzing'
            progressMessage.value = msg.message
          } else if (msg.type === 'completed') {
            status.value = 'completed'
            report.value = msg.report
            generatedAt.value = msg.generated_at
            resolve()
          } else if (msg.type === 'error') {
            status.value = 'error'
            errorMessage.value = msg.message
            reject(new Error(msg.message))
          }
        } catch {
          // ignore parse errors
        }
      }

      ws.onerror = () => {
        status.value = 'error'
        errorMessage.value = '连接失败'
        reject(new Error('WebSocket 连接失败'))
      }

      ws.onclose = () => {
        if (status.value === 'connecting' || status.value === 'analyzing') {
          status.value = 'error'
          errorMessage.value = '连接中断'
          reject(new Error('连接中断'))
        }
      }
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
