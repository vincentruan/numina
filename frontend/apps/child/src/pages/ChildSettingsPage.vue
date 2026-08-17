<template>
  <div class="settings-page">
    <PageHeader :title="t('home.settings')" />

    <div class="settings-body">
      <!-- Profile Card (centered layout) -->
      <div class="profile-card" @click="router.push('/settings/profile')">
        <UserAvatar
          :avatar-url="childAuthStore.childUser?.avatar_url ?? null"
          :avatar-color="childAuthStore.childUser?.avatar_color ?? 'var(--color-primary)'"
          :display-name="childAuthStore.childUser?.display_name || ''"
          :size="64"
        />
        <div class="profile-info">
          <div class="profile-name">{{ childAuthStore.childUser?.display_name }}</div>
          <div class="profile-username">@{{ childAuthStore.childUser?.username }}</div>
        </div>
      </div>

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
        <p class="settings-label">
          <span class="label-icon" aria-hidden="true">🌐</span>
          {{ t('home.settingsLanguage') }}
        </p>
        <div class="theme-options">
          <button
            v-for="opt in languageOptions"
            :key="opt.value"
            class="theme-btn"
            :class="{ active: currentLocale === opt.value }"
            @click="setLocale(opt.value)"
          >
            <span class="btn-flag" aria-hidden="true">{{ opt.flag }}</span>
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
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { showConfirmDialog, showToast } from 'vant'
import { useDarkMode } from '@/utils/darkMode'
import { useLocale } from '@/utils/locale'
import { useChildAuthStore } from '@numina/auth'
import { getMainBaseUrl } from '@/utils/mainApp'
import UserAvatar from '@/components/common/UserAvatar.vue'

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
  { value: 'zh-CN' as const, label: t('home.langZhCN'), flag: '🇨🇳' },
  { value: 'en-US' as const, label: t('home.langEnUS'), flag: '🇺🇸' },
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
  font-size: 14px;
  font-weight: 600;
  letter-spacing: 1px;
  text-transform: uppercase;
  color: var(--color-muted);
  margin: 0;
  display: flex;
  align-items: center;
  gap: 6px;
}
.label-icon {
  font-size: 14px;
  line-height: 1;
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
  font-size: 14px;
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
.btn-flag {
  font-size: 16px;
  line-height: 1;
  margin-right: 4px;
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

/* Profile Card */
.profile-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 24px 16px;
  background: var(--color-surface-card);
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: transform 0.15s;
}
.profile-card:active {
  transform: scale(0.98);
}
.profile-info {
  margin-top: 12px;
  text-align: center;
}
.profile-name {
  font-size: 18px;
  font-weight: 600;
  color: var(--color-ink);
  margin-bottom: 4px;
}
.profile-username {
  font-size: 13px;
  color: var(--color-muted);
}
</style>
