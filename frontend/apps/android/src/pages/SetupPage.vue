<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import {
  getServerUrl,
  setServerUrl,
  validateServer,
  classifyUrl,
  isAdvancedMode,
  setAdvancedMode,
  normalizeServerUrl,
} from '@/utils/server-config'

const serverUrl = ref('')
const validating = ref(false)
const connecting = ref(false)
const error = ref('')
const advancedMode = ref(false)

const urlClass = computed(() => classifyUrl(serverUrl.value))

const isHttpDanger = computed(() => urlClass.value === 'http-public')

const httpWarningText = computed(() => {
  if (urlClass.value === 'http-public') {
    return '⚠️ You are connecting to a public server over unencrypted HTTP. Data including login credentials will be sent in cleartext. This is strongly discouraged.'
  }
  if (urlClass.value === 'http-lan') {
    return '📡 You are connecting over local network HTTP. This works for home use but push notifications (PWA) require HTTPS. Consider setting up a reverse proxy with HTTPS for full functionality.'
  }
  return ''
})

const canConnect = computed(() => {
  const cls = urlClass.value
  if (cls === 'invalid') return false
  if (cls === 'http-public') return false // block public HTTP always
  if ((cls === 'http-lan') && !advancedMode.value) return false
  return serverUrl.value.trim().length > 0
})

onMounted(async () => {
  const [saved, advanced] = await Promise.all([getServerUrl(), isAdvancedMode()])
  if (saved) serverUrl.value = saved
  advancedMode.value = advanced
})

async function handleConnect() {
  if (!canConnect.value) return

  const url = normalizeServerUrl(serverUrl.value)
  validating.value = true
  error.value = ''

  const ok = await validateServer(url)
  validating.value = false

  if (!ok) {
    error.value = 'Cannot reach server. Please check the URL and ensure the Numina server is running.'
    return
  }

  connecting.value = true
  await setServerUrl(url)

  // Brief success feedback, then navigate the WebView to the remote H5.
  // replace (not href): pushing the setup page into history makes canGoBack()
  // true at the H5 root and the exit prompt unreachable.
  setTimeout(() => {
    window.location.replace(url)
  }, 500)
}

async function toggleAdvanced() {
  advancedMode.value = !advancedMode.value
  await setAdvancedMode(advancedMode.value)
}
</script>

<template>
  <div class="setup-page">
    <div class="setup-header">
      <div class="logo">
        <svg width="48" height="48" viewBox="0 0 48 48" fill="none">
          <rect width="48" height="48" rx="12" fill="var(--shell-primary)" />
          <text x="50%" y="54%" text-anchor="middle" dominant-baseline="middle"
                fill="white" font-size="20" font-weight="bold" font-family="system-ui">N</text>
        </svg>
      </div>
      <h1>Welcome to Numina</h1>
      <p class="subtitle">Connect to your self-hosted family asset server</p>
    </div>

    <div class="setup-form">
      <div class="input-group">
        <label for="server-url">Server Address</label>
        <input
          id="server-url"
          v-model="serverUrl"
          type="url"
          placeholder="https://numina.example.com"
          autocomplete="url"
          autocapitalize="off"
          autocorrect="off"
          spellcheck="false"
          :disabled="connecting"
          @keydown.enter="handleConnect"
        />
        <div v-if="urlClass === 'https'" class="url-badge badge-secure">🔒 HTTPS</div>
        <div v-else-if="urlClass === 'localhost'" class="url-badge badge-dev">🛠 Dev</div>
        <div v-else-if="urlClass === 'http-lan'" class="url-badge badge-lan">📡 LAN</div>
        <div v-else-if="urlClass === 'http-public'" class="url-badge badge-danger">🚫 Insecure</div>
      </div>

      <div v-if="urlClass === 'http-lan' && !advancedMode" class="warning-box">
        <p>{{ httpWarningText }}</p>
        <button class="link-btn" @click="toggleAdvanced">Enable Advanced Mode to continue →</button>
      </div>

      <div v-if="isHttpDanger" class="danger-box">
        <p>{{ httpWarningText }}</p>
      </div>

      <div v-if="urlClass === 'http-lan' && advancedMode" class="info-box">
        <p>{{ httpWarningText }}</p>
      </div>

      <div v-if="error" class="error-box">
        <p>❌ {{ error }}</p>
      </div>

      <div v-if="connecting" class="success-box">
        <p>✅ Connected! Redirecting…</p>
      </div>

      <button
        class="connect-btn"
        :disabled="!canConnect || validating || connecting"
        @click="handleConnect"
      >
        <span v-if="validating">Connecting…</span>
        <span v-else-if="connecting">Redirecting…</span>
        <span v-else>Connect</span>
      </button>

      <div class="footer-links">
        <router-link to="/advanced">Advanced Settings</router-link>
      </div>
    </div>
  </div>
</template>

<style scoped>
.setup-page {
  min-height: 100%;
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  padding: 2rem 1.5rem;
  padding-top: env(safe-area-inset-top, 2rem);
  padding-bottom: env(safe-area-inset-bottom, 2rem);
}

.setup-header {
  text-align: center;
  margin-bottom: 2rem;
}

.logo {
  margin-bottom: 1rem;
}

h1 {
  font-size: 1.5rem;
  font-weight: 700;
  margin-bottom: 0.25rem;
}

.subtitle {
  color: var(--shell-text-secondary);
  font-size: 0.9rem;
}

.setup-form {
  width: 100%;
  max-width: 400px;
}

.input-group {
  margin-bottom: 1rem;
  position: relative;
}

label {
  display: block;
  font-size: 0.85rem;
  font-weight: 600;
  margin-bottom: 0.4rem;
  color: var(--shell-text-secondary);
}

input[type="url"] {
  width: 100%;
  padding: 0.75rem 1rem;
  font-size: 1rem;
  border: 2px solid var(--shell-border);
  border-radius: 10px;
  background: var(--shell-surface);
  color: var(--shell-text);
  outline: none;
  transition: border-color 0.2s;
}

input[type="url"]:focus {
  border-color: var(--shell-primary);
}

input[type="url"]:disabled {
  opacity: 0.6;
}

@media (prefers-color-scheme: dark) {
  input[type="url"] {
    background: var(--shell-surface-dark);
    border-color: var(--shell-border-dark);
    color: var(--shell-text-dark);
  }
  input[type="url"]:focus {
    border-color: var(--shell-primary-dark);
  }
}

.url-badge {
  display: inline-block;
  margin-top: 0.4rem;
  padding: 0.2rem 0.5rem;
  border-radius: 6px;
  font-size: 0.75rem;
  font-weight: 600;
}
.badge-secure { background: #dcfce7; color: #166534; }
.badge-dev { background: #dbeafe; color: #1e40af; }
.badge-lan { background: #fef3c7; color: #92400e; }
.badge-danger { background: #fee2e2; color: #991b1b; }

@media (prefers-color-scheme: dark) {
  .badge-secure { background: #052e16; color: #4ade80; }
  .badge-dev { background: #172554; color: #60a5fa; }
  .badge-lan { background: #422006; color: #fbbf24; }
  .badge-danger { background: #450a0a; color: #f87171; }
}

.warning-box, .danger-box, .info-box, .error-box, .success-box {
  padding: 0.75rem 1rem;
  border-radius: 8px;
  margin-bottom: 1rem;
  font-size: 0.85rem;
  line-height: 1.5;
}

.warning-box {
  background: #fef3c7;
  border-left: 3px solid #f59e0b;
  color: #92400e;
}
.danger-box {
  background: #fee2e2;
  border-left: 3px solid #dc2626;
  color: #991b1b;
}
.info-box {
  background: #dbeafe;
  border-left: 3px solid #3b82f6;
  color: #1e40af;
}
.error-box {
  background: #fee2e2;
  border-left: 3px solid #dc2626;
  color: #991b1b;
}
.success-box {
  background: #dcfce7;
  border-left: 3px solid #16a34a;
  color: #166534;
}

@media (prefers-color-scheme: dark) {
  .warning-box { background: #422006; color: #fbbf24; }
  .danger-box { background: #450a0a; color: #f87171; }
  .info-box { background: #172554; color: #93c5fd; }
  .error-box { background: #450a0a; color: #f87171; }
  .success-box { background: #052e16; color: #4ade80; }
}

.link-btn {
  background: none;
  border: none;
  color: inherit;
  text-decoration: underline;
  cursor: pointer;
  font-size: 0.85rem;
  padding: 0.5rem 0;
  min-height: 44px;
  display: inline-flex;
  align-items: center;
  margin-top: 0.3rem;
  -webkit-tap-highlight-color: transparent;
  touch-action: manipulation;
}

.connect-btn {
  width: 100%;
  padding: 0.85rem;
  font-size: 1rem;
  font-weight: 600;
  border: none;
  border-radius: 10px;
  background: var(--shell-primary);
  color: white;
  cursor: pointer;
  transition: opacity 0.2s;
  -webkit-tap-highlight-color: transparent;
  touch-action: manipulation;
}

.connect-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.connect-btn:active:not(:disabled) {
  opacity: 0.8;
}

@media (prefers-color-scheme: dark) {
  .connect-btn {
    background: var(--shell-primary-dark);
    color: #0a0a1a;
  }
}

.footer-links {
  text-align: center;
  margin-top: 1.5rem;
}

.footer-links a {
  color: var(--shell-text-secondary);
  font-size: 0.85rem;
  text-decoration: none;
  padding: 0.5rem;
  min-height: 44px;
  display: inline-flex;
  align-items: center;
}

.footer-links a:hover {
  color: var(--shell-primary);
}
</style>
