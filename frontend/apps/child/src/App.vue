<template>
  <router-view />
  <LoadingOverlay />
</template>

<script setup lang="ts">
import { useDarkMode } from '@/utils/darkMode'
import { LoadingOverlay } from '@numina/auth'
// Initialize dark mode reactivity on app mount (watchEffect in composable handles DOM)
useDarkMode()
</script>
