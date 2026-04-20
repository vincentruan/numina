import { createWsTicket } from '@/api/notifications'
import { useNotificationStore } from '@/stores/notification'
import { useChoreStore } from '@/stores/chore'
import { useWishStore } from '@/stores/wish'
import { useAuthStore } from '@/stores/auth'

const MAX_RETRIES = 5
const BASE_DELAY_MS = 1000

let ws: WebSocket | null = null
let retryCount = 0
let retryTimer: ReturnType<typeof setTimeout> | null = null
let stopped = false

function clearRetryTimer() {
  if (retryTimer !== null) {
    clearTimeout(retryTimer)
    retryTimer = null
  }
}

async function openConnection() {
  const notificationStore = useNotificationStore()
  const choreStore = useChoreStore()
  const wishStore = useWishStore()
  const authStore = useAuthStore()

  try {
    const res = await createWsTicket()
    const ticket = res.data.ticket
    const protocol = location.protocol === 'https:' ? 'wss' : 'ws'
    const url = `${protocol}://${location.host}/api/v1/notifications/ws?ticket=${encodeURIComponent(ticket)}`

    ws = new WebSocket(url)

    ws.onopen = () => {
      notificationStore.isConnected = true
      retryCount = 0
    }

    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data)
        if (msg.type === 'ping') {
          ws?.send(JSON.stringify({ type: 'pong' }))
        } else if (msg.type === 'notification') {
          notificationStore.addNotification({
            event_type: msg.event_type,
            title: msg.title,
            message: msg.message,
            ref_id: msg.ref_id,
            ref_type: msg.ref_type,
          })
          // Trigger data refresh based on event type
          if (msg.event_type === 'wish_approved') {
            wishStore.fetchWishes().catch(() => {})
          } else if (msg.event_type === 'chore_completed') {
            choreStore.fetchPendingApprovals().catch(() => {})
          } else if (msg.event_type === 'coins_received') {
            authStore.fetchMe().catch(() => {})
          }
        }
      } catch {
        // ignore parse errors
      }
    }

    ws.onerror = () => {
      notificationStore.isConnected = false
    }

    ws.onclose = () => {
      notificationStore.isConnected = false
      ws = null
      if (!stopped && retryCount < MAX_RETRIES) {
        const delay = BASE_DELAY_MS * Math.pow(2, retryCount)
        retryCount++
        retryTimer = setTimeout(() => {
          if (!stopped) openConnection()
        }, delay)
      }
    }
  } catch {
    // ticket fetch failed — retry with backoff
    if (!stopped && retryCount < MAX_RETRIES) {
      const delay = BASE_DELAY_MS * Math.pow(2, retryCount)
      retryCount++
      retryTimer = setTimeout(() => {
        if (!stopped) openConnection()
      }, delay)
    }
  }
}

export function useNotifications() {
  function connect() {
    stopped = false
    retryCount = 0
    clearRetryTimer()
    openConnection()
  }

  function disconnect() {
    stopped = true
    clearRetryTimer()
    ws?.close()
    ws = null
    const notificationStore = useNotificationStore()
    notificationStore.isConnected = false
  }

  return { connect, disconnect }
}
