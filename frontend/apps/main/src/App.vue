<template>
  <van-config-provider :theme="resolvedTheme">
    <router-view />
  </van-config-provider>

  <van-dialog
    v-model:show="authStore.showTrustPrompt"
    teleport="body"
    :title="t('device.trustPromptTitle')"
    :message="t('device.trustPromptMessage')"
    :confirm-button-text="t('device.trustConfirm')"
    :cancel-button-text="t('device.trustCancel')"
    show-cancel-button
    @confirm="onTrustConfirm"
    @cancel="authStore.dismissTrustPrompt()"
  />
</template>

<script setup lang="ts">
import { computed, watch, onMounted, onUnmounted, ref } from 'vue'
import { showSuccessToast } from 'vant'
import { useAuthStore } from '@/stores/auth'
import { useFamilyStore } from '@/stores/family'
import { useI18n } from 'vue-i18n'
import { checkWebAuthnSupport, registerPasskey } from '@/utils/webauthn'
import { getDeviceTrustWebAuthnOptions, registerDeviceTrustWebAuthn } from '@/api/device'
import { refreshTokenIfNeeded } from '@/api'

const authStore = useAuthStore()
const familyStore = useFamilyStore()
const { locale, t } = useI18n()

// Proactive token refresh — keep the access cookie alive while the tab is
// visible. The access token TTL is 15 min; refreshing every 12 min leaves a
// 3-min safety margin and prevents the 401 toast users saw on idle return.
const PROACTIVE_REFRESH_INTERVAL_MS = 12 * 60 * 1000
let proactiveRefreshTimer: ReturnType<typeof setInterval> | null = null

function startProactiveRefresh() {
  if (proactiveRefreshTimer) return
  proactiveRefreshTimer = setInterval(async () => {
    if (document.visibilityState !== 'visible') return
    if (!authStore.user) return
    try {
      await refreshTokenIfNeeded()
    } catch {
      // best-effort; the axios interceptor will handle auth failure
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
  if (document.visibilityState === 'visible' && authStore.user) {
    try {
      await refreshTokenIfNeeded()
    } catch {
      // best-effort
    }
  }
}

// System dark mode detection
const systemIsDark = ref(window.matchMedia('(prefers-color-scheme: dark)').matches)
let mediaQuery: MediaQueryList | null = null

function handleSystemThemeChange(e: MediaQueryListEvent) {
  systemIsDark.value = e.matches
}

const resolvedTheme = computed(() => {
  const theme = authStore.user?.theme || 'system'
  if (theme === 'system') {
    return systemIsDark.value ? 'dark' : 'light'
  }
  return theme as 'light' | 'dark'
})

// Apply theme to document root
watch(resolvedTheme, (theme) => {
  document.documentElement.setAttribute('data-theme', theme)
}, { immediate: true })

// Apply language
watch(() => authStore.user?.language, (lang) => {
  if (lang) {
    locale.value = lang
  }
}, { immediate: true })

onMounted(() => {
  // Set initial theme
  document.documentElement.setAttribute('data-theme', resolvedTheme.value)
  // Set initial language
  if (authStore.user?.language) {
    locale.value = authStore.user.language
  }
  // Restore user-selected theme color on every page load
  const savedColor = localStorage.getItem('theme-primary')
  if (savedColor) {
    document.documentElement.style.setProperty('--van-primary-color', savedColor)
  }
  // Listen for system theme changes
  mediaQuery = window.matchMedia('(prefers-color-scheme: dark)')
  mediaQuery.addEventListener('change', handleSystemThemeChange)

  // Refresh token when tab becomes visible again — the access cookie may have
  // expired while the tab was in the background (timer is suspended by browsers).
  document.addEventListener('visibilitychange', onVisibilityChange)

  // Load family data for agent API calls (X-Family-Id header)
  // Must wait for fetchMe() to confirm the session is valid — otherwise these
  // requests fire before the 401-interceptor has a chance to refresh the token,
  // producing a wave of 401s that all need individual retry round-trips.
  // fetchMe() goes through the same interceptor: if access cookie is expired
  // it triggers /auth/refresh first, then retries /auth/me with the new token.
  // Either fetchMe() succeeds (session valid → safe to load data) or it rejects
  // (refresh failed → router guard redirects to /login → catch below).
  authStore.fetchMe()
    .then(() => {
      familyStore.fetchFamily()
      if (authStore.user && authStore.user.role !== 'child') {
        familyStore.loadCoinConfig()
      }
    })
    .catch(() => {
      // Session invalid — interceptor already cleared auth + redirected to /login.
      // Nothing to do here; router guard will handle navigation.
    })

  // Start proactive token refresh to prevent access cookie expiry
  startProactiveRefresh()

})

onUnmounted(() => {
  stopProactiveRefresh()
  document.removeEventListener('visibilitychange', onVisibilityChange)
  if (mediaQuery) {
    mediaQuery.removeEventListener('change', handleSystemThemeChange)
  }
})

watch(() => familyStore.family?.custom_title, (newTitle) => {
  document.title = newTitle || 'Numina'
}, { immediate: true })

async function onTrustConfirm() {
  await authStore.trustDevice({
    onTrusted: async () => {
      const { supported } = checkWebAuthnSupport()
      if (!supported) return
      try {
        const { data: regOptions } = await getDeviceTrustWebAuthnOptions()
        const credential = await registerPasskey(regOptions.options)
        await registerDeviceTrustWebAuthn(credential, regOptions.challenge)
      } catch {
        // User declined biometric or device unavailable — non-fatal
      }
    },
    onSuccess: () => showSuccessToast(t('toast.deviceTrustSuccess')),
  })
}
</script>
