<template>
  <router-view />
</template>

<script setup lang="ts">
import { onMounted, onUnmounted } from 'vue'
import { useDarkMode } from '@/utils/darkMode'
import { refreshTokenIfNeeded } from '@/api'

// Initialize dark mode reactivity on app mount (watchEffect in composable handles DOM)
useDarkMode()

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
})

onUnmounted(() => {
  stopProactiveRefresh()
  document.removeEventListener('visibilitychange', onVisibilityChange)
})
</script>
