<template>
  <router-view />
</template>

<script setup lang="ts">
import { useDarkMode } from '@/utils/darkMode'
// Initialize dark mode reactivity on app mount (watchEffect in composable handles DOM)
useDarkMode()
</script>
