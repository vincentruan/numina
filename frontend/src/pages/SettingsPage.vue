<template>
  <div class="settings-page">
    <PageHeader :title="t('settings.title')" />

    <van-cell-group inset :title="t('settings.dataManagement')">
      <van-cell :title="t('settings.categoryManage')" icon="apps-o" is-link to="/settings/categories" />
      <van-cell :title="t('settings.tagManage')" icon="label-o" is-link to="/settings/tags" />
    </van-cell-group>

    <van-cell-group inset :title="t('settings.userSettings')" class="section">
      <van-cell :title="t('settings.theme')" :value="themeLabel" @click="showThemePicker = true" is-link />
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
})

const showThemePicker = ref(false)
const showLanguagePicker = ref(false)
const showCurrencyPicker = ref(false)
const showViewModePicker = ref(false)
const showTitleDialog = ref(false)
const editTitleValue = ref('')
const selectedCurrency = ref(authStore.user?.default_currency || 'CNY')

const themeOptions = [
  { text: `☀️ ${t('settings.themeLight')}`, value: 'light' },
  { text: `🌙 ${t('settings.themeDark')}`, value: 'dark' },
  { text: `⚙️ ${t('settings.themeSystem')}`, value: 'system' },
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
</style>
