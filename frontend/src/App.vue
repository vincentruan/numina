<template>
  <van-config-provider :theme="resolvedTheme">
    <router-view />
  </van-config-provider>
</template>

<script setup lang="ts">
import { computed, watch, onMounted, onUnmounted, ref } from 'vue'

import { useAuthStore } from '@/stores/auth'
import { useFamilyStore } from '@/stores/family'
import { useNotifications } from '@/composables/useNotifications'
import { useI18n } from 'vue-i18n'

const authStore = useAuthStore()
const familyStore = useFamilyStore()
const { locale } = useI18n()
const { connect: connectNotifications, disconnect: disconnectNotifications } = useNotifications()

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

// Connect/disconnect notifications when auth state changes
watch(
  () => authStore.user,
  (user, prevUser) => {
    if (user && !prevUser) {
      connectNotifications()
    } else if (!user && prevUser) {
      disconnectNotifications()
    }
  },
)

onMounted(() => {
  // Set initial theme
  document.documentElement.setAttribute('data-theme', resolvedTheme.value)
  // Set initial language
  if (authStore.user?.language) {
    locale.value = authStore.user.language
  }
  // Listen for system theme changes
  mediaQuery = window.matchMedia('(prefers-color-scheme: dark)')
  mediaQuery.addEventListener('change', handleSystemThemeChange)

  // Load coin config for adult users (children don't have access to /family/settings)
  if (authStore.user && authStore.user.role !== 'child') {
    familyStore.loadCoinConfig()
  }

  // Connect notifications if already logged in
  if (authStore.user) {
    connectNotifications()
  }
})

onUnmounted(() => {
  if (mediaQuery) {
    mediaQuery.removeEventListener('change', handleSystemThemeChange)
  }
})

watch(() => familyStore.family?.custom_title, (newTitle) => {
  document.title = newTitle || 'Numina'
}, { immediate: true })
</script>
