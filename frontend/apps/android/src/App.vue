<script setup lang="ts">
import { onMounted } from 'vue'
import { getServerUrl, validateServer } from '@/utils/server-config'

onMounted(async () => {
  const savedUrl = await getServerUrl()
  if (savedUrl) {
    // Skip the round-trip when unreachable: the setup page lets the user fix it.
    const valid = await validateServer(savedUrl)
    if (valid) {
      window.location.href = savedUrl
    }
  }
})
</script>

<template>
  <router-view />
</template>

<style>
/* Global styles for the shell app */
:root {
  --shell-primary: #4361ee;
  --shell-primary-dark: #7c8aff;
  --shell-bg: #f5f5ff;
  --shell-bg-dark: #0a0a1a;
  --shell-surface: #ffffff;
  --shell-surface-dark: #12122a;
  --shell-text: #1a1a2e;
  --shell-text-dark: #e8e8f0;
  --shell-text-secondary: #666;
  --shell-border: #e2e8f0;
  --shell-border-dark: #2a2a4a;
  --shell-danger: #dc2626;
  --shell-success: #16a34a;
}

* {
  box-sizing: border-box;
  margin: 0;
  padding: 0;
}

html, body {
  height: 100%;
  width: 100%;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif;
  background: var(--shell-bg);
  color: var(--shell-text);
  -webkit-font-smoothing: antialiased;
  -webkit-text-size-adjust: 100%;
}

@media (prefers-color-scheme: dark) {
  html, body {
    background: var(--shell-bg-dark);
    color: var(--shell-text-dark);
  }
}
</style>
