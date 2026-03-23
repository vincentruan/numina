<template>
  <van-config-provider :theme="resolvedTheme">
    <router-view />
  </van-config-provider>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useSettingsStore } from '@/stores/settings'

const settingsStore = useSettingsStore()
const systemDark = ref(window.matchMedia('(prefers-color-scheme: dark)').matches)

const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)')
function onSystemThemeChange(e: MediaQueryListEvent) {
  systemDark.value = e.matches
}

onMounted(() => mediaQuery.addEventListener('change', onSystemThemeChange))
onUnmounted(() => mediaQuery.removeEventListener('change', onSystemThemeChange))

const resolvedTheme = computed(() => {
  if (settingsStore.theme === 'system') return systemDark.value ? 'dark' : 'light'
  return settingsStore.theme
})

import { useFamilyStore } from '@/stores/family'
import { watch } from 'vue'

const familyStore = useFamilyStore()

watch(() => familyStore.family?.custom_title, (newTitle) => {
  document.title = newTitle || 'Numina'
}, { immediate: true })
</script>
