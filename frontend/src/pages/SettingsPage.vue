<template>
  <div class="settings-page">
    <PageHeader title="设置" />

    <van-cell-group inset title="数据管理">
      <van-cell title="分类管理" icon="apps-o" is-link to="/settings/categories" />
      <van-cell title="标签管理" icon="label-o" is-link to="/settings/tags" />
    </van-cell-group>

    <van-cell-group inset title="用户设置" class="section">
      <van-cell title="主题模式" :value="themeLabel" @click="showThemePicker = true" is-link />
      <van-cell title="语言" :value="languageLabel" @click="showLanguagePicker = true" is-link />
      <van-cell title="默认币种" :value="authStore.user?.default_currency || 'CNY'" @click="showCurrencyPicker = true" is-link />
      <van-cell title="默认视图" :value="viewModeLabel" @click="showViewModePicker = true" is-link />
    </van-cell-group>

    <van-cell-group inset title="账户信息" class="section">
      <van-cell 
        title="家庭名称" 
        :value="familyStore.family?.custom_title || familyStore.family?.name" 
        :is-link="authStore.user?.role === 'owner'" 
        @click="onEditFamilyTitle" 
      />
      <van-cell title="当前用户" :value="authStore.user?.display_name" />
      <van-cell title="用户名" :value="authStore.user?.username" />
      <van-cell title="角色" :value="authStore.user?.role === 'owner' ? '管理员' : '成员'" />
    </van-cell-group>

    <div class="actions">
      <van-button block type="danger" plain @click="onLogout">
        退出登录
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
    <van-popup v-model:show="showCurrencyPicker" round position="bottom">
      <van-picker
        :columns="currencyOptions"
        @confirm="onCurrencyConfirm"
        @cancel="showCurrencyPicker = false"
      />
    </van-popup>

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
import { ref, computed, onMounted } from 'vue'
import { showConfirmDialog, showToast } from 'vant'
import { useAuthStore } from '@/stores/auth'
import { useFamilyStore } from '@/stores/family'
import { updateSettings } from '@/api/auth'
import PageHeader from '@/components/common/PageHeader.vue'

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

const themeOptions = [
  { text: '浅色模式', value: 'light' },
  { text: '深色模式', value: 'dark' },
]

const languageOptions = [
  { text: '简体中文', value: 'zh-CN' },
  { text: 'English', value: 'en-US' },
]

const currencyOptions = [
  { text: '人民币 (CNY)', value: 'CNY' },
  { text: '美元 (USD)', value: 'USD' },
  { text: '欧元 (EUR)', value: 'EUR' },
]

const viewModeOptions = [
  { text: '卡片视图', value: 'card' },
  { text: '列表视图', value: 'list' },
]

const themeLabel = computed(() => {
  return authStore.user?.theme === 'dark' ? '深色模式' : '浅色模式'
})

const languageLabel = computed(() => {
  return authStore.user?.language === 'en-US' ? 'English' : '简体中文'
})

const viewModeLabel = computed(() => {
  return authStore.user?.view_mode === 'list' ? '列表视图' : '卡片视图'
})

async function updateSetting(key: string, value: string) {
  try {
    await updateSettings({ [key]: value })
    await authStore.fetchMe()
    showToast('设置已保存')
  } catch {
    showToast('保存失败')
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

function onCurrencyConfirm({ selectedOptions }: { selectedOptions: Array<{ text: string; value: string }> }) {
  updateSetting('default_currency', selectedOptions[0].value)
  showCurrencyPicker.value = false
}

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
    await showConfirmDialog({ title: '确认', message: '确定要退出登录吗？' })
    authStore.logout()
  } catch {
    // cancelled
  }
}
</script>

<style scoped>
.settings-page {
  background: #f7f8fa;
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
