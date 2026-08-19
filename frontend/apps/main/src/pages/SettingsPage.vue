<template>
  <div class="settings-page">
    <PageHeader :title="t('settings.title')" :show-back="false" />

    <!-- Invite tooltip (shown once for owners on first visit) -->
    <div v-if="showInviteTip" class="feature-tip">{{ t('featureHints.settingsInvite') }}</div>

    <!-- Profile Card (centered layout) -->
    <div class="profile-card" @click="router.push('/settings/profile')">
      <UserAvatar
        :avatar-url="authStore.user?.avatar_url ?? null"
        :avatar-color="authStore.user?.avatar_color ?? 'var(--van-primary-color)'"
        :display-name="authStore.user?.display_name || ''"
        :size="64"
      />
      <div class="profile-info">
        <div class="profile-name">{{ authStore.user?.display_name }}</div>
        <div class="profile-family">
          <van-icon name="home-o" size="14" />
          <span>{{ familyStore.family?.custom_title || familyStore.family?.name }}</span>
        </div>
      </div>
    </div>

    <!-- 账户信息 -->
    <van-cell-group inset :title="t('settings.accountInfo')">
      <van-cell :title="t('settings.username')" :value="authStore.user?.username ?? ''" is-link to="/settings/username">
        <template #icon>
          <UsernameIcon :size="16" class="cell-icon" />
        </template>
      </van-cell>
      <van-cell :title="t('settings.role')" :value="authStore.user?.role === 'owner' ? t('family.owner') : t('family.member')" icon="medal-o" />
      <van-cell
        v-if="authStore.user?.role === 'owner' && familyStore.family?.creator_code"
        :title="t('settings.creationInviteCode')"
        :value="familyStore.family?.creator_code"
        icon="coupon-o"
      />
    </van-cell-group>

    <!-- 外观与偏好 -->
    <van-cell-group inset :title="t('settings.userSettings')" class="section">
      <van-cell :title="t('settings.theme')" :value="themeLabel" is-link @click="showThemePicker = true">
        <template #icon>
          <ThemeIcon :size="16" class="cell-icon" />
        </template>
      </van-cell>
      <van-cell :title="t('settings.themeColor')" icon="diamond-o" is-link @click="showThemeColorPicker = true">
        <template #value>
          <span class="theme-color-preview" :style="{ backgroundColor: currentThemeColor }"></span>
        </template>
      </van-cell>
      <van-cell :title="t('settings.language')" :value="languageLabel" is-link @click="showLanguagePicker = true">
        <template #icon>
          <LanguageIcon :size="16" class="cell-icon" />
        </template>
      </van-cell>
      <van-cell
        :title="t('settings.defaultCurrency')"
        :value="authStore.user?.default_currency || 'CNY'"
        :label="authStore.user?.default_currency && authStore.user.default_currency !== 'CNY' ? t('settings.currencyRateHint') : undefined"
        is-link
        @click="showCurrencyPicker = true"
      >
        <template #icon>
          <CurrencyIcon :size="16" class="cell-icon" />
        </template>
      </van-cell>
      <van-cell
        :title="t('settings.userAdvancedConfig')"
        icon="setting-o"
        is-link
        to="/settings/user/config"
      />
    </van-cell-group>
    <van-cell-group
      v-if="authStore.user?.role === 'owner' || authStore.user?.role === 'member'"
      inset
      :title="t('settings.familyManagement')"
      class="section"
    >
      <van-cell :title="t('settings.familyMembers')" icon="friends-o" is-link to="/settings/family/members" />
      <van-cell
        v-if="authStore.user?.role === 'owner'"
        :title="t('settings.familyAdvancedConfig')"
        icon="setting-o"
        is-link
        to="/settings/family/config"
      />
      <van-cell
        v-if="authStore.user?.role === 'owner'"
        :title="t('settings.debtThresholds')"
        icon="balance-pay"
        is-link
        to="/settings/family/debt-thresholds"
      />
      <van-cell
        v-if="authStore.user?.role === 'owner'"
        :title="t('manifesto.editManifesto')"
        icon="certificate"
        is-link
        to="/settings/family/manifesto"
      />
      <van-cell
        v-if="authStore.user?.role === 'owner'"
        :title="t('settings.familyRemoteBackup')"
        is-link
        to="/settings/family/storage"
      >
        <template #icon>
          <SvgIcon name="cloud-upload" :size="16" class="cell-icon" />
        </template>
      </van-cell>
    </van-cell-group>

    <!-- 账户安全 -->
    <van-cell-group inset :title="t('settings.accountSecurity')" class="section">
      <van-cell :title="t('settings.accountPassword')" icon="lock" is-link to="/settings/password" />
      <van-cell :title="t('secondFactor.title')" icon="shield-o" is-link to="/settings/second-factor" />
      <van-cell :title="t('device.title')" icon="phone-o" is-link to="/settings/devices" />
    </van-cell-group>

    <!-- 通知设置 -->
    <van-cell-group inset :title="t('settings.notificationSettings')" class="section">
      <van-cell :title="t('reminders.thresholdSettings')" icon="gold-coin-o" is-link to="/settings/notifications/threshold" />
      <van-cell
        :title="t('reminders.notificationSettings')"
        is-link
        icon="bell"
        @click="$router.push('/settings/notifications')"
      />
    </van-cell-group>

    <!-- AI 助手设置 -->
    <van-cell-group inset :title="t('settings.aiSettings')" class="section">
      <van-cell
        v-if="authStore.user?.role === 'owner'"
        center
        :title="t('settings.enableAI')"
        :label="hasAnyModel ? undefined : t('settings.enableAIDesc')"
      >
        <template #icon>
          <SvgIcon name="sparkles" :size="16" class="cell-icon" />
        </template>
        <template #value>
          <van-switch
            :model-value="aiEnabled"
            :disabled="!hasAnyModel || togglingAI"
            size="22px"
            @update:model-value="onToggleAI"
          />
        </template>
      </van-cell>
      <van-cell
        v-if="authStore.user?.role === 'owner' && aiEnabled"
        center
        :title="t('settings.autoReport')"
        :label="t('settings.autoReportDesc')"
      >
        <template #icon>
          <SvgIcon name="documentation" :size="16" class="cell-icon" />
        </template>
        <template #value>
          <van-switch
            :model-value="reportAutoGenerate"
            :disabled="togglingReportAuto"
            size="22px"
            @update:model-value="onToggleReportAuto"
          />
        </template>
      </van-cell>
      <van-cell :title="t('settings.aiAssistant')" is-link to="/settings/ai">
        <template #icon>
          <SvgIcon name="brain-circuit" :size="16" class="cell-icon" />
        </template>
        <template #value>
          <span
            v-if="aiSystemStatus && aiEnabled"
            class="ai-status-badge"
            :style="aiStatusBadgeStyle(aiSystemStatus)"
          >{{ aiStatusLabel(aiSystemStatus) }}</span>
        </template>
      </van-cell>
      <van-cell :title="t('settings.chatHistory')" is-link to="/ai/chat/history">
        <template #icon>
          <SvgIcon name="documentation" :size="16" class="cell-icon" />
        </template>
      </van-cell>
      <van-cell :title="t('settings.mcpManage')" is-link to="/settings/ai/mcp">
        <template #icon>
          <SvgIcon name="plug" :size="16" class="cell-icon" />
        </template>
      </van-cell>
      <van-cell :title="t('settings.webSearchManage')" is-link to="/settings/ai/web-search">
        <template #icon>
          <SvgIcon name="web-search" :size="16" class="cell-icon" />
        </template>
      </van-cell>
      <van-cell :title="t('settings.asrManage')" is-link to="/settings/ai/asr">
        <template #icon>
          <van-icon name="volume-o" size="16" class="cell-icon" />
        </template>
      </van-cell>
      <van-cell :title="t('settings.skillsManage')" is-link to="/settings/ai/skills">
        <template #icon>
          <SvgIcon name="wand" :size="16" class="cell-icon" />
        </template>
      </van-cell>
      <van-cell :title="t('settings.agentsManage')" is-link to="/settings/ai/agents">
        <template #icon>
          <SvgIcon name="robot" :size="16" class="cell-icon" />
        </template>
      </van-cell>
    </van-cell-group>

    <!-- 数据管理 -->
    <van-cell-group inset :title="t('settings.dataManagement')" class="section">
      <van-cell :title="t('settings.categoryManage')" icon="apps-o" is-link to="/settings/categories" />
      <van-cell :title="t('settings.tagManage')" icon="label-o" is-link to="/settings/tags" />
    </van-cell-group>

    <!-- 引导 -->

    <div class="actions">
      <van-button block type="danger" plain @click="onLogout">
        {{ t('settings.logout') }}
      </van-button>
    </div>

    <!-- Theme Picker -->
    <van-popup v-model:show="showThemePicker" round position="bottom">
      <van-picker
        :columns="themeOptions"
        :model-value="[authStore.user?.theme || 'system']"
        @confirm="onThemeConfirm"
        @cancel="showThemePicker = false"
      >
        <template #option="{ text, value }">
          <div class="theme-option">
            <svg v-if="value === 'light'" class="theme-option-icon" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round">
              <circle cx="12" cy="12" r="4" />
              <line x1="12" y1="2" x2="12" y2="5" />
              <line x1="12" y1="19" x2="12" y2="22" />
              <line x1="2" y1="12" x2="5" y2="12" />
              <line x1="19" y1="12" x2="22" y2="12" />
              <line x1="4.93" y1="4.93" x2="7.17" y2="7.17" />
              <line x1="16.83" y1="16.83" x2="19.07" y2="19.07" />
              <line x1="4.93" y1="19.07" x2="7.17" y2="16.83" />
              <line x1="16.83" y1="7.17" x2="19.07" y2="4.93" />
            </svg>
            <svg v-else-if="value === 'dark'" class="theme-option-icon" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
              <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" />
            </svg>
            <svg v-else class="theme-option-icon" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
              <rect x="2" y="3" width="20" height="14" rx="2" />
              <line x1="8" y1="21" x2="16" y2="21" />
              <line x1="12" y1="17" x2="12" y2="21" />
            </svg>
            <span>{{ text }}</span>
          </div>
        </template>
      </van-picker>
    </van-popup>

    <!-- Language Picker -->
    <van-popup v-model:show="showLanguagePicker" round position="bottom">
      <van-picker
        :columns="languageOptions"
        :model-value="[authStore.user?.language || 'zh-CN']"
        @confirm="onLanguageConfirm"
        @cancel="showLanguagePicker = false"
      >
        <template #option="{ text, value }">
          <div class="lang-option">
            <!-- Chinese flag -->
            <svg v-if="value === 'zh-CN'" class="lang-flag" width="22" height="16" viewBox="0 0 30 20">
              <rect width="30" height="20" rx="2" fill="#DE2910" />
              <polygon points="5,3 5.9,5.8 8.5,4.2 6.5,6.5 9,8 5.8,7.5 5,10.5 4.2,7.5 1,8 3.5,6.5 1.5,4.2 4.1,5.8" fill="#FFDE00" />
            </svg>
            <!-- US flag -->
            <svg v-else class="lang-flag" width="22" height="16" viewBox="0 0 30 20">
              <rect width="30" height="20" rx="2" fill="#B22234" />
              <rect y="3" width="30" height="2" fill="#fff" />
              <rect y="7" width="30" height="2" fill="#fff" />
              <rect y="11" width="30" height="2" fill="#fff" />
              <rect y="15" width="30" height="2" fill="#fff" />
              <rect width="12" height="10" fill="#3C3B6E" />
              <circle cx="3" cy="2.5" r="0.7" fill="#fff" />
              <circle cx="6" cy="2.5" r="0.7" fill="#fff" />
              <circle cx="9" cy="2.5" r="0.7" fill="#fff" />
              <circle cx="4.5" cy="5" r="0.7" fill="#fff" />
              <circle cx="7.5" cy="5" r="0.7" fill="#fff" />
              <circle cx="3" cy="7.5" r="0.7" fill="#fff" />
              <circle cx="6" cy="7.5" r="0.7" fill="#fff" />
              <circle cx="9" cy="7.5" r="0.7" fill="#fff" />
            </svg>
            <span>{{ text }}</span>
          </div>
        </template>
      </van-picker>
    </van-popup>

    <!-- Currency Picker -->
    <CurrencyPicker
      v-model:show="showCurrencyPicker"
      v-model="selectedCurrency"
    />

    <!-- Theme Color Picker -->
    <van-popup v-model:show="showThemeColorPicker" round position="bottom">
      <div class="theme-color-picker">
        <div class="color-picker-header">
          <span>{{ t('reminders.themeColorPickerTitle') }}</span>
          <van-icon name="cross" @click="showThemeColorPicker = false" />
        </div>
        <div class="color-options">
          <div
            v-for="color in themeColorOptions"
            :key="color.value"
            class="color-option"
            :class="{ active: currentThemeColor === color.value }"
            :style="{ backgroundColor: color.value }"
            :aria-label="color.name"
            role="radio"
            :aria-checked="currentThemeColor === color.value"
            tabindex="0"
            @click="selectThemeColor(color.value)"
            @keydown.enter="selectThemeColor(color.value)"
            @keydown.space.prevent="selectThemeColor(color.value)"
          >
            <van-icon v-if="currentThemeColor === color.value" name="success" />
          </div>
        </div>
      </div>
    </van-popup>

    <!-- Edit Family Title Dialog -->
    <van-dialog
      v-model:show="showTitleDialog"
      :title="t('reminders.editFamilyTitleDialog')"
      show-cancel-button
      @confirm="onTitleConfirm"
    >
      <van-field
        v-model="editTitleValue"
        :placeholder="t('reminders.editFamilyTitlePlaceholder')"
        clearable
      />
    </van-dialog>

    <!-- Error detail popup -->
    <van-popup
      v-model:show="showTestErrorPopup"
      position="bottom"
      round
      :style="{ maxHeight: '65vh' }"
    >
      <div class="error-popup">
        <div class="error-popup__header">
          <span class="error-popup__title">{{ t('aiConfig.testErrorTitle') }}</span>
          <van-icon name="cross" size="20" @click="showTestErrorPopup = false" />
        </div>
        <div class="error-popup__summary">{{ testErrorMessage }}</div>
        <div v-if="testErrorJson" class="error-popup__section-label">{{ t('aiConfig.testErrorRaw') }}</div>
        <div v-if="testErrorJson" class="error-popup__code">
          <pre>{{ testErrorJson }}</pre>
        </div>
        <van-button
          size="small"
          plain
          icon="description"
          class="error-popup__copy"
          @click="copyTestError"
        >
          {{ testErrorCopied ? t('aiConfig.testErrorCopied') : t('aiConfig.testErrorCopy') }}
        </van-button>
      </div>
    </van-popup>
  </div>
</template>

<script setup lang="ts">
defineOptions({ name: 'Settings' })
import { ref, computed, onMounted, onActivated, watch } from 'vue'
import { showConfirmDialog, showToast, showSuccessToast, showFailToast } from 'vant'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import { usePageLoading } from '@/composables/usePageLoading'
import { useMemberNotify } from '@/composables/useMemberNotify'
import { useAuthStore } from '@/stores/auth'
import { useFamilyStore } from '@/stores/family'
import { useAIStore } from '@/stores/ai'
import { updateSettings } from '@/api/auth'
import { getFamilySettings, updateFamilySettings } from '@/api/family'
import { isGuideDone, markGuideDone } from '@/utils/storage'
import * as aiApi from '@/api/ai'
import PageHeader from '@/components/common/PageHeader.vue'
import UserAvatar from '@/components/common/UserAvatar.vue'
import CurrencyPicker from '@/components/common/CurrencyPicker.vue'
import SvgIcon from '@/components/SvgIcon.vue'
import UserIcon from '@/components/common/UserIcon.vue'
import UsernameIcon from '@/components/common/UsernameIcon.vue'
import ThemeIcon from '@/components/common/ThemeIcon.vue'
import LanguageIcon from '@/components/common/LanguageIcon.vue'
import CurrencyIcon from '@/components/common/CurrencyIcon.vue'
import axios from 'axios'

const { t } = useI18n()
const router = useRouter()

const authStore = useAuthStore()
const familyStore = useFamilyStore()
const aiStore = useAIStore()
const { increment, decrement } = usePageLoading()
const { notifyConfigChange, markFamilySnapshot } = useMemberNotify()
// Track first KeepAlive activation to avoid duplicate loading:
// Vue 3 fires both onMounted and onActivated on first mount inside <KeepAlive>.
// onMounted handles initial load; onActivated only refreshes on reactivation.
let hasActivated = false

// Invite tooltip: show for owners who haven't dismissed it
const showInviteTip = ref(false)

onMounted(async () => {
  // Restart loading indicator for async data loading (router will auto-complete after 100ms)
  increment()
  try {
    if (!familyStore.family) {
      await familyStore.fetchFamily()
    }
    await authStore.fetchMe()
    if (authStore.user?.role === 'owner') {
      await aiStore.fetchConfigs()
      await loadReportAutoSetting()
    }
  } catch (err) {
    // API error (e.g., AUTH_TOKEN_EXPIRED) — axios interceptor handles redirect to /login
    // but this catch prevents the page from crashing with a blank screen
    console.error('[SettingsPage] Failed to load data:', err)
  } finally {
    decrement()
  }
  // Initialize theme color: prefer server-persisted value, fall back to localStorage
  const savedColor = authStore.user?.theme_color || localStorage.getItem('theme-primary')
  if (savedColor) {
    currentThemeColor.value = savedColor
    localStorage.setItem('theme-primary', savedColor)  // sync localStorage with server
    document.documentElement.style.setProperty('--theme-primary', savedColor)
    document.documentElement.style.setProperty('--van-primary-color', savedColor)
  }
  // Show invite tooltip for owners on first visit
  if (!isGuideDone('tip_settings-invite') && authStore.user?.role === 'owner') {
    showInviteTip.value = true
    setTimeout(() => { showInviteTip.value = false; markGuideDone('tip_settings-invite') }, 3000)
  }
})

// KeepAlive 缓存页面：返回时触发 onActivated 而非 onMounted
onActivated(async () => {
  if (!hasActivated) { hasActivated = true; return }
  increment()
  try {
    if (!familyStore.family) {
      await familyStore.fetchFamily()
    }
    await authStore.fetchMe()
    if (authStore.user?.role === 'owner') {
      await aiStore.fetchConfigs()
    }
  } catch (err) {
    console.error('[SettingsPage] Failed to load data:', err)
  } finally {
    decrement()
  }
  // Re-apply theme color on reactivation
  const savedColor = authStore.user?.theme_color || localStorage.getItem('theme-primary')
  if (savedColor) {
    currentThemeColor.value = savedColor
    localStorage.setItem('theme-primary', savedColor)
    document.documentElement.style.setProperty('--theme-primary', savedColor)
    document.documentElement.style.setProperty('--van-primary-color', savedColor)
  }
})

// AI toggle — reads from family-level flag (familyStore.aiEnabled)
const togglingAI = ref(false)

// Test error popup state
const showTestErrorPopup = ref(false)
const testErrorMessage = ref('')
const testErrorDetail = ref<Record<string, unknown> | null>(null)
const testErrorCopied = ref(false)

const testErrorJson = computed(() => {
  if (!testErrorDetail.value) return ''
  return JSON.stringify(testErrorDetail.value, null, 2)
})

function copyTestError() {
  const parts: string[] = [testErrorMessage.value]
  if (testErrorDetail.value) parts.push(JSON.stringify(testErrorDetail.value, null, 2))
  navigator.clipboard.writeText(parts.join('\n\n')).then(() => {
    testErrorCopied.value = true
    setTimeout(() => { testErrorCopied.value = false }, 2000)
  })
}

function openTestErrorPopup(message: string, detail?: Record<string, unknown> | null) {
  testErrorMessage.value = message
  testErrorDetail.value = detail ?? null
  showTestErrorPopup.value = true
}
// A config is "ready" when it has a model ID and an API key configured.
// `ai_api_key_masked` is non-null only when the backend has stored an encrypted key.
const hasAnyModel = computed(() =>
  aiStore.configs.some(
    (c) => (c.model_id || c.model_2_id || c.model_3_id) && c.ai_api_key_masked,
  ),
)
const aiEnabled = computed(() => familyStore.aiEnabled)

// AI system health: aggregate circuit state across all active providers
const aiSystemStatus = computed(() => {
  const active = aiStore.configs.filter(
    (c) => c.is_active && c.ai_api_key_masked,
  )
  if (active.length === 0) return null
  const allOpen = active.every((c) => c.circuit_state === 'open')
  if (allOpen) return 'unavailable'
  const anyDegraded = active.some(
    (c) => c.circuit_state === 'half_open' || c.circuit_state === 'open',
  )
  if (anyDegraded) return 'degraded'
  return 'healthy'
})

function aiStatusBadgeStyle(status: string | null) {
  if (status === 'unavailable')
    return { background: 'var(--van-danger-color)', color: '#fff' }
  if (status === 'degraded')
    return { background: 'var(--van-warning-color)', color: '#fff' }
  return { background: 'var(--van-success-color)', color: '#fff' }
}

function aiStatusLabel(status: string | null) {
  if (status === 'unavailable') return t('settings.aiStatusUnavailable')
  if (status === 'degraded') return t('settings.aiStatusDegraded')
  return t('settings.aiStatusHealthy')
}

async function onToggleAI(val: boolean) {
  if (!hasAnyModel.value) {
    showToast(t('settings.enableAINoModel'))
    return
  }
  togglingAI.value = true
  try {
    // 1. First activate/deactivate provider (can fail, easier to recover)
    const target = aiStore.configs.find(
      (c) => (c.model_id || c.model_2_id || c.model_3_id) && c.ai_api_key_masked,
    )
    if (target) {
      await aiApi.updateProviderConfig(target.id, { is_active: val })
      await aiStore.fetchConfigs()
    }

    // 2. Then update family-level master switch (with rollback)
    try {
      await updateFamilySettings({ aiEnabled: val })
      familyStore.aiEnabled = val
    } catch (e) {
      // Rollback provider change if family switch update fails
      if (target) {
        await aiApi.updateProviderConfig(target.id, { is_active: !val }).catch(() => {})
        await aiStore.fetchConfigs().catch(() => {})
      }
      throw e
    }

    showToast({
      message: val ? t('toast.aiEnabled') : t('toast.aiDisabled'),
      icon: 'none',
    })
    // After enabling, run a lightweight connection test so the user gets
    // immediate feedback if the model is unreachable (invalid key, outage…).
    if (val && target) {
      try {
        const result = await aiApi.testProviderConfig(target.id)
        const data = result.data
        if (data.connected) {
          // Build message: show fallback info if any provider fallback was used
          if (data.fallback_count && data.fallback_count > 0) {
            const circuitLabel = data.used_circuit_state === 'half_open'
              ? ' (降级中)'
              : data.used_circuit_state === 'open'
                ? ' (熔断中)'
                : ''
            showFailToast(
              `${data.message || '主模型不可用，已自动切换'}${circuitLabel}`
            )
          }
          // else: connected without fallback — no toast needed, AI is enabled
        } else {
          // All providers failed — show detailed error in popup
          const fallbackNote = data.fallback_count
            ? ` (已尝试 ${data.fallback_count + 1} 个候选模型)`
            : ''
          openTestErrorPopup(
            `${data.message || t('toast.aiTestFailed')}${fallbackNote}`,
            data.error_detail,
          )
        }
      } catch {
        // Test endpoint itself failed — not critical, the toggle was already saved.
        showFailToast(t('toast.aiTestFailed'))
      }
    }
  } catch {
    showFailToast(t('toast.operationFailed2'))
  } finally {
    togglingAI.value = false
  }
}

// Report auto-generate toggle
const reportAutoGenerate = ref(false)
const togglingReportAuto = ref(false)

async function loadReportAutoSetting() {
  try {
    const res = await getFamilySettings()
    reportAutoGenerate.value = res.data.report_auto_generate_enabled
  } catch {
    // silent
  }
}

async function onToggleReportAuto(val: boolean) {
  togglingReportAuto.value = true
  try {
    await updateFamilySettings({ reportAutoGenerateEnabled: val })
    reportAutoGenerate.value = val
    showSuccessToast(val ? t('toast.autoReportEnabled') : t('toast.autoReportDisabled'))
  } catch {
    showFailToast(t('toast.operationFailed2'))
  } finally {
    togglingReportAuto.value = false
  }
}

const showThemePicker = ref(false)
const showLanguagePicker = ref(false)
const showCurrencyPicker = ref(false)
const showThemeColorPicker = ref(false)
const showTitleDialog = ref(false)
const editTitleValue = ref('')
const selectedCurrency = ref(authStore.user?.default_currency || 'CNY')

const themeColorOptions = computed(() => [
  { name: t('settings.colorBlue'), value: '#007aff' },
  { name: t('settings.colorPurple'), value: '#5856d6' },
  { name: t('settings.colorIndigo'), value: '#3634a3' },
  { name: t('settings.colorOrange'), value: '#ff9500' },
  { name: t('settings.colorRed'), value: '#ff3b30' },
  { name: t('settings.colorPink'), value: '#ff2d55' },
  { name: t('settings.colorGreen'), value: '#248a3d' },
  { name: t('settings.colorTeal'), value: '#0071a4' },
])

const currentThemeColor = ref(localStorage.getItem('theme-primary') || '#007aff')

const themeOptions = [
  { text: t('settings.themeSystem'), value: 'system' },
  { text: t('settings.themeLight'), value: 'light' },
  { text: t('settings.themeDark'), value: 'dark' },
]

const languageOptions = [
  { text: t('settings.languageZhCN'), value: 'zh-CN' },
  { text: t('settings.languageEnUS'), value: 'en-US' },
]

const themeLabel = computed(() => {
  const theme = authStore.user?.theme
  if (theme === 'dark') return t('settings.themeDark')
  if (theme === 'system') return t('settings.themeSystem')
  return t('settings.themeLight')
})

const languageLabel = computed(() => {
  return authStore.user?.language === 'en-US' ? t('settings.languageEnUS') : t('settings.languageZhCN')
})

async function updateSetting(key: string, value: string) {
  try {
    await updateSettings({ [key]: value })
    await authStore.fetchMe()
    showToast(t('settings.settingsSaved'))
  } catch {
    showToast(t('settings.saveFailed'))
  }
}

function onThemeConfirm({ selectedOptions }: { selectedOptions: Array<{ text: string; value: string }> }) {
  updateSetting('theme', selectedOptions[0].value)
  showThemePicker.value = false
}

function onLanguageConfirm({ selectedOptions }: { selectedOptions: Array<{ text: string; value: string }> }) {
  updateSetting('language', selectedOptions[0].value)
  showLanguagePicker.value = false
}

// Watch for currency selection changes
watch(selectedCurrency, (newCurrency) => {
  if (newCurrency && newCurrency !== authStore.user?.default_currency) {
    updateSetting('default_currency', newCurrency)
  }
})

function onEditFamilyTitle() {
  if (authStore.user?.role !== 'owner') {
    showToast(t('toast.ownerOnlyWarning'))
    return
  }
  editTitleValue.value = familyStore.family?.custom_title || familyStore.family?.name || ''
  showTitleDialog.value = true
}

async function onTitleConfirm() {
  try {
    const newTitle = editTitleValue.value.trim()
    await familyStore.updateFamilyTitle(newTitle || null)
    showToast(t('toast.familyTitleUpdated'))
    notifyConfigChange()
    markFamilySnapshot()
  } catch (err) {
    const detail = axios.isAxiosError(err) ? err.response?.data?.detail : undefined
    showToast(detail || t('toast.modifyFailed'))
  }
}


async function selectThemeColor(color: string) {
  currentThemeColor.value = color
  localStorage.setItem('theme-primary', color)
  document.documentElement.style.setProperty('--theme-primary', color)
  document.documentElement.style.setProperty('--van-primary-color', color)
  showThemeColorPicker.value = false
  showSuccessToast(t('toast.themeChanged'))
  // Persist to server (fire-and-forget; localStorage already covers offline)
  try {
    await updateSettings({ theme_color: color })
    // Update local authStore user so subsequent renders use the server value
    if (authStore.user) authStore.user.theme_color = color
  } catch {
    // Non-critical: localStorage fallback preserves the choice locally
  }
}

async function onLogout() {
  try {
    await showConfirmDialog({ title: t('common.confirm'), message: t('settings.logoutConfirm') })
    authStore.logout({ onLogout: () => router.push('/login') })
  } catch {
    // cancelled
  }
}
</script>

<style scoped>
.settings-page {
  background: var(--bg-secondary);
  min-height: 100vh;
  padding-bottom: 20px;
}
.section {
  margin-top: 12px;
}
.actions {
  padding: 24px 16px;
}
.theme-color-preview {
  width: 24px;
  height: 24px;
  border-radius: 50%;
  display: inline-block;
}
.theme-color-picker {
  padding: 16px;
}
.color-picker-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
  font-weight: 500;
}
.color-options {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
}
.color-option {
  width: 48px;
  height: 48px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  border: 2px solid transparent;
  transition: transform 0.2s;
}
.color-option.active {
  border-color: var(--text-primary);
}
.color-option:active {
  transform: scale(0.95);
}
.color-option :deep(.van-icon) {
  color: #fff;
  font-size: 20px;
}
[data-theme='dark'] .color-option.active {
  border-color: var(--text-primary);
}

.theme-option {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}
.theme-option-icon {
  flex-shrink: 0;
  color: var(--van-text-color, var(--van-gray-8));
}
.lang-option {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}
.lang-flag {
  flex-shrink: 0;
  border-radius: 2px;
  overflow: hidden;
}
.cell-icon {
  margin-right: 4px;
  color: var(--van-gray-6);
  flex-shrink: 0;
  /* Override van-cell's align-items: normal which causes top alignment */
  align-self: center;
  /* Use inline-block for fallback vertical-align (works in non-flex contexts) */
  display: inline-block;
  vertical-align: middle;
}

/* Feature tooltip (auto-dismiss, non-interactive) */
.feature-tip {
  position: sticky;
  top: 0;
  z-index: 10;
  background: var(--card-bg);
  color: var(--text-secondary);
  padding: 10px 16px;
  text-align: center;
  font-size: 13px;
  border-bottom: 1px solid var(--separator);
  pointer-events: none;
  animation: feature-tip-fade 3s ease-in-out forwards;
}

@keyframes feature-tip-fade {
  0% { opacity: 0; transform: translateY(-4px); }
  10% { opacity: 1; transform: translateY(0); }
  80% { opacity: 1; }
  100% { opacity: 0; }
}

.ai-status-badge {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 10px;
  font-size: 11px;
  font-weight: 500;
  line-height: 1.4;
  white-space: nowrap;
}
/* Profile Card */
.profile-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 24px 16px;
  margin: 12px 16px;
  background: var(--card-bg, var(--van-background-2));
  border-radius: 12px;
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
  font-size: 17px;
  font-weight: 600;
  color: var(--text-primary, var(--van-text-color));
  margin-bottom: 4px;
}
.profile-family {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 13px;
  color: var(--text-secondary, var(--van-text-color-2));
}

/* Error popup */
.error-popup {
  padding: 16px;
  max-height: 65vh;
  display: flex;
  flex-direction: column;
}

.error-popup__header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.error-popup__title {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
}

.error-popup__summary {
  font-size: 14px;
  color: var(--text-primary);
  line-height: 1.5;
  word-break: break-all;
  margin-bottom: 12px;
}

.error-popup__section-label {
  font-size: 12px;
  color: var(--text-secondary);
  margin-bottom: 6px;
}

.error-popup__code {
  background: var(--bg-secondary);
  border-radius: 8px;
  padding: 12px;
  max-height: 35vh;
  overflow: auto;
  -webkit-overflow-scrolling: touch;
  margin-bottom: 12px;
}

.error-popup__code pre {
  margin: 0;
  font-family: 'SF Mono', Monaco, 'Cascadia Code', monospace;
  font-size: 12px;
  line-height: 1.5;
  white-space: pre-wrap;
  word-break: break-all;
  color: var(--text-primary);
  user-select: all;
}

.error-popup__copy {
  align-self: flex-end;
}
</style>
