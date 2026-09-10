/// <reference lib="webworker" />

// Narrow `self` to ServiceWorkerGlobalScope — the default WebWorker lib
// only provides WorkerGlobalScope which lacks SW-specific APIs.
declare const self: ServiceWorkerGlobalScope & { __WB_MANIFEST: unknown }

import { cleanupOutdatedCaches, precacheAndRoute } from 'workbox-precaching'
import { ExpirationPlugin } from 'workbox-expiration'
import { registerRoute } from 'workbox-routing'
import { StaleWhileRevalidate } from 'workbox-strategies'

// Activate the new SW immediately when installed
self.addEventListener('install', () => {
  self.skipWaiting()
})

// Claim all clients when activated
self.addEventListener('activate', () => {
  self.clients.claim()
})

// Clean up outdated caches and precache the manifest injected by vite-plugin-pwa
cleanupOutdatedCaches()
precacheAndRoute(self.__WB_MANIFEST)

// Runtime caching for API responses (offline read — R4, R5)
const apiRoutes: Array<{ pattern: RegExp; cacheName: string }> = [
  { pattern: /\/api\/v1\/dashboard\/summary/, cacheName: 'api-dashboard' },
  { pattern: /\/api\/v1\/dashboard\/allocation/, cacheName: 'api-dashboard' },
  { pattern: /\/api\/v1\/assets(\?|$)/, cacheName: 'api-assets' },
  { pattern: /\/api\/v1\/liabilities(\?|$)/, cacheName: 'api-liabilities' },
]

for (const { pattern, cacheName } of apiRoutes) {
  registerRoute(
    ({ url }) => pattern.test(url.pathname),
    new StaleWhileRevalidate({
      cacheName,
      plugins: [
        new ExpirationPlugin({ maxEntries: 10, maxAgeSeconds: 86400 }),
      ],
    }),
  )
}

// ── Push notification handling (R9, F3) ────────────────────────────────────

self.addEventListener('push', (event: PushEvent) => {
  if (!event.data) return

  try {
    const data = event.data.json()
    const title = data.title || 'Numina Kids'
    const options: NotificationOptions = {
      body: data.body || '',
      icon: '/child/pwa-icon-192.png',
      badge: '/child/pwa-icon-192.png',
      data: {
        navigateTo: data.navigate_to || '/child/',
        reminderType: data.reminder_type || '',
        reminderId: data.reminder_id || '',
      },
      tag: data.reminder_id || undefined,
    }
    event.waitUntil(self.registration.showNotification(title, options))
  } catch {
    event.waitUntil(
      self.registration.showNotification('Numina Kids', {
        body: event.data.text(),
        icon: '/child/pwa-icon-192.png',
      }),
    )
  }
})

self.addEventListener('notificationclick', (event: NotificationEvent) => {
  event.notification.close()
  const navigateTo = event.notification.data?.navigateTo || '/child/'

  event.waitUntil(
    self.clients.matchAll({ type: 'window', includeUncontrolled: true }).then((clients) => {
      for (const client of clients) {
        if ('focus' in client) {
          return (client as WindowClient).focus()
        }
      }
      if (self.clients.openWindow) {
        return self.clients.openWindow(navigateTo)
      }
      return undefined
    }),
  )
})
