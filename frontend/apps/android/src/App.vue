<script setup lang="ts">
import { onMounted } from 'vue'
import { getServerUrl, validateServer, classifyUrl, isAdvancedMode } from '@/utils/server-config'

onMounted(async () => {
  const savedUrl = await getServerUrl()
  if (!savedUrl) return

  // Re-apply the cleartext gate at launch: a user who saved an http-lan URL
  // with Advanced Mode ON, then turned the toggle OFF, must not silently keep
  // auto-connecting over cleartext. Same rule the setup page enforces.
  const cls = classifyUrl(savedUrl)
  const advanced = await isAdvancedMode()
  if (cls === 'http-public') return
  if (cls === 'http-lan' && !advanced) return

  const valid = await validateServer(savedUrl)
  if (valid) {
    // replace, not href: pushing the shell page into WebView history would
    // make canGoBack() true after navigating to the remote H5, and the
    // back-button exit prompt would never be reachable.
    window.location.replace(savedUrl)
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
