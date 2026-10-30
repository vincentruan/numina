<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import {
  getServerUrl,
  clearServerUrl,
  isAdvancedMode,
  setAdvancedMode,
} from '@/utils/server-config'

const router = useRouter()

const currentUrl = ref('')
const advancedMode = ref(false)
const cleared = ref(false)

onMounted(async () => {
  const saved = await getServerUrl()
  currentUrl.value = saved || '(not configured)'
  advancedMode.value = await isAdvancedMode()
})

async function handleClear() {
  await clearServerUrl()
  currentUrl.value = '(not configured)'
  cleared.value = true
  setTimeout(() => { cleared.value = false }, 2000)
}

async function toggleAdvanced() {
  advancedMode.value = !advancedMode.value
  await setAdvancedMode(advancedMode.value)
}

function goBack() {
  router.push('/')
}
</script>

<template>
  <div class="advanced-page">
    <div class="page-header">
      <button class="back-btn" @click="goBack">← Back</button>
      <h1>Advanced Settings</h1>
    </div>

    <div class="settings-content">
      <div class="setting-card">
        <h3>Server Address</h3>
        <p class="current-value">{{ currentUrl }}</p>
        <button class="action-btn" @click="handleClear">
          {{ cleared ? '✅ Cleared' : 'Clear & Reconfigure' }}
        </button>
      </div>

      <div class="setting-card">
        <h3>Advanced Mode</h3>
        <p class="description">
          Allow connecting to servers over unencrypted HTTP (e.g., LAN addresses like
          <code>http://192.168.1.100:80</code>). Only enable this for trusted local networks.
        </p>
        <label class="toggle-row">
          <input type="checkbox" :checked="advancedMode" @change="toggleAdvanced" />
          <span>Enable HTTP connections</span>
        </label>
      </div>

      <div class="setting-card info-card">
        <h3>About</h3>
        <p class="description">
          Numina Android Shell v1.0.0<br />
          This app connects to your self-hosted Numina server.
          All data stays on your server — this app is a thin WebView wrapper.
        </p>
      </div>
    </div>
  </div>
</template>

<style scoped>
.advanced-page {
  min-height: 100%;
  padding: 1.5rem;
  padding-top: calc(env(safe-area-inset-top, 1rem) + 1rem);
  padding-bottom: env(safe-area-inset-bottom, 2rem);
}

.page-header {
  margin-bottom: 1.5rem;
}

.back-btn {
  background: none;
  border: none;
  color: var(--shell-primary);
  font-size: 0.9rem;
  cursor: pointer;
  padding: 0.3rem 0;
  margin-bottom: 0.5rem;
  -webkit-tap-highlight-color: transparent;
}

h1 {
  font-size: 1.3rem;
  font-weight: 700;
}

.settings-content {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.setting-card {
  background: var(--shell-surface);
  border: 1px solid var(--shell-border);
  border-radius: 12px;
  padding: 1.25rem;
}

@media (prefers-color-scheme: dark) {
  .setting-card {
    background: var(--shell-surface-dark);
    border-color: var(--shell-border-dark);
  }
}

.setting-card h3 {
  font-size: 0.95rem;
  font-weight: 600;
  margin-bottom: 0.5rem;
}

.current-value {
  font-family: 'SF Mono', 'Fira Code', monospace;
  font-size: 0.85rem;
  color: var(--shell-text-secondary);
  word-break: break-all;
  margin-bottom: 0.75rem;
}

.description {
  font-size: 0.85rem;
  color: var(--shell-text-secondary);
  line-height: 1.5;
  margin-bottom: 0.75rem;
}

.description code {
  background: var(--shell-border);
  padding: 0.1em 0.3em;
  border-radius: 3px;
  font-size: 0.82rem;
}

@media (prefers-color-scheme: dark) {
  .description code {
    background: var(--shell-border-dark);
  }
}

.action-btn {
  padding: 0.5rem 1rem;
  font-size: 0.85rem;
  font-weight: 600;
  border: 1px solid var(--shell-border);
  border-radius: 8px;
  background: transparent;
  color: var(--shell-danger);
  cursor: pointer;
  -webkit-tap-highlight-color: transparent;
}

@media (prefers-color-scheme: dark) {
  .action-btn {
    border-color: var(--shell-border-dark);
  }
}

.toggle-row {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.9rem;
  cursor: pointer;
  -webkit-tap-highlight-color: transparent;
}

.toggle-row input[type="checkbox"] {
  width: 18px;
  height: 18px;
  accent-color: var(--shell-primary);
}

.info-card {
  opacity: 0.7;
}
</style>
