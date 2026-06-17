<template>
  <div class="change-password-page">
    <PageHeader :title="t('changePassword.title')" />

    <!-- Change password -->
    <van-cell-group inset :title="t('changePassword.sectionTitle')" class="section">
      <van-field
        v-model="form.oldPassword"
        :type="showOld ? 'text' : 'password'"
        :label="t('changePassword.currentPassword')"
        :placeholder="t('changePassword.currentPasswordPlaceholder')"
        autocomplete="current-password"
      >
        <template #right-icon>
          <van-icon :name="showOld ? 'eye-o' : 'closed-eye'" @click="showOld = !showOld" />
        </template>
      </van-field>
      <van-field
        v-model="form.newPassword"
        :type="showNew ? 'text' : 'password'"
        :label="t('changePassword.newPassword')"
        :placeholder="t('changePassword.newPasswordPlaceholder')"
        autocomplete="new-password"
      >
        <template #right-icon>
          <van-icon :name="showNew ? 'eye-o' : 'closed-eye'" @click="showNew = !showNew" />
        </template>
      </van-field>
      <van-field
        v-model="form.confirmPassword"
        :type="showConfirm ? 'text' : 'password'"
        :label="t('changePassword.confirmPassword')"
        :placeholder="t('changePassword.confirmPasswordPlaceholder')"
        autocomplete="new-password"
      >
        <template #right-icon>
          <van-icon :name="showConfirm ? 'eye-o' : 'closed-eye'" @click="showConfirm = !showConfirm" />
        </template>
      </van-field>
    </van-cell-group>

    <div class="action-area">
      <van-button
        round
        block
        type="primary"
        :loading="changingPassword"
        :disabled="!canChangePassword"
        @click="onChangePassword"
      >
        {{ t('changePassword.submit') }}
      </van-button>
    </div>

    <!-- Reset password via notification -->
    <van-cell-group inset :title="t('changePassword.forgotSection')" class="section">
      <van-cell
        :title="t('changePassword.resetViaNotification')"
        :label="t('changePassword.resetViaNotificationDesc')"
        is-link
        @click="onResetPassword"
      />
    </van-cell-group>
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

const form = ref({ oldPassword: '', newPassword: '', confirmPassword: '' })
const showOld = ref(false)
const showNew = ref(false)
const showConfirm = ref(false)
const changingPassword = ref(false)
const resettingPassword = ref(false)

const canChangePassword = computed(() =>
  form.value.oldPassword.length > 0 &&
  form.value.newPassword.length >= 8 &&
  form.value.newPassword === form.value.confirmPassword
)

async function onChangePassword() {
  if (form.value.newPassword !== form.value.confirmPassword) {
    showFailToast(t('changePassword.passwordMismatch'))
    return
  }
  try {
    await showConfirmDialog({ message: t('changePassword.confirmChange') })
  } catch {
    return
  }
  changingPassword.value = true
  try {
    await http.post('/auth/me/password', {
      old_password: form.value.oldPassword,
      new_password: form.value.newPassword,
    })
    showSuccessToast(t('changePassword.changeSuccess'))
    authStore.logout({ onLogout: () => router.push('/login') })
  } catch (e: unknown) {
    const err = e as { response?: { data?: { code?: string } } }
    const code = err.response?.data?.code
    if (code && t(`errors.${code}`) !== `errors.${code}`) {
      showFailToast(t(`errors.${code}`))
    } else {
      showFailToast(t('changePassword.changeFailed'))
    }
  } finally {
    changingPassword.value = false
  }
}

async function onResetPassword() {
  try {
    await showConfirmDialog({ message: t('changePassword.confirmReset') })
  } catch {
    return
  }
  resettingPassword.value = true
  try {
    await http.post('/auth/me/password/reset')
    showSuccessToast(t('changePassword.resetSuccess'))
    authStore.logout({ onLogout: () => router.push('/login') })
  } catch (e: unknown) {
    const err = e as { response?: { data?: { code?: string } } }
    const code = err.response?.data?.code
    if (code === 'NOTIFICATION_NO_CHANNEL') {
      showToast({ message: t('changePassword.noNotificationChannel'), icon: 'warning-o' })
    } else if (code && t(`errors.${code}`) !== `errors.${code}`) {
      showFailToast(t(`errors.${code}`))
    } else {
      showFailToast(t('changePassword.resetFailed'))
    }
  } finally {
    resettingPassword.value = false
  }
}
</script>

<style scoped>
.change-password-page {
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
