<template>
  <div class="change-username-page">
    <PageHeader :title="t('changeUsername.title')" />

    <van-cell-group inset :title="t('changeUsername.sectionTitle')" class="section">
      <van-cell :title="t('changeUsername.currentUsername')" :value="authStore.user?.username ?? '-'" />
      <van-cell :title="t('changeUsername.remainingChanges')" :value="remainingText" />
      <van-field
        v-model="newUsername"
        :label="t('changeUsername.newUsername')"
        :placeholder="t('changeUsername.newUsernamePlaceholder')"
        :rules="[{ required: true, message: t('changeUsername.usernameRequired') }]"
        autocomplete="username"
      />
    </van-cell-group>

    <div class="action-area">
      <van-button
        round
        block
        type="primary"
        :loading="changing"
        :disabled="!canSubmit"
        @click="onChangeUsername"
      >
        {{ t('changeUsername.submit') }}
      </van-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { showSuccessToast, showFailToast, showConfirmDialog } from 'vant'
import http from '@/api/index'
import PageHeader from '@/components/common/PageHeader.vue'
import { useAuthStore } from '@/stores/auth'

const { t } = useI18n()
const router = useRouter()
const authStore = useAuthStore()

const newUsername = ref('')
const changing = ref(false)

// Parse remaining changes from username_change_history (backend returns via /auth/me)
// For simplicity, we rely on the server to enforce the limit and show a generic message
const remainingText = computed(() => t('changeUsername.limitHint'))

const canSubmit = computed(() => {
  const v = newUsername.value.trim().toLowerCase()
  return v.length >= 3 && v.length <= 50 && /^[a-z0-9_.\-]+$/.test(v)
})

async function onChangeUsername() {
  const value = newUsername.value.trim()
  if (!canSubmit.value) return

  try {
    await showConfirmDialog({ message: t('changeUsername.confirmChange') })
  } catch {
    return
  }

  changing.value = true
  try {
    await http.post('/auth/me/username', { new_username: value })
    await authStore.fetchMe()
    showSuccessToast(t('changeUsername.changeSuccess'))
    router.back()
  } catch (e: unknown) {
    const err = e as { response?: { data?: { code?: string } } }
    const code = err.response?.data?.code
    if (code === 'AUTH_USERNAME_CHANGE_LIMIT') {
      showFailToast(t('changeUsername.limitReached'))
    } else if (code === 'AUTH_USERNAME_EXISTS') {
      showFailToast(t('changeUsername.usernameExists'))
    } else if (code && t(`errors.${code}`) !== `errors.${code}`) {
      showFailToast(t(`errors.${code}`))
    } else {
      showFailToast(t('changeUsername.changeFailed'))
    }
  } finally {
    changing.value = false
  }
}
</script>

<style scoped>
.change-username-page {
  min-height: 100vh;
  background: var(--van-background);
}

.section {
  margin-top: 12px;
}

.action-area {
  padding: 16px;
}
</style>
