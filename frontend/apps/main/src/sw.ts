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

// Clean up outdated clients and precache the manifest injected by vite-plugin-pwa
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
    const title = data.title || 'Numina'
    const options: NotificationOptions = {
      body: data.body || '',
      icon: '/pwa-icon-192.png',
      badge: '/pwa-icon-192.png',
      data: {
        navigateTo: data.navigate_to || '/',
        reminderType: data.reminder_type || '',
        reminderId: data.reminder_id || '',
      },
      tag: data.reminder_id || undefined,
    }
    event.waitUntil(self.registration.showNotification(title, options))
  } catch {
    // Fallback for non-JSON push data
    event.waitUntil(
      self.registration.showNotification('Numina', {
        body: event.data.text(),
        icon: '/pwa-icon-192.png',
      }),
    )
  }
})

self.addEventListener('notificationclick', (event: NotificationEvent) => {
  event.notification.close()
  const navigateTo = event.notification.data?.navigateTo || '/'

  event.waitUntil(
    self.clients.matchAll({ type: 'window', includeUncontrolled: true }).then((clients) => {
      const existing = clients.find((client) => 'focus' in client)
      if (existing) {
        // Focus, then hand the route to the SPA so App.vue can router.push()
        // — a full reload would land on start_url instead of the tapped route.
        void existing.focus().then(() => {
          existing.postMessage({ type: 'push-navigate', url: navigateTo })
        })
        return undefined
      }
      // No window to reuse — open a cold one directly at the target route.
      if (self.clients.openWindow) {
        return self.clients.openWindow(navigateTo)
      }
      return undefined
    }),
  )
})
// ── Subscription rotation (pushsubscriptionchange) ───────────────────────────
//
// Browsers periodically rotate push subscriptions without involving the page.
// Without this handler the backend keeps the stale endpoint and the next push
// silently fails (410 Gone). On rotation we:
//   1. DELETE the old endpoint from the backend.
//   2. POST the new subscription so subsequent pushes reach the new endpoint.
// Both steps are best-effort — the next user-driven re-subscribe will upsert
// away any drift, so a transient network failure during rotation is not fatal.
//
// TODO(#7 from 2026-10-30 review): this handler is duplicated in child/src/sw.ts
// (only the app_type literal differs). Extract to @numina/shared once a SW-safe
// shared module is available — the SW's webworker lib conflicts with
// @numina/shared's DOM lib, so a naive import breaks the SW build.
self.addEventListener('pushsubscriptionchange', (event: PushSubscriptionChangeEvent) => {
  const { oldSubscription, newSubscription } = event
  if (!newSubscription) return

  event.waitUntil((async () => {
    try {
      const p256dh = newSubscription.getKey('p256dh')
      const auth = newSubscription.getKey('auth')
      if (!p256dh || !auth) return

      // Remove the stale subscription from the backend (best-effort).
      if (oldSubscription?.endpoint) {
        const oldUrl = new URL('/api/v1/notifications/push/subscribe', self.location.origin)
        oldUrl.searchParams.set('endpoint', oldSubscription.endpoint)
        await fetch(oldUrl.href, { method: 'DELETE', credentials: 'include' }).catch(() => {})
      }

      // Register the new subscription.
      const bytes = (buf: ArrayBuffer): string => {
        const a = new Uint8Array(buf)
        let s = ''
        for (let i = 0; i < a.byteLength; i++) s += String.fromCharCode(a[i])
        return s
      }
      await fetch(new URL('/api/v1/notifications/push/subscribe', self.location.origin).href, {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          endpoint: newSubscription.endpoint,
          p256dh: btoa(bytes(p256dh)),
          auth: btoa(bytes(auth)),
          user_agent: navigator.userAgent,
          app_type: 'main',
        }),
      })
    } catch {
      // See comment at top of handler — a failed rotation is not fatal.
    }
  })())
})
