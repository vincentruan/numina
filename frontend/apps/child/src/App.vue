<template>
  <router-view />
  <PixelLoadingOverlay :aria-label="t('common.loading')" />
</template>

<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import { useDarkMode } from '@/utils/darkMode'
import { PixelLoadingOverlay } from '@numina/auth'

const { t } = useI18n()
// Initialize dark mode reactivity on app mount (watchEffect in composable handles DOM)
useDarkMode()
</script>
