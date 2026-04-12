<template>
  <div class="settings-page">
    <PageHeader :title="t('settings.title')" />

    <van-cell-group inset :title="t('settings.dataManagement')">
      <van-cell :title="t('settings.categoryManage')" icon="apps-o" is-link to="/settings/categories" />
      <van-cell :title="t('settings.tagManage')" icon="label-o" is-link to="/settings/tags" />
    </van-cell-group>

    <van-cell-group inset title="AI 智能功能" class="section">
      <van-cell title="AI 智能助手" icon="smile-o" is-link to="/settings/ai" />
      <van-cell title="家庭资产体检" icon="chart-trending-o" is-link to="/ai/report" />
      <van-cell title="资产老化预警" icon="warning-o" is-link to="/ai/alerts" />
      <van-cell title="闲置资产清仓" icon="delete-o" is-link to="/ai/disposal" />
      <van-cell title="负债优化顾问" icon="balance-o" is-link to="/ai/liability" />
      <van-cell title="AI 问答助手" icon="chat-o" is-link to="/ai/chat" />
      <van-cell title="配置漂移检测" icon="aim" is-link to="/ai/allocation" />
    </van-cell-group>

    <van-cell-group inset :title="t('settings.userSettings')" class="section">
      <van-cell :title="t('settings.theme')" :value="themeLabel" @click="showThemePicker = true" is-link />
      <van-cell :title="t('settings.themeColor')" @click="showThemeColorPicker = true" is-link>
        <template #value>
          <span class="theme-color-preview" :style="{ backgroundColor: currentThemeColor }"></span>
        </template>
      </van-cell>
      <van-cell :title="t('settings.language')" :value="languageLabel" @click="showLanguagePicker = true" is-link />
      <van-cell :title="t('settings.defaultCurrency')" :value="authStore.user?.default_currency || 'CNY'" @click="showCurrencyPicker = true" is-link />
      <van-cell :title="t('settings.defaultView')" :value="viewModeLabel" @click="showViewModePicker = true" is-link />
    </van-cell-group>

    <van-cell-group inset :title="t('settings.accountInfo')" class="section">
      <van-cell
        :title="t('family.familyName')"
        :value="familyStore.family?.custom_title || familyStore.family?.name"
        :is-link="authStore.user?.role === 'owner'"
        @click="onEditFamilyTitle"
      />
      <van-cell :title="t('settings.currentUser')" :value="authStore.user?.display_name" />
      <van-cell :title="t('settings.username')" :value="authStore.user?.username" />
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
import PageHeader from '@/components/common/PageHeader.vue'
import CurrencyPicker from '@/components/common/CurrencyPicker.vue'

const { t } = useI18n()

const authStore = useAuthStore()
const familyStore = useFamilyStore()

onMounted(() => {
  if (!familyStore.family) {
    familyStore.fetchFamily()
  }
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
    showToast('只有家庭创建者可以修改名称')
    return
  }
  editTitleValue.value = familyStore.family?.custom_title || familyStore.family?.name || ''
  showTitleDialog.value = true
}

async function onTitleConfirm() {
  try {
    const newTitle = editTitleValue.value.trim()
    await familyStore.updateFamilyTitle(newTitle || null)
    showToast('家庭名称已修改')
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
  showToast('主题色已更改')
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
