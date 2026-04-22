<template>
  <div class="settings-page">
    <PageHeader :title="t('settings.title')" />

    <van-cell-group inset :title="t('settings.dataManagement')">
      <van-cell :title="t('settings.categoryManage')" icon="apps-o" is-link to="/settings/categories" />
      <van-cell :title="t('settings.tagManage')" icon="label-o" is-link to="/settings/tags" />
    </van-cell-group>

    <van-cell-group inset title="AI 配置" class="section">
      <van-cell title="AI 智能助手" icon="smile-o" is-link to="/settings/ai" />
    </van-cell-group>

    <van-cell-group inset :title="t('settings.userSettings')" class="section">
      <van-cell :title="t('settings.theme')" :value="themeLabel" is-link @click="showThemePicker = true" />
      <van-cell :title="t('settings.themeColor')" is-link @click="showThemeColorPicker = true">
        <template #value>
          <span class="theme-color-preview" :style="{ backgroundColor: currentThemeColor }"></span>
        </template>
      </van-cell>
      <van-cell :title="t('settings.language')" :value="languageLabel" is-link @click="showLanguagePicker = true" />
      <van-cell :title="t('settings.defaultCurrency')" :value="authStore.user?.default_currency || 'CNY'" is-link @click="showCurrencyPicker = true" />
      <van-cell :title="t('settings.defaultView')" :value="viewModeLabel" is-link @click="showViewModePicker = true" />
    </van-cell-group>

    <van-cell-group
      v-if="authStore.user?.role === 'owner' || authStore.user?.role === 'member'"
      inset
      title="家庭管理"
      class="section"
    >
      <van-cell title="家庭成员管理" icon="friends-o" is-link to="/family" />
    </van-cell-group>

    <!-- Coin rate settings (owner only) -->
    <van-cell-group v-if="authStore.user?.role === 'owner'" inset title="⭐ 星星币兑换比例" class="section">
      <van-field
        v-model="copperToSilverStr"
        label="铜→银"
        type="digit"
        placeholder="默认 10"
      />
      <van-field
        v-model="silverToGoldStr"
        label="银→金"
        type="digit"
        placeholder="默认 10"
      />
      <van-cell>
        <template #title>
          <van-button size="small" type="primary" :loading="savingRates" @click="saveCoinRates">
            保存
          </van-button>
        </template>
      </van-cell>
    </van-cell-group>

    <van-cell-group inset :title="t('settings.accountInfo')" class="section">
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

    <div class="actions">
      <van-button block type="danger" plain @click="onLogout">
        {{ t('settings.logout') }}
      </van-button>
    </div>

    <!-- Theme Picker -->
    <van-popup v-model:show="showThemePicker" round position="bottom">
      <van-picker
        :columns="themeOptions"
        @confirm="onThemeConfirm"
        @cancel="showThemePicker = false"
      />
    </van-popup>

    <!-- Language Picker -->
    <van-popup v-model:show="showLanguagePicker" round position="bottom">
      <van-picker
        :columns="languageOptions"
        @confirm="onLanguageConfirm"
        @cancel="showLanguagePicker = false"
      />
    </van-popup>

    <!-- Currency Picker -->
    <CurrencyPicker
      v-model:show="showCurrencyPicker"
      v-model="selectedCurrency"
    />

    <!-- View Mode Picker -->
    <van-popup v-model:show="showViewModePicker" round position="bottom">
      <van-picker
        :columns="viewModeOptions"
        @confirm="onViewModeConfirm"
        @cancel="showViewModePicker = false"
      />
    </van-popup>

    <!-- Theme Color Picker -->
    <van-popup v-model:show="showThemeColorPicker" round position="bottom">
      <div class="theme-color-picker">
        <div class="color-picker-header">
          <span>选择主题色</span>
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
      title="修改家庭名称"
      show-cancel-button
      @confirm="onTitleConfirm"
    >
      <van-field
        v-model="editTitleValue"
        placeholder="请输入新的家庭名称"
        clearable
      />
    </van-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { showConfirmDialog, showToast } from 'vant'
import { useI18n } from 'vue-i18n'
import { useAuthStore } from '@/stores/auth'
import { useFamilyStore } from '@/stores/family'
import { updateSettings } from '@/api/auth'
import { updateFamilySettings } from '@/api/family'
import PageHeader from '@/components/common/PageHeader.vue'
import CurrencyPicker from '@/components/common/CurrencyPicker.vue'

const { t } = useI18n()

const authStore = useAuthStore()
const familyStore = useFamilyStore()

onMounted(() => {
  if (!familyStore.family) {
    familyStore.fetchFamily()
  }
  authStore.fetchMe()
  copperToSilverStr.value = String(familyStore.coinCopperToSilver)
  silverToGoldStr.value = String(familyStore.coinSilverToGold)
  // Initialize theme color from localStorage
  const savedColor = localStorage.getItem('theme-primary')
  if (savedColor) {
    document.documentElement.style.setProperty('--theme-primary', savedColor)
    document.documentElement.style.setProperty('--van-primary-color', savedColor)
  }
})

const showThemePicker = ref(false)
const showLanguagePicker = ref(false)
const showCurrencyPicker = ref(false)
const showViewModePicker = ref(false)
const showThemeColorPicker = ref(false)
const showTitleDialog = ref(false)
const editTitleValue = ref('')
const copperToSilverStr = ref(String(familyStore.coinCopperToSilver))
const silverToGoldStr = ref(String(familyStore.coinSilverToGold))
const savingRates = ref(false)
const selectedCurrency = ref(authStore.user?.default_currency || 'CNY')

const themeColorOptions = [
  { name: '蓝色', value: '#007aff' },
  { name: '紫色', value: '#5856d6' },
  { name: '绿色', value: '#34c759' },
  { name: '橙色', value: '#ff9500' },
  { name: '红色', value: '#ff3b30' },
  { name: '粉色', value: '#ff2d55' },
  { name: '青色', value: '#5ac8fa' },
  { name: '金色', value: '#ffcc00' },
]

const currentThemeColor = ref(localStorage.getItem('theme-primary') || '#007aff')

const themeOptions = [
  { text: t('settings.themeLight'), value: 'light' },
  { text: t('settings.themeDark'), value: 'dark' },
  { text: t('settings.themeSystem'), value: 'system' },
]

const languageOptions = [
  { text: t('settings.languageZhCN'), value: 'zh-CN' },
  { text: t('settings.languageEnUS'), value: 'en-US' },
]

const viewModeOptions = [
  { text: t('settings.viewCard'), value: 'card' },
  { text: t('settings.viewList'), value: 'list' },
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

const viewModeLabel = computed(() => {
  return authStore.user?.view_mode === 'list' ? t('settings.viewList') : t('settings.viewCard')
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

function onViewModeConfirm({ selectedOptions }: { selectedOptions: Array<{ text: string; value: string }> }) {
  updateSetting('view_mode', selectedOptions[0].value)
  showViewModePicker.value = false
}

function onEditFamilyTitle() {
  if (authStore.user?.role !== 'owner') {
    showToast(t('toast.ownerOnlyWarning'))
    return
  }
  editTitleValue.value = familyStore.family?.custom_title || familyStore.family?.name || ''
  showTitleDialog.value = true
}

async function saveCoinRates() {
  const c2s = parseInt(copperToSilverStr.value)
  const s2g = parseInt(silverToGoldStr.value)
  if (isNaN(c2s) || c2s < 1 || c2s > 100 || isNaN(s2g) || s2g < 1 || s2g > 100) {
    showToast(t('toast.coinRateInvalid'))
    return
  }
  savingRates.value = true
  try {
    await updateFamilySettings({ coinCopperToSilver: c2s, coinSilverToGold: s2g })
    familyStore.coinCopperToSilver = c2s
    familyStore.coinSilverToGold = s2g
    showToast(t('toast.saveSuccess'))
  } catch {
    showToast(t('toast.saveFailed'))
  } finally {
    savingRates.value = false
  }
}

async function onTitleConfirm() {
  try {
    const newTitle = editTitleValue.value.trim()
    await familyStore.updateFamilyTitle(newTitle || null)
    showToast(t('toast.familyTitleUpdated'))
  } catch (err: any) {
    showToast(err.response?.data?.detail || '修改失败')
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
    await showConfirmDialog({ title: '确认', message: t('settings.logoutConfirm') })
    authStore.logout()
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
</style>
