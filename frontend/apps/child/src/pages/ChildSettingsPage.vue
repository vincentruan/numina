<template>
  <div class="settings-page">
    <!-- Nav bar -->
    <div class="nav-bar">
      <button class="nav-back" :aria-label="t('common.back')" @click="router.back()">
        <van-icon name="arrow-left" size="20" />
      </button>
      <span class="nav-title">{{ t('home.settings') }}</span>
      <span class="nav-spacer" />
    </div>

    <div class="settings-body">
      <!-- Theme -->
      <div class="field-group">
        <p class="settings-label">{{ t('home.settingsTheme') }}</p>
        <div class="theme-options">
          <button
            v-for="opt in themeOptions"
            :key="opt.value"
            class="theme-btn"
            :class="{ active: themeMode === opt.value }"
            @click="setMode(opt.value)"
          >
            {{ opt.label }}
          </button>
        </div>
      </div>

      <!-- Language -->
      <div class="field-group">
        <p class="settings-label">{{ t('home.settingsLanguage') }}</p>
        <div class="theme-options">
          <button
            v-for="opt in languageOptions"
            :key="opt.value"
            class="theme-btn"
            :class="{ active: currentLocale === opt.value }"
            @click="setLocale(opt.value)"
          >
            {{ opt.label }}
          </button>
        </div>
      </div>

      <!-- Logout — destructive action, separated below the preferences -->
      <button class="logout-btn" @click="handleLogout">
        {{ t('home.logout') }}
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
defineOptions({ name: 'ChildSettings' })
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import { showConfirmDialog, showToast } from 'vant'
import { useDarkMode } from '@/utils/darkMode'
import { useLocale } from '@/utils/locale'
import { useChildAuthStore } from '@numina/auth'
import { getMainBaseUrl } from '@/utils/mainApp'

const { t } = useI18n()
const router = useRouter()
const { themeMode, setMode } = useDarkMode()
const { currentLocale, setLocale } = useLocale()
const childAuthStore = useChildAuthStore()

const themeOptions = computed(() => [
  { value: 'system' as const, label: t('home.themeSystem') },
  { value: 'light' as const, label: t('home.themeLight') },
  { value: 'dark' as const, label: t('home.themeDark') },
])

const languageOptions = computed(() => [
  { value: 'zh-CN' as const, label: t('home.langZhCN') },
  { value: 'en-US' as const, label: t('home.langEnUS') },
])

async function handleLogout() {
  try {
    await showConfirmDialog({
      title: t('common.confirm'),
      message: t('home.logoutConfirm'),
      confirmButtonText: t('common.confirm'),
      cancelButtonText: t('common.cancel'),
    })
    await childAuthStore.childLogout()
    showToast(t('toast.logoutSuccess'))
    // Redirect to main app login page (child app has no auth routes).
    // Use getMainBaseUrl() so dev mode (port 5174) redirects to main app (5173);
    // VITE_MAIN_APP_URL alone is empty in dev, which would hit /login on the child server → 404.
    const baseUrl = getMainBaseUrl()
    window.location.href = `${baseUrl}/login`
  } catch {
    // User cancelled or logout failed
  }
}
</script>

<style scoped>
.settings-page {
  background: var(--color-canvas);
  min-height: 100vh;
  display: flex;
  flex-direction: column;
}

/* ── Nav bar ── */
.nav-bar {
  display: flex;
  align-items: center;
  height: 56px;
  padding: 0 var(--space-md);
  background: var(--color-canvas);
  border-bottom: 1px solid var(--color-hairline);
  position: sticky;
  top: 0;
  z-index: 10;
}
.nav-back {
  width: 40px;
  height: 40px;
  border: none;
  background: transparent;
  color: var(--color-ink);
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: var(--radius-md);
  cursor: pointer;
  flex-shrink: 0;
}
.nav-back:active { background: var(--color-surface-soft); }
.nav-title {
  flex: 1;
  text-align: center;
  font-family: Inter, sans-serif;
  font-size: 17px;
  font-weight: 600;
  color: var(--color-ink);
  letter-spacing: -0.3px;
}
.nav-spacer { width: 40px; flex-shrink: 0; }

/* ── Body ── */
.settings-body {
  flex: 1;
  padding: var(--space-lg) var(--space-md) 48px;
  display: flex;
  flex-direction: column;
  gap: var(--space-lg);
}

.field-group {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.settings-label {
  font-family: Inter, sans-serif;
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 1px;
  text-transform: uppercase;
  color: var(--color-muted);
  margin: 0;
}
.theme-options {
  display: flex;
  gap: 8px;
}
.theme-btn {
  flex: 1;
  padding: 12px 4px;
  border-radius: var(--radius-md);
  border: 1px solid var(--color-hairline);
  background: var(--color-surface-soft);
  font-family: Inter, sans-serif;
  font-size: 13px;
  font-weight: 500;
  color: var(--color-muted);
  cursor: pointer;
  transition: all 0.15s;
  min-height: 44px;
}
.theme-btn.active {
  background: var(--color-brand-ochre);
  border-color: var(--color-brand-ochre);
  color: var(--color-ink);
  font-weight: 600;
}
.theme-btn:active { transform: scale(0.96); }

/* Logout — destructive action, visually separated below preferences */
.logout-btn {
  margin-top: auto;
  padding: 14px;
  border-radius: var(--radius-md);
  border: 1px solid var(--color-brand-coral);
  background: var(--color-surface-soft);
  font-family: Inter, sans-serif;
  font-size: 14px;
  font-weight: 600;
  color: var(--color-brand-coral);
  cursor: pointer;
  transition: all 0.15s;
  min-height: 44px;
}
.logout-btn:active { transform: scale(0.96); }
</style>
