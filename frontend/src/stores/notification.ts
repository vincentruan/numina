import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export interface Notification {
  id: string
  event_type: string
  title: string
  message: string
  ref_id?: string
  ref_type?: string
  timestamp: number
  read: boolean
}

const MAX_NOTIFICATIONS = 50

export const useNotificationStore = defineStore('notification', () => {
  const notifications = ref<Notification[]>([])
  const isConnected = ref(false)

  const unreadCount = computed(() => notifications.value.filter((n) => !n.read).length)

  function addNotification(n: Omit<Notification, 'id' | 'timestamp' | 'read'>) {
    const item: Notification = {
      ...n,
      id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
      timestamp: Date.now(),
      read: false,
    }
    notifications.value.unshift(item)
    if (notifications.value.length > MAX_NOTIFICATIONS) {
      notifications.value = notifications.value.slice(0, MAX_NOTIFICATIONS)
    }
  }

  function markAllRead() {
    notifications.value.forEach((n) => (n.read = true))
  }

  function clearAll() {
    notifications.value = []
  }

  return { notifications, isConnected, unreadCount, addNotification, markAllRead, clearAll }
})
