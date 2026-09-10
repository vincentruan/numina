import { ref, onMounted } from 'vue'
import http from '@/api'

type PermissionState = 'default' | 'granted' | 'denied' | 'unsupported'

const DISMISS_KEY = 'pwa_push_permission_dismissed'

export function usePushSubscription() {
  const permissionState = ref<PermissionState>('default')
  const vapidPublicKey = ref('')

  async function fetchVapidKey() {
    try {
      const res = await http.get<{ public_key: string }>('/notifications/push/vapid-public-key')
      vapidPublicKey.value = (res.data as { public_key: string }).public_key || res.data.public_key
    } catch {
      // VAPID key not available — push not configured on server
    }
  }

  async function checkPermission() {
    if (!('Notification' in window)) {
      permissionState.value = 'unsupported'
      return
    }
    permissionState.value = Notification.permission as PermissionState
  }

  async function requestPermission(): Promise<boolean> {
    if (!('Notification' in window)) {
      permissionState.value = 'unsupported'
      return false
    }

    const result = await Notification.requestPermission()
    permissionState.value = result as PermissionState

    if (result === 'granted') {
      await registerSubscription()
      return true
    }

    if (result === 'denied') {
      localStorage.setItem(DISMISS_KEY, new Date().toISOString())
    }

    return false
  }

  async function registerSubscription() {
    if (!vapidPublicKey.value) {
      await fetchVapidKey()
    }
    if (!vapidPublicKey.value) return

    try {
      const registration = await navigator.serviceWorker.ready
      const existing = await registration.pushManager.getSubscription()
      if (existing) {
        // Already subscribed — ensure backend has it
        await sendSubscriptionToBackend(existing)
        return
      }

      const subscription = await registration.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey: urlBase64ToUint8Array(vapidPublicKey.value).buffer as ArrayBuffer,
      })

      await sendSubscriptionToBackend(subscription)
    } catch (error) {
      console.warn('Push subscription failed:', error)
    }
  }

  async function sendSubscriptionToBackend(subscription: PushSubscription) {
    const key = subscription.getKey('p256dh')
    const auth = subscription.getKey('auth')
    if (!key || !auth) return

    await http.post('/notifications/push/subscribe', {
      endpoint: subscription.endpoint,
      p256dh: btoa(String.fromCharCode(...new Uint8Array(key))),
      auth: btoa(String.fromCharCode(...new Uint8Array(auth))),
      user_agent: navigator.userAgent,
      app_type: 'main',
    })
  }

  async function unsubscribe() {
    try {
      const registration = await navigator.serviceWorker.ready
      const subscription = await registration.pushManager.getSubscription()
      if (subscription) {
        await http.delete('/notifications/push/subscribe', {
          params: { endpoint: subscription.endpoint },
        })
        await subscription.unsubscribe()
      }
      permissionState.value = 'default'
    } catch (error) {
      console.warn('Unsubscribe failed:', error)
    }
  }

  function wasDismissed(): boolean {
    const dismissed = localStorage.getItem(DISMISS_KEY)
    if (!dismissed) return false
    return Date.now() - new Date(dismissed).getTime() < 7 * 24 * 60 * 60 * 1000
  }

  onMounted(async () => {
    await checkPermission()
    if (permissionState.value === 'granted') {
      await fetchVapidKey()
      await registerSubscription()
    }
  })

  return {
    permissionState,
    requestPermission,
    unsubscribe,
    wasDismissed,
  }
}

function urlBase64ToUint8Array(base64String: string): Uint8Array {
  const padding = '='.repeat((4 - (base64String.length % 4)) % 4)
  const base64 = (base64String + padding).replace(/-/g, '+').replace(/_/g, '/')
  const rawData = atob(base64)
  const outputArray = new Uint8Array(rawData.length)
  for (let i = 0; i < rawData.length; ++i) {
    outputArray[i] = rawData.charCodeAt(i)
  }
  return outputArray
}
