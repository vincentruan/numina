<template>
  <div class="settings-page">
    <PageHeader :title="t('settings.title')" :show-back="false" />

    <!-- 账户信息 -->
    <van-cell-group inset :title="t('settings.accountInfo')">
      <van-cell
        :title="t('family.familyName')"
        :value="familyStore.family?.custom_title || familyStore.family?.name"
        :is-link="authStore.user?.role === 'owner'"
        @click="onEditFamilyTitle"
      />
      <van-cell :title="t('settings.currentUser')" :value="authStore.user?.display_name" />
      <van-cell :title="t('settings.username')" :value="authStore.user?.username ?? ''" />
      <van-cell :title="t('settings.role')" :value="authStore.user?.role === 'owner' ? t('family.owner') : t('family.member')" />
    </van-cell-group>

    <!-- 外观与偏好 -->
    <van-cell-group inset :title="t('settings.userSettings')" class="section">
      <van-cell :title="t('settings.theme')" :value="themeLabel" is-link @click="showThemePicker = true" />
      <van-cell :title="t('settings.themeColor')" is-link @click="showThemeColorPicker = true">
        <template #value>
          <span class="theme-color-preview" :style="{ backgroundColor: currentThemeColor }"></span>
        </template>
      </van-cell>
      <van-cell :title="t('settings.language')" :value="languageLabel" is-link @click="showLanguagePicker = true" />
      <van-cell :title="t('settings.defaultCurrency')" :value="authStore.user?.default_currency || 'CNY'" is-link @click="showCurrencyPicker = true" />
    </van-cell-group>

    <!-- 家庭管理 -->
    <van-cell-group
      v-if="authStore.user?.role === 'owner' || authStore.user?.role === 'member'"
      inset
      :title="t('settings.familyManagement')"
      class="section"
    >
      <van-cell :title="t('settings.familyMembers')" icon="friends-o" is-link to="/family" />
      <van-cell
        v-if="authStore.user?.role === 'owner'"
        :title="t('settings.coinRate')"
        :value="t('settings.coinRateValue', { c2s: familyStore.coinCopperToSilver, s2g: familyStore.coinSilverToGold })"
        is-link
        to="/settings/family/coin-rates"
      />
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
        :title="t('settings.enableAI')"
        :label="hasAnyModel ? '' : t('settings.enableAIDesc')"
        icon="star-o"
      >
        <template #value>
          <van-switch
            :model-value="aiEnabled"
            :disabled="!hasAnyModel || togglingAI"
            size="22px"
            @update:model-value="onToggleAI"
          />
        </template>
      </van-cell>
      <van-cell :title="t('settings.aiAssistant')" is-link to="/settings/ai">
        <template #icon>
          <NuminaLogo :width="24" class="cell-logo" />
        </template>
      </van-cell>
      <van-cell :title="t('settings.mcpManage')" icon="cluster-o" is-link to="/settings/ai/mcp" />
      <van-cell :title="t('settings.skillsManage')" icon="gem-o" is-link to="/settings/ai/skills" />
      <van-cell :title="t('settings.agentsManage')" icon="manager-o" is-link to="/settings/ai/agents" />
    </van-cell-group>

    <!-- 数据管理 -->
    <van-cell-group inset :title="t('settings.dataManagement')" class="section">
      <van-cell :title="t('settings.categoryManage')" icon="apps-o" is-link to="/settings/categories" />
      <van-cell :title="t('settings.tagManage')" icon="label-o" is-link to="/settings/tags" />
    </van-cell-group>

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
      />
    </van-popup>

    <!-- Language Picker -->
    <van-popup v-model:show="showLanguagePicker" round position="bottom">
      <van-picker
        :columns="languageOptions"
        :model-value="[authStore.user?.language || 'zh-CN']"
        @confirm="onLanguageConfirm"
        @cancel="showLanguagePicker = false"
      />
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
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { showConfirmDialog, showToast } from 'vant'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useFamilyStore } from '@/stores/family'
import { useAIStore } from '@/stores/ai'
import { updateSettings } from '@/api/auth'
import * as aiApi from '@/api/ai'
import PageHeader from '@/components/common/PageHeader.vue'
import CurrencyPicker from '@/components/common/CurrencyPicker.vue'
import NuminaLogo from '@/components/common/NuminaLogo.vue'
import axios from 'axios'

const { t } = useI18n()
const router = useRouter()

const authStore = useAuthStore()
const familyStore = useFamilyStore()
const aiStore = useAIStore()

onMounted(() => {
  if (!familyStore.family) {
    familyStore.fetchFamily()
  }
  authStore.fetchMe()
  // Initialize theme color from localStorage
  const savedColor = localStorage.getItem('theme-primary')
  if (savedColor) {
    document.documentElement.style.setProperty('--theme-primary', savedColor)
    document.documentElement.style.setProperty('--van-primary-color', savedColor)
  }
  if (authStore.user?.role === 'owner') {
    aiStore.fetchConfigs()
  }
})

// AI toggle
const togglingAI = ref(false)
const hasAnyModel = computed(() =>
  aiStore.configs.some(
    (c) => c.model_id || c.model_2_id || c.model_3_id,
  ),
)
const aiEnabled = computed(() => aiStore.configs.some((c) => c.is_active))

async function onToggleAI(val: boolean) {
  if (!hasAnyModel.value) {
    showToast(t('settings.enableAINoModel'))
    return
  }
  const target = aiStore.configs.find((c) => c.model_id || c.model_2_id || c.model_3_id)
  if (!target) return
  togglingAI.value = true
  try {
    await aiApi.updateProviderConfig(target.id, { is_active: val })
    await aiStore.fetchConfigs()
    showToast(val ? t('toast.aiEnabled') : t('toast.aiDisabled'))
  } catch {
    showToast(t('toast.operationFailed2'))
  } finally {
    togglingAI.value = false
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
  { text: '🌓 ' + t('settings.themeSystem'), value: 'system' },
  { text: '☀️ ' + t('settings.themeLight'), value: 'light' },
  { text: '🌙 ' + t('settings.themeDark'), value: 'dark' },
]

const languageOptions = [
  { text: t('settings.languageZhCN'), value: 'zh-CN' },
  { text: t('settings.languageEnUS'), value: 'en-US' },
]

const themeLabel = computed(() => {
  const theme = authStore.user?.theme
  if (theme === 'dark') return '🌙 ' + t('settings.themeDark')
  if (theme === 'system') return '🌓 ' + t('settings.themeSystem')
  return '☀️ ' + t('settings.themeLight')
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
  } catch (err) {
    const detail = axios.isAxiosError(err) ? err.response?.data?.detail : undefined
    showToast(detail || t('toast.modifyFailed'))
  }
}


function selectThemeColor(color: string) {
  currentThemeColor.value = color
  localStorage.setItem('theme-primary', color)
  document.documentElement.style.setProperty('--theme-primary', color)
  document.documentElement.style.setProperty('--van-primary-color', color)
  showThemeColorPicker.value = false
  showToast(t('toast.themeChanged'))
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

.cell-logo {
  margin-right: 8px;
}
</style>
