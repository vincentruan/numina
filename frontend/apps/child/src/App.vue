<template>
  <router-view />
</template>

<script setup lang="ts">
import { onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { useDarkMode } from '@/utils/darkMode'
import { refreshTokenIfNeeded } from '@/api'
import { usePushSubscription } from '@/composables/usePushSubscription'

// Initialize dark mode reactivity on app mount (watchEffect in composable handles DOM)
useDarkMode()

const router = useRouter()

// Sync this device's Web Push subscription to the backend when permission is
// already granted. Never prompts — the opt-in UI is a separate concern.
// The backend forces app_type='child' for child sessions, so parent-only
// reminders (e.g. large_purchase) never reach a child device.
usePushSubscription()

// vue-router re-applies the app base, so a payload path like '/child/wishes'
// must lose its prefix before router.push() or it becomes '/child/child/wishes'.
function toRoutePath(url: string): string {
  const base = import.meta.env.BASE_URL
  if (base !== '/' && url.startsWith(base)) return `/${url.slice(base.length)}`
  return url
}

// A push notification click focuses this window and posts the target route
// (see sw.ts `notificationclick`) so we route in-app instead of reloading.
function onServiceWorkerMessage(event: MessageEvent) {
  const data: unknown = event.data
  if (typeof data !== 'object' || data === null) return
  const { type, url } = data as { type?: unknown; url?: unknown }
  if (type !== 'push-navigate' || typeof url !== 'string') return
  router.push(toRoutePath(url)).catch(() => {
    // Navigation may be rejected (duplicate target or guard redirect) — non-fatal.
  })
}

// Proactive token refresh — keep the child access cookie alive while the tab is
// visible. The access token TTL is 15 min; refreshing every 12 min leaves a
// 3-min safety margin and prevents the child user from being bounced to the
// main-app login page when the token expires mid-session.
const PROACTIVE_REFRESH_INTERVAL_MS = 12 * 60 * 1000
let proactiveRefreshTimer: ReturnType<typeof setInterval> | null = null

function startProactiveRefresh() {
  if (proactiveRefreshTimer) return
  proactiveRefreshTimer = setInterval(async () => {
    if (document.visibilityState !== 'visible') return
    try {
      await refreshTokenIfNeeded()
    } catch {
      // best-effort; the 401 interceptor in api/index.ts handles redirect
    }
  }, PROACTIVE_REFRESH_INTERVAL_MS)
}

function stopProactiveRefresh() {
  if (proactiveRefreshTimer) {
    clearInterval(proactiveRefreshTimer)
    proactiveRefreshTimer = null
  }
}

async function onVisibilityChange() {
  if (document.visibilityState === 'visible') {
    try {
      await refreshTokenIfNeeded()
    } catch {
      // best-effort
    }
  }
}

onMounted(() => {
  startProactiveRefresh()
  document.addEventListener('visibilitychange', onVisibilityChange)
  navigator.serviceWorker?.addEventListener('message', onServiceWorkerMessage)
})

onUnmounted(() => {
  stopProactiveRefresh()
  document.removeEventListener('visibilitychange', onVisibilityChange)
  navigator.serviceWorker?.removeEventListener('message', onServiceWorkerMessage)
})
</script>
